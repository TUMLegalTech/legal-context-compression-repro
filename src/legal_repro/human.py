"""Published human judgments, aligned to frozen answer text without private keys."""
from __future__ import annotations

import csv
import hashlib
from html import escape
import io
import json
from pathlib import Path

from . import bundle, expert_review as expert
from .expert_agreement import CONDITIONS, REVIEWERS, summarize
from .paths import fresh_directory

ASSET = 'human_evaluation/annotations.json'
FIELDS = {'status', 'positions', 'rank_groups', 'notes', 'reference_issue',
          'material_difference', 'cannot_assess'}
NAMES = {'raw': 'Uncompressed context', expert.PRIMARY_CANDIDATE: 'Legal LLMLingua-2 (1.10x)',
         'oracle_bgb_paragraph_ids': 'Paragraph IDs', 'no_context': 'No context'}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def match_answers(task, rows):
    """Fail closed on missing/ambiguous questions or answer-text matches."""
    matches = [row for row in rows if (row['question'], row['gold']) == (task['question'], task['gold'])]
    if len(matches) != 1:
        raise ValueError('Expected one exact question and Gold match')
    row = matches[0]
    mapping = {}
    for label, answer in task['answers'].items():
        candidates = [name for name in CONDITIONS if row['conditions'][name]['answer'] == answer]
        if len(candidates) != 1:
            raise ValueError('Expected one exact answer-text match within the four study conditions')
        mapping[label] = candidates[0]
    if set(mapping) != set(expert.LETTERS) or set(mapping.values()) != set(CONDITIONS):
        raise ValueError('The task does not cover each study condition exactly once')
    return row, mapping


def llm_ranks(row):
    ranks = row['rankings'][expert.PRIMARY_CANDIDATE]['midranks']
    return {expert.PRIMARY_CANDIDATE if name == 'matching_compressed' else name: rank
            for name, rank in ranks.items()}


def condition_ranks(judgment):
    if judgment['status'] != 'ranked':
        return None
    return {judgment['labels'][label]: rank
            for label, rank in expert.occupied_midranks(judgment['rank_groups']).items()}


def normalize_returns(returns, packets, payload):
    """Export only scientific response fields after checking the distributed packets."""
    if set(returns) != set(REVIEWERS) or set(packets) != set(REVIEWERS):
        raise ValueError('Both assigned annotator returns and packets are required')
    cases, provenance = {}, {}
    for code in REVIEWERS:
        raw, packet = returns[code], packets[code]
        expert.validate_packet(packet)
        judgments = expert.validate_responses(raw, packet)
        if packet['reviewer_code'] != code or not raw['response']['finalized_at']:
            raise ValueError('Expected the assigned annotator final submission')
        if packet['question_count'] != packet['task_count']:
            raise ValueError('Expected one four-answer task per question')
        provenance[code] = {'packet_sha256': packet['packet_sha256'], 'finalized': True}
        seen = set()
        for order, task in enumerate(packet['tasks'], 1):
            row, labels = match_answers(task, payload['rows'])
            if row['id'] in seen:
                raise ValueError('Duplicate study question')
            seen.add(row['id'])
            feedback = packet['completion_feedback'][task['task_id']]
            aligned = {labels[label]: rank for label, rank in expert.occupied_midranks(feedback['rank_groups']).items()}
            if aligned != llm_ranks(row) or [labels[k] for k in feedback['focus_pair']] != [expert.PRIMARY_CANDIDATE, 'raw']:
                raise ValueError('Distributed LLM feedback differs from frozen reference results')
            case = cases.setdefault(row['id'], {
                'row_id': row['id'], 'question_order': order,
                'answer_sha256': {name: row['conditions'][name]['answer_sha256'] for name in CONDITIONS},
                'reviewers': {},
            })
            if case['question_order'] != order:
                raise ValueError('Annotator question order differs')
            judgment = judgments[task['task_id']]
            case['reviewers'][code] = {'labels': labels, **{k: judgment[k] for k in sorted(FIELDS)}}
        if len(seen) != packet['question_count']:
            raise ValueError('Question count differs from the distributed packet')
    document = {'format': 'legal-repro-human-annotations-v1', 'conditions': list(CONDITIONS),
                'reviewers': list(REVIEWERS), 'source_returns': provenance, 'cases': list(cases.values())}
    result = analyze(document, payload)
    # Cached browser feedback is checked, never used as the analysis input.
    for code in REVIEWERS:
        computed, cached = result['agreement'][code + '_vs_llm'], returns[code]['agreement']
        if computed.keys() != cached.keys() or any(
            abs(computed[k] - cached[k]) > 1e-12 if isinstance(computed[k], float)
            else computed[k] != cached[k] for k in computed
        ):
            raise ValueError('Recomputed agreement differs from the final return')
    return document


