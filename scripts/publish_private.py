"""Publish only after approval/activation of the exact local publication contract."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from legal_repro import contracts
from legal_repro.io import write_new,utc_now

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--contract',type=Path,required=True)
args=parser.parse_args()
contract=contracts.load(args.contract,'publish')
root=Path(contract['WORKSPACE'])
output=Path(contract['OUTPUT_ROOT'])


def command(arguments, *, cwd=root, check=True):
    result=subprocess.run(arguments,cwd=cwd,text=True,capture_output=True)
    if check and result.returncode:
        # Command arguments never contain keys. Do not expose arbitrary auth output.
        raise RuntimeError(f'{arguments[0]} failed with exit {result.returncode}; inspect authentication or repository permissions locally')
    return result


manifest=json.loads((root/'RELEASE_MANIFEST.json').read_bytes())
for name,expected in manifest['files'].items():
    path=root/name
    if path.is_symlink() or not path.resolve().is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected['sha256']:
        raise ValueError('Release differs from the reviewed file manifest')
if command(['git','status','--porcelain']).stdout.strip():
    raise ValueError('Commit the reviewed release before publishing')
head=command(['git','rev-parse','HEAD']).stdout.strip()
name='mpriorust/legal-context-compression-repro'
existing=command(['gh','repo','view',name,'--json','isPrivate,nameWithOwner,url'],check=False)
if existing.returncode==0:
    metadata=json.loads(existing.stdout)
    if not metadata['isPrivate'] or metadata['nameWithOwner']!=name:
        raise PermissionError('Destination must be the exact named private repository')
    ref=command(['gh','api',f'repos/{name}/git/ref/heads/main'],check=False)
    if ref.returncode==0 and json.loads(ref.stdout)['object']['sha']!=head:
        raise PermissionError('An existing destination has different history; refusing to adopt or overwrite it')
else:
    command(['gh','repo','create',name,'--private','--description','Frozen-evidence figure reconstruction and one-key hosted replication of German legal context compression'])
metadata=json.loads(command(['gh','repo','view',name,'--json','isPrivate,nameWithOwner,url']).stdout)
if metadata['isPrivate'] is not True or metadata['nameWithOwner']!=name:
    raise PermissionError('Repository identity/privacy verification failed')
remote=command(['git','remote','get-url','origin'],check=False)
if remote.returncode:
    command(['git','remote','add','origin',contracts.REMOTE])
elif remote.stdout.strip()!=contracts.REMOTE:
    raise PermissionError('Unexpected origin remote')
git=['git','-c','credential.helper=','-c','credential.https://github.com.helper=!gh auth git-credential']
command([*git,'push','-u','origin','main'])
ref=json.loads(command(['gh','api',f'repos/{name}/git/ref/heads/main']).stdout)
metadata=json.loads(command(['gh','repo','view',name,'--json','isPrivate,nameWithOwner,url']).stdout)
if ref['object']['sha']!=head or metadata['isPrivate'] is not True:
    raise ValueError('Published revision/privacy differs from the verified local release')
output.mkdir(parents=True,exist_ok=True)
clone=output/'github-clone'
if clone.exists():
    raise FileExistsError('Fresh-clone destination exists; preserve it and inspect before retrying')
command([*git,'clone',contracts.REMOTE,str(clone)])
command(['uv','sync','--frozen'],cwd=clone)
verification=json.loads(command(['uv','run','--frozen','legal-repro','verify'],cwd=clone).stdout)
if verification.get('accepted') is not True:
    raise ValueError('Fresh private GitHub clone did not verify')
receipt={'accepted':True,'created_at':utc_now(),'remote':contracts.REMOTE,'private':True,
         'commit':head,'fresh_github_clone_verified':True,'verification':verification}
write_new(output/'PUBLISHED.json',receipt)
print(json.dumps(receipt,indent=2))
