"""Portable expert app: sampling, blinding, exact joins and response safety."""

import base64
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

import pytest

from legal_repro import expert_review as expert


ASSETS = expert.evidence.WORKSPACE / "ui/expert"
SEED = "1a" * 32


def payload(size=5):
    """Synthetic evidence; not expert judgments or actual experimental results."""
    rows = []
    for n in range(size):
        row = {"id": f"source-question:{n:04d}", "cluster": f"cluster-{n // 2}",
               "question": f"Frage {n}: Was gilt?", "gold": f"Referenz {n}: Es besteht ein Anspruch.",
               "conditions": {}, "rankings": {}}
        for i, condition in enumerate(("raw", *expert.SELECTED, "oracle_bgb_paragraph_ids", "no_context")):
            answer = f"Antworttext {n}/{i}: Es kommt auf die Voraussetzungen an."
            row["conditions"][condition] = {
                "answer": answer, "answer_sha256": expert.evidence.digest(answer.encode()),
                "generation_id": f"generation:{n}:{condition}", "compression": None,
                "scores": [{"replicate": rep, "dimensions": dict.fromkeys(expert.evidence.METRICS, .9 if rep == 1 else .7),
                            "reasons": dict.fromkeys(expert.evidence.METRICS, "Testbegründung.")} for rep in (1, 2)],
            }
        for i, condition in enumerate(expert.SELECTED):
            groups = [
                [["raw", "matching_compressed"], ["oracle_bgb_paragraph_ids"], ["no_context"]],
                [["matching_compressed"], ["raw"], ["oracle_bgb_paragraph_ids", "no_context"]],
                [["raw"], ["matching_compressed"], ["oracle_bgb_paragraph_ids", "no_context"]],
            ][i]
            row["rankings"][condition] = {"task_id": f"rank:{n}:{condition}", "groups": groups,
                "midranks": expert.evidence.midranks(groups), "explanation": "Synthetic LLM judgment.",
                "reasons": dict.fromkeys(expert.evidence.ROLES, "Test."), "blind_labels": {}}
        rows.append(row)
    return {"rows": rows, "meta": {"bindings": {"verified_source": {"sha256": "0" * 64}}, "models": {"score": "test-judge"}}}


def study(size=5, **kwargs):
    return expert.make_study(payload(size), seed=SEED, sample_size=size, **kwargs)


def responses(packet):
    value = {"schema_version": packet["schema_version"], "study_id": packet["study_id"], "packet_sha256": packet["packet_sha256"],
            "reviewer_code": packet["reviewer_code"], "revision": 0, "exported_at": "2026-09-07T00:00:00Z",
            "judgments": [{"task_id": t["task_id"], "status": "draft", "positions": dict.fromkeys(expert.answer_labels(packet)),
                "rank_groups": None, "notes": "", "reference_issue": False, "material_difference": "",
                "cannot_assess": False, "updated_at": ""} for t in packet["tasks"]]}
    if packet["schema_version"] == 2:
        value["finalized_at"] = None
    return value


def rank(record, positions=None):
    letters = tuple(record["positions"])
    record.update(status="ranked", positions=positions or dict(zip(letters, (1, 1, 2, 4) if len(letters) == 4 else (1, 2))),
                  cannot_assess=False)
    record["rank_groups"] = expert.groups_from_positions(record["positions"], letters)


def html_for(packet):
    files = ("pairwise.html", "pairwise.css", "pairwise.js") if len(expert.answer_labels(packet)) == 2 else ("index.html", "styles.css", "app.js")
    template, css, js = ((ASSETS / name).read_text() for name in files)
    if packet["schema_version"] == 2:
        js = (ASSETS / "agreement.js").read_text() + "\n" + js
    return expert.evidence.render_html(packet, template, css, js)


