"""Prepare blinded expert packets and link returned judgments, without services."""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import random
import re
import secrets
from datetime import datetime, timezone
import zipfile

from . import review_bundle as evidence


SELECTED = ("legal_llmlingua2-r1p1", "german_legal_selector_v2-r1p1", "legal_llmlingua2-r1p25")
PRIMARY_CANDIDATE = "legal_llmlingua2-r1p1"
LETTERS = ("A", "B", "C", "D")
PAIR_LETTERS = ("A", "B")
PANELS = ("pairwise", "selected", "llm-matched", "four-contexts")
MATCHED_PANELS = ("llm-matched", "four-contexts")
RECORD_FIELDS = {"task_id", "status", "positions", "rank_groups", "notes", "reference_issue",
                 "material_difference", "cannot_assess", "updated_at"}
EXPORT_FIELDS = {"schema_version", "study_id", "packet_sha256", "reviewer_code", "revision",
                 "exported_at", "judgments"}
NOTE_LIMIT = 10000


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def derive(seed: str, purpose: str) -> str:
    return hmac.new(bytes.fromhex(seed), purpose.encode(), hashlib.sha256).hexdigest()


def groups_from_positions(positions: dict, letters: tuple = LETTERS) -> list[list[str]]:
    if set(positions) != set(letters) or any(type(v) is not int or not 1 <= v <= len(letters) for v in positions.values()):
        raise ValueError("A completed ranking must assign every answer a valid rank")
    if min(positions.values()) != 1:
        raise ValueError("At least one answer must have rank 1")
    return [[label for label in letters if positions[label] == rank] for rank in sorted(set(positions.values()))]


def occupied_midranks(groups: list[list[str]], letters: tuple = LETTERS) -> dict[str, float]:
    if not groups or not all(isinstance(g, list) and g for g in groups):
        raise ValueError("Empty rank group")
    if sorted(label for group in groups for label in group) != sorted(letters):
        raise ValueError("Rank groups must contain every anonymous label exactly once")
    result, position = {}, 1
    for group in groups:
        for label in group:
            result[label] = position + (len(group) - 1) / 2
        position += len(group)
    return result


