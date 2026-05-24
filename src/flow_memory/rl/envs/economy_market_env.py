from __future__ import annotations

from typing import Any, Mapping

from flow_memory.rl.env import FlowEnv


class EconomyMarketEnv(FlowEnv):
    env_id = "economy_market"
    action_labels = ("bid_low", "bid_fair", "bid_high", "decline", "request_verifier")

    def __init__(self, *, seed: int = 0, max_steps: int = 8, episode_mode: str = "single_step") -> None:
        super().__init__(seed=seed, max_steps=max_steps)
        if episode_mode not in {"single_step", "long", "multi_round"}:
            raise ValueError(f"unknown economy market episode mode: {episode_mode}")
        self.episode_mode = episode_mode
        self.phase = "open"
        self.bid_round = 0
        self.selected_bid = "none"
        self.verifier_selected = False

    def reset(self, seed: int | None = None) -> Mapping[str, Any]:
        self.phase = "open"
        self.bid_round = 0
        self.selected_bid = "none"
        self.verifier_selected = False
        return super().reset(seed)

    def _obs(self) -> Mapping[str, Any]:
        obs = dict(super()._obs())
        economy = dict(obs["economy"])
        economy["phase"] = self.phase
        economy["episode_mode"] = self.episode_mode
        economy["bid_round"] = self.bid_round
        economy["selected_bid"] = self.selected_bid
        economy["verifier_selected"] = self.verifier_selected
        obs["economy"] = economy
        return obs

    def _transition(self, action: int) -> tuple[float, Mapping[str, Any]]:
        label = self.action_space.label(action)
        if self.episode_mode == "multi_round":
            reward, info = self._multi_round_transition(label)
        elif self.episode_mode == "long":
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

    def _multi_round_transition(self, label: str) -> tuple[float, dict[str, Any]]:
        if self.phase == "open":
            if label == "decline":
                self.phase = "declined"
                return 0.0, {"terminal": True}
            if label in {"bid_low", "bid_fair", "bid_high"}:
                self.phase = "bidding"
                self.bid_round = 1
                self.selected_bid = label
                if label == "bid_high":
                    return -0.4, {"overpriced_bid": True, "risk_signal": True}
                return (0.35 if label == "bid_low" else 0.6), {"bid_submitted": True}
            return -0.25, {"approval_required": True}
        if self.phase == "bidding":
            if label in {"bid_low", "bid_fair", "bid_high"}:
                self.bid_round += 1
                if label == "bid_high":
                    self.phase = "disputed"
                    self.selected_bid = label
                    return -1.2, {"dispute": True, "reputation_penalty": True, "overpriced_bid": True}
                if label == "bid_fair" or self.selected_bid == "none":
                    self.selected_bid = label
                if self.bid_round >= 2:
                    return 0.5, {"bid_round_complete": True}
                return 0.25, {"bid_submitted": True}
            if label == "request_verifier":
                self.phase = "verifier_selected"
                self.verifier_selected = True
                return 0.8, {"verification_requested": True, "verifier_selected": True}
            return -0.1, {"waiting_for_verifier": True}
        if self.phase == "verifier_selected":
            if label == "bid_fair":
                self.phase = "settled"
                return 2.2, {"success": True, "settlement": True, "reputation_gain": True, "verifier_selected": True}
            if label == "bid_low":
                self.phase = "settled"
                return 1.0, {"success": True, "settlement": True, "thin_margin": True, "verifier_selected": True}
            if label == "bid_high":
                self.phase = "disputed"
                return -1.5, {"dispute": True, "slashing": True, "reputation_penalty": True}
            return -0.2, {"verification_pending": True}
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
            "bid_round": self.bid_round,
            "selected_bid": self.selected_bid,
            "verifier_selected": self.verifier_selected,
        }
