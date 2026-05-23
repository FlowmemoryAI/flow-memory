"""Plain-dict API schema helpers."""
from __future__ import annotations

from typing import Mapping


def object_schema(properties: Mapping[str, Mapping[str, object]], required: tuple[str, ...] = ()) -> Mapping[str, object]:
    return {"type": "object", "properties": dict(properties), "required": tuple(required)}
