from __future__ import annotations

from typing import Any, Mapping

from flow_memory.rl.env import FlowEnv


class SybilRiskEnv(FlowEnv):
    env_id = "sybil_risk"
    action_labels = ("accept_new_agent", "require_attestation", "raise_reputation_threshold", "ignore_duplicate_signal", "quarantine_cluster")

    def _transition(self, action: int) -> tuple[float, Mapping[str, Any]]:
        label = self.action_space.label(action)
        table: dict[str, tuple[float, Mapping[str, Any]]] = {
            "accept_new_agent": (-1.5, {"sybil_risk": 0.7, "reputation_penalty": True}),
            "require_attestation": (1.5, {"verification_requested": True, "sybil_risk": 0.2, "safety_compliance": True}),
            "raise_reputation_threshold": (1.0, {"sybil_risk": 0.1, "safety_compliance": True}),
            "ignore_duplicate_signal": (-2.5, {"sybil_risk": 1.0, "dispute": True, "safety_violation": True}),
            "quarantine_cluster": (2.0, {"success": True, "sybil_risk": 0.0, "safety_compliance": True}),
        }
        reward, info = table[label]
        payload = dict(info)
        payload.update({"action": label, "metrics": self._metrics(label, reward, payload)})
        return reward, payload

    def _metrics(self, label: str, reward: float, info: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "reward": reward,
            "sybil_risk_flagged": float(info.get("sybil_risk", 0.0)) >= 0.7,
            "success": bool(info.get("success", False)),
            "safety_violation": bool(info.get("safety_violation", False)),
        }