def analyze(document=None, payload=None):
    document = json.loads(bundle.asset_bytes(ASSET)) if document is None else document
    payload = bundle.load_payload() if payload is None else payload
    if (set(document) != {'format', 'conditions', 'reviewers', 'source_returns', 'cases'}
            or document['format'] != 'legal-repro-human-annotations-v1'
            or document['conditions'] != list(CONDITIONS) or document['reviewers'] != list(REVIEWERS)
            or set(document['source_returns']) != set(REVIEWERS)):
        raise ValueError('Unexpected published annotation schema')
    for source in document['source_returns'].values():
        if (set(source) not in ({'packet_sha256', 'finalized'},
                               {'packet_sha256', 'finalized', 'return_sha256', 'return_bytes', 'zip_sha256'})
                or source['finalized'] is not True):
            raise ValueError('Unexpected annotation provenance')
    by_id = {row['id']: row for row in payload['rows']}
    cases, seen = [], set()
    counts = {code: {'ranked': 0, 'ungradable': 0, 'reference_issues': 0, 'with_notes': 0} for code in REVIEWERS}
    comparisons = {code + '_vs_llm': [] for code in REVIEWERS}
    comparisons['annotator_1_vs_annotator_2'] = []
    for order, source in enumerate(document['cases'], 1):
        if (set(source) != {'row_id', 'question_order', 'answer_sha256', 'reviewers'}
                or source['question_order'] != order or source['row_id'] in seen
                or source['row_id'] not in by_id or set(source['reviewers']) != set(REVIEWERS)):
            raise ValueError('Unexpected, missing or duplicate study question')
        seen.add(source['row_id'])
        row = by_id[source['row_id']]
        if source['answer_sha256'] != {name: row['conditions'][name]['answer_sha256'] for name in CONDITIONS}:
            raise ValueError('Published answer identities differ from the frozen reference')
        aligned = {}
        for code, judgment in source['reviewers'].items():
            if (set(judgment) != FIELDS | {'labels'} or set(judgment['labels']) != set(expert.LETTERS)
                    or set(judgment['labels'].values()) != set(CONDITIONS)
                    or judgment['status'] not in ('ranked', 'ungradable')):
                raise ValueError('Unexpected published judgment or label mapping')
            # Reuse the original study validation for selections, ties and abstentions.
            record = {k: judgment[k] for k in FIELDS}
            packet = {'schema_version': 2, 'study_id': 'published', 'reviewer_code': code,
                      'packet_sha256': 'published', 'tasks': [{'task_id': 'published', 'answers': dict.fromkeys(expert.LETTERS)}]}
            response = {'schema_version': 2, 'study_id': 'published', 'reviewer_code': code,
                        'packet_sha256': 'published', 'revision': 0, 'exported_at': '', 'finalized_at': 'published',
                        'judgments': [{**record, 'task_id': 'published', 'updated_at': ''}]}
            expert.validate_responses(response, packet)
            counts[code][judgment['status']] += 1
            counts[code]['reference_issues'] += judgment['reference_issue']
            counts[code]['with_notes'] += bool(judgment['notes'])
            ranks = condition_ranks(judgment)
            aligned[code] = {**judgment, 'condition_midranks': ranks}
            if ranks is not None:
                comparisons[code + '_vs_llm'].append({'left': ranks, 'right': llm_ranks(row),
                                                     'focus_pair': [expert.PRIMARY_CANDIDATE, 'raw']})
        left, right = (aligned[code]['condition_midranks'] for code in REVIEWERS)
        if left is not None and right is not None:
            comparisons['annotator_1_vs_annotator_2'].append({'left': left, 'right': right,
                                                           'focus_pair': [expert.PRIMARY_CANDIDATE, 'raw']})
        cases.append({**source, 'question': row['question'], 'gold': row['gold'], 'cluster': row['cluster'],
                      'answers': {name: row['conditions'][name]['answer'] for name in CONDITIONS},
                      'reviewers': aligned, 'llm_midranks': llm_ranks(row)})
    if not cases:
        raise ValueError('No published human judgments')
    return {'kind': 'published_human_evaluation', 'question_count': len(cases),
            'context_cluster_count': len({case['cluster'] for case in cases}), 'counts': counts,
            'agreement': {name: summarize(rows, len(cases)) for name, rows in comparisons.items()},
            'inference': 'Descriptive agreement; clustered uncertainty and equivalence are not established.',
            'live_model_requests': 0, 'cases': cases}


