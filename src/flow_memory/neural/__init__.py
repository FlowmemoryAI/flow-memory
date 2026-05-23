"""Optional neural subsystem for Flow Memory.

The base package imports without PyTorch. Constructing torch-backed encoders or
backends raises OptionalDependencyError when flow-memory[ml] is not installed.
"""

from flow_memory.neural.checkpoints import CheckpointRef, CheckpointRegistry
from flow_memory.neural.config import NeuralBackendConfig, neural_config_from_mapping
from flow_memory.neural.features import (
    DorsalFeatures,
    DualStreamFeatures,
    NeuralEvaluationResult,
    NeuralFeature,
    SurpriseScore,
    VentralFeatures,
    VideoTensorSpec,
    WorldModelPrediction,
)
from flow_memory.neural.registry import NeuralBackendRegistry
from flow_memory.neural.torch_optional import OptionalDependencyError, is_numpy_available, is_torch_available
from flow_memory.neural.traces import AgentTrace, EconomyTrace, PlanTrace, SkillTrace

__all__ = [
    "AgentTrace",
    "CheckpointRef",
    "CheckpointRegistry",
    "DorsalFeatures",
    "DualStreamFeatures",
    "EconomyTrace",
    "NeuralBackendConfig",
    "NeuralBackendRegistry",
    "NeuralEvaluationResult",
    "NeuralFeature",
    "OptionalDependencyError",
    "PlanTrace",
    "SkillTrace",
    "SurpriseScore",
    "VentralFeatures",
    "VideoTensorSpec",
    "WorldModelPrediction",
    "is_numpy_available",
    "is_torch_available",
    "neural_config_from_mapping",
]
