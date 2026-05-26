"""Bundler adapter seam."""
from collections.abc import Mapping


class BundlerNotConfigured(RuntimeError):
    pass


class BundlerAdapter:
    def send_user_operation(self, _operation: Mapping[str, object]) -> Mapping[str, object]:
        raise BundlerNotConfigured("Bundler is not configured; dry-run only")
