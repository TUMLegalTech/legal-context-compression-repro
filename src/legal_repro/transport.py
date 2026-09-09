"""One-key OpenRouter transport with fixed model/provider routing."""
import json
import urllib.error
import urllib.request

from .io import digest_text
from .schemas import rank_schema, score_schema, transport_schema
from .task_protocol import derived_seed

BASE = 'https://openrouter.ai/api/v1'


class RequestFailure(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable=retryable


def request_payload(kind, task, messages, protocol, attempt):
    role='generator' if kind=='generation' else 'judge'
    settings=protocol['generation' if role=='generator' else 'judge']
    profile=protocol['hosted_models'][role]
    payload={'model':profile['model'],'messages':messages,'stream':False,
             'temperature':settings['temperature'],
             'provider':{'only':[profile['provider']],'allow_fallbacks':False,'require_parameters':True,
                         'max_price':{'prompt':profile['max_prompt_price'],'completion':profile['max_completion_price']}}}
    if kind=='generation':
        payload.update(max_tokens=settings['max_new_tokens'], reasoning={'enabled':False},
                       seed=derived_seed(protocol['seed'],'generation',task['id'],attempt),
                       repetition_penalty=1.0 if attempt==0 else settings['retry_repetition_penalty'])
    else:
        payload.update(max_tokens=settings['max_tokens'] if attempt==0 else settings['retry_max_tokens'],
                       reasoning={'effort':settings['reasoning_effort']},
                       seed=int(digest_text(f"minimal\0{protocol['seed']}\0{kind}\0{task['pass_id']}\0{task['id']}\0{attempt}")[:8],16)&0x7fffffff)
        schema=score_schema() if kind=='score' else rank_schema(sorted(task['blind_to_condition']))
        payload['response_format']={'type':'json_schema','json_schema':{'name':'legal_'+kind,'schema':transport_schema(schema),'strict':True}}
    return payload


def conservative_cost(payload, profile):
    # UTF-8 bytes upper-bound ordinary BPE tokens; extra allowance covers wrappers.
    input_bound=len(json.dumps(payload,ensure_ascii=False).encode())+4096
    return (input_bound*profile['max_prompt_price']+payload['max_tokens']*profile['max_completion_price'])/1_000_000


class OpenRouter:
    def __init__(self, key, timeout=120):
        if not isinstance(key,str) or not key.strip() or any(c.isspace() for c in key):
            raise ValueError('OPENROUTER_API_KEY is missing or malformed')
        self._key=key
        self.timeout=timeout

    def preflight(self, protocol):
        snapshots={}
        for role,profile in protocol['hosted_models'].items():
            with urllib.request.urlopen(BASE+'/models/'+profile['model']+'/endpoints',timeout=30) as response:
                data=json.load(response)
            matches=[e for e in data['data']['endpoints'] if e.get('tag')==profile['provider'] and e.get('status')==0]
            if len(matches)!=1:
                raise RequestFailure(f'Pinned {role} endpoint is unavailable; change requires a new protocol/run')
            entry=matches[0]
            required={'temperature','reasoning','max_tokens','seed'}
            required |= {'repetition_penalty'} if role=='generator' else {'response_format','structured_outputs'}
            if not required<=set(entry['supported_parameters']):
                raise RequestFailure(f'Pinned {role} endpoint lacks required parameters')
            if float(entry['pricing']['prompt'])*1e6>profile['max_prompt_price']+1e-10 or float(entry['pricing']['completion'])*1e6>profile['max_completion_price']+1e-10:
                raise RequestFailure(f'Pinned {role} prices exceed this protocol')
            snapshots[role]=entry
        return snapshots

    def complete(self, payload, profile):
        request=urllib.request.Request(BASE+'/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode(),
            headers={'Content-Type':'application/json','Authorization':'Bearer '+self._key},method='POST')
        try:
            with urllib.request.urlopen(request,timeout=self.timeout) as response:
                body=json.load(response)
        except urllib.error.HTTPError as error:
            # Never persist arbitrary provider error bodies or request headers.
            raise RequestFailure(f'OpenRouter HTTP {error.code}',error.code in (408,429) or 500<=error.code<600) from None
        except (urllib.error.URLError,TimeoutError):
            raise RequestFailure('OpenRouter transport timeout or connection failure',True) from None
        except (ValueError,UnicodeError):
            raise RequestFailure('OpenRouter returned malformed JSON',True) from None
        if body.get('model')!=payload['model'] or body.get('provider')!=profile['provider_name']:
            raise RequestFailure('Response model/provider identity differs from the pinned request')
        choices=body.get('choices',[])
        if len(choices)!=1 or choices[0].get('finish_reason')!='stop':
            raise RequestFailure('Completion is missing, multiple, refused, or truncated',True)
        content=choices[0].get('message',{}).get('content')
        if not isinstance(content,str) or not content.strip():
            raise RequestFailure('Empty completion',True)
        return {'content':content,'response_id':body.get('id'),'response_model':body['model'],
                'provider':body['provider'],'finish_reason':'stop','usage':body.get('usage',{})}