def make_study(payload: dict, *, seed: str, sample_size: int = 100,
               reviewer_code: str = "expert01", panel: str = "selected",
               feedback_after_submit: bool = False) -> tuple[dict, dict]:
    if not re.fullmatch(r"[0-9a-f]{64}", seed):
        raise ValueError("Use a 256-bit private hexadecimal seed")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", reviewer_code):
        raise ValueError("Reviewer code must be a short pseudonym, using letters, digits, _ or -")
    if panel not in PANELS:
        raise ValueError("Unknown panel")
    if feedback_after_submit and panel != "four-contexts":
        raise ValueError("Completion feedback requires the matched four-context panel")
    by_id = {row["id"]: row for row in payload["rows"]}
    if len(by_id) != len(payload["rows"]) or type(sample_size) is not int or not 1 <= sample_size <= len(by_id):
        raise ValueError("Invalid sample size or duplicate source questions")
    # No source score or ranking participates in sampling or permutations.
    sample_rng = random.Random(int(derive(seed, "question-sample-v1"), 16))
    selected_ids = sample_rng.sample(sorted(by_id), sample_size)
    order_rng = random.Random(int(derive(seed, "question-order-v1"), 16))
    order_rng.shuffle(selected_ids)
    source_bindings = payload["meta"].get("bindings", {})
    identity = f"expert-v1:{reviewer_code}:{sample_size}:{panel}:{sha(source_bindings)}"
    if feedback_after_submit:
        identity += ":completion-feedback-v2"
    study_id = "study-" + derive(seed, identity)[:24]
    public = {"schema_version": 1, "study_id": study_id, "reviewer_code": reviewer_code,
              "question_count": sample_size, "tasks": []}
    key_tasks = {}
    for row_id in selected_ids:
        row = by_id[row_id]
        if panel == "pairwise":
            panels = [("pairwise", ("raw", PRIMARY_CANDIDATE))]
        elif panel == "selected":
            panels = [("selected", ("raw", *SELECTED))]
        else:
            candidates = (PRIMARY_CANDIDATE,) if panel == "four-contexts" else SELECTED
            panels = [(candidate, ("raw", candidate, "oracle_bgb_paragraph_ids", "no_context")) for candidate in candidates]
        for panel_id, conditions in panels:
            ordered = list(conditions)
            # Reviewer-specific, per-question randomization; not one global label key.
            random.Random(int(derive(seed, f"answer-order-v1:{reviewer_code}:{row_id}:{panel_id}"), 16)).shuffle(ordered)
            mapping = dict(zip(PAIR_LETTERS if panel == "pairwise" else LETTERS, ordered))
            task_id = "task-" + derive(seed, f"task-v1:{identity}:{row_id}:{panel_id}")[:24]
            public["tasks"].append({"task_id": task_id, "question": row["question"], "gold": row["gold"],
                                    "answers": {label: row["conditions"][condition]["answer"] for label, condition in mapping.items()}})
            included = (PRIMARY_CANDIDATE,) if panel == "pairwise" else SELECTED if panel == "selected" else (panel_id,)
            key_tasks[task_id] = {
                "row_id": row_id, "context_cluster_id": row["cluster"], "blind_to_condition": mapping,
                "answers": {label: {"condition_id": condition, **{key: row["conditions"][condition][key]
                    for key in ("generation_id", "answer_sha256", "scores", "compression")}}
                    for label, condition in mapping.items()},
                "llm_rankings": {candidate: row["rankings"][candidate] for candidate in included},
                "same_candidate_set_as_llm": panel in MATCHED_PANELS,
            }
    if panel == "llm-matched":
        random.Random(int(derive(seed, "task-order-v1:" + reviewer_code), 16)).shuffle(public["tasks"])
    public["task_count"] = len(public["tasks"])
    if feedback_after_submit:
        public["schema_version"] = 2
        feedback = {}
        for task in public["tasks"]:
            entry = key_tasks[task["task_id"]]
            reverse = {condition: label for label, condition in entry["blind_to_condition"].items()}
            rank = entry["llm_rankings"][PRIMARY_CANDIDATE]
            feedback[task["task_id"]] = {
                "rank_groups": [[reverse[PRIMARY_CANDIDATE if role == "matching_compressed" else role]
                                 for role in group] for group in rank["groups"]],
                "focus_pair": [reverse[PRIMARY_CANDIDATE], reverse["raw"]],
            }
        public["completion_feedback"] = feedback
    public["packet_sha256"] = sha(public)
    private = {
        "schema_version": 1, "private_seed": seed, "packet": public, "tasks": key_tasks,
        "source_bindings": source_bindings, "models": payload["meta"].get("models", {}),
        "protocol": {"panel": panel, "selected_settings": [PRIMARY_CANDIDATE] if panel in ("pairwise", "four-contexts") else list(SELECTED),
                     "sampling": "uniform_questions_without_replacement_not_score_filtered",
                     "population_questions": len(by_id), "sampled_questions": sample_size,
                     "sampled_context_clusters": len({by_id[row_id]["cluster"] for row_id in selected_ids}),
                     "post_selection_expert_evaluation": True,
                     "default_comparison_limit": "Raw-relative relations are cross-panel unless same_candidate_set_as_llm is true"},
    }
    validate_packet(public)
    return public, private


def answer_labels(packet: dict) -> tuple[str, ...]:
    if not isinstance(packet.get("tasks"), list) or not packet["tasks"]:
        raise ValueError("Participant packet must contain tasks")
    labels = tuple(sorted(packet["tasks"][0]["answers"]))
    if labels not in (PAIR_LETTERS, LETTERS):
        raise ValueError("Expected two or four anonymous answers")
    return labels


