"""V-JEPA 2 adapter seam.

This adapter never downloads checkpoints automatically. A real backend must be
configured with local dependencies and local checkpoint material.
"""

from __future__ import annotations

from pathlib import Path

from flow_memory.neural.config import NeuralBackendConfig
from flow_memory.neural.torch_optional import OptionalDependencyError, require_torch


class VJEPA2Adapter:
    def __init__(self, config: NeuralBackendConfig) -> None:
        self.config = config
        require_torch()
        if not config.checkpoint_path or not Path(config.checkpoint_path).exists():
            raise OptionalDependencyError("V-JEPA 2 requires an explicit local checkpoint_path; no download is attempted")

    def encode_video(self, video):
        raise OptionalDependencyError("V-JEPA 2 runtime is an adapter seam until local model code is installed")

    def encode_latents(self, video):
        return self.encode_video(video)

    def predict_next_latent(self, video):
        raise OptionalDependencyError("V-JEPA 2 predictor is unavailable without a configured local model")
