"""Maintainer-only export of two final returns; no private linkage keys or API calls."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

from legal_repro import bundle
from legal_repro.human import json_bytes, normalize_returns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for code in ('annotator-1', 'annotator-2'):
        parser.add_argument('--' + code, type=Path, required=True)
        parser.add_argument('--' + code + '-zip', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    returns, packets, sources = {}, {}, {}
    for code in ('annotator_1', 'annotator_2'):
        path, archive_path = getattr(args, code), getattr(args, code + '_zip')
        raw, zipped = path.read_bytes(), archive_path.read_bytes()
        returns[code] = json.loads(raw)
        with zipfile.ZipFile(archive_path) as archive:
            html = archive.read('index.html').decode()
        match = re.search(r'<script id="review-data" type="application/json">(.*?)</script>', html, re.S)
        if match is None:
            raise ValueError('Distributed packet is missing')
        packets[code] = json.loads(match[1])
        sources[code] = {'return_sha256': hashlib.sha256(raw).hexdigest(), 'return_bytes': len(raw),
                         'zip_sha256': hashlib.sha256(zipped).hexdigest()}
    result = normalize_returns(returns, packets, bundle.load_payload())
    for code, values in sources.items():
        result['source_returns'][code].update(values)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(json_bytes(result))
    print(json.dumps({'output': str(args.output), 'questions': len(result['cases']),
                      'annotators': len(result['reviewers']), 'live_model_requests': 0}))


if __name__ == '__main__':
    main()