def validate_packet(packet: dict) -> None:
    expected = {"schema_version", "study_id", "reviewer_code", "question_count", "task_count", "tasks", "packet_sha256"}
    if packet.get("schema_version") == 2:
        expected.add("completion_feedback")
    if set(packet) != expected or packet["schema_version"] not in (1, 2):
        raise ValueError("Participant packet has unexpected metadata")
    if sha({k: v for k, v in packet.items() if k != "packet_sha256"}) != packet["packet_sha256"]:
        raise ValueError("Participant packet fingerprint changed")
    letters = answer_labels(packet)
    ids = set()
    for task in packet["tasks"]:
        if set(task) != {"task_id", "question", "gold", "answers"} or set(task["answers"]) != set(letters):
            raise ValueError("Participant task leaks metadata or has the wrong answer count")
        if not re.fullmatch(r"task-[0-9a-f]{24}", task["task_id"]) or task["task_id"] in ids:
            raise ValueError("Invalid or duplicate opaque task ID")
        if any(not isinstance(text, str) or not text.strip() for text in (task["question"], task["gold"], *task["answers"].values())):
            raise ValueError("Empty participant text")
        ids.add(task["task_id"])
    if len(ids) != packet["task_count"]:
        raise ValueError("Participant task count changed")
    if packet["schema_version"] == 2:
        feedback = packet["completion_feedback"]
        if letters != LETTERS or not isinstance(feedback, dict) or set(feedback) != ids:
            raise ValueError("Completion feedback does not cover exactly the four-answer tasks")
        for item in feedback.values():
            if not isinstance(item, dict) or set(item) != {"rank_groups", "focus_pair"}:
                raise ValueError("Unexpected completion feedback metadata")
            occupied_midranks(item["rank_groups"])
            pair = item["focus_pair"]
            if not isinstance(pair, list) or len(pair) != 2 or len(set(pair)) != 2 or not set(pair).issubset(LETTERS):
                raise ValueError("Invalid focus comparison")


def unpack_response(value: dict, packet: dict) -> dict:
    """Accept self-contained v2 returns without trusting their cached summary."""
    if isinstance(value, dict) and value.get("format") == "legal-expert-return-v2":
        if set(value) != {"format", "packet", "response", "agreement"} or value["packet"] != packet:
            raise ValueError("Returned question/answer packet does not match the verified packet")
        return value["response"]
    return value


def validate_responses(value: dict, packet: dict) -> dict:
    value = unpack_response(value, packet)
    letters = answer_labels(packet)
    expected = EXPORT_FIELDS | ({"finalized_at"} if packet["schema_version"] == 2 else set())
    if not isinstance(value, dict) or set(value) != expected or value["schema_version"] != packet["schema_version"]:
        raise ValueError("Wrong response schema")
    if packet["schema_version"] == 2 and value["finalized_at"] is not None:
        if not isinstance(value["finalized_at"], str) or not value["finalized_at"].strip():
            raise ValueError("Invalid final submission timestamp")
    for key in ("study_id", "reviewer_code", "packet_sha256"):
        if value[key] != packet[key]:
            raise ValueError(f"Response {key} does not match this expert packet")
    if type(value["revision"]) is not int or value["revision"] < 0 or not isinstance(value["exported_at"], str):
        raise ValueError("Invalid response revision or export time")
    valid_ids = {task["task_id"] for task in packet["tasks"]}
    if not isinstance(value["judgments"], list):
        raise ValueError("Judgments must be a list")
    by_id = {}
    for record in value["judgments"]:
        if not isinstance(record, dict) or set(record) != RECORD_FIELDS:
            raise ValueError("Unexpected judgment fields")
        task_id = record["task_id"]
        if task_id not in valid_ids or task_id in by_id:
            raise ValueError("Unknown or duplicate judgment task")
        if (record["status"] not in ("draft", "ranked", "ungradable")
                or type(record["reference_issue"]) is not bool
                or type(record["cannot_assess"]) is not bool
                or record["material_difference"] not in ("", "yes", "no", "uncertain")
                or not isinstance(record["notes"], str) or len(record["notes"]) > NOTE_LIMIT
                or not isinstance(record["updated_at"], str)):
            raise ValueError("Invalid judgment disposition or notes")
        positions = record["positions"]
        if (not isinstance(positions, dict) or set(positions) != set(letters)
                or any(v is not None and (type(v) is not int or not 1 <= v <= len(letters)) for v in positions.values())):
            raise ValueError("Invalid anonymous rank selections")
        if record["status"] == "ranked":
            if record["cannot_assess"]:
                raise ValueError("An unassessable judgment cannot be ranked")
            groups = groups_from_positions(positions, letters)
            if record["rank_groups"] != groups:
                raise ValueError("Rank groups disagree with selected ranks")
        elif record["rank_groups"] is not None:
            raise ValueError("Incomplete or unassessable judgments cannot have ranks")
        if record["status"] == "ungradable" and (not record["cannot_assess"] or not record["notes"].strip()):
            raise ValueError("An unassessable judgment needs its disposition and a reason")
        by_id[task_id] = record
    if set(by_id) != valid_ids:
        raise ValueError("Response must preserve every task, including ungraded drafts")
    if value.get("finalized_at") and any(r["status"] == "draft" for r in by_id.values()):
        raise ValueError("Final submission cannot contain unfinished questions")
    return by_id


