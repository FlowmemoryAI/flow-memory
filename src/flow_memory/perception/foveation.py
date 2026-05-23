"""Foveated attention routing.

The implementation is deterministic and dependency-light. It provides the same interface
needed by future image/video foveation modules: a high-resolution center stream and a
compressed peripheral stream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.core.types import Observation

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


@dataclass
class FoveatedAttention:
    """Center-high-resolution / periphery-low-resolution attention proxy."""

    center_weight: float = 1.0
    periphery_weight: float = 0.35
    text_center_tokens: int = 12

    def apply(self, observation: Observation) -> Mapping[str, Any]:
        if observation.modality in {"video", "frames"} or _has_frames(observation.content):
            frame_count = len(_extract_frames(observation.content))
            return {
                "mode": "video",
                "frame_count": frame_count,
                "center_region": "central_50_percent",
                "periphery_region": "outer_context",
                "center_weight": self.center_weight,
                "periphery_weight": self.periphery_weight,
            }

        tokens = _WORD_RE.findall(observation.as_text())
        center = tokens[: min(self.text_center_tokens, len(tokens))]
        periphery = tokens[min(self.text_center_tokens, len(tokens)) :]
        return {
            "mode": "text",
            "center_tokens": center,
            "periphery_token_count": len(periphery),
            "center_weight": self.center_weight,
            "periphery_weight": self.periphery_weight,
        }


def _has_frames(content: Any) -> bool:
    if isinstance(content, Mapping):
        return isinstance(content.get("frames"), (list, tuple))
    return isinstance(content, (list, tuple)) and bool(content) and isinstance(content[0], (list, tuple))


def _extract_frames(content: Any) -> list[Any]:
    if isinstance(content, Mapping) and isinstance(content.get("frames"), (list, tuple)):
        return list(content["frames"])
    if isinstance(content, (list, tuple)):
        return list(content)
    return []
