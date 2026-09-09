"""Sequential, budgeted, resumable hosted replication from frozen contexts."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import time
import urllib.request

from . import bundle, contracts
from .io import append, canonical, digest_json, digest_text, ledger, utc_now, write_new
from .planning import messages, plan
from .schemas import parse_rank, parse_score
from .task_protocol import repeated_ngram_fraction
from .transport import OpenRouter, RequestFailure, conservative_cost, request_payload

TOKENIZER_SHA256 = '5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42'


def api_key(contract):
    value=os.environ.get(contract['API_KEY_ENV'],'')
    if value:
        return value
    path=Path(contract['WORKSPACE'])/'.env'
    if not path.exists():
        raise ValueError('Set OPENROUTER_API_KEY or add its single assignment to this workspace .env')
    if path.is_symlink():
        raise PermissionError('The key file must not be a symlink')
    lines=[line.strip() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if len(lines)!=1 or not lines[0].startswith('OPENROUTER_API_KEY='):
        raise ValueError('The local .env must contain only OPENROUTER_API_KEY=<value>')
    value=lines[0].partition('=')[2]
    if len(value)>=2 and value[0]==value[-1] and value[0] in ('"',"'"):
        value=value[1:-1]
    return value


def tokenizer_for(output, protocol):
    from tokenizers import Tokenizer
    path=output/'tokenizer.json'
    if not path.exists():
        spec=protocol['tokenizer']
        url=f"https://huggingface.co/{spec['model']}/resolve/{spec['revision']}/{spec['file']}"
        with urllib.request.urlopen(url,timeout=60) as response:
            data=response.read(13_000_000)
        if hashlib.sha256(data).hexdigest()!=TOKENIZER_SHA256:
            raise ValueError('Pinned public tokenizer differs from its published SHA-256')
        with path.open('xb') as stream:
            stream.write(data)
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=TOKENIZER_SHA256:
        raise ValueError('Cached tokenizer differs from the pinned artifact')
    return Tokenizer.from_file(str(path))


def source_identity():
    # Bind every executable module and the locked resource manifest, also in a wheel.
    package=Path(__file__).parent
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package.glob('*.py'))}


def request_history(output,expected,fingerprint):
    events=ledger(output/'requests.jsonl')
    starts=[]; results=set(); task_attempts={}
    for event in events:
        request_id=event.get('request_id')
        if event.get('event')=='start':
            key=(event.get('kind'),event.get('task_id'))
            cost=event.get('reserved_usd')
            if (request_id!=len(starts)+1 or key[0] not in expected or key[1] not in expected[key[0]]
                    or event.get('protocol_sha256')!=fingerprint or event.get('attempt')!=task_attempts.get(key,0)
                    or not isinstance(cost,(int,float)) or not math.isfinite(cost) or cost<=0):
                raise ValueError('Invalid request reservation ledger')
            task_attempts[key]=event['attempt']+1
            starts.append(event)
        elif event.get('event')=='result':
            cost=event.get('actual_cost_usd')
            if (type(request_id) is not int or not 1<=request_id<=len(starts) or request_id in results
                    or (cost is not None and (not isinstance(cost,(int,float)) or not math.isfinite(cost) or cost<0))):
                raise ValueError('Invalid request result ledger')
            results.add(request_id)
        else:
            raise ValueError('Unknown request ledger event')
    return events,starts


def finalize(output,planned,protocol,original,fingerprint,accepted,expected):
    from .results import summarize,full_statistics
    events,started=request_history(output,expected,fingerprint)
    summary=summarize(planned,accepted)
    summary['transport_kind']=original['identity']['transport_kind']
    if planned['mode']=='evaluate':
        summary['contrasts']=full_statistics(planned,accepted,protocol)
    path=output/'summary.json'
    if path.exists():
        if path.read_bytes()!=canonical(summary):
            raise ValueError('Existing summary differs from accepted rows')
    else:
        write_new(path,summary)
    artifacts=('answers.jsonl','scores.jsonl','ranks.jsonl','summary.json','requests.jsonl')
    if (output/'failures.jsonl').exists():
        artifacts+=('failures.jsonl',)
    receipt={'accepted':True,'created_at':utc_now(),'kind':original['identity']['transport_kind'],
             'protocol_sha256':fingerprint,'counts':planned['counts'],'requests':len(started),
             'reserved_upper_bound_usd':sum(e['reserved_usd'] for e in started),
             'reported_cost_usd_known':sum(e.get('actual_cost_usd') or 0 for e in events if e['event']=='result'),
             'hosted_revision_verified':False,'original_runtime_equivalence_claimed':False,
             'artifacts':{name:hashlib.sha256((output/name).read_bytes()).hexdigest()
                          for name in artifacts},'output':str(output)}
    write_new(output/'COMPLETE.json',receipt)
    return receipt


def run(contract_path, mode='smoke', resume=False, *, backend=None, tokenizer=None, sleep=time.sleep):
    contract=contracts.load(Path(contract_path),mode)
    planned=plan(mode)
    protocol=bundle.protocol()
    output=Path(contract['OUTPUT_ROOT'])
    if resume and contract['ALLOW_RESUME']!='true':
        raise PermissionError('Contract does not authorize resume')
    transport_kind='live_api' if backend is None else 'synthetic_transport_test'
    identity={'schema_version':1,'contract':contract,'mode':mode,'counts':planned['counts'],
              'protocol':protocol,'assets':digest_json(bundle.manifest()),'source':source_identity(),
              'transport_kind':transport_kind,'plan_sha256':digest_json({k:planned[k] for k in ('generation','score','rank')})}
    fingerprint=digest_json(identity)
    if output.exists():
        if not resume:
            raise FileExistsError('Output exists; explicit --resume is required')
        original=json.loads((output/'manifest.json').read_bytes())
        if original['identity']!=identity or original['protocol_sha256']!=fingerprint:
            raise ValueError('Cannot resume: contract, source, inputs, plan or protocol changed')
    else:
        if resume:
            raise FileNotFoundError('There is no run to resume')
        output.mkdir(parents=True,exist_ok=False)
        original={'created_at':utc_now(),'created_unix':time.time(),'protocol_sha256':fingerprint,'identity':identity}
        write_new(output/'manifest.json',original)
    with (output/'run.lock').open('a') as lock:
        try:
            if os.name=='nt':
                import msvcrt
                lock.write('0');lock.flush();lock.seek(0)
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Another process owns this run') from None
        return _run_locked(output,contract,planned,protocol,original,fingerprint,backend,tokenizer,sleep)


def _run_locked(output,contract,planned,protocol,original,fingerprint,backend,tokenizer,sleep):
    expected={kind:{task['id']:task for task in planned[kind]} for kind in ('generation','score','rank')}
    names={'generation':'answers.jsonl','score':'scores.jsonl','rank':'ranks.jsonl'}
    accepted={}
    for kind in names:
        rows=ledger(output/names[kind])
        indexed={r['id']:r for r in rows}
        if len(indexed)!=len(rows) or not set(indexed)<=set(expected[kind]):
            raise ValueError('Duplicate or out-of-plan accepted result')
        for task_id,row in indexed.items():
            if row['protocol_sha256']!=fingerprint or row['task_sha256']!=digest_json(expected[kind][task_id]):
                raise ValueError('Accepted result no longer matches the run/task')
            if row.get('finish_reason')!='stop':
                raise ValueError('Accepted result did not finish naturally')
            if kind=='generation':
                if not row['answer'].strip() or digest_text(row['answer'])!=row['answer_sha256']:
                    raise ValueError('Accepted answer content changed')
            else:
                parser=parse_score if kind=='score' else lambda text:parse_rank(text,sorted(expected[kind][task_id]['blind_to_condition']))
                if parser(row['content'])!=row['parsed']:
                    raise ValueError('Accepted judgment content changed')
        accepted[kind]=indexed
    answers={(row['row_id'],row['candidate_id']):row for row in accepted['generation'].values()}
    # Bind existing scores/ranks to exact fresh answers, including interrupted resumes.
    for kind in ('score','rank'):
        for task_id,row in accepted[kind].items():
            if digest_json(messages(kind,expected[kind][task_id],planned,answers))!=row['messages_sha256']:
                raise ValueError('Accepted judgment refers to different answers')
    if (output/'COMPLETE.json').exists():
        receipt=json.loads((output/'COMPLETE.json').read_bytes())
        if (receipt.get('protocol_sha256')!=fingerprint or receipt.get('kind')!=original['identity']['transport_kind']
                or receipt.get('accepted') is not True or receipt.get('counts')!=planned['counts']
                or not {'answers.jsonl','scores.jsonl','ranks.jsonl','summary.json','requests.jsonl'}<=set(receipt.get('artifacts',{}))
                or not set(receipt['artifacts'])<={'answers.jsonl','scores.jsonl','ranks.jsonl','summary.json','requests.jsonl','failures.jsonl'}):
            raise ValueError('Completion receipt differs from this run')
        if not all(set(accepted[k])==set(expected[k]) for k in names):
            raise ValueError('Completion receipt has incomplete ledgers')
        for name,digest in receipt['artifacts'].items():
            if hashlib.sha256((output/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Completed run artifact changed')
        return receipt
    if all(set(accepted[k])==set(expected[k]) for k in names):
        return finalize(output,planned,protocol,original,fingerprint,accepted,expected)
    attempts,started=request_history(output,expected,fingerprint)
    deadline=original['created_unix']+int(contract['MAX_SECONDS'])
    if time.time()>=deadline:
        raise RuntimeError('Contract wall-clock limit exhausted')
    # The sole credential read occurs only after the active contract and resume checks.
    client=backend if backend is not None else OpenRouter(api_key(contract),timeout=min(120,int(contract['MAX_SECONDS'])))
    try:
        snapshots=client.preflight(protocol)
        event=output/f'preflight-{time.time_ns()}.json'
        write_new(event,{'created_at':utc_now(),'endpoints':snapshots,'hosted_revision_verified':False})
        tokenization=tokenizer if tokenizer is not None else tokenizer_for(output,protocol)
        reserved=sum(e['reserved_usd'] for e in started)
        actual_known=sum(e.get('actual_cost_usd') or 0 for e in attempts if e['event']=='result')
        for kind in names:
            for task in planned[kind]:
                if task['id'] in accepted[kind]:
                    continue
                role='generator' if kind=='generation' else 'judge'
                profile=protocol['hosted_models'][role]
                limits=protocol['generation' if role=='generator' else 'judge']
                maximum=limits['maximum_completion_attempts' if role=='generator' else 'maximum_attempts']
                previous=sum(e['kind']==kind and e['task_id']==task['id'] for e in started)
                success=False
                for attempt in range(previous,maximum):
                    content_messages=messages(kind,task,planned,answers)
                    payload=request_payload(kind,task,content_messages,protocol,attempt)
                    reservation=conservative_cost(payload,profile)
                    if time.time()>=deadline or len(started)>=int(contract['MAX_REQUESTS']) or reserved+reservation>float(contract['MAX_USD']):
                        raise RuntimeError('Contract time, request or conservative spending limit reached')
                    record={'event':'start','created_at':utc_now(),'kind':kind,'task_id':task['id'],'attempt':attempt,
                            'request_id':len(started)+1,'reserved_usd':reservation,
                            'payload_sha256':digest_json(payload),'seed':payload['seed'],'protocol_sha256':fingerprint}
                    append(output/'requests.jsonl',record)
                    started.append(record); reserved+=reservation
                    response=None
                    try:
                        if hasattr(client,'timeout'):
                            client.timeout=min(120,max(1,deadline-time.time()))
                        response=client.complete(payload,profile)
                        cost=response.get('usage',{}).get('cost')
                        cost=None if cost is None else float(cost)
                        if cost is not None and (not math.isfinite(cost) or cost<0):
                            raise RequestFailure('Invalid reported API cost')
                        actual_known+=cost or 0
                        append(output/'requests.jsonl',{'event':'result','request_id':record['request_id'],'actual_cost_usd':cost,
                                                       'usage':response.get('usage',{}),'response_id':response.get('response_id')})
                        if actual_known>float(contract['MAX_USD']):
                            raise RequestFailure('Reported API cost exceeded the contract; stop and inspect billing')
                        common={k:response.get(k) for k in ('response_id','response_model','provider','finish_reason','usage')}
                        result={'id':task['id'],'kind':kind,'row_id':task['row_id'],'candidate_id':task['candidate_id'],
                                'protocol_sha256':fingerprint,'task_sha256':digest_json(task),'messages_sha256':digest_json(content_messages),
                                'accepted_attempt':attempt,'seed':payload['seed'],'hosted_revision':None,
                                'request_payload':payload, **common}
                        if kind=='generation':
                            ids=tokenization.encode(response['content'],add_special_tokens=False).ids
                            repetition=repeated_ngram_fraction(ids)
                            if repetition>limits['maximum_repeated_8gram_fraction']:
                                raise RequestFailure('Repeated output exceeds the original eight-gram limit',True)
                            result.update(answer=response['content'],answer_sha256=digest_text(response['content']),
                                          answer_tokens=len(ids),repeated_8gram_fraction=repetition)
                        else:
                            try:
                                parsed=parse_score(response['content']) if kind=='score' else parse_rank(response['content'],sorted(task['blind_to_condition']))
                            except ValueError:
                                raise RequestFailure('Judgment failed the original local schema validator',True) from None
                            result.update(content=response['content'],parsed=parsed)
                            if kind=='score':
                                result.update(generation_id=task['generation_id'],replicate=task['replicate'],**parsed)
                            else:
                                blind=task['blind_to_condition']
                                result.update(pass_id=task['pass_id'],blind_to_condition=blind,
                                    blind_rank_groups=parsed['rank_groups'],rank_groups=[[blind[label] for label in g] for g in parsed['rank_groups']],
                                    candidate_justifications={blind[k]:v for k,v in parsed['candidate_justifications'].items()},
                                    comparative_justification=parsed['comparative_justification'])
                        append(output/names[kind],result)
                        accepted[kind][task['id']]=result
                        if kind=='generation':
                            answers[(task['row_id'],task['candidate_id'])]=result
                        success=True
                        print(json.dumps({'stage':kind,'completed':len(accepted[kind]),'total':len(expected[kind]),'reserved_usd':round(reserved,6)}),flush=True)
                        break
                    except RequestFailure as error:
                        append(output/'failures.jsonl',{'created_at':utc_now(),'request_id':record['request_id'],
                            'kind':kind,'task_id':task['id'],'attempt':attempt,'error':str(error),'retryable':error.retryable,
                            'response':response})
                        if not error.retryable:
                            raise
                        if attempt+1<maximum:
                            sleep(min(2**attempt,8))
                if not success:
                    raise RuntimeError(f'Bounded attempts exhausted for {kind} task {task["id"]}')
        return finalize(output,planned,protocol,original,fingerprint,accepted,expected)
    except Exception as error:
        # Generic exception text may include transport internals; retain the type only.
        append(output/'interruptions.jsonl',{'created_at':utc_now(),'exception_type':type(error).__name__})
        raise
