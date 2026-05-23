"""Optional PyTorch/Numpy dependency helpers for Flow Memory neural modules."""

from __future__ import annotations

import importlib
import importlib.util
from typing import Any


class OptionalDependencyError(ImportError):
    """Raised when an optional neural dependency is requested but unavailable."""


def is_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def is_torch_available() -> bool:
    return is_available("torch")


def is_numpy_available() -> bool:
    return is_available("numpy")


def require_module(module_name: str, *, extra: str = "ml") -> Any:
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:  # pragma: no cover - exercised when optional deps absent
        raise OptionalDependencyError(
            f"Optional dependency {module_name!r} is required for this neural feature. "
            f"Install flow-memory[{extra}] and provide local checkpoints if needed."
        ) from exc


def require_torch() -> Any:
    return require_module("torch")


def require_numpy() -> Any:
    return require_module("numpy")


def tensor_shape(value: Any) -> tuple[int, ...]:
    shape = getattr(value, "shape", None)
    if shape is not None:
        return tuple(int(dim) for dim in shape)
    if isinstance(value, (list, tuple)):
        dims: list[int] = []
        item: Any = value
        while isinstance(item, (list, tuple)):
            dims.append(len(item))
            item = item[0] if item else ()
        return tuple(dims)
    return ()
