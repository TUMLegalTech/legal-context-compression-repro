"""Deterministic serialization and append-only experiment receipts."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def digest_json(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def digest_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def write_new(path, value):
    path = Path(path)
    with path.open('xb') as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())


def append(path, value):
    with Path(path).open('ab') as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())


def ledger(path):
    path = Path(path)
    if not path.exists():
        return []
    data = path.read_bytes()
    if data and not data.endswith(b'\n'):
        raise ValueError(f'Incomplete ledger tail: {path.name}; preserve and inspect it before resuming')
    return [json.loads(line) for line in data.splitlines()]
