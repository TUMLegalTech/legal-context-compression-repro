"""Prepare a two-reviewer offline study and join its self-contained final returns."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import zipfile

from . import expert_review as expert

REVIEWERS = ("annotator_1", "annotator_2")
CONDITIONS = ("raw", expert.PRIMARY_CANDIDATE, "oracle_bgb_paragraph_ids", "no_context")


def relation(a: float, b: float) -> int:
    return 0 if a > b else 1 if a == b else 2


def summarize(rows: list[dict], total: int) -> dict:
    """Question-weighted descriptive agreement; never treat six pairs as IID."""
    matrix = [[0] * 3 for _ in range(3)]
    full = pair_matches = 0
    for row in rows:
        left, right = row["left"], row["right"]
        names = sorted(left)
        target, baseline = row["focus_pair"]
        if len(names) != 4 or set(left) != set(right) or target == baseline or not {target, baseline}.issubset(names):
            raise ValueError("The comparison must align the same four answers")
        matrix[relation(left[target], left[baseline])][relation(right[target], right[baseline])] += 1
        matches = sum(relation(left[a], left[b]) == relation(right[a], right[b])
                      for i, a in enumerate(names) for b in names[i + 1:])
        pair_matches += matches
        full += matches == 6
    n = len(rows)
    if total < n:
        raise ValueError("Invalid question denominator")
    row_totals = list(map(sum, matrix))
    col_totals = [sum(row[j] for row in matrix) for j in range(3)]
    observed = sum((1 - abs(i-j)/2) * matrix[i][j] / n for i in range(3) for j in range(3)) if n else 0
    expected = sum((1 - abs(i-j)/2) * row_totals[i] * col_totals[j] / n**2 for i in range(3) for j in range(3)) if n else 0
    def ratio(value):
        return value / n if n else None
    return {
        "compared_questions": n, "excluded_questions": total - n, "focus_matrix": matrix,
        "focus_exact_agreement": ratio(sum(matrix[i][i] for i in range(3))),
        "focus_linear_weighted_kappa": (observed - expected) / (1 - expected) if n and abs(1 - expected) > 1e-12 else None,
        "focus_preference_reversal_rate": ratio(matrix[0][2] + matrix[2][0]),
        "left_favourable_rate": ratio(sum(row_totals[1:])), "right_favourable_rate": ratio(sum(col_totals[1:])),
        "right_minus_left_favourable_pp": 100 * (sum(col_totals[1:]) - sum(row_totals[1:])) / n if n else None,
        "complete_ranking_agreement": ratio(full), "all_pairwise_agreement": pair_matches / (6*n) if n else None,
    }


def participant_summary(private: dict, returned: dict) -> dict:
    linked = expert.link_responses(private, returned)
    if not linked["finalized_at"]:
        raise ValueError("Agreement feedback requires final submission")
    rows = []
    for case in linked["cases"]:
        if not case["expert_condition_midranks"]:
            continue
        reference = case["llm_rankings"][expert.PRIMARY_CANDIDATE]["midranks"]
        llm = {expert.PRIMARY_CANDIDATE if role == "matching_compressed" else role: rank for role, rank in reference.items()}
        rows.append({"left": case["expert_condition_midranks"], "right": llm,
                     "focus_pair": [expert.PRIMARY_CANDIDATE, "raw"]})
    return summarize(rows, private["packet"]["task_count"])


def join_study(keys: dict, returns: dict) -> dict:
    if set(keys) != set(REVIEWERS) or set(returns) != set(REVIEWERS):
        raise ValueError("Two different assigned reviewers are required")
    linked = {code: expert.link_responses(keys[code], returns[code]) for code in REVIEWERS}
    if any(not item["finalized_at"] for item in linked.values()):
        raise ValueError("Import final submissions, not unfinished backups")
    by_row = {code: {case["row_id"]: case for case in value["cases"]} for code, value in linked.items()}
    if (set(by_row[REVIEWERS[0]]) != set(by_row[REVIEWERS[1]])
            or keys[REVIEWERS[0]]["source_bindings"] != keys[REVIEWERS[1]]["source_bindings"]):
        raise ValueError("The reviewers did not assess the same source questions")
    cases, human_pairs = [], []
    public_tasks = {code: {t["task_id"]: t for t in key["packet"]["tasks"]} for code, key in keys.items()}
    for first in linked[REVIEWERS[0]]["cases"]:
        row_id = first["row_id"]
        left_task = public_tasks[REVIEWERS[0]][first["task_id"]]
        assembled = {"row_id": row_id, "context_cluster_id": first["context_cluster_id"],
                     "question": left_task["question"], "gold": left_task["gold"], "answers": {}, "reviewers": {},
                     "llm_ranking": first["llm_rankings"][expert.PRIMARY_CANDIDATE]}
        for code in REVIEWERS:
            case = by_row[code][row_id]
            task = public_tasks[code][case["task_id"]]
            if (task["question"], task["gold"], case["context_cluster_id"], case["llm_rankings"]) != (
                    left_task["question"], left_task["gold"], first["context_cluster_id"], first["llm_rankings"]):
                raise ValueError("Question, reference, context or LLM judgment changed between reviewers")
            for label, answer in case["answer_links"].items():
                item = {**answer, "text": task["answers"][label]}
                condition = answer["condition_id"]
                if condition in assembled["answers"] and assembled["answers"][condition] != item:
                    raise ValueError("The annotators saw different generated answers")
                assembled["answers"][condition] = item
            assembled["reviewers"][code] = case
        left, right = (assembled["reviewers"][code]["expert_condition_midranks"] for code in REVIEWERS)
        if left and right:
            human_pairs.append({"left": left, "right": right, "focus_pair": [expert.PRIMARY_CANDIDATE, "raw"]})
        cases.append(assembled)
    summaries = {code + "_vs_llm": participant_summary(keys[code], returns[code]) for code in REVIEWERS}
    summaries["annotator_1_vs_annotator_2"] = summarize(human_pairs, len(cases))
    return {"format": "legal-expert-combined-v1", "question_count": len(cases),
            "context_cluster_count": len({c["context_cluster_id"] for c in cases}),
            "agreement": summaries, "cases": cases, "submitted_returns": returns,
            "inference": "Descriptive only; clustered uncertainty and equivalence are not established."}


def zip_files(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in files.items():
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content)
    return buffer.getvalue()


def build_study(output: Path, private_output: Path, seed_from: Path, sample_size: int = 100) -> dict:
    public_root, private_root = expert.fresh_path(output), expert.fresh_path(private_output)
    if public_root == private_root or public_root.is_relative_to(private_root) or private_root.is_relative_to(public_root):
        raise ValueError("Participant and organizer roots must be separate")
    prior = expert.load_private(seed_from.parent)
    if seed_from.name != "linkage.json" or prior["packet"]["question_count"] != sample_size:
        raise ValueError("Use the private key of the existing same-size question sample")
    public_root.mkdir(parents=True, exist_ok=False)
    private_root.mkdir(parents=True, exist_ok=False, mode=0o700)
    packets, results = {}, {}
    for code in REVIEWERS:
        result = expert.build(public_root / code, private_root / code, reviewer_code=code,
                              sample_size=sample_size, panel="four-contexts", seed_from=seed_from,
                              feedback_after_submit=True)
        results[code] = result
        key = expert.load_private(private_root / code)
        packets[code] = {name: key[name] for name in ("packet", "tasks", "source_bindings")}
    asset_root = expert.evidence.WORKSPACE / "ui/expert"
    organizer_js = (asset_root / "agreement.js").read_text() + "\n" + (asset_root / "organizer.js").read_text()
    html = expert.evidence.render_html({"reviewers": packets}, (asset_root / "organizer.html").read_text(),
                                      (asset_root / "styles.css").read_text(), organizer_js).encode()
    instructions = (
        "NUR FÜR DIE STUDIENLEITUNG – NICHT AN ANNOTATOREN SENDEN\n\n"
        "Je Person nur die entsprechend benannte annotator_1.zip oder annotator_2.zip senden.\n"
        "Beide bearbeiten dieselben 100 Fragen unabhängig. Jeder liefert eine FINAL_…json zurück.\n"
        "Diese index.html öffnen und beide FINAL-Dateien auswählen. Die Übersicht zeigt\n"
        "Mensch–LLM, Mensch–Mensch und alle Fragen, Antworten, Rangfolgen und Anmerkungen.\n"
        "Über 'Gesamtdaten herunterladen' können Sie alles zusammen als JSON sichern.\n"
        "Originaldateien und private Schlüssel aufbewahren. Keine automatische Übertragung.\n"
    ).encode()
    expert.write_new(private_root / "index.html", html, mode=0o600)
    expert.write_new(private_root / "START_HERE.txt", instructions, mode=0o600)
    expert.write_new(private_root / "organizer.zip", zip_files({"index.html": html, "START_HERE.txt": instructions}), mode=0o600)
    expert.write_new(private_root / "DESIGN.md", (asset_root / "DUAL_STUDY.md").read_bytes(), mode=0o600)
    receipt = {"question_count": sample_size, "reviewers": results, "human_judgments": 0,
               "service_started": False, "organizer_html_sha256": expert.evidence.digest(html),
               "builder_sha256": expert.evidence.digest(Path(__file__).read_bytes()),
               "organizer_js_sha256": expert.evidence.digest(organizer_js.encode())}
    expert.write_new(private_root / "verification.json", expert.canonical(receipt) + b"\n", mode=0o600)
    return {"annotator_zips": {code: result["send_this_zip"] for code, result in results.items()},
            "organizer_zip_do_not_send": str(private_root / "organizer.zip"),
            "questions_per_annotator": sample_size, "human_judgments": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--private-output", type=Path, required=True)
    build.add_argument("--seed-from", type=Path, required=True)
    join = commands.add_parser("join")
    join.add_argument("--private-root", type=Path, required=True)
    join.add_argument("--annotator-1", type=Path, required=True)
    join.add_argument("--annotator-2", type=Path, required=True)
    join.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = build_study(args.output, args.private_output, args.seed_from)
    else:
        destination = expert.fresh_path(args.output)
        keys = {code: expert.load_private(args.private_root / code) for code in REVIEWERS}
        returns = {code: json.loads(path.read_bytes()) for code, path in zip(REVIEWERS, (args.annotator_1, args.annotator_2))}
        combined = join_study(keys, returns)
        destination.mkdir(parents=True, exist_ok=False, mode=0o700)
        expert.write_new(destination / "combined.json", expert.canonical(combined) + b"\n", mode=0o600)
        result = {"output": str(destination / "combined.json"), "agreement": combined["agreement"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
