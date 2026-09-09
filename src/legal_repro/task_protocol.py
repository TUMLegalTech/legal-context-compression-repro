"""Unchanged deterministic rank-label and seed derivation."""
import hashlib
import random
from typing import Sequence
ORACLE_CONDITION = "oracle_bgb_paragraph_ids"

def rank_blind_map(*, seed: int, pass_id: str, row_id: str, candidate: str) -> dict[str, str]:
    conditions = ["raw", "matching_compressed", ORACLE_CONDITION, "no_context"]
    derived = int(hashlib.sha256(f"minimal-four-way\0{seed}\0{pass_id}\0{row_id}\0{candidate}".encode()).hexdigest()[:16], 16)
    random.Random(derived).shuffle(conditions)
    return {f"C{index + 1:02d}": condition for index, condition in enumerate(conditions)}

def derived_seed(seed: int, *parts: object) -> int:
    payload = "\x1f".join(str(value) for value in (seed, *parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & 0x7FFF_FFFF


def repeated_ngram_fraction(token_ids: Sequence[int], width: int = 8) -> float:
    values = [int(value) for value in token_ids]
    windows = [tuple(values[index : index + width]) for index in range(len(values) - width + 1)]
    return 0.0 if not windows else (len(windows) - len(set(windows))) / len(windows)
