"""A2A gateway seam."""
from collections.abc import Mapping


class A2AGatewayNotConfigured(RuntimeError):
    pass


class A2AGateway:
    def send(self, _message: Mapping[str, object]) -> None:
        raise A2AGatewayNotConfigured("A2A gateway transport is not configured")
