"""libp2p adapter seam."""

class Libp2pNotConfigured(RuntimeError):
    pass


class Libp2pAdapter:
    def publish(self, _topic: str, _payload: bytes):
        raise Libp2pNotConfigured("libp2p transport is not configured")