def compare_relation(a: float, b: float) -> str:
    return "better" if a < b else "worse" if a > b else "tie"


def link_responses(private: dict, responses: dict) -> dict:
    packet = private["packet"]
    validate_packet(packet)
    letters = answer_labels(packet)
    judgments = validate_responses(responses, packet)
    if set(private["tasks"]) != set(judgments):
        raise ValueError("Private key coverage does not match participant tasks")
    cases, pairs = [], []
    counts = {status: 0 for status in ("draft", "ranked", "ungradable")}
    for task in packet["tasks"]:
        task_id = task["task_id"]
        entry, judgment = private["tasks"][task_id], judgments[task_id]
        mapping = entry["blind_to_condition"]
        if set(mapping) != set(letters) or len(set(mapping.values())) != len(letters) or "raw" not in mapping.values():
            raise ValueError("Invalid private answer mapping")
        panel = private["protocol"]["panel"]
        candidates = set(entry["llm_rankings"])
        if (panel not in PANELS or set(entry["answers"]) != set(letters)
                or entry["same_candidate_set_as_llm"] is not (panel in MATCHED_PANELS)):
            raise ValueError("Private panel metadata changed")
        if panel == "pairwise":
            expected = {"raw", PRIMARY_CANDIDATE}
            if candidates != {PRIMARY_CANDIDATE}:
                raise ValueError("The pairwise panel must contain only Legal LLMLingua-2 at 1.10")
        elif panel == "selected":
            expected = {"raw", *SELECTED}
            if candidates != set(SELECTED):
                raise ValueError("Selected comparison coverage changed")
        else:
            if len(candidates) != 1 or not candidates.issubset(SELECTED):
                raise ValueError("Matched panel has the wrong comparison")
            if panel == "four-contexts" and candidates != {PRIMARY_CANDIDATE}:
                raise ValueError("The four-context panel must use Legal LLMLingua-2 at 1.10")
            expected = {"raw", "oracle_bgb_paragraph_ids", "no_context", *candidates}
        if set(mapping.values()) != expected:
            raise ValueError("Private panel contains unexpected conditions")
        if packet["schema_version"] == 2:
            feedback = packet["completion_feedback"][task_id]
            reverse = {condition: label for label, condition in mapping.items()}
            if feedback["focus_pair"] != [reverse[PRIMARY_CANDIDATE], reverse["raw"]]:
                raise ValueError("Completion feedback has the wrong focus comparison")
            reference = entry["llm_rankings"][PRIMARY_CANDIDATE]["midranks"]
            expected_ranks = {reverse[PRIMARY_CANDIDATE if role == "matching_compressed" else role]: rank
                              for role, rank in reference.items()}
            if occupied_midranks(feedback["rank_groups"]) != expected_ranks:
                raise ValueError("Completion feedback differs from the saved LLM judgment")
        for label, answer in entry["answers"].items():
            if answer["condition_id"] != mapping[label] or evidence.digest(task["answers"][label].encode()) != answer["answer_sha256"]:
                raise ValueError("Private key points to a different answer")
        counts[judgment["status"]] += 1
        human = ({mapping[label]: rank for label, rank in occupied_midranks(judgment["rank_groups"], letters).items()}
                 if judgment["status"] == "ranked" else {})
        cases.append({"task_id": task_id, "row_id": entry["row_id"], "context_cluster_id": entry["context_cluster_id"],
                      "expert_judgment": judgment, "expert_condition_midranks": human,
                      "expert_condition_rank_groups": [[mapping[label] for label in group] for group in judgment["rank_groups"]] if human else None,
                      "answer_links": entry["answers"], "llm_rankings": entry["llm_rankings"],
                      "same_candidate_set_as_llm": entry["same_candidate_set_as_llm"]})
        for candidate, rank in entry["llm_rankings"].items():
            if evidence.midranks(rank["groups"]) != rank["midranks"]:
                raise ValueError("LLM midranks disagree with saved rank groups")
            label = next(label for label, condition in mapping.items() if condition == candidate)
            answer = entry["answers"][label]
            scores = answer["scores"][0]
            if scores["replicate"] != 1:
                raise ValueError("Linked pointwise scores must use primary replicate 1")
            llm = compare_relation(rank["midranks"]["matching_compressed"], rank["midranks"]["raw"])
            expert = compare_relation(human[candidate], human["raw"]) if human else None
            pairs.append({"study_id": packet["study_id"], "reviewer_code": packet["reviewer_code"],
                          "task_id": task_id, "row_id": entry["row_id"], "context_cluster_id": entry["context_cluster_id"],
                          "candidate_id": candidate, "generation_id": answer["generation_id"], "answer_sha256": answer["answer_sha256"],
                          "llm_rank_task_id": rank["task_id"], "expert_status": judgment["status"],
                          "expert_relation_to_raw": expert, "llm_relation_to_raw": llm,
                          "relation_agreement": expert == llm if expert is not None else None,
                          "same_candidate_set_as_llm": entry["same_candidate_set_as_llm"],
                          **{"llm_" + key: scores["dimensions"][key] for key in evidence.METRICS},
                          "reference_issue": judgment["reference_issue"], "material_difference": judgment["material_difference"],
                          "expert_notes": judgment["notes"]})
    return {"schema_version": 1, "study_id": packet["study_id"], "reviewer_code": packet["reviewer_code"],
            "finalized_at": unpack_response(responses, packet).get("finalized_at"),
            "counts": counts, "cases": cases, "raw_relative_comparisons": pairs,
            "caution": "Raw-relative comparisons are cross-panel unless same_candidate_set_as_llm is true. Drafts and abstentions are not ties. No significance or human-validation claim is inferred."}


