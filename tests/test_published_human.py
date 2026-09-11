"""Scientific release checks; synthetic joins are distinct from published returns."""
import copy
import json

import pytest

from legal_repro import bundle, expert_agreement, expert_review as expert, human
from test_expert_agreement import final_return
from test_expert_review import SEED, payload, rank


def fixture_returns():
    data = payload(3)
    keys = {code: expert.make_study(data, seed=SEED, sample_size=3, reviewer_code=code,
                                   panel='four-contexts', feedback_after_submit=True)[1]
            for code in expert_agreement.REVIEWERS}
    returns = {code: final_return(key) for code, key in keys.items()}
    desired = dict(zip(expert_agreement.CONDITIONS, (1, 1, 2, 3)))
    for code, key in keys.items():
        for record in returns[code]['response']['judgments']:
            labels = key['tasks'][record['task_id']]['blind_to_condition']
            rank(record, {label: desired[name] for label, name in labels.items()})
            record['notes'] = 'Synthetic note about answer A.'
    returns['annotator_2']['response']['judgments'][0].update(
        status='ungradable', rank_groups=None, cannot_assess=True, notes='Synthetic abstention.')
    for code in keys:
        returns[code]['agreement'] = expert_agreement.participant_summary(keys[code], returns[code])
    return data, keys, returns


def test_text_alignment_matches_independent_private_key_join_and_preserves_ties():
    data, keys, returns = fixture_returns()
    packets = {code: key['packet'] for code, key in keys.items()}
    document = human.normalize_returns(returns, packets, data)
    actual = human.analyze(document, data)
    expected = expert_agreement.join_study(keys, returns)
    assert actual['agreement'] == expected['agreement']
    assert actual['agreement']['annotator_1_vs_annotator_2']['compared_questions'] == 2
    assert actual['agreement']['annotator_1_vs_annotator_2']['complete_ranking_agreement'] == 1
    for case in actual['cases']:
        ranks = case['reviewers']['annotator_1']['condition_midranks']
        assert [ranks[name] for name in expert_agreement.CONDITIONS] == [1.5, 1.5, 3, 4]
        assert case['reviewers']['annotator_1']['notes'] == 'Synthetic note about answer A.'
    serialized = json.dumps(document)
    for private_field in ('private_seed', 'finalized_at', 'exported_at', 'updated_at', 'study_id', 'task_id'):
        assert private_field not in serialized


@pytest.mark.parametrize('corruption', ['missing_answer', 'ambiguous_answer', 'different_gold', 'duplicate_question'])
def test_export_rejects_nonunique_or_changed_answer_identity(corruption):
    data, keys, returns = fixture_returns()
    packets = {code: key['packet'] for code, key in keys.items()}
    row = data['rows'][0]
    if corruption == 'missing_answer':
        row['conditions']['raw']['answer'] = 'Changed answer'
    elif corruption == 'ambiguous_answer':
        row['conditions']['no_context']['answer'] = row['conditions']['raw']['answer']
    elif corruption == 'different_gold':
        row['gold'] = 'Changed reference'
    else:
        data['rows'].append(copy.deepcopy(row))
    with pytest.raises(ValueError, match='exact'):
        human.normalize_returns(returns, packets, data)


def test_export_rejects_mismatched_packet_and_unfinished_return():
    data, keys, returns = fixture_returns()
    packets = {code: key['packet'] for code, key in keys.items()}
    changed = copy.deepcopy(returns)
    changed['annotator_1']['packet']['tasks'][0]['question'] += ' changed'
    with pytest.raises(ValueError, match='packet'):
        human.normalize_returns(changed, packets, data)
    returns['annotator_1']['response']['finalized_at'] = None
    with pytest.raises(ValueError, match='final submission'):
        human.normalize_returns(returns, packets, data)


def test_published_coverage_and_no_imputation():
    result = human.analyze()
    assert result['question_count'] == 100
    assert [(result['counts'][code]['ranked'], result['counts'][code]['ungradable'])
            for code in expert_agreement.REVIEWERS] == [(99, 1), (97, 3)]
    paired = result['agreement']['annotator_1_vs_annotator_2']
    assert (paired['compared_questions'], paired['excluded_questions']) == (96, 4)
    assert len(result['cases']) == 100
    ungradable = [j for case in result['cases'] for j in case['reviewers'].values() if j['status'] == 'ungradable']
    assert len(ungradable) == 4
    assert all(j['condition_midranks'] is None and j['notes'] for j in ungradable)


def test_published_annotations_reject_unexpected_metadata():
    document = json.loads(bundle.asset_bytes(human.ASSET))
    document['cases'][0]['reviewers']['annotator_1']['email'] = 'synthetic@example.invalid'
    with pytest.raises(ValueError, match='Unexpected published judgment'):
        human.analyze(document)


def test_report_escapes_comments_and_preserves_ungradable_rows():
    import csv
    import io
    data, keys, returns = fixture_returns()
    note = '<script>alert("synthetic")</script>\n=1+1'
    returns['annotator_1']['response']['judgments'][0]['notes'] = note
    document = human.normalize_returns(returns, {code: key['packet'] for code, key in keys.items()}, data)
    files = human.report_files(human.analyze(document, data))
    page = files['index.html'].decode()
    assert '<script>' not in page and '&lt;script&gt;' in page
    rows = list(csv.DictReader(io.StringIO(files['judgments.csv'].decode())))
    assert len(rows) == 6
    abstention = next(row for row in rows if row['status'] == 'ungradable')
    assert all(abstention[name] == '' for name in expert_agreement.CONDITIONS)
    assert next(row for row in rows if row['notes'] == note)['annotator'] == 'annotator_1'
