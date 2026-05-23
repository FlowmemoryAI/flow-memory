"""libp2p adapter seam for decentralized agent discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class LibP2PNodeSpec:
    peer_id: str
    listen_addresses: tuple[str, ...]
    protocols: tuple[str, ...] = ("/flow-memory/a2a/1.0.0",)
    metadata: Mapping[str, str] | None = None