def test_sample_is_uniform_reproducible_and_independent_of_quality():
    data = payload(526)
    packet, key = expert.make_study(data, seed=SEED)
    assert packet["question_count"] == packet["task_count"] == 100
    assert len({t["row_id"] for t in key["tasks"].values()}) == 100
    assert len({tuple(t["blind_to_condition"].values()) for t in key["tasks"].values()}) > 15
    changed = copy.deepcopy(data)
    changed["rows"].reverse()
    for row in changed["rows"]:
        for answer in row["conditions"].values():
            answer["scores"] = []
        row["rankings"] = dict.fromkeys(expert.SELECTED, {"irrelevant": "different scores and ranks"})
    again, _ = expert.make_study(changed, seed=SEED)
    assert packet == again
    other, other_key = expert.make_study(data, seed="2b" * 32)
    assert set(t["row_id"] for t in other_key["tasks"].values()) != set(t["row_id"] for t in key["tasks"].values())
    assert other["study_id"] != packet["study_id"]
    other_reviewer, other_key = expert.make_study(data, seed=SEED, reviewer_code="expert02")
    assert [t["row_id"] for t in other_key["tasks"].values()] == [t["row_id"] for t in key["tasks"].values()]
    assert other_reviewer["study_id"] != packet["study_id"]
    assert [t["answers"] for t in other_reviewer["tasks"]] != [t["answers"] for t in packet["tasks"]]


@pytest.mark.parametrize("panel,task_count", [("selected", 100), ("llm-matched", 300), ("four-contexts", 100)])
def test_blinding_and_exact_answer_panel(panel, task_count):
    packet, private = study(100, panel=panel)
    assert packet["task_count"] == task_count
    serialized = html_for(packet)
    for forbidden in (SEED, *expert.SELECTED, "source-question:", "generation:", "rank:", "test-judge", "pointwise"):
        assert forbidden not in serialized
    for task in packet["tasks"]:
        key = private["tasks"][task["task_id"]]
        conditions = set(key["blind_to_condition"].values())
        expected = {"raw", *expert.SELECTED} if panel == "selected" else {"raw", "oracle_bgb_paragraph_ids", "no_context", *key["llm_rankings"]}
        assert conditions == expected
        for label in expert.LETTERS:
            assert expert.evidence.digest(task["answers"][label].encode()) == key["answers"][label]["answer_sha256"]
    assert not any(r["same_candidate_set_as_llm"] for r in private["tasks"].values()) if panel == "selected" else all(r["same_candidate_set_as_llm"] for r in private["tasks"].values())


@pytest.mark.parametrize("positions,groups,midranks", [
    ([1, 1, 1, 1], [["A", "B", "C", "D"]], [2.5] * 4),
    ([1, 1, 2, 4], [["A", "B"], ["C"], ["D"]], [1.5, 1.5, 3, 4]),
    ([2, 1, 4, 2], [["B"], ["A", "D"], ["C"]], [2.5, 1, 4, 2.5]),
])
def test_tie_semantics(positions, groups, midranks):
    actual = expert.groups_from_positions(dict(zip(expert.LETTERS, positions)))
    assert actual == groups
    actual_ranks = expert.occupied_midranks(actual)
    assert [actual_ranks[l] for l in expert.LETTERS] == midranks
    assert sum(actual_ranks.values()) == 10


@pytest.mark.parametrize("positions", [[2, 2, 3, 4], [1, 2, 3, None], [1, 2, 3, True], [1, 2, 3, 5], [1, 2, 3, 1.0]])
def test_invalid_ranks_rejected(positions):
    with pytest.raises(ValueError):
        expert.groups_from_positions(dict(zip(expert.LETTERS, positions)))


@pytest.mark.parametrize("corruption", ["study", "reviewer", "fingerprint", "missing", "duplicate", "extra_task", "extra_field",
    "revision", "bool_rank", "incomplete", "no_rank_one", "bad_groups", "ungraded_groups", "flag", "empty_abstention", "contradictory_abstention"])
