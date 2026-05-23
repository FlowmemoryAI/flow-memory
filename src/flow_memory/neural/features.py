"""Typed neural feature contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.neural.torch_optional import tensor_shape


def _summary(value: Any) -> Mapping[str, Any]:
    return {"shape": tensor_shape(value), "type": type(value).__name__}


@dataclass(frozen=True)
class VideoTensorSpec:
    batch: int
    frames: int
    channels: int
    height: int
    width: int

    @classmethod
    def from_value(cls, value: Any) -> "VideoTensorSpec":
        shape = tensor_shape(value)
        if len(shape) != 5:
            raise ValueError(f"video tensor must follow [B, T, C, H, W], got {shape}")
        return cls(*shape)

    def as_record(self) -> Mapping[str, int]:
        return {"batch": self.batch, "frames": self.frames, "channels": self.channels, "height": self.height, "width": self.width}


@dataclass(frozen=True)
class NeuralFeature:
    name: str
    values: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {"name": self.name, "values": _summary(self.values), "metadata": dict(self.metadata)}


@dataclass(frozen=True)
class VentralFeatures:
    semantic_tokens: Any
    entity_logits: Any
    appearance_signature: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "semantic_tokens": _summary(self.semantic_tokens),
            "entity_logits": _summary(self.entity_logits),
            "appearance_signature": _summary(self.appearance_signature),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DorsalFeatures:
    motion_tokens: Any
    geometry_tokens: Any
    flow_proxy: Any
    depth_proxy: Any
    egomotion_proxy: Any
    invariance_metrics: Mapping[str, float] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "motion_tokens": _summary(self.motion_tokens),
            "geometry_tokens": _summary(self.geometry_tokens),
            "flow_proxy": _summary(self.flow_proxy),
            "depth_proxy": _summary(self.depth_proxy),
            "egomotion_proxy": _summary(self.egomotion_proxy),
            "invariance_metrics": dict(self.invariance_metrics),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DualStreamFeatures:
    ventral: VentralFeatures
    dorsal: DorsalFeatures
    fused_tokens: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "ventral": self.ventral.as_record(),
            "dorsal": self.dorsal.as_record(),
            "fused_tokens": _summary(self.fused_tokens),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class WorldModelPrediction:
    predicted_latent: Any
    predicted_dorsal: Any
    horizon_steps: int = 1
    uncertainty: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "predicted_latent": _summary(self.predicted_latent),
            "predicted_dorsal": _summary(self.predicted_dorsal),
            "horizon_steps": self.horizon_steps,
            "uncertainty": self.uncertainty,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SurpriseScore:
    prediction_error: float
    dorsal_error: float
    ventral_error: float
    free_energy_proxy: float

    def as_record(self) -> Mapping[str, float]:
        return {
            "prediction_error": self.prediction_error,
            "dorsal_error": self.dorsal_error,
            "ventral_error": self.ventral_error,
            "free_energy_proxy": self.free_energy_proxy,
        }


@dataclass(frozen=True)
class NeuralEvaluationResult:
    output_quality: float
    policy_compliance: float
    novelty_surprise: float
    memory_usefulness: float
    economic_value: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def total_score(self) -> float:
        return (self.output_quality + self.policy_compliance + self.novelty_surprise + self.memory_usefulness + self.economic_value) / 5.0

    def as_record(self) -> Mapping[str, Any]:
        return {
            "output_quality": self.output_quality,
            "policy_compliance": self.policy_compliance,
            "novelty_surprise": self.novelty_surprise,
            "memory_usefulness": self.memory_usefulness,
            "economic_value": self.economic_value,
            "total_score": self.total_score,
            "metadata": dict(self.metadata),
        }
