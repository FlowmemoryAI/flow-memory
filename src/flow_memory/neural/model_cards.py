"""Model-card helpers for neural evidence metadata."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def parse_model_card_text(text: str) -> Mapping[str, Any]:
    title = ""
    first_paragraph = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and not title:
            title = stripped.lstrip("#").strip()
            continue
        if stripped and not stripped.startswith("#") and not first_paragraph:
            first_paragraph = stripped
    lowered = text.lower()
    return {
        "title": title,
        "first_paragraph": first_paragraph,
        "mentions_smoke": "smoke" in lowered,
        "mentions_production": "production" in lowered,
        "characters": len(text),
    }


def parse_model_card(path: Path) -> Mapping[str, Any]:
    return parse_model_card_text(path.read_text(encoding="utf-8"))
