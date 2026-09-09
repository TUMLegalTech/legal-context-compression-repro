"""Stable public data types for configuration, contracts, and ledgers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


class ContextKind(str, Enum):
    STATUTORY_TEXT = "gesetzestext"
    PARAGRAPH_LIST = "paragraphenliste"
    NO_CONTEXT = "kein_kontext"


@dataclass(frozen=True)
class CampaignConfig:
    path: Path
    value: Mapping[str, Any]
    sha256: str


@dataclass(frozen=True)
class Contract:
    path: Path
    fields: Mapping[str, str]
    sha256: str
    active: bool

    @property
    def contract_id(self) -> str:
        return self.fields["CONTRACT_ID"]