def test_responses_fail_closed(corruption):
    packet, _ = study()
    value = responses(packet)
    r = value["judgments"][0]
    rank(r)
    if corruption == "study": value["study_id"] = "wrong"
    if corruption == "reviewer": value["reviewer_code"] = "wrong"
    if corruption == "fingerprint": value["packet_sha256"] = "wrong"
    if corruption == "missing": value["judgments"].pop()
    if corruption == "duplicate": value["judgments"].append(copy.deepcopy(r))
    if corruption == "extra_task": r["task_id"] = "task-wrong"
    if corruption == "extra_field": r["method"] = "raw"
    if corruption == "revision": value["revision"] = True
    if corruption == "bool_rank": r["positions"]["A"] = True
    if corruption == "incomplete": r["positions"]["D"] = None
    if corruption == "no_rank_one": r["positions"] = dict.fromkeys(expert.LETTERS, 2)
    if corruption == "bad_groups": r["rank_groups"] = [["A"], ["B", "C", "D"]]
    if corruption == "ungraded_groups": r["status"] = "draft"
    if corruption == "flag": r["reference_issue"] = 1
    if corruption == "empty_abstention": r.update(status="ungradable", rank_groups=None, cannot_assess=True)
    if corruption == "contradictory_abstention": r["cannot_assess"] = True
    with pytest.raises(ValueError):
        expert.validate_responses(value, packet)


@pytest.mark.parametrize("panel", ["selected", "llm-matched", "four-contexts"])
def test_link_preserves_identity_and_excludes_abstentions_and_drafts(panel):
    packet, key = study(panel=panel)
    value = responses(packet)
    r = value["judgments"][0]
    rank(r)
    r["notes"] = "=SUM(A1:A3)"
    value["judgments"][1].update(status="ungradable", cannot_assess=True, notes="Test: nicht beurteilbar.")
    result = expert.link_responses(key, value)
    assert result["counts"] == {"ranked": 1, "ungradable": 1, "draft": packet["task_count"] - 2}
    assert len(result["raw_relative_comparisons"]) == (5 if panel == "four-contexts" else 15)
    assert sum(result["cases"][0]["expert_condition_midranks"].values()) == 10
    for pair in result["raw_relative_comparisons"]:
        assert pair["same_candidate_set_as_llm"] is (panel in expert.MATCHED_PANELS)
        if pair["expert_status"] != "ranked":
            assert pair["expert_relation_to_raw"] is None and pair["relation_agreement"] is None
        label = next(l for l, c in key["tasks"][pair["task_id"]]["blind_to_condition"].items() if c == pair["candidate_id"])
        answer = key["tasks"][pair["task_id"]]["answers"][label]
        assert pair["generation_id"] == answer["generation_id"]
        assert pair["answer_sha256"] == answer["answer_sha256"]
        assert pair["llm_outcome_correctness"] == .9  # Never averages primary and repeat.
        assert pair["llm_relation_to_raw"] == dict(zip(expert.SELECTED, ("tie", "better", "worse")))[pair["candidate_id"]]
    assert expert.csv_safe(r["notes"]) == "'=SUM(A1:A3)"


@pytest.mark.parametrize("corruption", ["missing_answer", "wrong_hash", "wrong_condition", "missing_comparison", "wrong_llm_ranks", "wrong_panel"])
def test_link_rejects_changed_key(corruption):
    packet, key = study()
    entry = next(iter(key["tasks"].values()))
    if corruption == "missing_answer": entry["answers"].pop("A")
    if corruption == "wrong_hash": entry["answers"]["A"]["answer_sha256"] = "wrong"
    if corruption == "wrong_condition": entry["answers"]["A"]["condition_id"] = "wrong"
    if corruption == "missing_comparison": entry["llm_rankings"].pop(expert.SELECTED[0])
    if corruption == "wrong_llm_ranks": entry["llm_rankings"][expert.SELECTED[0]]["midranks"]["raw"] = 9
    if corruption == "wrong_panel": entry["same_candidate_set_as_llm"] = True
    with pytest.raises(ValueError):
        expert.link_responses(key, responses(packet))


