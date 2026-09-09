"""CPU-only checks for the additive, offline full-526 evidence viewer."""

import copy
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from legal_repro import review_bundle as review


def fixture():
    answers, scores, ranks, repeats, compressions = [], [], [], [], []
    for row_number in range(2):
        row_id = f"question:{row_number}"
        cluster = str(row_number) * 64
        for condition in (*review.CONTROLS, *review.CANDIDATES):
            text = f"Answer {row_number} / {condition}"
            context = "[KEIN KONTEXT BEREITGESTELLT]" if condition == "no_context" else ["§ 631", "§ 242"] if condition == "oracle_bgb_paragraph_ids" else f"Context {condition}"
            context_kind = "kein_kontext" if condition == "no_context" else "paragraphenliste" if condition == "oracle_bgb_paragraph_ids" else "gesetzestext"
            generation = f"generation:{row_number}:{condition}"
            answers.append({
                "row_id": row_id, "candidate_id": condition, "condition_id": condition,
                "natural_eos": True, "answer": text, "answer_sha256": review.digest(text.encode()),
                "question": f"Question {row_number}?", "gold": "Reference answer", "context_cluster_id": cluster,
                "generation_id": generation, "context": context, "context_kind": context_kind, "answer_tokens": 10,
                "model_id": "generator", "model_revision": "pinned-generator",
            })
            scores.append({
                "row_id": row_id, "candidate_id": condition, "condition_id": condition,
                "replicate": 1, "generation_id": generation, "answer_sha256": review.digest(text.encode()),
                "context_cluster_id": cluster, "natural_eos": True,
                "dimensions": {key: value for key, value in zip(review.METRICS, (.8, .6, .4))},
                "justifications": {key: "Grade reason " + key for key in review.METRICS},
                "model_id": "judge", "model_revision": "pinned-judge",
            })
            if condition in review.CANDIDATES:
                compressions.append({
                    "context_id": "context:" + cluster[:32], "candidate_id": condition,
                    "requested_ratio": review.RATIOS[condition.rsplit("-", 1)[1]], "actual_ratio": 1.25,
                    "source_tokens": 100, "compressed_tokens": 80, "target_met": True,
                    "no_op": False, "no_op_reason": None, "compressed_sha256": review.digest(context.encode()),
                })
        for candidate in review.CANDIDATES:
            ranks.append({
                "row_id": row_id, "candidate_id": candidate, "pass_id": "primary", "natural_eos": True,
                "rank_task_id": f"rank:{row_number}:{candidate}",
                "rank_groups": [["raw", "matching_compressed"], ["oracle_bgb_paragraph_ids"], ["no_context"]],
                "blind_to_condition": dict(zip(("C01", "C02", "C03", "C04"), review.ROLES)),
                "blind_rank_groups": [["C01", "C02"], ["C03"], ["C04"]],
                "candidate_justifications": {role: "Ranking reason " + role for role in review.ROLES},
                "comparative_justification": "C01 and C02 are tied.",
                "model_id": "judge", "model_revision": "pinned-judge",
            })
    repeat = copy.deepcopy(scores[0])
    repeat["replicate"] = 2
    repeat["dimensions"] = {metric: 0.1 for metric in review.METRICS}
    scores.append(repeat)
    repeat = copy.deepcopy(ranks[0])
    repeat["pass_id"] = "retest"
    repeat["rank_task_id"] += ":repeat"
    repeat["rank_groups"] = [["matching_compressed"], ["raw"], ["no_context"], ["oracle_bgb_paragraph_ids"]]
    repeat["blind_rank_groups"] = [["C02"], ["C01"], ["C04"], ["C03"]]
    repeats.append(repeat)
    return answers, scores, ranks, repeats, compressions


def assembled():
    return review.assemble(*fixture(), expected_rows=2)


def test_complete_four_way_and_all_answer_geometry():
    data = assembled()
    assert data["meta"]["questions"] == 2
    assert data["meta"]["answers"] == data["meta"]["primary_scores"] == 36
    assert data["meta"]["primary_rankings"] == 30
    assert all(len(row["conditions"]) == 18 and len(row["rankings"]) == 15 for row in data["rows"])
    assert len(data["contexts"]) == 18  # Identical contexts are interned, not rewritten.


def test_primary_grades_and_rankings_do_not_average_repeats():
    data = assembled()
    row = data["rows"][0]
    assert row["conditions"]["raw"]["scores"][0]["dimensions"][review.METRICS[0]] == .8
    assert row["conditions"]["raw"]["scores"][1]["dimensions"][review.METRICS[0]] == .1
    primary = row["rankings"][review.CANDIDATES[0]]
    assert primary["midranks"]["matching_compressed"] == 1.5
    assert primary["retest"]["midranks"]["matching_compressed"] == 1
    assert data["meta"]["score_repeats"] == data["meta"]["ranking_repeats"] == 1


def test_id_list_and_empty_context_match_the_actual_prompt_renderer():
    inputs = fixture()
    for answer in inputs[0]:
        if answer["candidate_id"] == "no_context":
            answer["context"] = ""
    data = review.assemble(*inputs, expected_rows=2)
    row = data["rows"][0]
    assert data["contexts"][row["conditions"]["oracle_bgb_paragraph_ids"]["context"]] == '["§ 631","§ 242"]'
    assert data["contexts"][row["conditions"]["no_context"]["context"]] == "[KEIN KONTEXT BEREITGESTELLT]"


