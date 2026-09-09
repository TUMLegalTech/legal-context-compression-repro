import io
import json
from pathlib import Path
from types import SimpleNamespace
import urllib.error

import pytest

from legal_repro import bundle,contracts
from legal_repro.io import digest_json,ledger
from legal_repro.planning import plan
from legal_repro.runner import run
from legal_repro.schemas import SCORE_DIMENSIONS
from legal_repro.transport import OpenRouter,RequestFailure,request_payload


class Tokenizer:
    def encode(self,text,add_special_tokens=False):
        return SimpleNamespace(ids=list(range(len(text.split()))))


class Fake:
    def __init__(self, fail_on=None, transient=0, malformed=0):
        self.calls=[]; self.fail_on=fail_on; self.transient=transient; self.malformed=malformed
    def preflight(self,protocol):
        return {'synthetic':True}
    def complete(self,payload,profile):
        self.calls.append(payload)
        if len(self.calls)==self.fail_on:
            raise RequestFailure('Synthetic stop',False)
        if self.transient:
            self.transient-=1
            raise RequestFailure('Synthetic HTTP 429',True)
        schema=payload.get('response_format',{}).get('json_schema',{})
        if schema.get('name')=='legal_score':
            content=json.dumps({k:{'score':.75,'justification':'Synthetic justification.'} for k in SCORE_DIMENSIONS})
        elif schema.get('name')=='legal_rank':
            ids=sorted(schema['schema']['properties']['candidate_justifications']['properties'])
            content=json.dumps({'rank_groups':[ids[:2],ids[2:]],'candidate_justifications':dict.fromkeys(ids,'Synthetic reason.'),'comparative_justification':'Synthetic comparison.'})
        else:
            content='Synthetic answer for transport verification only. '+str(len(self.calls))
        if schema and self.malformed:
            self.malformed-=1; content='{"malformed":true}'
        return {'content':content,'response_id':str(len(self.calls)),'response_model':profile['model'],
                'provider':profile['provider_name'],'finish_reason':'stop','usage':{'cost':0.00001}}


def active_contract(monkeypatch,tmp_path,**limits):
    monkeypatch.chdir(tmp_path)
    path=tmp_path/'contract.txt'
    contracts.draft(path,tmp_path/'run')
    text=path.read_text().replace('STATUS: DRAFT','STATUS: ACTIVE')
    for key,value in limits.items():
        text='\n'.join(f'{key}: {value}' if line.startswith(key+':') else line for line in text.splitlines())+'\n'
    path.write_text(text)
    return path


