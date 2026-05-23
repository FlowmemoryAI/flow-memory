"""Prediction-error and free-energy proxy scoring."""

from __future__ import annotations

from flow_memory.neural.features import SurpriseScore, WorldModelPrediction
from flow_memory.neural.torch_optional import require_torch


def compute_surprise_score(prediction: WorldModelPrediction, actual_latent, actual_dorsal=None) -> SurpriseScore:
    torch = require_torch()
    prediction_error = torch.mean((prediction.predicted_latent - actual_latent) ** 2).item()
    if actual_dorsal is None:
        actual_dorsal = actual_latent[:, : prediction.predicted_dorsal.shape[1], :]
    dorsal_error = torch.mean((prediction.predicted_dorsal - actual_dorsal) ** 2).item()
    ventral_error = prediction_error
    free_energy = prediction_error + 0.5 * dorsal_error + float(prediction.uncertainty)
    return SurpriseScore(float(prediction_error), float(dorsal_error), float(ventral_error), float(free_energy))
