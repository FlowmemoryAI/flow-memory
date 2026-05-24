from __future__ import annotations

from typing import Any, Mapping

from flow_memory.rl.env import FlowEnv


class ColludingVerifierEnv(FlowEnv):
    env_id = "colluding_verifier"
    action_labels = ("single_verifier_approve", "multi_verifier_vote", "request_evidence", "escalate_dispute", "slash_colluder")

    def _transition(self, action: int) -> tuple[float, Mapping[str, Any]]:
        label = self.action_space.label(action)
        table: dict[str, tuple[float, Mapping[str, Any]]] = {
            "single_verifier_approve": (-2.0, {"collusion_risk": 0.9, "false_approval": True, "reputation_penalty": True}),
            "multi_verifier_vote": (2.0, {"success": True, "collusion_risk": 0.1, "verification_requested": True}),
            "request_evidence": (1.0, {"collusion_risk": 0.2, "verification_requested": True}),
            "escalate_dispute": (0.8, {"dispute": True, "collusion_risk": 0.2}),
            "slash_colluder": (1.5, {"success": True, "slashing": True, "collusion_risk": 0.0}),
        }
        reward, info = table[label]
        payload = dict(info)
        payload.update({"action": label, "metrics": self._metrics(label, reward, payload)})
        return reward, payload

    def _metrics(self, label: str, reward: float, info: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "reward": reward,
            "collusion_detected": float(info.get("collusion_risk", 0.0)) >= 0.8,
            "success": bool(info.get("success", False)),
            "false_approval": bool(info.get("false_approval", False)),
            "slashing": bool(info.get("slashing", False)),
        }
