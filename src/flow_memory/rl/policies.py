"""Baseline policies for Flow Arena."""
from __future__ import annotations
import json, random
from dataclasses import dataclass, field
from typing import Any, Mapping
from flow_memory.rl.env import FlowEnv

class RandomPolicy:
    def __init__(self, seed:int=0): self.rng=random.Random(seed)
    def act(self, observation:Mapping[str,Any], env:FlowEnv)->int: return self.rng.randrange(env.action_space.n)

class HeuristicPolicy:
    PREFERRED={"tool_use":"use_safe_tool","memory_retrieval":"retrieve_relevant_memory","economy_market":"bid_fair","verifier":"request_evidence","swarm_delegation":"delegate_high_rep","safety_gate":"choose_safer_plan","self_repair":"disable_failing_skill","gridworld":"right","reputation_gaming":"decline_suspicious_task","sybil_risk":"quarantine_cluster","colluding_verifier":"multi_verifier_vote"}
    def act(self, observation:Mapping[str,Any], env:FlowEnv)->int:
        label=self.PREFERRED.get(env.env_id, env.action_labels[0])
        return env.action_labels.index(label) if label in env.action_labels else 0

@dataclass
class TabularQPolicy:
    q: dict[str, list[float]] = field(default_factory=dict)
    epsilon: float = 0.1
    seed: int = 0
    def _key(self, observation:Mapping[str,Any])->str: return json.dumps({k:observation.get(k) for k in sorted(observation)}, sort_keys=True, default=str)
    def values(self, observation:Mapping[str,Any], env:FlowEnv)->list[float]:
        key=self._key(observation)
        self.q.setdefault(key, [0.0]*env.action_space.n)
        return self.q[key]
    def act(self, observation:Mapping[str,Any], env:FlowEnv)->int:
        rng=random.Random(self.seed + len(self.q))
        if rng.random() < self.epsilon: return rng.randrange(env.action_space.n)
        values=self.values(observation, env)
        return max(range(len(values)), key=lambda i: values[i])
    def update(self, observation, action:int, reward:float, next_observation, env:FlowEnv, *, alpha:float=0.5, gamma:float=0.9):
        values=self.values(observation, env)
        next_values=self.values(next_observation, env)
        values[action] = values[action] + alpha*(reward + gamma*max(next_values) - values[action])
    def as_record(self): return {"q": self.q, "epsilon": self.epsilon, "seed": self.seed}
    @classmethod
    def from_record(cls, record:Mapping[str,Any])->"TabularQPolicy": return cls(q={str(k):list(v) for k,v in dict(record.get('q',{})).items()}, epsilon=float(record.get('epsilon',0.1)), seed=int(record.get('seed',0)))
