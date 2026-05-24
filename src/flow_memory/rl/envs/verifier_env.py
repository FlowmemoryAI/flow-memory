from __future__ import annotations

from typing import Any, Mapping

from flow_memory.rl.env import FlowEnv


class VerifierEnv(FlowEnv):
    env_id = "verifier"
    action_labels = ("approve", "reject", "request_evidence", "escalate_dispute")

    def __init__(self, *, seed: int = 0, max_steps: int = 8, work_quality: str = "unknown", collusion: bool = False) -> None:
        super().__init__(seed=seed, max_steps=max_steps)
        if work_quality not in {"unknown", "good", "bad"}:
            raise ValueError(f"unknown work quality: {work_quality}")
        self.work_quality = work_quality
        self.collusion = collusion
        self.evidence_requested = False

    def reset(self, seed: int | None = None) -> Mapping[str, Any]:
        self.evidence_requested = False
        return super().reset(seed)

    def _obs(self) -> Mapping[str, Any]:
        obs = dict(super()._obs())
        obs["verification"] = {
            "work_quality": self.work_quality,
            "collusion_risk": 1.0 if self.collusion else 0.0,
            "evidence_requested": self.evidence_requested,
        }
        return obs

    def _transition(self, action: int) -> tuple[float, Mapping[str, Any]]:
        label = self.action_space.label(action)
        reward, info = self._score_action(label)
        info.update({"action": label, "metrics": self._metrics(label, reward, info)})
        return reward, info

    def _score_action(self, label: str) -> tuple[float, dict[str, Any]]:
        if label == "request_evidence":
            self.evidence_requested = True
            return 2.0, {"success": True, "verifier_accuracy": 1.0, "evidence_requested": True}
        if label == "escalate_dispute":
            return 0.75, {"dispute": True, "verifier_accuracy": 0.8}
        if self.work_quality == "good":
            if label == "approve":
                return 2.0, {"success": True, "verifier_accuracy": 1.0}
            if label == "reject":
                return -1.5, {"false_rejection": True, "verifier_accuracy": 0.0, "dispute": True}
        if self.work_quality == "bad":
            if label == "reject":
                return 2.0, {"success": True, "verifier_accuracy": 1.0}
            if label == "approve":
                penalty = -3.0 if self.collusion else -2.0
                return penalty, {"false_approval": True, "collusion_risk": self.collusion, "verifier_accuracy": 0.0, "dispute": True, "slashing": self.collusion}
        # Unknown work quality: direct approve/reject is lower confidence; evidence is best.
        if label in {"approve", "reject"}:
            return 0.5, {"verifier_accuracy": 0.5, "uncertain_verification": True}
        return 0.0, {}

    def _metrics(self, label: str, reward: float, info: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "reward": reward,
            "success": bool(info.get("success", False)),
            "safety_violation": bool(info.get("safety_violation", False)),
            "dispute": bool(info.get("dispute", False)),
            "slashing": bool(info.get("slashing", False)),
            "verifier_accuracy": float(info.get("verifier_accuracy", 0.0)),
            "collusion_risk": bool(info.get("collusion_risk", False)),
        }
