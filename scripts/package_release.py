"""Allowlisted, manifest-bound release archive. No credentials or remote actions."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TOP=('.env.example','.gitignore','.gitattributes','.python-version','AGENTS.md','README.md','LICENSE',
     'THIRD_PARTY_NOTICES.md','CITATION.cff','pyproject.toml','package.json','package-lock.json','uv.lock')
FOLDERS=('.github','docs','figures','human_evaluation','participant_apps','prompts','scripts','src/legal_repro','tests')

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--refresh-manifest',action='store_true',help='Preserve the previous local manifest beside the new archive')
args=parser.parse_args()
if Path.cwd().resolve()!=ROOT or subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip()!=str(ROOT):
    raise PermissionError('Run packaging in this exact Git root')
paths=[ROOT/name for name in TOP]+[ROOT/'contracts/README.md']
for folder in FOLDERS:
    paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo'))
files={}
for path in sorted(set(paths)):
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
        raise PermissionError('Release files must be regular and contained')
    name=path.relative_to(ROOT).as_posix()
    if any(part in ('_prev','node_modules','.venv','outputs','review') for part in path.relative_to(ROOT).parts[:-1]) and not name.startswith('src/legal_repro/assets/ui/review/'):
        raise PermissionError('Excluded release tree')
    data=path.read_bytes()
    if path.suffix in ('.py','.md','.txt','.json','.toml','.yml','.js','.cjs','.html','.csv'):
        # Check allowlisted publishable text only; never open a real credential file.
        if re.search(rb'(?:sk-or-v1-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)',data):
            raise PermissionError('Possible credential found in release path '+name)
    files[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
manifest={'schema_version':1,'intended_remote':'https://github.com/TUMLegalTech/legal-context-compression-repro.git',
          'visibility':'public','files':files,'file_count':len(files),'total_bytes':sum(f['bytes'] for f in files.values())}
manifest_path=ROOT/'RELEASE_MANIFEST.json'
if manifest_path.exists():
    if not args.refresh_manifest:
        raise FileExistsError('Existing release manifest; use an explicit fresh archive and --refresh-manifest')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.with_suffix('.previous-manifest.json').open('xb') as stream:
        stream.write(manifest_path.read_bytes())
with manifest_path.open('w' if args.refresh_manifest else 'x') as stream:
    json.dump(manifest,stream,indent=2,sort_keys=True);stream.write('\n')
args.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(args.output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for path in [*(ROOT/name for name in files),manifest_path]:
        archive.write(path,'legal-context-compression-repro/'+path.relative_to(ROOT).as_posix())
print(json.dumps({'archive':str(args.output.resolve()),'archive_bytes':args.output.stat().st_size,
                  'archive_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),
                  'file_count':len(files)+1,'uncompressed_bytes':manifest['total_bytes']}))
