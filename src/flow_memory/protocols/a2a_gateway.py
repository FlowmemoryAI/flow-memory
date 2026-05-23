"""A2A gateway seam."""

class A2AGatewayNotConfigured(RuntimeError):
    pass


class A2AGateway:
    def send(self, _message):
        raise A2AGatewayNotConfigured("A2A gateway transport is not configured")
