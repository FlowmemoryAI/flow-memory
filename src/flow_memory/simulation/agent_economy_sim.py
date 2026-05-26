"""Deterministic offline agent-economy adversarial simulation.

The simulator is a local prototype seam for preflight evidence. It uses no network,
private keys, chain state, or funds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence, cast

from flow_memory.simulation.adversaries import (
    ADVERSARY_RULES,
    COLLUDING_VERIFIER,
    HONEST,
    REPEATED_DISPUTER,
    REPUTATION_FARMER,
    SPAM_BIDDER,
    SYBIL_DUPLICATE,
    UNDERPRICED_FAILED_BIDDER,
)


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    kind: str = HONEST
    quality: float = 1.0
    bid_multiplier: float = 1.0
    identity_fingerprint: str = ""
    allies: tuple[str, ...] = ()

    def as_record(self) -> Mapping[str, Any]:
        return {
            "agent_id": self.agent_id,
            "kind": self.kind,
            "quality": self.quality,
            "bid_multiplier": self.bid_multiplier,
            "identity_fingerprint": self.identity_fingerprint or self.agent_id,
            "allies": self.allies,
        }


@dataclass(frozen=True)
class SimulationResult:
    scenario: str
    events: tuple[Mapping[str, Any], ...]
    reputations: Mapping[str, float]
    balances: Mapping[str, float]

    def as_record(self) -> Mapping[str, Any]:
        return {
            "scenario": self.scenario,
            "events": self.events,
            "reputations": dict(sorted(self.reputations.items())),
            "balances": dict(sorted(self.balances.items())),
            "scope": "local-prototype",
        }


@dataclass
class AgentEconomySimulation:
    agents: Sequence[AgentProfile]
    quality_threshold: float = 0.7
    max_bid_multiplier: float = 1.25
    dispute_limit_per_agent: int = 2
    reputation_farm_window: int = 3
    reputations: dict[str, float] = field(default_factory=dict)
    balances: dict[str, float] = field(default_factory=dict)
    dispute_counts: dict[str, int] = field(default_factory=dict)
    task_index: int = 0
    event_index: int = 0

    def __post_init__(self) -> None:
        for agent in self.agents:
            self.reputations.setdefault(agent.agent_id, 0.0)
            self.balances.setdefault(agent.agent_id, 0.0)

    def run_tasks(self, scenario: str, tasks: Sequence[Mapping[str, Any]]) -> SimulationResult:
        events: list[Mapping[str, Any]] = []
        for task in tasks:
            self.task_index += 1
            task_id = str(task.get("task_id") or f"task-{self.task_index:03d}")
            reward = float(task.get("reward", 10.0))
            requester = str(task.get("requester", "requester"))
            bidders = self._task_agents(task.get("bidders"))
            verifier = self._agent(str(task.get("verifier", requester))) if task.get("verifier") else None
            events.append(self._event(scenario, task_id, "task_created", requester, {"reward": reward}))

            valid_bids: list[tuple[float, AgentProfile]] = []
            for bidder in bidders:
                price = round(reward * bidder.bid_multiplier, 2)
                bid_payload = {"agent": bidder.agent_id, "price": price, "kind": bidder.kind}
                if price > reward * self.max_bid_multiplier:
                    events.append(self._event(scenario, task_id, "bid_rejected", bidder.agent_id, bid_payload | {"reason": "overpriced"}))
                    self.reputations[bidder.agent_id] -= 1.0
                    continue
                if bidder.kind == SPAM_BIDDER and len([event for event in events if event["actor"] == bidder.agent_id and event["type"] == "bid_submitted"]) >= 2:
                    events.append(self._event(scenario, task_id, "bid_rejected", bidder.agent_id, bid_payload | {"reason": "spam"}))
                    self.reputations[bidder.agent_id] -= 0.5
                    continue
                valid_bids.append((price, bidder))
                events.append(self._event(scenario, task_id, "bid_submitted", bidder.agent_id, bid_payload))

            if not valid_bids:
                events.append(self._event(scenario, task_id, "task_unassigned", requester, {}))
                continue

            price, worker = sorted(valid_bids, key=lambda item: (item[0], item[1].agent_id))[0]
            events.append(self._event(scenario, task_id, "task_assigned", requester, {"worker": worker.agent_id, "price": price}))
            accepted = worker.quality >= self.quality_threshold
            if verifier and verifier.kind == COLLUDING_VERIFIER and worker.agent_id in verifier.allies:
                accepted = True
                events.append(self._event(scenario, task_id, "collusion_detected", verifier.agent_id, {"worker": worker.agent_id}))
                self.reputations[verifier.agent_id] -= 4.0
            events.append(self._event(scenario, task_id, "work_submitted", worker.agent_id, {"quality": worker.quality}))
            events.append(self._event(scenario, task_id, "verification", (verifier.agent_id if verifier else requester), {"accepted": accepted}))

            if accepted:
                self.balances[worker.agent_id] += price
                self.reputations[worker.agent_id] += 2.0
                events.append(self._event(scenario, task_id, "settlement", requester, {"worker": worker.agent_id, "amount": price}))
                if worker.kind == REPUTATION_FARMER and self.reputations[worker.agent_id] >= self.reputation_farm_window * 2:
                    events.append(self._event(scenario, task_id, "reputation_farming_detected", worker.agent_id, {"score": self.reputations[worker.agent_id]}))
                    self.reputations[worker.agent_id] -= 3.0
            else:
                self.reputations[worker.agent_id] -= 3.0
                reason = "underpriced_failed" if worker.kind == UNDERPRICED_FAILED_BIDDER else "quality_failed"
                events.append(self._event(scenario, task_id, "dispute_opened", requester, {"worker": worker.agent_id, "reason": reason}))
                self.dispute_counts[worker.agent_id] = self.dispute_counts.get(worker.agent_id, 0) + 1
                if worker.kind == REPEATED_DISPUTER or self.dispute_counts[worker.agent_id] > self.dispute_limit_per_agent:
                    events.append(self._event(scenario, task_id, "repeated_dispute_detected", worker.agent_id, {"count": self.dispute_counts[worker.agent_id]}))
                    self.reputations[worker.agent_id] -= 2.0
                events.append(self._event(scenario, task_id, "slashing", worker.agent_id, {"delta": -3.0}))

        for fingerprint, duplicates in self._duplicate_fingerprints().items():
            if len(duplicates) > 1:
                for agent_id in duplicates:
                    self.reputations[agent_id] -= 2.0
                events.append(self._event(scenario, "identity", "sybil_duplicate_detected", "simulator", {"fingerprint": fingerprint, "agents": tuple(duplicates)}))

        return SimulationResult(scenario, tuple(events), dict(self.reputations), dict(self.balances))

    def _task_agents(self, value: object) -> tuple[AgentProfile, ...]:
        if value is None:
            return tuple(self.agents)
        requested = {str(agent_id) for agent_id in cast(Iterable[object], value)}
        return tuple(agent for agent in self.agents if agent.agent_id in requested)

    def _agent(self, agent_id: str) -> AgentProfile:
        for agent in self.agents:
            if agent.agent_id == agent_id:
                return agent
        rule = ADVERSARY_RULES[HONEST]
        return AgentProfile(agent_id, HONEST, rule.default_quality, rule.default_bid_multiplier)

    def _duplicate_fingerprints(self) -> Mapping[str, tuple[str, ...]]:
        buckets: dict[str, list[str]] = {}
        for agent in self.agents:
            fingerprint = agent.identity_fingerprint or agent.agent_id
            if agent.kind == SYBIL_DUPLICATE:
                buckets.setdefault(fingerprint, []).append(agent.agent_id)
        return {fingerprint: tuple(agent_ids) for fingerprint, agent_ids in buckets.items()}

    def _event(self, scenario: str, task_id: str, event_type: str, actor: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.event_index += 1
        return {
            "event_id": f"sim-{self.event_index:04d}",
            "scenario": scenario,
            "task_id": task_id,
            "type": event_type,
            "actor": actor,
            "payload": dict(payload),
        }


def profile(agent_id: str, kind: str, *, fingerprint: str = "", allies: tuple[str, ...] = ()) -> AgentProfile:
    rule = ADVERSARY_RULES[kind]
    return AgentProfile(agent_id, kind, rule.default_quality, rule.default_bid_multiplier, fingerprint, allies)
