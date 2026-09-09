"""Unchanged paired context-cluster statistical kernels from the original study."""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Mapping, Sequence
import numpy as np
ORACLE_CONDITION = "oracle_bgb_paragraph_ids"
DIMENSIONS = ("outcome_correctness", "legal_reasoning_correctness", "legal_basis_correctness", "overall_score")

def _holm(rows: list[dict[str, Any]]) -> None:
    ordered = sorted(enumerate(rows), key=lambda item: (float(item[1]["p_value"]), item[0]))
    running = 0.0
    total = len(ordered)
    adjusted: dict[int, float] = {}
    for position, (index, row) in enumerate(ordered):
        value = min(1.0, (total - position) * float(row["p_value"]))
        running = max(running, value)
        adjusted[index] = running
    for index, value in adjusted.items():
        rows[index]["holm_p"] = value


def _cluster_totals(
    differences: Sequence[float], clusters: Sequence[str]
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for value, cluster in zip(differences, clusters, strict=True):
        grouped[str(cluster)].append(float(value))
    names = tuple(sorted(grouped))
    if not names:
        raise ValueError("Context-cluster inference requires at least one row")
    return (
        np.asarray([sum(grouped[name]) for name in names], dtype=np.float64),
        np.asarray([len(grouped[name]) for name in names], dtype=np.int64),
        names,
    )


def _inference(differences: Sequence[float], clusters: Sequence[str], *, bootstrap_replicates: int, randomizations: int, seed: int) -> dict[str, Any]:
    cluster_sums, cluster_counts, names = _cluster_totals(differences, clusters)
    observed = float(cluster_sums.sum() / cluster_counts.sum())
    rng = np.random.default_rng(int(seed))
    indexes = rng.integers(0, len(cluster_sums), size=(int(bootstrap_replicates), len(cluster_sums)))
    boot = cluster_sums[indexes].sum(axis=1) / cluster_counts[indexes].sum(axis=1)
    extreme = 0
    remaining = int(randomizations)
    while remaining:
        batch = min(4096, remaining)
        signs = rng.choice(np.asarray([-1.0, 1.0]), size=(batch, len(cluster_sums)))
        randomized = (signs * cluster_sums).sum(axis=1) / cluster_counts.sum()
        extreme += int(np.count_nonzero(np.abs(randomized) >= abs(observed) - 1e-15))
        remaining -= batch
    p = (extreme + 1) / (int(randomizations) + 1)
    return {
        "mean_difference": observed,
        "ci95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
        "p_value": p,
        "estimand": "evaluation_row_mean_with_context_cluster_resampling",
        "clusters": len(names),
        "rows": len(differences),
        "wins": sum(value > 0 for value in differences),
        "ties": sum(value == 0 for value in differences),
        "losses": sum(value < 0 for value in differences),
    }


def _contrasts(
    *,
    averaged: Mapping[tuple[str, str], Mapping[str, float]],
    clusters: Mapping[str, str],
    row_ids: Sequence[str],
    candidates: Sequence[str],
    bootstrap_replicates: int,
    randomizations: int,
    seed: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        for reference in ("raw", ORACLE_CONDITION, "no_context"):
            for metric in DIMENSIONS:
                differences = [
                    float(averaged[(row_id, candidate)][metric])
                    - float(averaged[(row_id, reference)][metric])
                    for row_id in row_ids
                ]
                result = _inference(
                    differences,
                    [clusters[row_id] for row_id in row_ids],
                    bootstrap_replicates=int(bootstrap_replicates),
                    randomizations=int(randomizations),
                    seed=int(seed) + len(rows),
                )
                rows.append(
                    {
                        "candidate_id": candidate,
                        "reference": reference,
                        "metric": metric,
                        "holm_family": f"{reference}:{metric}",
                        **result,
                    }
                )
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for contrast in rows:
        families[str(contrast["holm_family"])].append(contrast)
    for family in families.values():
        _holm(family)
    return rows
