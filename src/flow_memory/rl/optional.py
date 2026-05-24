"""Optional RL backend helpers."""
from __future__ import annotations
import importlib.util
class OptionalRlDependencyError(ImportError): pass
def is_pufferlib_available()->bool: return importlib.util.find_spec("pufferlib") is not None
def require_pufferlib():
    if not is_pufferlib_available():
        raise OptionalRlDependencyError("PufferLib is optional and not installed; install it in an isolated experiment environment")
    import pufferlib
    return pufferlib