def report_files(result):
    summary = {key: value for key, value in result.items() if key != 'cases'}
    csv_rows, sections = [], []
    for case in result['cases']:
        cells = []
        for name in CONDITIONS:
            values = []
            for code in REVIEWERS:
                judgment = case['reviewers'][code]
                label = next(label for label, condition in judgment['labels'].items() if condition == name)
                rank = judgment['positions'][label] if judgment['status'] == 'ranked' else 'ungradable'
                values.append(f'{label}: {rank}')
            cells.append('<tr><th>' + escape(NAMES[name]) + '</th>'
                         + ''.join('<td>' + escape(str(v)) + '</td>' for v in [*values, case['llm_midranks'][name]]) + '</tr>')
        notes = []
        for code in REVIEWERS:
            judgment = case['reviewers'][code]
            csv_rows.append({'question_order': case['question_order'], 'row_id': case['row_id'], 'annotator': code,
                             'status': judgment['status'],
                             **{name: (judgment['condition_midranks'][name] if judgment['condition_midranks'] else '') for name in CONDITIONS},
                             'original_labels': json.dumps(judgment['labels'], ensure_ascii=False, sort_keys=True),
                             'original_positions': json.dumps(judgment['positions'], sort_keys=True),
                             'original_rank_groups': json.dumps(judgment['rank_groups']),
                             **{k: judgment[k] for k in ('notes', 'reference_issue', 'material_difference', 'cannot_assess')}})
            notes.append(f'<h3>{code}</h3><p>Status: {judgment["status"]}; reference issue: {judgment["reference_issue"]}; '
                         f'material difference: {escape(judgment["material_difference"]) or "unspecified"}</p>'
                         f'<p class="text">{escape(judgment["notes"]) or "No note."}</p>')
        answers = ''.join(f'<h3>{escape(NAMES[name])}</h3><div class="text">{escape(case["answers"][name])}</div>' for name in CONDITIONS)
        sections.append(f'<details id="q{case["question_order"]}"><summary>{case["question_order"]}. {escape(case["question"])}</summary>'
                        f'<p class="id">{escape(case["row_id"])}</p><h3>Gold reference answer</h3><div class="text">{escape(case["gold"])}</div>'
                        '<table><thead><tr><th>Answer condition</th><th>Annotator 1: label / entered rank</th>'
                        '<th>Annotator 2: label / entered rank</th><th>LLM midrank</th></tr></thead><tbody>'
                        + ''.join(cells) + '</tbody></table>' + ''.join(notes) + answers + '</details>')
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(csv_rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows({k: expert.csv_safe(v) for k, v in row.items()} for row in csv_rows)
    agreement_rows = ''.join('<tr><th>' + escape(name) + '</th>' + ''.join(
        '<td>' + escape(str(values[key]) if key == 'compared_questions' else f'{values[key]:.4f}' if values[key] is not None else 'undefined') + '</td>'
        for key in ('compared_questions', 'focus_exact_agreement', 'focus_linear_weighted_kappa', 'complete_ranking_agreement')) + '</tr>'
        for name, values in summary['agreement'].items())
    html = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            '<title>Published human evaluation</title><style>body{max-width:1000px;margin:40px auto;padding:0 20px;font:16px/1.6 system-ui;color:#18232b}'
            'table{width:100%;border-collapse:collapse;margin:20px 0}th,td{text-align:left;border-bottom:1px solid #ddd;padding:8px}'
            'details{border:1px solid #cbd5dc;border-radius:6px;margin:18px 0;padding:18px}summary{font-weight:600;cursor:pointer}'
            '.text{white-space:pre-wrap;overflow-wrap:anywhere}.id{font-family:monospace;font-size:12px}h3{margin-bottom:6px}</style>'
            f'<h1>Published human evaluation</h1><p>Two finalized annotator returns; {result["question_count"]} questions and four saved answers per question. '
            'Open a question to inspect both judgments, original letter assignments, notes and the answer texts. This page works offline.</p>'
            '<p>Original rank selections are preserved. Tied groups are converted to occupied midranks for analysis; '
            'ungradable cases remain visible and are excluded only from comparisons requiring that judgment. '
            'Notes refer to each annotator’s original A–D labels shown in the table.</p>'
            '<p>Focus comparison: Legal LLMLingua-2 (1.10x) versus uncompressed context. Agreement is descriptive.</p>'
            '<table><thead><tr><th>Comparison</th><th>Questions</th><th>Focus agreement</th><th>Weighted κ</th><th>Full ranking agreement</th>'
            '</tr></thead><tbody>' + agreement_rows + '</tbody></table>' + ''.join(sections) + '</html>\n')
    return {'summary.json': json_bytes(summary), 'judgments.csv': buffer.getvalue().encode(), 'index.html': html.encode()}


def build(output: Path):
    result = analyze()
    files = report_files(result)
    root = fresh_directory(output)
    for name, content in files.items():
        (root / name).write_bytes(content)
    return {'output': str(root), **{k: v for k, v in result.items() if k != 'cases'},
            'files': {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}
