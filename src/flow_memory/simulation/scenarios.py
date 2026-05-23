"""Deterministic adversarial economy scenarios."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.simulation.adversaries import (
    COLLUDING_VERIFIER,
    HONEST,
    LOW_QUALITY,
    OVERPRICED_BIDDER,
    REPEATED_DISPUTER,
    REPUTATION_FARMER,
    SPAM_BIDDER,
    SYBIL_DUPLICATE,
    UNDERPRICED_FAILED_BIDDER,
)
from flow_memory.simulation.agent_economy_sim import AgentEconomySimulation, SimulationResult, profile
from flow_memory.simulation.metrics import compute_metrics


def scenario_honest_baseline() -> SimulationResult:
    agents = (profile("honest-worker", HONEST),)
    return AgentEconomySimulation(agents).run_tasks(
        "honest_baseline",
        ({"task_id": "honest-001", "reward": 10.0, "bidders": ("honest-worker",)},),
    )


def scenario_low_quality_and_underpriced() -> SimulationResult:
    agents = (
        profile("underpriced-fail", UNDERPRICED_FAILED_BIDDER),
        profile("quality-fail", LOW_QUALITY),
        profile("honest-worker", HONEST),
    )
    return AgentEconomySimulation(agents).run_tasks(
        "low_quality_underpriced",
        ({"task_id": "quality-001", "reward": 10.0, "bidders": ("underpriced-fail", "quality-fail", "honest-worker")},),
    )


def scenario_colluding_verifier() -> SimulationResult:
    agents = (
        profile("low-quality-ally", LOW_QUALITY),
        profile("colluding-verifier", COLLUDING_VERIFIER, allies=("low-quality-ally",)),
    )
    return AgentEconomySimulation(agents).run_tasks(
        "colluding_verifier",
        ({"task_id": "collude-001", "reward": 10.0, "bidders": ("low-quality-ally",), "verifier": "colluding-verifier"},),
    )


def scenario_spam_and_overpriced_bids() -> SimulationResult:
    agents = (
        profile("spam-bidder", SPAM_BIDDER),
        profile("overpriced-bidder", OVERPRICED_BIDDER),
        profile("honest-worker", HONEST),
    )
    return AgentEconomySimulation(agents).run_tasks(
        "spam_and_overpriced_bids",
        (
            {"task_id": "spam-001", "reward": 10.0, "bidders": ("spam-bidder", "overpriced-bidder", "honest-worker")},
            {"task_id": "spam-002", "reward": 10.0, "bidders": ("spam-bidder", "honest-worker")},
            {"task_id": "spam-003", "reward": 10.0, "bidders": ("spam-bidder", "honest-worker")},
        ),
    )


def scenario_reputation_farming() -> SimulationResult:
    agents = (profile("farmer", REPUTATION_FARMER), profile("honest-worker", HONEST))
    return AgentEconomySimulation(agents).run_tasks(
        "reputation_farming",
        (
            {"task_id": "farm-001", "reward": 3.0, "bidders": ("farmer",)},
            {"task_id": "farm-002", "reward": 3.0, "bidders": ("farmer",)},
            {"task_id": "farm-003", "reward": 3.0, "bidders": ("farmer",)},
        ),
    )


def scenario_repeated_disputes_and_sybil() -> SimulationResult:
    agents = (
        profile("disputer", REPEATED_DISPUTER),
        profile("sybil-a", SYBIL_DUPLICATE, fingerprint="fp-shared"),
        profile("sybil-b", SYBIL_DUPLICATE, fingerprint="fp-shared"),
        profile("honest-worker", HONEST),
    )
    return AgentEconomySimulation(agents).run_tasks(
        "repeated_disputes_and_sybil",
        (
            {"task_id": "dispute-001", "reward": 10.0, "bidders": ("disputer", "honest-worker")},
            {"task_id": "dispute-002", "reward": 10.0, "bidders": ("disputer", "honest-worker")},
            {"task_id": "sybil-001", "reward": 10.0, "bidders": ("sybil-a", "sybil-b", "honest-worker")},
        ),
    )


def run_adversarial_scenarios() -> Mapping[str, Any]:
    results = (
        scenario_honest_baseline(),
        scenario_low_quality_and_underpriced(),
        scenario_colluding_verifier(),
        scenario_spam_and_overpriced_bids(),
        scenario_reputation_farming(),
        scenario_repeated_disputes_and_sybil(),
    )
    metrics = tuple(compute_metrics(result.scenario, result.events, result.reputations).as_record() for result in results)
    return {
        "scope": "local-prototype",
        "scenario_count": len(results),
        "scenarios": tuple(result.as_record() for result in results),
        "metrics": metrics,
    }
