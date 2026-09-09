"""Build an offline, read-only viewer from the accepted full-526 evidence.

Standard library only. No server, model imports, network calls or evidence writes.
The original 128-row viewer and all sealed artifacts remain untouched.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .prompts import render_qa


from .paths import ASSETS
WORKSPACE = ASSETS
METHODS = {
    "legal_llmlingua2": "Legal LLMLingua-2",
    "xprovence_six_probe_atoms": "XProvence",
    "multi_probe_bge": "Multi-probe BGE",
    "german_legal_selector_v2": "German legal selector",
    "dac_native_tokens": "DAC",
}
RATIOS = {"r1p1": 1.1, "r1p25": 1.25, "r2p0": 2.0}
CANDIDATES = tuple(f"{method}-{ratio}" for method in METHODS for ratio in RATIOS)
ROLES = ("raw", "matching_compressed", "oracle_bgb_paragraph_ids", "no_context")
CONTROLS = ("raw", "oracle_bgb_paragraph_ids", "no_context")
METRICS = ("outcome_correctness", "legal_reasoning_correctness", "legal_basis_correctness")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked(path: Path, binding: dict) -> bytes:
    if path.is_symlink() or "_prev" in path.parts:
        raise ValueError("Refusing a symlink or quarantined evidence input")
    data = path.read_bytes()
    if digest(data) != binding["sha256"] or len(data) != binding.get("bytes", len(data)):
        raise ValueError(f"Accepted evidence changed: {path.name}")
    return data


def records(data: bytes) -> Iterable[dict]:
    for number, line in enumerate(io.BytesIO(data), 1):
        if not line.strip():
            raise ValueError(f"Blank evidence record at line {number}")
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("Evidence records must be objects")
        yield row


def midranks(groups: list) -> dict[str, float]:
    if not groups or not all(isinstance(g, list) and g for g in groups):
        raise ValueError("Invalid rank groups")
    if sorted(role for group in groups for role in group) != sorted(ROLES):
        raise ValueError("Ranking must contain each of the four roles exactly once")
    result, position = {}, 1
    for group in groups:
        for role in group:
            result[role] = position + (len(group) - 1) / 2
        position += len(group)
    if sum(result.values()) != 10:
        raise ValueError("Four midranks must sum to ten")
    return result


def compact_rank(record: dict, expected_pass: str) -> dict:
    if record["pass_id"] != expected_pass or record["natural_eos"] is not True:
        raise ValueError("Wrong ranking pass or incomplete judgment")
    groups = record["rank_groups"]
    values = midranks(groups)
    mapping = record["blind_to_condition"]
    if sorted(mapping.values()) != sorted(ROLES):
        raise ValueError("Invalid anonymous-label mapping")
    translated = [[mapping[label] for label in group] for group in record["blind_rank_groups"]]
    if [sorted(g) for g in translated] != [sorted(g) for g in groups]:
        raise ValueError("Anonymous ranking disagrees with semantic ranking")
    if set(record["candidate_justifications"]) != set(ROLES):
        raise ValueError("Missing per-answer rank explanation")
    return {
        "task_id": record["rank_task_id"], "groups": groups, "midranks": values,
        "explanation": record["comparative_justification"],
        "reasons": record["candidate_justifications"], "blind_labels": mapping,
    }


def assemble(answers: Iterable[dict], scores: Iterable[dict], ranks: Iterable[dict],
             retests: Iterable[dict], compressions: Iterable[dict], *,
             candidates: tuple[str, ...] = CANDIDATES, expected_rows: int = 526) -> dict:
    """Join by exact row/condition/generation identities; never average repeats."""
    conditions = (*CONTROLS, *candidates)
    rows, generations, contexts, context_index = {}, {}, [], {}
    models = {"answer": set(), "score": set(), "rank": set()}
    compression_index = {}
    for record in compressions:
        key = (record["context_id"], record["candidate_id"])
        if key in compression_index:
            raise ValueError("Duplicate compression identity")
        compression_index[key] = {k: record[k] for k in (
            "requested_ratio", "actual_ratio", "source_tokens", "compressed_tokens",
            "target_met", "no_op", "no_op_reason", "compressed_sha256")}
    for answer in answers:
        row_id, candidate = answer["row_id"], answer["candidate_id"]
        if candidate not in conditions or answer["condition_id"] != candidate:
            raise ValueError("Unknown or mismatched answer condition")
        if answer["natural_eos"] is not True or not answer["answer"].strip():
            raise ValueError("Incomplete answer")
        if digest(answer["answer"].encode()) != answer["answer_sha256"]:
            raise ValueError("Answer text does not match its recorded hash")
        row = rows.setdefault(row_id, {
            "id": row_id, "question": answer["question"], "gold": answer["gold"],
            "cluster": answer["context_cluster_id"], "conditions": {}, "rankings": {},
        })
        if (row["question"], row["gold"], row["cluster"]) != (
                answer["question"], answer["gold"], answer["context_cluster_id"]):
            raise ValueError("Question, Gold or context identity differs between conditions")
        generation = answer["generation_id"]
        if candidate in row["conditions"] or generation in generations:
            raise ValueError("Duplicate answer identity")
        # Use the campaign's renderer: paragraph arrays become compact JSON,
        # and absent context becomes its explicit sentinel, exactly as prompted.
        context = render_qa("{context}", context_kind=answer["context_kind"],
                            context=answer["context"], question=answer["question"])
        if context not in context_index:
            context_index[context] = len(contexts)
            contexts.append(context)
        compression = None
        if candidate in candidates:
            key = ("context:" + row["cluster"][:32], candidate)
            compression = compression_index[key]
            if digest(context.encode()) != compression["compressed_sha256"]:
                raise ValueError("Displayed compression differs from supplied answer context")
        row["conditions"][candidate] = {
            "answer": answer["answer"], "answer_sha256": answer["answer_sha256"],
            "generation_id": generation, "answer_tokens": answer["answer_tokens"],
            "context": context_index[context], "context_kind": answer["context_kind"],
            "compression": compression, "scores": [],
        }
        generations[generation] = (row_id, candidate)
        models["answer"].add((answer["model_id"], answer["model_revision"]))
    if len(rows) != expected_rows or any(set(r["conditions"]) != set(conditions) for r in rows.values()):
        raise ValueError("Incomplete question-by-answer matrix")
    seen_scores = set()
    for score in scores:
        key = (score["row_id"], score["candidate_id"])
        replicate = score["replicate"]
        identity = (*key, replicate)
        if replicate not in (1, 2) or identity in seen_scores:
            raise ValueError("Duplicate or invalid score replicate")
        if generations.get(score["generation_id"]) != key or score["condition_id"] != key[1]:
            raise ValueError("Score is attached to the wrong answer")
        row = rows[key[0]]
        condition = row["conditions"][key[1]]
        if (score["answer_sha256"] != condition["answer_sha256"]
                or score["context_cluster_id"] != row["cluster"]
                or score["natural_eos"] is not True):
            raise ValueError("Score evidence disagrees with answer identity")
        dimensions = score["dimensions"]
        if (set(dimensions) != set(METRICS) or set(score["justifications"]) != set(METRICS)
                or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                       or not math.isfinite(v) or not 0 <= v <= 1 for v in dimensions.values())):
            raise ValueError("Invalid three-dimension score")
        condition["scores"].append({"replicate": replicate, "dimensions": dimensions,
                                    "reasons": score["justifications"]})
        seen_scores.add(identity)
        models["score"].add((score["model_id"], score["model_revision"]))
    for row in rows.values():
        for condition in row["conditions"].values():
            condition["scores"].sort(key=lambda s: s["replicate"])
            if not condition["scores"] or condition["scores"][0]["replicate"] != 1:
                raise ValueError("Answer is missing its primary score")
    tasks = set()
    for rank in ranks:
        row_id, candidate = rank["row_id"], rank["candidate_id"]
        if (row_id not in rows or candidate not in candidates
                or candidate in rows[row_id]["rankings"] or rank["rank_task_id"] in tasks):
            raise ValueError("Unknown or duplicate primary ranking")
        rows[row_id]["rankings"][candidate] = compact_rank(rank, "primary")
        tasks.add(rank["rank_task_id"])
        models["rank"].add((rank["model_id"], rank["model_revision"]))
    if any(set(row["rankings"]) != set(candidates) for row in rows.values()):
        raise ValueError("Incomplete full-question ranking matrix")
    retest_count = 0
    for rank in retests:
        row_id, candidate = rank["row_id"], rank["candidate_id"]
        primary = rows[row_id]["rankings"][candidate]
        if "retest" in primary or rank["rank_task_id"] in tasks:
            raise ValueError("Duplicate ranking repeat")
        primary["retest"] = compact_rank(rank, "retest")
        tasks.add(rank["rank_task_id"])
        retest_count += 1
        models["rank"].add((rank["model_id"], rank["model_revision"]))
    return {
        "schema_version": 1, "rows": [rows[k] for k in sorted(rows)], "contexts": contexts,
        "methods": METHODS, "ratios": RATIOS, "candidates": list(candidates),
        "meta": {
            "questions": len(rows), "conditions": len(conditions), "answers": len(generations),
            "clusters": len({r["cluster"] for r in rows.values()}),
            "primary_scores": len(generations), "score_repeats": len(seen_scores) - len(generations),
            "primary_rankings": len(tasks) - retest_count, "ranking_repeats": retest_count,
            "read_only": True, "models": {k: sorted(v) for k, v in models.items()},
        },
    }


def load_payload() -> dict:
    from .bundle import load_payload as load
    return load()


def render_html(payload: dict, template: str, css: str, javascript: str) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    # Model output is untrusted text. It must never close a script element.
    data = data.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    css_hash = base64.b64encode(hashlib.sha256(css.encode()).digest()).decode()
    js_hash = base64.b64encode(hashlib.sha256(javascript.encode()).digest()).decode()
    substitutions = {"__REVIEW_CSS_HASH__": css_hash, "__REVIEW_JS_HASH__": js_hash,
                     "__REVIEW_CSS__": css, "__REVIEW_DATA__": data, "__REVIEW_JS__": javascript}
    # Split once: inserted evidence is never interpreted as another placeholder.
    import re
    return re.sub("|".join(re.escape(k) for k in substitutions), lambda m: substitutions[m[0]], template)


def build(output: Path) -> dict:
    absolute = output.expanduser().absolute()
    resolved = absolute.resolve()
    if resolved != absolute or resolved.exists() or resolved.is_relative_to(ASSETS):
        raise PermissionError("Use a fresh non-symlink output outside packaged resources")
    payload = load_payload()
    source = WORKSPACE / "ui/review"
    assets = {name: (source / name).read_text() for name in ("index.html", "styles.css", "app.js")}
    html = render_html(payload, assets["index.html"], assets["styles.css"], assets["app.js"]).encode()
    receipt = {"created_at": datetime.now(timezone.utc).isoformat(), "read_only": True,
               "meta": payload["meta"], "files": {"index.html": {"bytes": len(html), "sha256": digest(html)}},
               "builder_sha256": digest(Path(__file__).read_bytes()),
               "assets_sha256": {name: digest(text.encode()) for name, text in assets.items()}}
    # All source validation finishes before any deliverable is written.
    resolved.mkdir(parents=True, exist_ok=False)
    with (resolved / "index.html").open("xb") as handle:
        handle.write(html)
    with (resolved / "verification.json").open("x") as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return {"output": str(resolved / "index.html"), "bytes": len(html),
            "questions": payload["meta"]["questions"], "answers": payload["meta"]["answers"],
            "primary_rankings": payload["meta"]["primary_rankings"], "read_only": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh output directory")
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))


if __name__ == "__main__":
    main()
