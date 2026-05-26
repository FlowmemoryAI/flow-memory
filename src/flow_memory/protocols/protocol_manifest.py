"""Protocol manifest."""

from typing import TypeAlias

ProtocolEntry: TypeAlias = dict[str, str]
ProtocolManifest: TypeAlias = dict[str, tuple[ProtocolEntry, ...]]

PROTOCOLS: tuple[str, ...] = ("mcp", "a2a", "libp2p")


def protocol_manifest() -> ProtocolManifest:
    return {"protocols": tuple({"name": name, "status": "adapter_seam"} for name in PROTOCOLS)}