@pytest.mark.parametrize("panel", ["pairwise", "four-contexts"])
def test_builder_and_zip_separate_secrets_and_refuse_overwrite(monkeypatch, tmp_path, panel):
    monkeypatch.setattr(expert.evidence, "WORKSPACE", tmp_path)
    monkeypatch.setattr(expert.evidence, "load_payload", lambda: payload(12))
    monkeypatch.chdir(tmp_path)
    shutil.copytree(ASSETS, tmp_path / "ui/expert")
    public, private = tmp_path / "review/participant", tmp_path / "review/analyst"
    result = expert.build(public, private, sample_size=10, panel=panel)
    archive_path = Path(result["send_this_zip"])
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.namelist() == ["index.html", "START_HERE.txt"]
        assert archive.testzip() is None
        assert archive.read("index.html") == (public / "index.html").read_bytes()
        assert archive.read("START_HERE.txt") == (public / "START_HERE.txt").read_bytes()
    key = expert.load_private(private)
    assert key["private_seed"] not in (public / "index.html").read_text()
    assert private.stat().st_mode & 0o777 == 0o700
    assert (private / "linkage.json").stat().st_mode & 0o777 == 0o600
    receipt = json.loads((private / "verification.json").read_bytes())
    assert receipt["files"]["participant.zip"]["sha256"] == expert.evidence.digest(archive_path.read_bytes())
    assert receipt["initial_human_judgments"] == 0
    again = expert.build(tmp_path / "review/replica", tmp_path / "review/replica_key", sample_size=10,
                         seed_from=private / "linkage.json", panel=panel)
    assert Path(again["send_this_zip"]).read_bytes() == archive_path.read_bytes()
    with pytest.raises(PermissionError):
        expert.build(public, tmp_path / "review/new_key", sample_size=10)
    with pytest.raises(ValueError, match="linkage.json"):
        expert.build(tmp_path / "review/new_packet", tmp_path / "review/new_key", sample_size=10,
                     seed_from=private / "not_the_key.json")
    returned = tmp_path / "synthetic-return.json"
    fake = responses(key["packet"])
    rank(fake["judgments"][0])
    returned.write_bytes(expert.canonical(fake))
    destination = tmp_path / "review/linked"
    joined = expert.link(private, returned, destination)
    assert joined["counts"]["ranked"] == 1
    assert (destination / "raw_relative_comparisons.csv").exists()
    with pytest.raises(PermissionError):
        expert.link(private, returned, destination)
    (private / "linkage.json").write_text("corrupted test key")
    with pytest.raises(ValueError, match="evidence changed"):
        expert.load_private(private)


def test_builder_refuses_nested_existing_zip_and_outside_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(expert.evidence, "WORKSPACE", tmp_path)
    monkeypatch.setattr(expert.evidence, "load_payload", lambda: pytest.fail("Must refuse before loading sources"))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="non-nested"):
        expert.build(tmp_path / "review/public", tmp_path / "review/public/key")
    from legal_repro.paths import ASSETS as packaged
    for path in (packaged / "results/fresh", packaged / "review"):
        with pytest.raises(PermissionError):
            expert.build(path, tmp_path / "review/key")
    (tmp_path / "review").mkdir()
    (tmp_path / "review/public.zip").write_bytes(b"protected archive")
    with pytest.raises(PermissionError):
        expert.build(tmp_path / "review/public", tmp_path / "review/key")
    assert (tmp_path / "review/public.zip").read_bytes() == b"protected archive"


def test_offline_csp_and_data_injection():
    packet, _ = study()
    attack = '</script><script>window.PWNED=true</script>__REVIEW_JS__<&'
    packet["tasks"][0]["gold"] = attack
    html = html_for(packet)
    assert html.count("<script") == 2
    assert "<script>window.PWNED" not in html
    assert "connect-src 'none'" in html
    for name in ("styles.css", "app.js"):
        data = (ASSETS / name).read_bytes()
        assert "'sha256-" + base64.b64encode(hashlib.sha256(data).digest()).decode() + "'" in html
    assert "fetch(" not in html and "XMLHttpRequest" not in html


