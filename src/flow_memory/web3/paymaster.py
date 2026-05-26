"""Paymaster adapter seam."""
from collections.abc import Mapping


class PaymasterNotConfigured(RuntimeError):
    pass


class PaymasterAdapter:
    def sponsor_user_operation(self, _operation: Mapping[str, object]) -> Mapping[str, object]:
        raise PaymasterNotConfigured("Paymaster is not configured; dry-run only")
