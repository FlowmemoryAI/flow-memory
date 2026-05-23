"""Protocol manifest."""

PROTOCOLS = ("mcp", "a2a", "libp2p")


def protocol_manifest():
    return {"protocols": tuple({"name": name, "status": "adapter_seam"} for name in PROTOCOLS)}
