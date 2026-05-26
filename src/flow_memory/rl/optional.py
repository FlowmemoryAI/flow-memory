"""Optional RL backend helpers."""
from __future__ import annotations
import importlib
import importlib.util
from types import ModuleType


class OptionalRlDependencyError(ImportError):
    pass


def is_pufferlib_available() -> bool:
    return importlib.util.find_spec("pufferlib") is not None


def require_pufferlib() -> ModuleType:
    if not is_pufferlib_available():
        raise OptionalRlDependencyError("PufferLib is optional and not installed; install it in an isolated experiment environment")
    return importlib.import_module("pufferlib")
