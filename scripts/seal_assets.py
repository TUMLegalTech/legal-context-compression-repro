"""Bind the allowlisted release assets. Run only after an intentional reviewed export."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]/'src/legal_repro'
assets=root/'assets'
files={}
for path in sorted(assets.rglob('*')):
    if path.is_symlink():
        raise ValueError('Release assets must not be symlinks')
    if path.is_file() and path!=assets/'MANIFEST.json':
        value=path.read_bytes()
        files[str(path.relative_to(assets))]={'sha256':hashlib.sha256(value).hexdigest(),'bytes':len(value)}
data=(json.dumps({'schema_version':1,'files':files},sort_keys=True,indent=2)+'\n').encode()
(assets/'MANIFEST.json').write_bytes(data)
(root/'integrity.py').write_text('"""Identity of the intentionally exported resource bundle."""\nMANIFEST_SHA256 = '+repr(hashlib.sha256(data).hexdigest())+'\n')
print(json.dumps({'assets':len(files),'manifest_sha256':hashlib.sha256(data).hexdigest()}))
