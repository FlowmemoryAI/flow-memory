"""Optional PufferLib adapter seam.

Flow Memory does not vendor PufferLib and does not require it for the base RL
Arena. This adapter exists so future high-throughput experiments have a clear
integration boundary.
"""
from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, NoReturn

from flow_memory.rl.optional import (
    OptionalRlDependencyError as _OptionalRlDependencyError,
    is_pufferlib_available as _is_pufferlib_available,
    require_pufferlib as _require_pufferlib,
)

if TYPE_CHECKING:
    class _PufferLibUnavailableBase(ImportError):
        pass
else:
    _PufferLibUnavailableBase = _OptionalRlDependencyError


class PufferLibUnavailable(_PufferLibUnavailableBase):
    """Raised when the optional PufferLib backend is requested but unavailable."""


class PufferLibAdapter:
    name = "pufferlib"

    @property
    def available(self) -> bool:
        return bool(_is_pufferlib_available())

    def load(self) -> ModuleType:
        try:
            return _require_pufferlib()
        except _OptionalRlDependencyError as exc:
            raise PufferLibUnavailable(str(exc)) from exc

    def make_env(self, env_id: str, **kwargs: object) -> NoReturn:
        self.load()
        raise NotImplementedError(
            "PufferLib mapping is a future adapter seam; no Puffer code is vendored"
        )
