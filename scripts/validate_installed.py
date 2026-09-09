"""Offline wheel acceptance. Block source-checkout reads and all network access."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--forbid',type=Path,action='append',default=[])
args=parser.parse_args()
forbidden=[p.resolve() for p in args.forbid]
blocked_attempts=[]


def audit(event,values):
    if event=='socket.connect':
        raise RuntimeError('Network is disabled during installed-wheel acceptance')
    if event in ('open','os.listdir','os.scandir') and values and isinstance(values[0],(str,bytes)):
        path=Path(values[0].decode() if isinstance(values[0],bytes) else values[0]).absolute()
        if any(path==root or path.is_relative_to(root) for root in forbidden):
            blocked_attempts.append(str(path))
            raise RuntimeError('Installed release attempted to read a forbidden source checkout')
    if event=='import' and values[0].split('.')[0] in ('torch','transformers','legal_pruning'):
        raise RuntimeError('Offline release attempted a model or historical-package import')


sys.addaudithook(audit)
import legal_repro
from legal_repro import expert_review,expert_agreement,review_bundle
from legal_repro.build_figures import build
from legal_repro.planning import plan
from legal_repro.verification import verify
from legal_repro.io import write_new

package=Path(legal_repro.__file__).resolve()
if not package.is_relative_to(Path(sys.prefix).resolve()):
    raise RuntimeError('Expected a wheel installed in this isolated environment')
root=args.output.resolve()
root.mkdir(parents=True,exist_ok=False)
verification=verify()
figure_receipt=build(root/'figures')
view=review_bundle.build(root/'viewer')
pair=expert_review.build(root/'pairwise',root/'pairwise-key',panel='pairwise')
four=expert_review.build(root/'four',root/'four-key',panel='four-contexts',seed_from=root/'pairwise-key/linkage.json')
dual=expert_agreement.build_study(root/'dual',root/'dual-key',root/'four-key/linkage.json')
receipt={'accepted':True,'kind':'isolated_installed_wheel_offline','python':sys.version.split()[0],
         'installed_package':str(package),'source_reads_blocked':True,'attempted_source_reads':blocked_attempts,
         'network_blocked':True,'live_model_requests':0,'verification':verification,
         'figures':{'plots':figure_receipt['plot_names'],'numerical_points':figure_receipt['numerical_points_verified'],
                    'ranking_segments':figure_receipt['ranking_segments_verified'],'csv_sha256':{k:v for k,v in figure_receipt['output_sha256'].items() if k.startswith('data/')}},
         'viewer':{'questions':view['questions'],'answers':view['answers']},
         'participant_zip_paths':[pair['send_this_zip'],four['send_this_zip'],*dual['annotator_zips'].values()],
         'human_judgments_created':0,'full_plan':plan('evaluate')['counts']}
write_new(root/'ACCEPTANCE.json',receipt)
print(json.dumps(receipt,indent=2))
