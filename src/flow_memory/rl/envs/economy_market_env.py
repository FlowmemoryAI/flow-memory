
from __future__ import annotations
from typing import Mapping, Any
from flow_memory.rl.env import FlowEnv

class EconomyMarketEnv(FlowEnv):
    env_id = "economy_market"
    action_labels = ('bid_low', 'bid_fair', 'bid_high', 'decline', 'request_verifier')
    def _transition(self, action:int) -> tuple[float, Mapping[str, Any]]:
        label=self.action_space.label(action)
        table={'bid_low': (0.2, {}), 'bid_fair': (2.0, {'success': True, 'settlement': True, 'reputation_gain': True}), 'bid_high': (-0.5, {'dispute': True}), 'decline': (0.0, {}), 'request_verifier': (1.0, {'verification_requested': True})}
        reward=float(table.get(label, (0.0, {}))[0])
        info=dict(table.get(label, (0.0, {}))[1])
        info.update({"action": label, "metrics": self._metrics(label, reward, info)})
        return reward, info
    def _metrics(self, label:str, reward:float, info:Mapping[str, Any]) -> Mapping[str, Any]:
        return {"reward": reward, "success": bool(info.get("success", False)), "safety_violation": bool(info.get("safety_violation", False)), "dispute": bool(info.get("dispute", False)), "slashing": bool(info.get("slashing", False))}