def fresh_path(path: Path) -> Path:
    from .paths import ASSETS
    absolute = path.expanduser().absolute()
    resolved = absolute.resolve()
    if resolved == ASSETS or resolved.is_relative_to(ASSETS) or absolute != resolved or path.exists():
        raise PermissionError("Use a fresh non-symlink path outside packaged resources")
    return resolved



def write_new(path: Path, data: bytes, *, mode: int = 0o644) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode), "wb") as handle:
        handle.write(data)


def load_private(root: Path) -> dict:
    root = root.resolve(strict=True)
    receipt = json.loads((root / "verification.json").read_bytes())
    private = json.loads(evidence.checked(root / "linkage.json", receipt["files"]["linkage.json"]))
    validate_packet(private["packet"])
    if private["packet"]["packet_sha256"] != receipt["packet_sha256"]:
        raise ValueError("Private receipt does not bind this packet")
    return private


def build(output: Path, private_output: Path, *, reviewer_code: str = "expert01", sample_size: int = 100,
          panel: str = "pairwise", seed_from: Path | None = None,
          feedback_after_submit: bool = False) -> dict:
    public_root, private_root = fresh_path(output), fresh_path(private_output)
    archive_path = fresh_path(public_root.with_name(public_root.name + ".zip"))
    if public_root == private_root or public_root.is_relative_to(private_root) or private_root.is_relative_to(public_root):
        raise ValueError("Participant and analyst directories must be separate and non-nested")
    if archive_path == private_root or private_root.is_relative_to(archive_path):
        raise ValueError("Participant ZIP and analyst directory must be separate")
    if seed_from is not None and seed_from.name != "linkage.json":
        raise ValueError("--seed-from must name the original private linkage.json")
    prior = load_private(seed_from.parent) if seed_from is not None else None
    seed = prior["private_seed"] if prior is not None else secrets.token_hex(32)
    packet, private = make_study(evidence.load_payload(), seed=seed, sample_size=sample_size,
                                 reviewer_code=reviewer_code, panel=panel, feedback_after_submit=feedback_after_submit)
    if prior is not None:
        if prior["source_bindings"] != private["source_bindings"]:
            raise ValueError("Seed reuse must refer to the same verified source evidence")
        same_sample = {t["row_id"] for t in prior["tasks"].values()} == {t["row_id"] for t in private["tasks"].values()}
        if prior["packet"]["question_count"] == sample_size and not same_sample:
            raise ValueError("The previously selected questions changed")
        private["derived_from"] = {"study_id": prior["packet"]["study_id"],
                                   "packet_sha256": prior["packet"]["packet_sha256"],
                                   "sample_rows_preserved": same_sample}
    source = evidence.WORKSPACE / "ui/expert"
    asset_files = dict(zip(("index.html", "styles.css", "app.js"),
                          ("pairwise.html", "pairwise.css", "pairwise.js") if panel == "pairwise"
                          else ("index.html", "styles.css", "app.js")))
    assets = {name: (source / filename).read_text() for name, filename in asset_files.items()}
    if feedback_after_submit:
        assets["agreement.js"] = (source / "agreement.js").read_text()
        asset_files["agreement.js"] = "agreement.js"
        assets["app.js"] = assets["agreement.js"] + "\n" + assets["app.js"]
    html = evidence.render_html(packet, assets["index.html"], assets["styles.css"], assets["app.js"]).encode()
    # Inspectable page source must not contain any condition key, seed or source ID.
    for forbidden in (*SELECTED, "oracle_bgb_paragraph_ids", "no_context", private["private_seed"],
                      *[entry["row_id"] for entry in private["tasks"].values()]):
        if forbidden.encode() in html:
            raise ValueError("Participant page leaks a private identifier")
    instructions = (
        "JURISTISCHE ANTWORTBEWERTUNG\n\n"
        "1. ZIP-Datei zuerst vollständig entpacken (z. B. Rechtsklick > Alle extrahieren).\n"
        "2. Die entpackte index.html mit einem aktuellen Desktop-Webbrowser öffnen.\n"
        "   Keine Installation, kein Konto und keine Internetverbindung nötig.\n"
        "3. Je Fall Frage und Referenz lesen und die vier Antworten nach rechtlicher Qualität ordnen.\n"
        "   1 = beste Antwort. Gleiche Rangzahlen bedeuten Gleichstand.\n"
        "   Die Referenz ist keine fünfte Antwort. Bei Zweifeln an ihr den Hinweis setzen und erläutern.\n"
        "4. Bewertungen ausdrücklich bestätigen. Nicht beurteilbare Fälle benötigen eine Begründung.\n"
        "   Jede Auswahl wird sofort als Entwurf gespeichert; erst das Bestätigen schließt den Fall ab.\n"
        "   Der Speicherstatus zeigt, ob die Speicherung im Browser überprüft wurde.\n"
        "5. Vor jeder Pause auf 'Ergebnisse / Sicherung herunterladen' klicken. Die JSON-Datei aufbewahren.\n"
        "   Zum Fortsetzen index.html öffnen und ggf. über 'Sicherung laden' die letzte JSON-Datei wählen.\n"
        "6. Am Ende nochmals herunterladen und diese neueste JSON-Datei an die Studienleitung senden.\n"
        "   Nicht die HTML- oder ZIP-Datei zurücksenden: Sie enthalten Ihre Bewertungen nicht!\n\n"
        "Bitte den Download im Download-Ordner kontrollieren. Es erfolgt keine automatische Übertragung.\n"
        "Browser-Speicherung allein ist keine sichere Abgabe. Verwenden Sie keine privaten/Inkognito-Fenster.\n"
        "Bei einem Speicherfehler vor dem Wechsel zu einem anderen Fall eine JSON-Sicherung herunterladen.\n"
        "Nutzen Sie dieses Paket nur für die zugewiesene Person und nicht gleichzeitig in mehreren Tabs.\n"
    ).encode()
    if panel == "pairwise":
        instructions = (
            "JURISTISCHE ANTWORTBEWERTUNG – KURZANLEITUNG\n\n"
            "1. ZIP entpacken und index.html in einem normalen Desktop-Browser öffnen.\n"
            "2. Frage und Referenz lesen, dann A besser, Gleichstand oder B besser wählen.\n"
            "   Jeder Klick wird sofort gespeichert; mit 'Weiter' zum nächsten Fall gehen.\n"
            "3. Im selben Browser und am selben Speicherort wird Ihr Fortschritt wieder geladen.\n"
            "   Vor jeder Pause 'Ergebnisse sichern' anklicken und die JSON-Datei aufbewahren.\n"
            "4. Bei Bedarf 'Sicherung laden' wählen, um mit Ihrer letzten JSON-Datei fortzusetzen.\n"
            "5. Am Ende 'Ergebnisse sichern' anklicken und diese neueste JSON-Datei zurücksenden.\n\n"
            "Kein Konto, keine Installation und keine Internetverbindung nötig.\n"
            "Die Referenz ist kein Kandidat. Gleichstand ist ausdrücklich erlaubt.\n"
            "Für nicht beurteilbare Fälle gibt es eine eigene Option mit kurzer Begründung.\n"
            "Achten Sie auf den Speicherstatus. Bei einem Speicherfehler wird 'Weiter' gesperrt,\n"
            "bis eine Sicherung heruntergeladen wurde. Keine privaten/Inkognito-Fenster nutzen.\n"
            "Nur einen Tab verwenden. Browserdaten nicht löschen. Kein automatischer Versand.\n"
            "Nicht die HTML- oder ZIP-Datei zurücksenden: Ihre Ergebnisse stehen in der JSON-Datei.\n"
        ).encode()
    if feedback_after_submit:
        instructions += (
            "\nABSCHLUSS UND ÜBEREINSTIMMUNG\n"
            "Bewerten Sie unabhängig und ausschließlich relativ zur Referenz. Keine externen Quellen.\n"
            "Gleichstand bedeutet rechtlich gleichwertig, nicht Unsicherheit. Kurze Begründungen sind hilfreich.\n"
            "Nach allen Fällen: 'Endgültig abschließen & Übersicht anzeigen' wählen.\n"
            "Die Bewertungen werden gesperrt; erst danach erscheint Ihr Vergleich mit dem LLM.\n"
            "Die automatisch heruntergeladene FINAL_…json enthält alle Fragen, Antworten und Bewertungen.\n"
            "Diese FINAL-Datei an die Studienleitung senden. Den Download bitte kontrollieren.\n"
            "Nicht mit der anderen Person austauschen, bevor beide endgültig abgeschlossen haben.\n"
            "Keine Quelltextansicht nutzen: Der Offline-Abschlussmechanismus ist keine Verschlüsselung.\n"
        ).encode()
    # Explicit allowlist: never zip a directory tree containing the analyst key.
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in (("index.html", html), ("START_HERE.txt", instructions)):
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content)
    archive_bytes = bundle.getvalue()
    key = canonical(private) + b"\n"
    receipt = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
               "packet_sha256": packet["packet_sha256"], "study_id": packet["study_id"],
               "question_count": packet["question_count"], "task_count": packet["task_count"],
               "files": {"linkage.json": {"sha256": evidence.digest(key), "bytes": len(key)},
                         "participant/index.html": {"sha256": evidence.digest(html), "bytes": len(html)},
                         "participant/START_HERE.txt": {"sha256": evidence.digest(instructions), "bytes": len(instructions)},
                         "participant.zip": {"sha256": evidence.digest(archive_bytes), "bytes": len(archive_bytes)}},
               "builder_sha256": evidence.digest(Path(__file__).read_bytes()),
               "asset_files": asset_files,
               "assets_sha256": {name: evidence.digest(text.encode()) for name, text in assets.items()},
               "source_bindings": private["source_bindings"], "initial_human_judgments": 0,
               "participant_contains_key_or_llm_grades": bool(feedback_after_submit),
               "contains_private_condition_key": False,
               "anonymous_llm_feedback_after_finalization": bool(feedback_after_submit),
               "offline_blinding_is_workflow_only": bool(feedback_after_submit)}
    # No output is written until evidence and blinding checks have passed.
    public_root.mkdir(parents=True, exist_ok=False)
    private_root.mkdir(parents=True, exist_ok=False, mode=0o700)
    write_new(public_root / "index.html", html)
    write_new(public_root / "START_HERE.txt", instructions)
    write_new(private_root / "linkage.json", key, mode=0o600)
    write_new(private_root / "verification.json", canonical(receipt) + b"\n", mode=0o600)
    write_new(archive_path, archive_bytes)
    return {"send_this_zip": str(archive_path), "zip_bytes": len(archive_bytes),
            "participant_ui": str(public_root / "index.html"), "private_analyst_root": str(private_root),
            "questions": packet["question_count"], "ranking_tasks": packet["task_count"],
            "sampled_context_clusters": private["protocol"]["sampled_context_clusters"],
            "panel": panel, "human_judgments": 0, "service_started": False}


