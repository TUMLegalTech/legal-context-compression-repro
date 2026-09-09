import hashlib
import json
from pathlib import Path

import pytest

from legal_repro import bundle
from legal_repro.planning import messages, plan
from legal_repro.verification import verify


def test_full_reference_reconstruction_and_negative_compression_evidence():
    receipt=verify()
    assert receipt['accepted'] and receipt['score_means_recomputed']==54
    assert receipt['max_score_mean_error']<1e-12
    assert receipt['retained_rows_with_downstream_token_expansion']==24
    assert receipt['ranking_blocks_verified']==[128,398,526]
    assert receipt['live_model_requests']==0


def test_task_geometry_and_generation_answer_firewall(monkeypatch):
    monkeypatch.setattr(bundle,'references',lambda:pytest.fail('Generation planning must not open reference answers'))
    smoke=plan('smoke'); full=plan('evaluate')
    assert smoke['counts']=={'questions':2,'conditions':4,'generation':8,'score':8,'rank':2,'semantic_calls':18}
    assert full['counts']=={'questions':526,'conditions':18,'generation':9468,'score':10404,'rank':8679,'semantic_calls':28551}
    assert sum(r['pass_id']=='retest' for r in full['rank'])==789
    assert len({r['row_id'] for r in full['score'] if r['replicate']==2})==52
    assert {r['pass_id'] for r in full['score'] if r['replicate']==2}=={'reliability-score-2'}
    for task in smoke['generation']:
        assert not {'gold','answer','scores','rankings'} & set(task)
        rendered=messages('generation',task,smoke,{})
        assert len(rendered)==1 and rendered[0]['role']=='user'
        row=next(r for r in smoke['rows'] if r['id']==task['row_id'])
        assert row['gold'] not in rendered[0]['content']
        if task['candidate_id']=='no_context':
            assert '[KEIN KONTEXT BEREITGESTELLT]' in rendered[0]['content']
        if task['candidate_id']=='oracle_bgb_paragraph_ids':
            assert json.dumps(task['context'],ensure_ascii=False,separators=(',',':')) in rendered[0]['content']


def test_assets_reject_tampering_and_manifest_changes(monkeypatch,tmp_path):
    import shutil
    shutil.copytree(bundle.ASSETS,tmp_path/'assets')
    monkeypatch.setattr(bundle,'ASSETS',tmp_path/'assets')
    original=bundle.asset_bytes('prompts/qa_user.txt')
    (bundle.ASSETS/'prompts/qa_user.txt').write_bytes(original+b'changed')
    with pytest.raises(ValueError,match='asset changed'):
        bundle.asset_bytes('prompts/qa_user.txt')
    (bundle.ASSETS/'MANIFEST.json').write_text('{}')
    with pytest.raises(ValueError,match='manifest changed'):
        bundle.manifest()


def test_figures_are_portable_and_match_all_original_csv_bytes(monkeypatch,tmp_path):
    from legal_repro.build_figures import build
    monkeypatch.chdir(tmp_path)
    receipt=build(tmp_path/'fresh-figures')
    assert receipt['numerical_points_verified']==45
    assert receipt['ranking_segments_verified']==45
    expected={'score_values.csv':'3e44c473084e039a2938b0815345d858bce057b9b48ea233ab85879ab85c7ceb',
              'reference_values.csv':'49225deb53f10c012d75b59a75e4900a7bbb820bcc6d078327911ac348fc2053',
              'ranking_values.csv':'28b8ebb534ae1bd00f0f4dcae7910d5bea0b453d3d7ee3ea8a84f429f7d14bc5'}
    for name,digest in expected.items():
        assert hashlib.sha256((tmp_path/'fresh-figures/data'/name).read_bytes()).hexdigest()==digest
    for plot in receipt['plot_names']:
        for suffix in ('png','svg','pdf'):
            assert (tmp_path/'fresh-figures'/f'{plot}.{suffix}').stat().st_size>0
    with pytest.raises(PermissionError):
        build(tmp_path/'fresh-figures')


def test_statistics_preserve_question_weighting():
    from legal_repro.statistics import _inference
    result=_inference([1,1,-1],['a','a','b'],bootstrap_replicates=200,randomizations=200,seed=42)
    assert result['mean_difference']==pytest.approx(1/3)
    assert result['rows']==3 and result['clusters']==2


def test_review_build_works_outside_source_checkout(monkeypatch,tmp_path):
    from legal_repro import review_bundle
    from test_review_bundle import assembled
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(review_bundle,'load_payload',assembled)
    result=review_bundle.build(tmp_path/'portable-viewer')
    assert Path(result['output']).is_file()


def test_every_scheduled_rank_preserves_original_blind_map():
    planned=plan('evaluate')
    reference={r['id']:r for r in bundle.references()['rows']}
    for task in planned['rank']:
        original=reference[task['row_id']]['rankings'][task['candidate_id']]
        if task['pass_id']=='retest':
            original=original['retest']
        assert original['task_id']==task['id']
        assert original['blind_labels']==task['blind_to_condition']
