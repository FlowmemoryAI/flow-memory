"""Dry-run transaction payload builder."""

from __future__ import annotations

from typing import Mapping


def build_dry_run_transaction(to: str, data: str = "0x", value: int = 0, chain_id: int = 84532) -> Mapping[str, object]:
    return {"to": to, "data": data, "value": value, "chain_id": chain_id, "dry_run": True}
