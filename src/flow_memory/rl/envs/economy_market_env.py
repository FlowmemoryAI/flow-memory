from __future__ import annotations

from typing import Any, Mapping

from flow_memory.rl.env import FlowEnv


class EconomyMarketEnv(FlowEnv):
    env_id = "economy_market"
    action_labels = ("bid_low", "bid_fair", "bid_high", "decline", "request_verifier")

    def __init__(self, *, seed: int = 0, max_steps: int = 8, episode_mode: str = "single_step") -> None:
        super().__init__(seed=seed, max_steps=max_steps)
        if episode_mode not in {"single_step", "long"}:
            raise ValueError(f"unknown economy market episode mode: {episode_mode}")
        self.episode_mode = episode_mode
        self.phase = "open"

    def reset(self, seed: int | None = None) -> Mapping[str, Any]:
        self.phase = "open"
        return super().reset(seed)

    def _obs(self) -> Mapping[str, Any]:
        obs = dict(super()._obs())
        economy = dict(obs["economy"])
        economy["phase"] = self.phase
        economy["episode_mode"] = self.episode_mode
        obs["economy"] = economy
        return obs

    def _transition(self, action: int) -> tuple[float, Mapping[str, Any]]:
        label = self.action_space.label(action)
        if self.episode_mode == "long":
            reward, info = self._long_transition(label)
        else:
            table = {
                "bid_low": (0.2, {}),
                "bid_fair": (2.0, {"success": True, "settlement": True, "reputation_gain": True}),
                "bid_high": (-0.5, {"dispute": True}),
                "decline": (0.0, {}),
                "request_verifier": (1.0, {"verification_requested": True}),
            }
            reward = float(table.get(label, (0.0, {}))[0])
            info = dict(table.get(label, (0.0, {}))[1])
        info.update({"action": label, "economy_phase": self.phase, "episode_mode": self.episode_mode, "metrics": self._metrics(label, reward, info)})
        return reward, info

    def _long_transition(self, label: str) -> tuple[float, dict[str, Any]]:
        if self.phase == "open":
            if label == "decline":
                self.phase = "declined"
                return 0.0, {"terminal": True}
            if label == "bid_high":
                self.phase = "disputed"
                return -1.0, {"dispute": True, "reputation_penalty": True}
            if label in {"bid_low", "bid_fair"}:
                self.phase = "bid_submitted"
                return (0.25 if label == "bid_low" else 0.5), {"bid_submitted": True}
            return -0.25, {"approval_required": True}
        if self.phase == "bid_submitted":
            if label == "request_verifier":
                self.phase = "verifier_selected"
                return 0.75, {"verification_requested": True}
            if label == "bid_high":
                self.phase = "disputed"
                return -1.0, {"dispute": True, "reputation_penalty": True}
            return -0.1, {"waiting_for_verifier": True}
        if self.phase == "verifier_selected":
            if label == "bid_fair":
                self.phase = "settled"
                return 2.0, {"success": True, "settlement": True, "reputation_gain": True}
            if label == "bid_high":
                self.phase = "disputed"
                return -1.5, {"dispute": True, "slashing": True, "reputation_penalty": True}
            return -0.25, {"verification_pending": True}
        return 0.0, {"terminal": self.phase in {"settled", "declined", "disputed"}}

    def _metrics(self, label: str, reward: float, info: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "reward": reward,
            "success": bool(info.get("success", False)),
            "safety_violation": bool(info.get("safety_violation", False)),
            "dispute": bool(info.get("dispute", False)),
            "slashing": bool(info.get("slashing", False)),
            "settlement": bool(info.get("settlement", False)),
            "phase": self.phase,
        }
