"""Recompute published point estimates and all primary ranking counts."""
import csv
import hashlib
import io
import json
import math
from collections import Counter

from . import bundle
from .io import digest_text
from .prompts import render_qa
from .review_bundle import CANDIDATES, CONTROLS, METRICS, midranks


def verify():
    asset_count = bundle.verify_assets()
    data = bundle.inputs()
    payload = bundle.load_payload()
    rows = payload['rows']
    expected_conditions = set(CANDIDATES) | set(CONTROLS)
    if len(rows) != 526 or len({r['id'] for r in rows}) != 526 or len({r['cluster'] for r in rows}) != 360:
        raise ValueError('Evaluation question/context geometry changed')
    score_repeats = rank_repeats = token_expansions = 0
    for row in rows:
        if set(row['conditions']) != expected_conditions or set(row['rankings']) != set(CANDIDATES):
            raise ValueError('Missing evaluation condition or ranking')
        for name, value in row['conditions'].items():
            context = bundle.context_for(data, value)
            rendered = render_qa('{context}', context_kind=value['context_kind'], context=context, question=row['question'])
            if rendered != data['contexts'][value['context']]:
                raise ValueError('Context rendering changed')
            if digest_text(row['question']) != value['question_sha256'] or digest_text(row['gold']) != value['gold_sha256']:
                raise ValueError('Question or Gold changed')
            if digest_text(value['answer']) != value['answer_sha256']:
                raise ValueError('Reference answer changed')
            replicates = [s['replicate'] for s in value['scores']]
            expected = [1,2] if row['id'] in data['sampling']['pointwise_reliability_rows'] else [1]
            if replicates != expected:
                raise ValueError('Pointwise reliability membership changed')
            for score in value['scores']:
                if set(score['dimensions']) != set(METRICS):
                    raise ValueError('Score dimensions changed')
                if any(isinstance(v,bool) or not math.isfinite(v) or not 0 <= v <= 1 for v in score['dimensions'].values()):
                    raise ValueError('Invalid reference score')
            score_repeats += len(replicates)-1
            if value['compression']:
                compression = value['compression']
                if digest_text(rendered) != compression['compressed_sha256']:
                    raise ValueError('Frozen compressed context changed')
                if not (type(compression['compressed_tokens']) is int and type(compression['source_tokens']) is int
                        and compression['compressed_tokens']>0 and compression['source_tokens']>0):
                    raise ValueError('Invalid frozen token counts')
                # Native-token DAC can expand under downstream Qwen retokenization.
                # This is retained negative evidence, not a reason to rewrite inputs.
                token_expansions += compression['compressed_tokens']>compression['source_tokens']
                if not math.isclose(compression['actual_ratio'],compression['source_tokens']/compression['compressed_tokens'],abs_tol=1e-12):
                    raise ValueError('Frozen realized ratio differs from token accounting')
        for rank in row['rankings'].values():
            if midranks(rank['groups']) != rank['midranks']:
                raise ValueError('Rank tie semantics changed')
            if 'retest' in rank:
                rank_repeats += 1
                if midranks(rank['retest']['groups']) != rank['retest']['midranks']:
                    raise ValueError('Repeated rank tie semantics changed')
    if (score_repeats,rank_repeats) != (936,789):
        raise ValueError('Reliability repeat coverage changed')
    means = list(csv.DictReader(io.StringIO(bundle.asset_bytes('paper/evidence/condition_means.csv').decode())))
    differences = []
    for expected in means:
        values = [r['conditions'][expected['condition_id']] for r in rows]
        for metric in METRICS:
            actual = sum(v['scores'][0]['dimensions'][metric] for v in values)/len(values)
            error = actual-float(expected[metric])
            differences.append(abs(error))
            if abs(error)>1e-12:
                raise ValueError('Recomputed score mean differs from paper')
        if values[0]['compression']:
            original=sum(v['compression']['source_tokens'] for v in values)
            retained=sum(v['compression']['compressed_tokens'] for v in values)
            if abs(1-retained/original-float(expected['row_weighted_downstream_deletion_fraction']))>1e-12:
                raise ValueError('Recomputed row-weighted compression differs from paper')
    summary = json.loads(bundle.asset_bytes('paper/evidence/ranking_summary.json'))
    original = set(data['sampling']['original_ranking_rows'])
    for block, selected in [('rank_summary', rows), ('original_128_rank_summary',[r for r in rows if r['id'] in original]),
                            ('additional_398_rank_summary',[r for r in rows if r['id'] not in original])]:
        for candidate in CANDIDATES:
            counts = Counter()
            for row in selected:
                ranks=row['rankings'][candidate]['midranks']
                for control in CONTROLS:
                    delta=ranks['matching_compressed']-ranks[control]
                    counts[f'compressed_{"above" if delta<0 else "below" if delta>0 else "tied"}_{control}']+=1
            if {'rows':len(selected),**counts} != summary[block][candidate]:
                raise ValueError('Recomputed ranking block differs from paper')
    from .human import analyze
    human = analyze(payload=payload)
    return {'accepted':True, 'kind':'offline_reconstruction', 'asset_files_verified':asset_count,
            'questions':526,'conditions':18,'reference_answers':9468,'primary_scores':9468,
            'score_repeats':936,'primary_rankings':7890,'ranking_repeats':789,
            'score_means_recomputed':54,'compression_fractions_recomputed':15,
            'retained_rows_with_downstream_token_expansion':token_expansions,
            'max_score_mean_error':max(differences),'ranking_blocks_verified':[128,398,526],
            'human_questions':human['question_count'],
            'human_judgments':sum(c['ranked']+c['ungradable'] for c in human['counts'].values()),
            'human_jointly_ranked_questions':human['agreement']['annotator_1_vs_annotator_2']['compared_questions'],
            'live_model_requests':0}
