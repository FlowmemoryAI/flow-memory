"""Loss functions for tiny neural smoke training."""

from __future__ import annotations

from typing import Any

from flow_memory.neural.torch_optional import require_torch


def predictive_latent_loss(predicted: Any, target: Any) -> Any:
    torch = require_torch()
    return torch.mean((predicted - target) ** 2)


def temporal_consistency_loss(tokens: Any) -> Any:
    torch = require_torch()
    if tokens.shape[1] < 2:
        return torch.tensor(0.0, dtype=tokens.dtype, device=tokens.device)
    return torch.mean((tokens[:, 1:] - tokens[:, :-1]) ** 2)


def motion_equivariance_loss(a: Any, b: Any) -> Any:
    return predictive_latent_loss(a, b)


def depth_consistency_loss(depth_proxy: Any) -> Any:
    return temporal_consistency_loss(depth_proxy.unsqueeze(-1) if depth_proxy.ndim == 2 else depth_proxy)


def egomotion_compensation_loss(predicted_motion: Any, egomotion: Any) -> Any:
    return predictive_latent_loss(predicted_motion.mean(dim=1), egomotion)


def appearance_suppression_loss(dorsal_a: Any, dorsal_b: Any) -> Any:
    return predictive_latent_loss(dorsal_a, dorsal_b)


def plan_success_loss(predicted_success: Any, target_success: Any) -> Any:
    torch = require_torch()
    return torch.mean((predicted_success.float() - target_success.float()) ** 2)


def skill_routing_loss(scores: Any, labels: Any) -> Any:
    torch = require_torch()
    return torch.nn.functional.cross_entropy(scores, labels)


def risk_prediction_loss(predicted_risk: Any, target_risk: Any) -> Any:
    return predictive_latent_loss(predicted_risk.float(), target_risk.float())


def memory_retrieval_loss(query: Any, positive: Any, negative: Any) -> Any:
    torch = require_torch()
    pos = torch.nn.functional.cosine_similarity(query, positive).mean()
    neg = torch.nn.functional.cosine_similarity(query, negative).mean()
    return torch.clamp(0.2 - pos + neg, min=0.0)


def total_dual_stream_loss(predicted: Any, target: Any, dorsal_a: Any, dorsal_b: Any) -> Any:
    return predictive_latent_loss(predicted, target) + 0.25 * appearance_suppression_loss(dorsal_a, dorsal_b)


def total_agent_policy_loss(success_pred: Any, success_target: Any, risk_pred: Any, risk_target: Any) -> Any:
    return plan_success_loss(success_pred, success_target) + 0.5 * risk_prediction_loss(risk_pred, risk_target)
