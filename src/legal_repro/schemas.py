"""Strict JSON schemas and parsers for independent pointwise and rank judgments."""

from __future__ import annotations

import json
import math
from typing import Any, Sequence


SCORE_DIMENSIONS = ("outcome_correctness", "legal_reasoning_correctness", "legal_basis_correctness")


def _strict_json(text: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"JSON repeats key {key}")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=unique, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Forbidden constant {value}")))


def _criterion_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {"score": {"type": "number", "minimum": 0.0, "maximum": 1.0}, "justification": {"type": "string", "minLength": 1}}, "required": ["score", "justification"], "additionalProperties": False}


def transport_schema(value: Any) -> Any:
    """Translate unsupported wire constraints without relaxing local acceptance.

    The pinned structured-output backends do not both accept ``uniqueItems``.
    Our teacher and rank validators still enforce uniqueness, including across
    ranking groups. The canonical schemas remain unchanged for provenance and
    validation.
    """
    if isinstance(value, dict):
        return {key: transport_schema(item) for key, item in value.items() if key != "uniqueItems"}
    if isinstance(value, list):
        return [transport_schema(item) for item in value]
    return value


def score_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {name: _criterion_schema() for name in SCORE_DIMENSIONS}, "required": list(SCORE_DIMENSIONS), "additionalProperties": False}


def rank_schema(blind_ids: Sequence[str] = ("C01", "C02", "C03", "C04")) -> dict[str, Any]:
    ids = list(blind_ids)
    return {
        "type": "object",
        "properties": {
            "rank_groups": {"type": "array", "minItems": 1, "items": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "enum": ids}}},
            "candidate_justifications": {"type": "object", "properties": {item: {"type": "string", "minLength": 1} for item in ids}, "required": ids, "additionalProperties": False},
            "comparative_justification": {"type": "string", "minLength": 1},
        },
        "required": ["rank_groups", "candidate_justifications", "comparative_justification"],
        "additionalProperties": False,
    }


def parse_score(text: str) -> dict[str, Any]:
    value = _strict_json(text)
    if not isinstance(value, dict) or set(value) != set(SCORE_DIMENSIONS):
        raise ValueError("Score JSON has unexpected fields")
    dimensions: dict[str, float] = {}
    justifications: dict[str, str] = {}
    for name in SCORE_DIMENSIONS:
        criterion = value[name]
        if not isinstance(criterion, dict) or set(criterion) != {"score", "justification"}:
            raise ValueError(f"Invalid score criterion {name}")
        score = criterion["score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError(f"Non-numeric score {name}")
        number = float(score)
        if not math.isfinite(number) or not 0 <= number <= 1 or round(number, 2) != number:
            raise ValueError(f"Score precision/range changed for {name}")
        if not isinstance(criterion["justification"], str):
            raise ValueError(f"Non-string justification {name}")
        justification = " ".join(criterion["justification"].split())
        if not justification:
            raise ValueError(f"Empty justification {name}")
        dimensions[name] = number
        justifications[name] = justification
    return {"dimensions": dimensions, "justifications": justifications, "overall_score": sum(dimensions.values()) / len(dimensions)}


def parse_rank(text: str, expected_ids: Sequence[str] = ("C01", "C02", "C03", "C04")) -> dict[str, Any]:
    value = _strict_json(text)
    if not isinstance(value, dict) or set(value) != {"rank_groups", "candidate_justifications", "comparative_justification"}:
        raise ValueError("Rank JSON has unexpected fields")
    expected = set(expected_ids)
    groups = value["rank_groups"]
    if not isinstance(groups, list) or not groups or any(not isinstance(group, list) or not group for group in groups):
        raise ValueError("Rank groups are empty")
    flattened = [str(item) for group in groups if isinstance(group, list) for item in group]
    if len(flattened) != len(expected) or set(flattened) != expected:
        raise ValueError("Rank groups must contain every candidate exactly once")
    justifications = value["candidate_justifications"]
    if not isinstance(justifications, dict) or set(justifications) != expected:
        raise ValueError("Rank justifications do not match candidates")
    if any(
        not isinstance(justifications[key], str)
        or not " ".join(justifications[key].split())
        for key in expected_ids
    ) or not isinstance(value["comparative_justification"], str) or not " ".join(
        value["comparative_justification"].split()
    ):
        raise ValueError("Rank justifications must be nonempty strings")
    return {
        "rank_groups": [[str(item) for item in group] for group in groups],
        "candidate_justifications": {key: " ".join(str(justifications[key]).split()) for key in expected_ids},
        "comparative_justification": " ".join(str(value["comparative_justification"]).split()),
    }


__all__ = ["SCORE_DIMENSIONS", "parse_rank", "parse_score", "rank_schema", "score_schema"]
