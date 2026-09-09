#!/usr/bin/env python3
"""One-time allowlisted export. Reads only the explicitly approved source inputs.

Run into a fresh scaffold; exclusive writes refuse a repeated export. The
release's normal commands never need the original checkout.
"""
from __future__ import annotations

import ast
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SOURCE = Path('/home/prioma/code/ma_contextcompression_minimal')
DESTINATION = Path(__file__).resolve().parents[1]
PACKAGE = DESTINATION / 'src/legal_repro'
ASSETS = PACKAGE / 'assets'
PARENT = SOURCE / 'results/legal-pruning-minimal-run-20260905T072343Z/report_evidence'
RANKING = SOURCE / 'results/legal-pruning-minimal-run-20260906T184613Z/report_evidence'
PAPER = SOURCE / 'paper/full526-20260907T041200Z'
source_files = {}
export_files = {}


def read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_relative_to(SOURCE) or '_prev' in path.parts:
        raise PermissionError(path)
    value = path.read_bytes()
    source_files[str(path.relative_to(SOURCE))] = {'sha256': hashlib.sha256(value).hexdigest(), 'bytes': len(value)}
    return value


def write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(value)
    export_files[str(path.relative_to(DESTINATION))] = {'sha256': hashlib.sha256(value).hexdigest(), 'bytes': len(value)}


