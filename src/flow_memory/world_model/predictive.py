"""Predictive coding world model.

This module exposes the production seam for V-JEPA/VideoMAE-style latent prediction while
keeping the default implementation deterministic and testable on CPU-only machines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import PerceptionOutput, Prediction


@dataclass
class VJEPAPredictor:
    """Lightweight stand-in for a JEPA/video predictive encoder.

    Real deployments should subclass or replace this with a torch-backed adapter that
    returns latent predictions from video embeddings.
    """

    name: str = "vjepa-compatible-null-predictor"

    def __call__(self, perception: PerceptionOutput | Mapping[str, Any]) -> Mapping[str, Any]:
        if isinstance(perception, PerceptionOutput):
            entity_labels = [entity.label for entity in perception.entities]
            affordances = list(perception.motion_geometry.affordances)
            motion_confidence = perception.motion_geometry.confidence
            modality = perception.latent_state.get("modality", "unknown")
            motion_signature = _extract_motion_signature(perception.motion_geometry.spatial_relations)
        else:
            entity_labels = list(perception.get("entities", []))
            affordances = list(perception.get("affordances", []))
            motion_confidence = float(perception.get("motion_confidence", 0.0))
            modality = str(perception.get("modality", "unknown"))
            motion_signature = perception.get("motion_signature")
        confidence = min(0.95, 0.35 + 0.05 * len(entity_labels) + 0.15 * motion_confidence + 0.04 * len(affordances))
        predicted = {
            "predictor": self.name,
            "modality": modality,
            "expected_entities": entity_labels,
            "expected_affordances": affordances,
            "motion_geometry_confidence": motion_confidence,
            "confidence": round(confidence, 4),
        }
        if motion_signature is not None:
            predicted["motion_signature"] = motion_signature
        return predicted



def _extract_motion_signature(spatial_relations: Any) -> Mapping[str, Any] | None:
    if not isinstance(spatial_relations, (list, tuple)):
        return None
    for relation in spatial_relations:
        if isinstance(relation, Mapping):
            signature = relation.get("appearance_invariant_signature")
            if isinstance(signature, Mapping):
                return signature
    return None

@dataclass
class FreeEnergyMinimizer:
    """Prediction-error regularizer used by the default world model."""

    regularization: float = 0.05

    def optimize(self, predicted_state: Mapping[str, Any]) -> Mapping[str, Any]:
        optimized = dict(predicted_state)
        confidence = float(optimized.get("confidence", 0.5))
        motion_confidence = float(optimized.get("motion_geometry_confidence", confidence))
        free_energy = (1.0 - confidence) * (1.0 + abs(confidence - motion_confidence))
        optimized["free_energy_proxy"] = round(max(0.0, min(1.0, free_energy)), 4)
        optimized["regularization"] = self.regularization
        optimized["objective"] = "minimize_prediction_error"
        return optimized


@dataclass
class PredictiveWorldModel:
    """Latent-state predictor for the cognitive loop."""

    latent_predictor: VJEPAPredictor = field(default_factory=VJEPAPredictor)
    surprise_minimizer: FreeEnergyMinimizer = field(default_factory=FreeEnergyMinimizer)

    def forecast(self, perception: PerceptionOutput, horizon_steps: int = 1) -> Prediction:
        predicted_state = dict(self.latent_predictor(perception))
        predicted_state["horizon_steps"] = horizon_steps
        optimized = self.surprise_minimizer.optimize(predicted_state)
        return Prediction(
            state=optimized,
            horizon_steps=horizon_steps,
            confidence=float(optimized.get("confidence", 0.5)),
        )

    def predict(self, current_state: Mapping[str, Any]) -> Mapping[str, Any]:
        predicted = dict(current_state)
        predicted.setdefault("confidence", 0.5)
        return self.surprise_minimizer.optimize(predicted)
