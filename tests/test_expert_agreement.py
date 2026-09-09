"""Two-reviewer completion gates and descriptive agreement; synthetic data only."""

import copy
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

import pytest

from legal_repro import expert_agreement as agreement
from legal_repro import expert_review as expert
from test_expert_review import ASSETS, SEED, html_for, payload, rank, responses


def two_keys(size=5):
    return {code: expert.make_study(payload(size), seed=SEED, sample_size=size,
                                   reviewer_code=code, panel="four-contexts", feedback_after_submit=True)[1]
            for code in agreement.REVIEWERS}


def final_return(key):
    value = responses(key["packet"])
    for record in value["judgments"]:
        rank(record, dict.fromkeys(expert.LETTERS, 1))
    value["finalized_at"] = "2026-09-09T00:00:00Z"
    value["revision"] = 11
    return {"format": "legal-expert-return-v2", "packet": key["packet"], "response": value,
            "agreement": agreement.participant_summary(key, value)}


def organizer_html(keys):
    data = {"reviewers": {code: {field: key[field] for field in ("packet", "tasks", "source_bindings")}
                          for code, key in keys.items()}}
    return expert.evidence.render_html(data, (ASSETS / "organizer.html").read_text(),
        (ASSETS / "styles.css").read_text(), (ASSETS / "agreement.js").read_text() + "\n" + (ASSETS / "organizer.js").read_text())


def test_two_reviewers_same_sample_new_identities_and_valid_feedback():
    keys = two_keys(100)
    a, b = keys.values()
    assert a["packet"]["question_count"] == b["packet"]["question_count"] == 100
    assert a["packet"]["study_id"] != b["packet"]["study_id"]
    assert [(t["question"],t["gold"]) for t in a["packet"]["tasks"]] == [(t["question"],t["gold"]) for t in b["packet"]["tasks"]]
    assert len([1 for ta,tb in zip(a["packet"]["tasks"],b["packet"]["tasks"]) if ta["answers"] != tb["answers"]]) > 80
    original, _ = expert.make_study(payload(100), seed=SEED, sample_size=100, reviewer_code="annotator_1", panel="four-contexts")
    assert original["study_id"] != a["packet"]["study_id"]
    for key in keys.values():
        expert.validate_packet(key["packet"])
        assert key["packet"]["schema_version"] == 2
        assert len(key["packet"]["completion_feedback"]) == 100
        html = html_for(key["packet"])
        for secret in (SEED, *expert.SELECTED, "source-question:", "generation:", "oracle_bgb_paragraph_ids", "no_context"):
            assert secret not in html
        assert "completion_feedback" in html  # Honest offline UI gate, not encryption.
        expert.link_responses(key, final_return(key))


def test_hand_computed_agreement_and_denominators():
    left = {"A":1,"B":2,"C":3,"D":4}
    same = {"left":left,"right":left,"focus_pair":["A","B"]}
    reverse = {"left":left,"right":{"A":4,"B":3,"C":2,"D":1},"focus_pair":["A","B"]}
    result = agreement.summarize([same, reverse], 3)
    assert result["compared_questions"] == 2 and result["excluded_questions"] == 1
    assert result["focus_exact_agreement"] == .5
    assert result["focus_preference_reversal_rate"] == .5
    assert result["complete_ranking_agreement"] == .5
    assert result["all_pairwise_agreement"] == .5
    assert result["focus_linear_weighted_kappa"] == 0
    assert result["right_minus_left_favourable_pp"] == -50
    assert agreement.summarize([same],1)["focus_linear_weighted_kappa"] is None
    empty = agreement.summarize([],5)
    assert empty["compared_questions"] == 0 and empty["excluded_questions"] == 5
    assert empty["focus_exact_agreement"] is None
    assert empty["all_pairwise_agreement"] is None


def test_final_returns_are_self_contained_and_join_exact_answers():
    keys = two_keys()
    returned = {code: final_return(key) for code,key in keys.items()}
    # A cached client-side summary is untrusted and must never drive the analysis.
    returned["annotator_1"]["agreement"] = {"invented": 999}
    result = agreement.join_study(keys, returned)
    assert result["question_count"] == 5
    assert len(result["cases"]) == 5
    assert result["agreement"]["annotator_1_vs_annotator_2"]["focus_exact_agreement"] == 1
    for case in result["cases"]:
        assert case["question"] and case["gold"]
        assert set(case["answers"]) == set(agreement.CONDITIONS)
        assert all(answer["text"] and answer["generation_id"] for answer in case["answers"].values())
        assert set(case["reviewers"]) == set(agreement.REVIEWERS)