@pytest.mark.parametrize("groups,expected", [
    ([list(review.ROLES)], [2.5, 2.5, 2.5, 2.5]),
    ([["raw", "matching_compressed", "oracle_bgb_paragraph_ids"], ["no_context"]], [2, 2, 2, 4]),
    ([[role] for role in review.ROLES], [1, 2, 3, 4]),
])
def test_ties_share_positions_not_dense_group_numbers(groups, expected):
    ranks = review.midranks(groups)
    assert [ranks[role] for role in review.ROLES] == expected


@pytest.mark.parametrize("groups", [[], [[]], [["raw", "raw", "no_context", "matching_compressed"]]])
def test_rejects_incomplete_or_duplicate_rank_roles(groups):
    with pytest.raises(ValueError):
        review.midranks(groups)


@pytest.mark.parametrize("corruption,match", [
    ("score_join", "wrong answer"), ("score_hash", "answer identity"),
    ("score_duplicate", "Duplicate"), ("primary_missing", "primary score"),
    ("rank_missing", "ranking matrix"), ("rank_duplicate", "duplicate"),
    ("rank_repeat_duplicate", "Duplicate ranking repeat"),
    ("blind_mapping", "Anonymous ranking"), ("wrong_pass", "ranking pass"),
    ("answer_hash", "recorded hash"), ("question", "differs between conditions"),
    ("compression", "supplied answer context"), ("score_nan", "three-dimension"),
])
def test_fail_closed_on_scientifically_wrong_evidence(corruption, match):
    answers, scores, ranks, repeats, compressions = fixture()
    if corruption == "score_join": scores[0]["generation_id"] = scores[1]["generation_id"]
    if corruption == "score_hash": scores[0]["answer_sha256"] = "wrong"
    if corruption == "score_duplicate": scores.append(copy.deepcopy(scores[0]))
    if corruption == "primary_missing": scores.pop(0)
    if corruption == "rank_missing": ranks.pop()
    if corruption == "rank_duplicate": ranks.append(copy.deepcopy(ranks[0]))
    if corruption == "rank_repeat_duplicate": repeats.append(copy.deepcopy(repeats[0]))
    if corruption == "blind_mapping": ranks[0]["blind_rank_groups"] = [["C04"], ["C01", "C02"], ["C03"]]
    if corruption == "wrong_pass": ranks[0]["pass_id"] = "retest"
    if corruption == "answer_hash": answers[0]["answer"] += "changed"
    if corruption == "question": answers[1]["question"] += "changed"
    if corruption == "compression": compressions[0]["compressed_sha256"] = "wrong"
    if corruption == "score_nan": scores[0]["dimensions"][review.METRICS[0]] = float("nan")
    with pytest.raises(ValueError, match=match):
        review.assemble(answers, scores, ranks, repeats, compressions, expected_rows=2)


def test_hash_verification_rejects_changed_bytes(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_bytes(b'{"accepted":true}\n')
    assert review.checked(path, {"sha256": review.digest(path.read_bytes()), "bytes": path.stat().st_size})
    with pytest.raises(ValueError, match="evidence changed"):
        review.checked(path, {"sha256": "wrong"})


def test_html_embedding_cannot_execute_answer_text_or_replace_markers():
    data = assembled()
    attack = '</script><script>window.PWNED=true</script>__REVIEW_JS__<&'
    data["rows"][0]["gold"] = attack
    template = '<style>__REVIEW_CSS__</style><script id="review-data" type="application/json">__REVIEW_DATA__</script><script>__REVIEW_JS__</script>'
    html = review.render_html(data, template, "body{}", "window.REVIEW_STARTED=true;")
    assert html.count("<script") == 2
    assert "<script>window.PWNED" not in html
    encoded = html.split('type="application/json">', 1)[1].split("</script>", 1)[0]
    assert json.loads(encoded)["rows"][0]["gold"] == attack
    assert html.count("window.REVIEW_STARTED=true;") == 1


def test_builder_rejects_existing_or_out_of_scope_destinations(monkeypatch, tmp_path):
    monkeypatch.chdir(review.WORKSPACE)
    monkeypatch.setattr(review, "load_payload", lambda: pytest.fail("Must reject before reading evidence"))
    for path in [review.WORKSPACE / "review", review.WORKSPACE / "results/NEW", tmp_path]:
        with pytest.raises(PermissionError, match="fresh non-symlink"):
            review.build(path)


def test_existing_export_is_not_overwritten_or_read_as_input(monkeypatch, tmp_path):
    monkeypatch.setattr(review, "WORKSPACE", tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(review, "load_payload", lambda: pytest.fail("Existing export must be rejected first"))
    output = tmp_path / "review/existing"
    output.mkdir(parents=True)
    protected = output / "index.html"
    protected.write_text("previous export")
    with pytest.raises(PermissionError, match="fresh non-symlink"):
        review.build(output)
    assert protected.read_text() == "previous export"


def test_actual_template_has_no_external_resources_and_hashes_match():
    import base64
    source = review.WORKSPACE / "ui/review"
    css = (source / "styles.css").read_text()
    js = (source / "app.js").read_text()
    html = review.render_html(assembled(), (source / "index.html").read_text(), css, js)
    resources = []
    class Parser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if key in ("src", "href") and not value.startswith("#"):
                    resources.append((tag, key, value))
    Parser().feed(html)
    assert resources == []
    assert "connect-src 'none'" in html
    for content in (css, js):
        sha = base64.b64encode(hashlib.sha256(content.encode()).digest()).decode()
        assert f"'sha256-{sha}'" in html
    assert "fetch(" not in js and "XMLHttpRequest" not in js
