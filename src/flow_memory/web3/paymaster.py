"""Paymaster adapter seam."""

class PaymasterNotConfigured(RuntimeError):
    pass


class PaymasterAdapter:
    def sponsor_user_operation(self, _operation):
        raise PaymasterNotConfigured("Paymaster is not configured; dry-run only")
