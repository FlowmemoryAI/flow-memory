"""VideoMAE adapter seam with no automatic downloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any, NoReturn

from flow_memory.neural.config import NeuralBackendConfig
from flow_memory.neural.torch_optional import OptionalDependencyError, require_torch


class VideoMAEAdapter:
    def __init__(self, config: NeuralBackendConfig) -> None:
        self.config = config
        require_torch()
        if not config.checkpoint_path or not Path(config.checkpoint_path).exists():
            raise OptionalDependencyError("VideoMAE requires an explicit local checkpoint_path; no download is attempted")

    def encode_video(self, video: Any) -> NoReturn:
        raise OptionalDependencyError("VideoMAE runtime is an adapter seam until local model code is installed")

    def masked_pretrain_features(self, video: Any) -> NoReturn:
        self.encode_video(video)
