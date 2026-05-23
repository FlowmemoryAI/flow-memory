"""Verifier selection helpers."""

from __future__ import annotations

from typing import Mapping


def select_highest_reputation(candidates: tuple[str, ...], reputation: Mapping[str, float]) -> str:
    if not candidates:
        raise ValueError("at least one verifier candidate is required")
    return sorted(candidates, key=lambda agent: reputation.get(agent, 0.0), reverse=True)[0]