@pytest.mark.parametrize("error", ["wrong_packet", "unfinished", "wrong_person", "missing_record", "empty_final_time", "feedback_mapping"])
def test_bad_returns_and_feedback_rejected(error):
    keys = two_keys()
    value = final_return(keys["annotator_1"])
    if error == "wrong_packet":
        value = copy.deepcopy(value)
        value["packet"]["tasks"][0]["answers"]["A"] = "Changed answer"
    if error == "unfinished": value["response"]["judgments"][0].update(status="draft", rank_groups=None)
    if error == "wrong_person": value["response"]["reviewer_code"] = "annotator_2"
    if error == "missing_record": value["response"]["judgments"].pop()
    if error == "empty_final_time": value["response"]["finalized_at"] = " "
    if error == "feedback_mapping":
        packet = keys["annotator_1"]["packet"]
        next(iter(packet["completion_feedback"].values()))["focus_pair"].reverse()
        packet["packet_sha256"] = expert.sha({k:v for k,v in packet.items() if k != "packet_sha256"})
        value["response"]["packet_sha256"] = packet["packet_sha256"]
    with pytest.raises(ValueError):
        expert.link_responses(keys["annotator_1"], value)


def test_no_summary_for_drafts_and_no_partial_combined_study():
    keys = two_keys()
    with pytest.raises(ValueError, match="final submission"):
        agreement.participant_summary(keys["annotator_1"], responses(keys["annotator_1"]["packet"]))
    with pytest.raises(ValueError, match="Two different"):
        agreement.join_study(keys, {"annotator_1":final_return(keys["annotator_1"])})


def test_completion_and_organizer_browser_roundtrip():
    keys = two_keys()
    inputs = {"participants": {code:html_for(key["packet"]) for code,key in keys.items()}, "organizer":organizer_html(keys)}
    result = subprocess.run(["node", str(Path(__file__).parent / "expert_completion_dom.cjs")],
                            input=json.dumps(inputs), text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "passed"
    expected = agreement.join_study(keys, report["returns"])
    for comparison, values in expected["agreement"].items():
        for metric, value in values.items():
            actual = report["combined"]["agreement"][comparison][metric]
            assert actual == pytest.approx(value) if isinstance(value, float) else actual == value
    assert report["combined"]["cases"][0]["answers"] == expected["cases"][0]["answers"]
    assert report["combined"]["question_count"] == 5


def test_two_zip_builder_and_private_organizer(monkeypatch, tmp_path):
    monkeypatch.setattr(expert.evidence, "WORKSPACE", tmp_path)
    monkeypatch.setattr(expert.evidence, "load_payload", lambda:payload(5))
    monkeypatch.chdir(tmp_path)
    shutil.copytree(ASSETS, tmp_path / "ui/expert")
    expert.build(tmp_path / "review/original", tmp_path / "review/original_key", sample_size=5, panel="four-contexts")
    original = (tmp_path / "review/original.zip").read_bytes()
    root, private = tmp_path / "review/dual", tmp_path / "review/dual_analyst"
    result = agreement.build_study(root, private, tmp_path / "review/original_key/linkage.json", sample_size=5)
    assert private.stat().st_mode & 0o777 == 0o700
    assert result["human_judgments"] == 0
    for code, path in result["annotator_zips"].items():
        key = expert.load_private(private / code)
        assert key["packet"]["reviewer_code"] == code
        with zipfile.ZipFile(path) as z:
            assert z.namelist() == ["index.html", "START_HERE.txt"]
            assert z.testzip() is None
            assert key["private_seed"].encode() not in z.read("index.html")
    with zipfile.ZipFile(result["organizer_zip_do_not_send"]) as z:
        assert z.namelist() == ["index.html", "START_HERE.txt"]
        assert z.testzip() is None
    assert (tmp_path / "review/original.zip").read_bytes() == original
    with pytest.raises(PermissionError):
        agreement.build_study(root, private, tmp_path / "review/original_key/linkage.json", sample_size=5)
