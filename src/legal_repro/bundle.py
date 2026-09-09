"""Read immutable bundled inputs independently of saved answers."""
import gzip
import hashlib
import json
from functools import lru_cache

from .paths import ASSETS


def manifest():
    from .integrity import MANIFEST_SHA256
    data = (ASSETS / 'MANIFEST.json').read_bytes()
    if hashlib.sha256(data).hexdigest() != MANIFEST_SHA256:
        raise ValueError('Packaged asset manifest changed')
    return json.loads(data)


def asset_bytes(name):
    entries = manifest()['files']
    if name not in entries:
        raise ValueError('Asset is not in the release manifest')
    path = ASSETS / name
    if path.is_symlink() or not path.resolve().is_relative_to(ASSETS):
        raise ValueError('Asset escapes the package')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entries[name]['sha256'] or len(data) != entries[name]['bytes']:
        raise ValueError(f'Packaged asset changed: {name}')
    return data


def verify_assets():
    for name in manifest()['files']:
        asset_bytes(name)
    return len(manifest()['files'])


def inputs():
    return json.loads(gzip.decompress(asset_bytes('data/inputs.json.gz')))


def references():
    return json.loads(gzip.decompress(asset_bytes('data/reference_results.json.gz')))


def protocol():
    return json.loads(asset_bytes('protocol.json'))


def context_for(data, condition):
    if condition['context_kind'] == 'paragraphenliste':
        return condition['paragraph_ids']
    return data['contexts'][condition['context']]


def load_payload():
    from .review_bundle import METHODS, RATIOS, CANDIDATES
    data, reference = inputs(), references()
    by_id = {r['id']:r for r in reference['rows']}
    if len(by_id) != len(reference['rows']) or set(by_id) != {r['id'] for r in data['rows']}:
        raise ValueError('Input/reference question identities do not match')
    rows = []
    for row in data['rows']:
        ref = by_id[row['id']]
        if set(row['conditions']) != set(ref['conditions']):
            raise ValueError('Input/reference conditions do not match')
        rows.append({**{k:row[k] for k in ('id','question','gold','cluster')},
                     'conditions':{name:{**condition, **ref['conditions'][name]} for name,condition in row['conditions'].items()},
                     'rankings':ref['rankings']})
    return {'schema_version':1,'rows':rows,'contexts':data['contexts'],'methods':METHODS,
            'ratios':RATIOS,'candidates':list(CANDIDATES),'meta':data['meta']}
