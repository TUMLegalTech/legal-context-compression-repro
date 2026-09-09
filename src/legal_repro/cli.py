"""Small command surface for evidence, figures, offline apps and hosted runs."""
import argparse
import json
from pathlib import Path
import sys

from . import contracts
from .io import write_new


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    verify=commands.add_parser('verify',help='Recompute original figure statistics without models')
    verify.add_argument('--receipt',type=Path)
    figures=commands.add_parser('figures',help='Rebuild four original figures from verified evidence')
    figures.add_argument('--output',type=Path,required=True)
    review=commands.add_parser('review',help='Build the complete offline reference viewer')
    review.add_argument('--output',type=Path,required=True)
    for name in ('smoke','evaluate'):
        run=commands.add_parser(name,help='Hosted replication; requires an approved active contract')
        run.add_argument('--contract',type=Path)
        run.add_argument('--resume',action='store_true')
        run.add_argument('--dry-run',action='store_true',help='Count tasks without credentials, downloads, or requests')
    draft=commands.add_parser('contract',help='Create an inactive execution contract for review')
    draft.add_argument('--write',type=Path,required=True)
    draft.add_argument('--output-root',type=Path,required=True)
    draft.add_argument('--action',choices=('smoke','evaluate','publish'),default='smoke')
    draft.add_argument('--max-usd',type=float,default=1.0)
    draft.add_argument('--max-requests',type=int,default=64)
    draft.add_argument('--max-seconds',type=int)
    expert=commands.add_parser('expert',help='Build/link offline human studies')
    expert.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    try:
        if args.command=='verify':
            from .verification import verify
            result=verify()
            if args.receipt:
                args.receipt.parent.mkdir(parents=True,exist_ok=True)
                write_new(args.receipt,result)
        elif args.command=='figures':
            from .verification import verify
            from .build_figures import build
            verify()
            result=build(args.output)
        elif args.command=='review':
            from .verification import verify
            from .review_bundle import build
            verify()
            result=build(args.output)
        elif args.command in ('smoke','evaluate'):
            if args.dry_run:
                from .planning import plan
                result={'kind':'content_only_plan','live_model_requests':0,**plan(args.command)['counts']}
            else:
                if args.contract is None:
                    parser.error('--contract is required for API execution')
                from .runner import run
                result=run(args.contract,args.command,args.resume)
        elif args.command=='contract':
            result=contracts.draft(args.write,args.output_root,args.action,args.max_usd,args.max_requests,args.max_seconds)
        else:
            from . import expert_review,expert_agreement
            arguments=args.arguments
            if not arguments:
                parser.error('expert requires build, link, dual-build, or dual-join')
            target=expert_review
            if arguments[0] in ('dual-build','dual-join'):
                target=expert_agreement
                arguments=[arguments[0].removeprefix('dual-'),*arguments[1:]]
            original=sys.argv
            try:
                sys.argv=['legal-repro expert',*arguments]
                target.main()
            finally:
                sys.argv=original
            return
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,RuntimeError,PermissionError,FileExistsError,FileNotFoundError) as error:
        print(f'{type(error).__name__}: {error}',file=sys.stderr)
        raise SystemExit(2) from None
