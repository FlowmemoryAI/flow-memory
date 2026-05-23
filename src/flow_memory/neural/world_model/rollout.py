"""Latent rollout helpers."""

from __future__ import annotations

from flow_memory.neural.features import DualStreamFeatures, WorldModelPrediction
from flow_memory.neural.world_model.jepa import TinyJEPAWorldModel


def latent_rollout(model: TinyJEPAWorldModel, features: DualStreamFeatures, *, steps: int = 3, uncertainty_threshold: float = 0.8) -> tuple[WorldModelPrediction, ...]:
    predictions: list[WorldModelPrediction] = []
    current = features
    for horizon in range(1, steps + 1):
        prediction = model.predict(current, horizon_steps=horizon)
        predictions.append(prediction)
        if prediction.uncertainty > uncertainty_threshold:
            break
    return tuple(predictions)
