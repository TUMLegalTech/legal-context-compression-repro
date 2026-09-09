"""Load and render the exact sealed prompt surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .types import ContextKind


NO_CONTEXT_SENTINEL = "[KEIN KONTEXT BEREITGESTELLT]"


def prompt_root(repository: str | Path) -> Path:
    return Path(repository).expanduser().resolve(strict=True) / "prompts"


def load_prompt(repository: str | Path, name: str) -> str:
    if name not in {"qa_user", "score_developer", "score_user", "rank_developer", "rank_user", "teacher_developer", "teacher_user"}:
        raise ValueError(f"Unknown prompt: {name}")
    return (prompt_root(repository) / f"{name}.txt").read_text(encoding="utf-8")


def render_qa(
    template: str,
    *,
    context_kind: ContextKind | str,
    context: str | list[str],
    question: str,
) -> str:
    kind = ContextKind(context_kind)
    if not str(question).strip():
        raise ValueError("Question is empty")
    if kind is ContextKind.PARAGRAPH_LIST:
        if not isinstance(context, list) or not context or any(not isinstance(value, str) or not value.strip() for value in context):
            raise ValueError("Paragraph-list context requires a nonempty ordered string list")
        rendered = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    elif kind is ContextKind.NO_CONTEXT:
        if context not in {"", NO_CONTEXT_SENTINEL}:
            raise ValueError("No-context condition cannot carry hidden text")
        rendered = NO_CONTEXT_SENTINEL
    else:
        if not isinstance(context, str) or not context.strip():
            raise ValueError("Statutory-text context is empty")
        rendered = context
    return template.format(context_kind=kind.value, context=rendered, question=question)


def render_named(template: str, values: Mapping[str, Any]) -> str:
    return template.format(**{key: str(value) for key, value in values.items()})


__all__ = ["NO_CONTEXT_SENTINEL", "load_prompt", "prompt_root", "render_named", "render_qa"]