def test_active_contract_is_required_before_any_credential_or_transport(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    path=tmp_path/'draft.txt'; contracts.draft(path,tmp_path/'run')
    with pytest.raises(PermissionError,match='ACTIVE'):
        run(path,backend=Fake(),tokenizer=Tokenizer())
    assert not (tmp_path/'run').exists()
    path.write_text(path.read_text().replace('STATUS: DRAFT','STATUS: ACTIVE')+'STATUS: ACTIVE\n')
    with pytest.raises(ValueError,match='duplicate'):
        run(path,backend=Fake(),tokenizer=Tokenizer())


def test_complete_smoke_uses_only_fresh_answers_and_resume_makes_no_calls(monkeypatch,tmp_path):
    path=active_contract(monkeypatch,tmp_path)
    client=Fake()
    result=run(path,backend=client,tokenizer=Tokenizer(),sleep=lambda _:None)
    assert result['kind']=='synthetic_transport_test' and result['requests']==18
    assert result['counts']['semantic_calls']==18
    assert all('Synthetic answer' in p['messages'][-1]['content'] for p in client.calls[8:])
    assert all(p['provider']['allow_fallbacks'] is False for p in client.calls)
    assert all(p['provider']['require_parameters'] is True for p in client.calls)
    assert result['reported_cost_usd_known']==pytest.approx(.00018)
    second=Fake()
    assert run(path,resume=True,backend=second,tokenizer=Tokenizer())==result
    assert second.calls==[]
    with pytest.raises(FileExistsError):
        run(path,backend=second,tokenizer=Tokenizer())


def test_partial_resume_preserves_success_and_retries_only_missing(monkeypatch,tmp_path):
    path=active_contract(monkeypatch,tmp_path)
    with pytest.raises(RequestFailure,match='Synthetic stop'):
        run(path,backend=Fake(fail_on=4),tokenizer=Tokenizer(),sleep=lambda _:None)
    original=(tmp_path/'run/answers.jsonl').read_bytes()
    resumed=Fake()
    result=run(path,resume=True,backend=resumed,tokenizer=Tokenizer(),sleep=lambda _:None)
    assert len(resumed.calls)==15 and result['requests']==19
    assert (tmp_path/'run/answers.jsonl').read_bytes().startswith(original)


def test_transient_and_schema_failures_are_bounded_and_recorded(monkeypatch,tmp_path):
    path=active_contract(monkeypatch,tmp_path)
    client=Fake(transient=1,malformed=1)
    result=run(path,backend=client,tokenizer=Tokenizer(),sleep=lambda _:None)
    assert result['requests']==20
    assert len(ledger(tmp_path/'run/failures.jsonl'))==2
    assert client.calls[0]['seed']!=client.calls[1]['seed']
    scores=[p for p in client.calls if p.get('response_format',{}).get('json_schema',{}).get('name')=='legal_score']
    assert scores[0]['max_tokens']==8192 and scores[1]['max_tokens']==16384


@pytest.mark.parametrize('limit,value',[('MAX_REQUESTS',1),('MAX_USD',.0000001)])
def test_budget_stops_before_dispatch(monkeypatch,tmp_path,limit,value):
    path=active_contract(monkeypatch,tmp_path,**{limit:value})
    client=Fake()
    with pytest.raises(RuntimeError,match='limit'):
        run(path,backend=client,tokenizer=Tokenizer(),sleep=lambda _:None)
    assert len(client.calls)==(1 if limit=='MAX_REQUESTS' else 0)


def test_exhaustion_and_changed_results_fail_closed(monkeypatch,tmp_path):
    path=active_contract(monkeypatch,tmp_path)
    with pytest.raises(RuntimeError,match='exhausted'):
        run(path,backend=Fake(transient=99),tokenizer=Tokenizer(),sleep=lambda _:None)
    assert len(ledger(tmp_path/'run/requests.jsonl'))==3
    with pytest.raises(RuntimeError,match='exhausted'):
        run(path,resume=True,backend=Fake(),tokenizer=Tokenizer(),sleep=lambda _:None)


def test_changed_accepted_answer_is_rejected_on_resume(monkeypatch,tmp_path):
    path=active_contract(monkeypatch,tmp_path)
    run(path,backend=Fake(),tokenizer=Tokenizer(),sleep=lambda _:None)
    file=tmp_path/'run/answers.jsonl'
    file.write_text(file.read_text().replace('Synthetic answer','Changed answer',1))
    with pytest.raises(ValueError,match='answer content changed'):
        run(path,resume=True,backend=Fake(),tokenizer=Tokenizer())


def test_request_settings_preserve_original_protocol():
    planned=plan();protocol=bundle.protocol();task=planned['generation'][0]
    first=request_payload('generation',task,[{'role':'user','content':'test'}],protocol,0)
    retry=request_payload('generation',task,[{'role':'user','content':'test'}],protocol,1)
    assert first['temperature']==0 and first['max_tokens']==2048 and first['reasoning']=={'enabled':False}
    assert first['repetition_penalty']==1 and retry['repetition_penalty']==1.1


@pytest.mark.parametrize('justification',(None,True,[],42))
def test_non_string_score_explanations_fail_schema(justification):
    from legal_repro.schemas import parse_score
    value={k:{'score':.5,'justification':'Valid reason.'} for k in SCORE_DIMENSIONS}
    value[SCORE_DIMENSIONS[0]]['justification']=justification
    with pytest.raises(ValueError,match='Non-string'):
        parse_score(json.dumps(value))


def test_finalize_after_interruption_needs_no_network(monkeypatch,tmp_path):
    from legal_repro import runner
    path=active_contract(monkeypatch,tmp_path)
    real_write=runner.write_new
    def interrupt_receipt(destination,value):
        if destination.name=='COMPLETE.json':
            raise RuntimeError('Synthetic receipt interruption')
        return real_write(destination,value)
    monkeypatch.setattr(runner,'write_new',interrupt_receipt)
    with pytest.raises(RuntimeError,match='receipt interruption'):
        run(path,backend=Fake(),tokenizer=Tokenizer(),sleep=lambda _:None)
    monkeypatch.setattr(runner,'write_new',real_write)
    client=Fake()
    client.preflight=lambda _:pytest.fail('CPU-only finalization must not contact the provider')
    receipt=run(path,resume=True,backend=client,tokenizer=Tokenizer())
    assert receipt['accepted'] and not client.calls


def test_changed_request_reservation_is_rejected(monkeypatch,tmp_path):
    path=active_contract(monkeypatch,tmp_path)
    with pytest.raises(RequestFailure):
        run(path,backend=Fake(fail_on=1),tokenizer=Tokenizer())
    file=tmp_path/'run/requests.jsonl'
    records=ledger(file);records[0]['reserved_usd']=-1
    file.write_text(''.join(json.dumps(r)+'\n' for r in records))
    with pytest.raises(ValueError,match='reservation ledger'):
        run(path,resume=True,backend=Fake(),tokenizer=Tokenizer())


@pytest.mark.parametrize('failure',('http','model','provider','truncated','empty','multiple'))
def test_transport_authentication_and_response_validation(monkeypatch,failure):
    key='fixture-key-never-real'
    def urlopen(request,timeout):
        assert request.get_header('Authorization')=='Bearer '+key
        assert request.full_url=='https://openrouter.ai/api/v1/chat/completions'
        if failure=='http':
            raise urllib.error.HTTPError(request.full_url,401,'Unauthorized',{},io.BytesIO(key.encode()))
        body={'model':'model','provider':'provider','choices':[{'finish_reason':'stop','message':{'content':'text'}}]}
        if failure=='model': body['model']='unexpected'
        if failure=='provider': body['provider']='unexpected'
        if failure=='truncated': body['choices'][0]['finish_reason']='length'
        if failure=='empty': body['choices'][0]['message']['content']=''
        if failure=='multiple': body['choices']*=2
        return io.BytesIO(json.dumps(body).encode())
    monkeypatch.setattr('urllib.request.urlopen',urlopen)
    with pytest.raises(RequestFailure) as caught:
        OpenRouter(key).complete({'model':'model'}, {'provider_name':'provider'})
    assert key not in str(caught.value)
