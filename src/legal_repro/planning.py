"""Content-separated plans: generation never reads archived answers or judgments."""
import json
from . import bundle
from .io import digest_json
from .prompts import render_qa
from .task_protocol import derived_seed
from .review_bundle import CONTROLS, CANDIDATES

SMOKE_CONDITIONS = ('raw','legal_llmlingua2-r1p1','oracle_bgb_paragraph_ids','no_context')


def plan(mode='smoke'):
    data = bundle.inputs()
    if mode not in ('smoke','evaluate'):
        raise ValueError('Unknown evaluation mode')
    conditions = SMOKE_CONDITIONS if mode=='smoke' else (*CONTROLS,*CANDIDATES)
    wanted = set(data['sampling']['smoke_rows']) if mode=='smoke' else {r['id'] for r in data['rows']}
    selected = [r for r in data['rows'] if r['id'] in wanted]
    if len(selected)!=len(wanted):
        raise ValueError('Missing selected question')
    generations = []
    for row in selected:
        for candidate in conditions:
            value = row['conditions'][candidate]
            generations.append({'id':value['generation_id'],'row_id':row['id'],'candidate_id':candidate,
                                'question':row['question'],'context_kind':value['context_kind'],
                                'context':bundle.context_for(data,value),'context_sha256':value['context_sha256']})
    repeat_rows = set() if mode=='smoke' else set(data['sampling']['pointwise_reliability_rows'])
    scores = []
    for item in generations:
        for replicate in ((1,2) if item['row_id'] in repeat_rows else (1,)):
            identity={'generation_id':item['id'],'replicate':replicate}
            scores.append({'id':'score:'+digest_json(identity)[:32],**identity,'row_id':item['row_id'],
                           'candidate_id':item['candidate_id'],'pass_id':'primary-score-1' if replicate==1 else 'reliability-score-2'})
    ranks = []
    for key in ('primary_rank_tasks',) if mode=='smoke' else ('primary_rank_tasks','repeat_rank_tasks'):
        ranks.extend({**item,'id':item['rank_task_id']} for item in data['sampling'][key]
                     if item['row_id'] in wanted and item['candidate_id'] in conditions)
    return {'mode':mode,'data':data,'rows':selected,'conditions':conditions,
            'generation':generations,'score':scores,'rank':ranks,
            'counts':{'questions':len(selected),'conditions':len(conditions),'generation':len(generations),
                      'score':len(scores),'rank':len(ranks),'semantic_calls':len(generations)+len(scores)+len(ranks)}}


def messages(kind, task, planned, answers):
    if kind=='generation':
        template=bundle.asset_bytes('prompts/qa_user.txt').decode()
        return [{'role':'user','content':render_qa(template,context_kind=task['context_kind'],context=task['context'],question=task['question'])}]
    row=next(r for r in planned['rows'] if r['id']==task['row_id'])
    developer=bundle.asset_bytes(f'prompts/{kind}_developer.txt').decode()
    template=bundle.asset_bytes(f'prompts/{kind}_user.txt').decode()
    if kind=='score':
        answer=answers[(task['row_id'],task['candidate_id'])]['answer']
        user=template.format(question=row['question'],gold=row['gold'],answer=answer)
    else:
        blind={label:answers[(task['row_id'], task['candidate_id'] if role=='matching_compressed' else role)]['answer']
               for label,role in task['blind_to_condition'].items()}
        user=template.format(question=row['question'],gold=row['gold'],candidates_json=json.dumps(blind,ensure_ascii=False,indent=2,sort_keys=True))
    return [{'role':'system','content':developer},{'role':'user','content':user}]
