"""Ventral stream encoder: entity, object, symbol, and semantic recognition."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from flow_memory.core.types import Entity, Observation

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
KNOWN_ENTITY_TERMS = {
    "agent", "environment", "task", "wallet", "marketplace", "memory", "robot", "object", "tool", "contract", "identity",
}


def _dedupe(labels: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for label in labels:
        normalized = str(label).strip(" _-:")
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


@dataclass
class VentralStreamEncoder:
    """Entity, category, symbol, and language encoder."""

    max_entities: int = 12

    def encode(self, observation: Observation) -> Sequence[Entity]:
        structured = self._from_structured_content(observation.content)
        labels = structured if structured else self._from_text(observation.as_text())
        return tuple(
            Entity(
                label=label,
                confidence=max(0.35, min(1.0, 0.98 - idx * 0.04)),
                attributes={"stream": "ventral", "source_modality": observation.modality},
            )
            for idx, label in enumerate(labels[: self.max_entities])
        )

    def _from_structured_content(self, content: Any) -> list[str]:
        if not isinstance(content, Mapping):
            return []
        labels: list[str] = []
        for key in ("entities", "objects", "labels", "symbols"):
            value = content.get(key)
            if isinstance(value, str):
                labels.append(value)
            elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                for item in value:
                    if isinstance(item, Mapping):
                        labels.append(str(item.get("label") or item.get("id") or item.get("name") or "object"))
                    else:
                        labels.append(str(item))
        if "agent" in content:
            labels.append(str(content["agent"]))
        if "task" in content:
            labels.append("task")
        return _dedupe(labels)

    def _from_text(self, text: str) -> list[str]:
        tokens = WORD_RE.findall(text)
        candidates: list[str] = []
        for token in tokens:
            lower = token.lower()
            if token[0].isupper() or lower in KNOWN_ENTITY_TERMS:
                candidates.append(token)
            if len(_dedupe(candidates)) >= self.max_entities:
                break
        if not candidates and tokens:
            candidates = tokens[: min(3, len(tokens))]
        return _dedupe(candidates)


@dataclass
class VideoBackboneAdapter:
    """Placeholder seam for VideoMAE/V-JEPA-family ventral encoders."""

    model_name: str = "local-symbolic"

    def encode(self, observation: Observation) -> Sequence[Entity]:
        return VentralStreamEncoder().encode(observation)
