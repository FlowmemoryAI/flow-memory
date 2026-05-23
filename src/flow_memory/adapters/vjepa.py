"""V-JEPA adapter seam.

The adapter intentionally avoids importing heavyweight ML packages until runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class VJEPAAdapter:
    model_name: str = "vjepa2"
    device: str = "cpu"

    def load(self) -> None:
        try:
            import torch  # noqa: F401
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install flow-memory[ml] to use VJEPAAdapter") from exc

    def predict_latent(self, video: Any) -> Mapping[str, Any]:
        self.load()
        raise NotImplementedError("Wire this adapter to the selected V-JEPA checkpoint for production use")