def csv_safe(value: object) -> object:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def link(private_root: Path, responses: Path, output: Path) -> dict:
    destination = fresh_path(output)
    private = load_private(private_root)
    raw = responses.read_bytes()
    linked = link_responses(private, json.loads(raw))
    linked["returned_file_sha256"] = evidence.digest(raw)
    buffer = io.StringIO(newline="")
    pairs = linked["raw_relative_comparisons"]
    writer = csv.DictWriter(buffer, fieldnames=list(pairs[0]))
    writer.writeheader()
    writer.writerows({k: csv_safe(v) for k, v in row.items()} for row in pairs)
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    write_new(destination / "linked_judgments.json", canonical(linked) + b"\n", mode=0o600)
    write_new(destination / "raw_relative_comparisons.csv", buffer.getvalue().encode("utf-8-sig"), mode=0o600)
    return {"output": str(destination), "counts": linked["counts"], "comparison_rows": len(pairs)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("--output", type=Path, required=True)
    make.add_argument("--private-output", type=Path, required=True)
    make.add_argument("--reviewer-code", default="expert01")
    make.add_argument("--sample-size", type=int, default=100)
    make.add_argument("--panel", choices=PANELS, default="pairwise")
    make.add_argument("--feedback-after-submit", action="store_true")
    make.add_argument("--seed-from", type=Path, help="Prior private linkage.json; never pass a seed on a command line")
    join = commands.add_parser("link")
    join.add_argument("--private-root", type=Path, required=True)
    join.add_argument("--responses", type=Path, required=True)
    join.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = build(args.output, args.private_output, reviewer_code=args.reviewer_code,
                       sample_size=args.sample_size, panel=args.panel, seed_from=args.seed_from,
                       feedback_after_submit=args.feedback_after_submit)
    else:
        result = link(args.private_root, args.responses, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
