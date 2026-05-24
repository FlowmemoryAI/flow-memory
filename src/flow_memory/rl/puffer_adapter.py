"""Optional PufferLib adapter seam.

Flow Memory does not vendor PufferLib and does not require it for the base RL
Arena. This adapter exists so future high-throughput experiments have a clear
integration boundary.
"""
from __future__ import annotations

from flow_memory.rl.optional import OptionalRlDependencyError, is_pufferlib_available, require_pufferlib


class PufferLibUnavailable(OptionalRlDependencyError):
    """Raised when the optional PufferLib backend is requested but unavailable."""


class PufferLibAdapter:
    name = "pufferlib"

    @property
    def available(self) -> bool:
        return is_pufferlib_available()

    def load(self):
        try:
            return require_pufferlib()
        except OptionalRlDependencyError as exc:
            raise PufferLibUnavailable(str(exc)) from exc

    def make_env(self, env_id: str, **kwargs):
        self.load()
        raise NotImplementedError(
            "PufferLib mapping is a future adapter seam; no Puffer code is vendored"
        )