def encode(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def copy(relative: str, destination: Path) -> None:
    write(destination, read(SOURCE / relative))


def records(path: Path) -> list[dict]:
    return [json.loads(line) for line in read(path).splitlines()]


def selected_functions(relative: str, names: tuple[str, ...]) -> str:
    text = read(SOURCE / relative).decode()
    nodes = {node.name: node for node in ast.parse(text).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    return '\n\n\n'.join(ast.get_source_segment(text, nodes[name]) for name in names) + '\n'


def main() -> None:
    if SOURCE.resolve() != SOURCE or DESTINATION == SOURCE:
        raise PermissionError('Unexpected source or destination')
    sys.path.insert(0, str(SOURCE / 'src'))
    from legal_pruning.review_bundle import load_payload
    payload = load_payload()  # verifies accepted seals, every answer join and ranking counts
    inputs, references = [], []
    answers = records(PARENT / 'evaluation/answer_matrix.jsonl')
    answer_by_key = {(r['row_id'],r['candidate_id']):r for r in answers}
    for row in payload['rows']:
        input_row = {k: row[k] for k in ('id','question','gold','cluster')}
        input_row['conditions'] = {}
        reference_row = {'id':row['id'], 'conditions':{}, 'rankings':row['rankings']}
        for name, condition in row['conditions'].items():
            original = answer_by_key[(row['id'], name)]
            # Keep paragraph lists as arrays, not doubly JSON-encoded UI strings.
            item = {k:condition[k] for k in ('context','context_kind','compression')}
            item.update({k:original[k] for k in ('generation_id','context_sha256','question_sha256','gold_sha256','source_lineage')})
            if item['context_kind'] == 'paragraphenliste':
                item['paragraph_ids'] = original['context']
            input_row['conditions'][name] = item
            reference_row['conditions'][name] = {k:v for k,v in condition.items() if k not in ('context','context_kind','compression')}
        inputs.append(input_row)
        references.append(reference_row)
    configuration = json.loads(read(PARENT / 'configs/campaign.json'))
    ranks = records(RANKING / 'evaluation/ranks_526.jsonl')
    retests = records(RANKING / 'evaluation/rank_retests_526.jsonl')
    original_ranks = records(PARENT / 'evaluation/ranks.jsonl')
    original_ids = sorted({r['row_id'] for r in original_ranks})
    def rank_binding(r):
        return {k:r[k] for k in ('row_id','candidate_id','pass_id','rank_task_id','blind_to_condition','seed')}
    sampling = {
        'original_ranking_rows':original_ids,
        'pointwise_reliability_rows':sorted({r['id'] for r in payload['rows'] if any(len(c['scores'])>1 for c in r['conditions'].values())}),
        'primary_rank_tasks':[rank_binding(r) for r in ranks],
        'repeat_rank_tasks':[rank_binding(r) for r in retests],
        'smoke_rows':['domainllm:validation:000474:84878348911a','domainllm:validation:000063:f0ffc4413305'],
        'smoke_selection':'Seed 42, two distinct contexts <=1024 source tokens with changed LLMLingua-2 r1.10; no score selection',
    }
    for name,value in (
        ('inputs.json.gz', {'schema_version':1,'rows':inputs,'contexts':payload['contexts'],'sampling':sampling,'meta':payload['meta']}),
        ('reference_results.json.gz', {'schema_version':1,'rows':references}),
    ):
        write(ASSETS / 'data' / name, gzip.compress(encode(value), mtime=0))
    for name in ('qa_user','score_developer','score_user','rank_developer','rank_user'):
        write(ASSETS/'prompts'/f'{name}.txt', read(PARENT/'prompts'/f'{name}.txt'))
    # Only scientific settings; no service, remote, live contract or cache paths.
    protocol = {key:configuration[key] for key in ('seed','source','ratios','generation','judge','statistics')}
    protocol['original_models'] = {k:configuration['models'][k] for k in ('generator','judge')}
    protocol['hosted_models'] = {
        'generator':{'model':'qwen/qwen3.5-9b','provider':'parasail/bf16','provider_name':'Parasail','quantization':'bf16','max_prompt_price':0.10,'max_completion_price':0.25},
        'judge':{'model':'mistralai/mistral-small-2603','provider':'mistral/zdr','provider_name':'Mistral','quantization':'unknown','max_prompt_price':0.15,'max_completion_price':0.60},
    }
    protocol['tokenizer'] = {'model':'Qwen/Qwen3.5-9B','revision':configuration['models']['generator']['revision'],'file':'tokenizer.json'}
    write(ASSETS/'protocol.json',encode(protocol))
    for name in ('MANIFEST.json','evidence/condition_means.csv','evidence/all_180_contrasts.csv','evidence/ranking_summary.json'):
        write(ASSETS/'paper'/name,read(PAPER/name))
    for p in sorted((SOURCE/'paper/figures/final').iterdir()):
        if p.is_file() and p.suffix in ('.pdf','.svg','.png','.json','.md'):
            write(DESTINATION/'figures'/p.name,read(p))
    for name in ('score_values.csv','reference_values.csv','ranking_values.csv'):
        copy('paper/figures/final/data/'+name,DESTINATION/'figures/data'/name)
    for name in ('expert100_simple.zip','expert100_four_answers.zip'):
        copy('review/'+name, DESTINATION/'participant_apps'/name)
    for folder,names in {
        'expert':('index.html','styles.css','app.js','pairwise.html','pairwise.css','pairwise.js','agreement.js','organizer.html','organizer.js','DUAL_STUDY.md'),
        'review':('index.html','styles.css','app.js'),
    }.items():
        for name in names: copy('ui/'+folder+'/'+name,ASSETS/'ui'/folder/name)
    for name in ('types','prompts','schemas','expert_review','expert_agreement','review_bundle'):
        copy('src/legal_pruning/'+name+'.py', PACKAGE/(name+'.py'))
    for name in ('figure_style','plot_score_dimensions','plot_rankings','build_figures'):
        copy('paper/'+name+'.py',PACKAGE/(name+'.py'))
    write(PACKAGE/'statistics.py', (
        '"""Unchanged paired context-cluster statistical kernels from the original study."""\n'
        'from __future__ import annotations\nfrom collections import defaultdict\nfrom typing import Any, Mapping, Sequence\nimport numpy as np\n'
        'ORACLE_CONDITION = "oracle_bgb_paragraph_ids"\nDIMENSIONS = ("outcome_correctness", "legal_reasoning_correctness", "legal_basis_correctness", "overall_score")\n\n'
        + selected_functions('src/legal_pruning/analysis.py', ('_holm','_cluster_totals','_inference','_contrasts'))
    ).encode())
    write(PACKAGE/'task_protocol.py', (
        '"""Unchanged deterministic rank-label and seed derivation."""\n'
        'import hashlib\nimport random\nfrom typing import Sequence\nORACLE_CONDITION = "oracle_bgb_paragraph_ids"\n\n'
        + selected_functions('src/legal_pruning/evaluation.py', ('rank_blind_map',))
        + '\n' + selected_functions('src/legal_pruning/generation.py', ('derived_seed','repeated_ngram_fraction'))
    ).encode())
    for name in ('test_expert_review.py','test_expert_agreement.py','test_review_bundle.py','expert_pairwise_dom.cjs','expert_review_dom.cjs','expert_completion_dom.cjs','review_ui_dom.cjs'):
        copy('tests/'+name,DESTINATION/'tests'/name)
    # Preserve receipt identities without copying active contracts or operational logs.
    for root,label in ((PARENT,'parent'),(RANKING,'ranking')):
        read(root/'terminal/TERMINAL.json')
    for relative,binding in payload['meta']['bindings'].items():
        if relative.startswith('paper/'):
            read(PAPER/relative.removeprefix('paper/'))
        elif relative.startswith('parent/'):
            read(PARENT/relative.removeprefix('parent/'))
        elif relative.startswith('ranking/'):
            read(RANKING/relative.removeprefix('ranking/'))
    manifest = {
        'schema_version':1, 'source_git_commit':subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip(),
        'source_is_uncommitted_worktree':True, 'source_files':source_files,
        'original_export_files_before_portability_changes':export_files,
        'accepted_bindings':payload['meta']['bindings'],
        'scope':'Frozen evaluation inputs and reference outputs; hosted generation and judging only',
    }
    write(ASSETS/'provenance.json',encode(manifest))
    print(json.dumps({'source_files':len(source_files),'export_files':len(export_files),'rows':len(inputs)}))


if __name__ == '__main__':
    main()
