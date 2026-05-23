"""Bundler adapter seam."""

class BundlerNotConfigured(RuntimeError):
    pass


class BundlerAdapter:
    def send_user_operation(self, _operation):
        raise BundlerNotConfigured("Bundler is not configured; dry-run only")