@pytest.mark.parametrize("panel", ["selected", "four-contexts"])
def test_portable_browser_workflow_and_python_roundtrip(panel):
    packet, key = study(panel=panel)
    packet["tasks"][0]["gold"] = '</script><script>window.PWNED=true</script><&__REVIEW_JS__'
    packet["packet_sha256"] = expert.sha({k: v for k, v in packet.items() if k != "packet_sha256"})
    runner = Path(__file__).parent / "expert_review_dom.cjs"
    result = subprocess.run(["node", str(runner)], input=html_for(packet), text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "passed"
    joined = expert.link_responses(key, report["synthetic_export"])
    assert joined["counts"] == {"ranked": 2, "ungradable": 1, "draft": 2}


def test_pairwise_preserves_sample_and_only_includes_requested_method():
    original, original_key = study(100)
    packet, key = study(100, panel="pairwise")
    assert packet["task_count"] == packet["question_count"] == 100
    assert packet["study_id"] != original["study_id"]
    assert [t["row_id"] for t in key["tasks"].values()] == [t["row_id"] for t in original_key["tasks"].values()]
    # Canonical JSON sorts private dictionary keys. Question order belongs to
    # the public task list, never to incidental private-dictionary iteration.
    roundtrip = json.loads(expert.canonical(key))
    previous_roundtrip = json.loads(expert.canonical(original_key))
    def row_order(private):
        return [private["tasks"][task["task_id"]]["row_id"] for task in private["packet"]["tasks"]]
    assert row_order(roundtrip) == row_order(previous_roundtrip)
    assert key["protocol"]["selected_settings"] == [expert.PRIMARY_CANDIDATE]
    assert {tuple(t["blind_to_condition"].values()) for t in key["tasks"].values()} == {
        ("raw", expert.PRIMARY_CANDIDATE), (expert.PRIMARY_CANDIDATE, "raw")}
    for task in packet["tasks"]:
        assert set(task["answers"]) == {"A", "B"}
        entry = key["tasks"][task["task_id"]]
        assert set(entry["llm_rankings"]) == {expert.PRIMARY_CANDIDATE}
        assert entry["same_candidate_set_as_llm"] is False
    serialized = html_for(packet)
    for secret in (*expert.SELECTED, SEED, "source-question:", "generation:", "test-judge"):
        assert secret not in serialized
    assert "connect-src 'none'" in serialized
    assert "fetch(" not in serialized and "XMLHttpRequest" not in serialized


@pytest.mark.parametrize("positions,expected", [({"A":1,"B":2}, {"A":1,"B":2}),
    ({"A":2,"B":1}, {"A":2,"B":1}), ({"A":1,"B":1}, {"A":1.5,"B":1.5})])
def test_pairwise_midranks_and_exact_llm_link(positions, expected):
    packet, key = study(panel="pairwise")
    returned = responses(packet)
    rank(returned["judgments"][0], positions)
    assert expert.occupied_midranks(returned["judgments"][0]["rank_groups"], expert.PAIR_LETTERS) == expected
    linked = expert.link_responses(key, returned)
    assert linked["counts"] == {"ranked":1,"draft":4,"ungradable":0}
    assert len(linked["raw_relative_comparisons"]) == 5
    pair = linked["raw_relative_comparisons"][0]
    mapping = next(iter(key["tasks"].values()))["blind_to_condition"]
    candidate = next(label for label, condition in mapping.items() if condition == expert.PRIMARY_CANDIDATE)
    raw = next(label for label, condition in mapping.items() if condition == "raw")
    assert pair["expert_relation_to_raw"] == expert.compare_relation(expected[candidate], expected[raw])
    assert pair["candidate_id"] == expert.PRIMARY_CANDIDATE
    assert pair["llm_relation_to_raw"] == "tie" and pair["same_candidate_set_as_llm"] is False
    assert sum(linked["cases"][0]["expert_condition_midranks"].values()) == 3


def test_two_answer_packet_rejects_old_four_answer_responses_and_bad_counts():
    packet, key = study(panel="pairwise")
    old_packet, _ = study()
    with pytest.raises(ValueError, match="does not match"):
        expert.link_responses(key, responses(old_packet))
    value = responses(packet)
    value["judgments"][0]["positions"] = {"A":1,"B":2,"C":3,"D":4}
    with pytest.raises(ValueError, match="rank selections"):
        expert.validate_responses(value, packet)
    changed = copy.deepcopy(packet)
    changed["tasks"][1]["answers"]["C"] = "Not part of this panel"
    changed["packet_sha256"] = expert.sha({k:v for k,v in changed.items() if k != "packet_sha256"})
    with pytest.raises(ValueError, match="answer count"):
        expert.validate_packet(changed)


def test_simple_browser_autosave_and_python_roundtrip():
    packet, key = study(panel="pairwise")
    packet["tasks"][0]["gold"] += '</script><script>window.PWNED=true</script><&__REVIEW_JS__'
    packet["packet_sha256"] = expert.sha({k:v for k,v in packet.items() if k != "packet_sha256"})
    runner = Path(__file__).parent / "expert_pairwise_dom.cjs"
    result = subprocess.run(["node", str(runner)], input=html_for(packet), text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "passed"
    joined = expert.link_responses(key, report["synthetic_export"])
    assert joined["counts"] == {"ranked":2,"ungradable":1,"draft":2}
    assert len(joined["raw_relative_comparisons"]) == 5


def test_four_contexts_preserves_questions_and_matches_the_exact_llm_panel():
    simple, simple_key = study(100, panel="pairwise")
    packet, key = study(100, panel="four-contexts")
    assert packet["question_count"] == packet["task_count"] == 100
    assert simple["study_id"] != packet["study_id"]
    assert {t["task_id"] for t in simple["tasks"]}.isdisjoint(t["task_id"] for t in packet["tasks"])
    def row_order(private):
        return [private["tasks"][t["task_id"]]["row_id"] for t in private["packet"]["tasks"]]
    assert row_order(json.loads(expert.canonical(key))) == row_order(json.loads(expert.canonical(simple_key)))
    assert [(t["question"], t["gold"]) for t in packet["tasks"]] == [(t["question"], t["gold"]) for t in simple["tasks"]]
    assert key["protocol"]["selected_settings"] == [expert.PRIMARY_CANDIDATE]
    expected = {"raw", expert.PRIMARY_CANDIDATE, "oracle_bgb_paragraph_ids", "no_context"}
    assert {c for t in key["tasks"].values() for c in t["blind_to_condition"].values()} == expected
    assert len({tuple(t["blind_to_condition"].values()) for t in key["tasks"].values()}) > 15
    returned = responses(packet)
    for record in returned["judgments"]:
        entry = key["tasks"][record["task_id"]]
        assert set(entry["llm_rankings"]) == {expert.PRIMARY_CANDIDATE}
        assert entry["same_candidate_set_as_llm"] is True
        llm = entry["llm_rankings"][expert.PRIMARY_CANDIDATE]
        # Synthetic human response copied from fixture ranks only to test linkage.
        positions = {label: next(i + 1 for i, group in enumerate(llm["groups"])
                                if ("matching_compressed" if condition == expert.PRIMARY_CANDIDATE else condition) in group)
                     for label, condition in entry["blind_to_condition"].items()}
        rank(record, positions)
    linked = expert.link_responses(key, returned)
    assert linked["counts"] == {"ranked":100,"draft":0,"ungradable":0}
    assert len(linked["raw_relative_comparisons"]) == 100
    assert all(pair["same_candidate_set_as_llm"] and pair["relation_agreement"] for pair in linked["raw_relative_comparisons"])
    for case in linked["cases"]:
        llm = case["llm_rankings"][expert.PRIMARY_CANDIDATE]["midranks"]
        assert case["expert_condition_midranks"] == {
            expert.PRIMARY_CANDIDATE if role == "matching_compressed" else role: value for role, value in llm.items()}
    with pytest.raises(ValueError, match="does not match"):
        expert.link_responses(key, responses(simple))
    old_four, _ = study(100, panel="selected")
    with pytest.raises(ValueError, match="does not match"):
        expert.link_responses(key, responses(old_four))


def test_four_contexts_rejects_substitution_of_another_compression_setting():
    packet, key = study(panel="four-contexts")
    entry = key["tasks"][packet["tasks"][0]["task_id"]]
    entry["llm_rankings"][expert.SELECTED[1]] = entry["llm_rankings"].pop(expert.PRIMARY_CANDIDATE)
    with pytest.raises(ValueError, match="must use Legal LLMLingua-2"):
        expert.link_responses(key, responses(packet))
