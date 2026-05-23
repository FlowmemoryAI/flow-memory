"""Metrics for deterministic offline economy simulations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class EconomyMetrics:
    scenario: str
    task_count: int
    settled_count: int
    slashing_count: int
    dispute_count: int
    rejected_bid_count: int
    detection_count: int
    collusion_detected: int
    sybil_duplicates_detected: int
    reputation_farming_detected: int
    repeated_disputes_detected: int
    total_paid: float
    min_reputation: float
    max_reputation: float

    def as_record(self) -> Mapping[str, Any]:
        return {
            "scenario": self.scenario,
            "task_count": self.task_count,
            "settled_count": self.settled_count,
            "slashing_count": self.slashing_count,
            "dispute_count": self.dispute_count,
            "rejected_bid_count": self.rejected_bid_count,
            "detection_count": self.detection_count,
            "collusion_detected": self.collusion_detected,
            "sybil_duplicates_detected": self.sybil_duplicates_detected,
            "reputation_farming_detected": self.reputation_farming_detected,
            "repeated_disputes_detected": self.repeated_disputes_detected,
            "total_paid": self.total_paid,
            "min_reputation": self.min_reputation,
            "max_reputation": self.max_reputation,
            "scope": "local-prototype",
        }


def compute_metrics(scenario: str, events: Iterable[Mapping[str, Any]], reputations: Mapping[str, float]) -> EconomyMetrics:
    materialized = tuple(events)
    event_types = tuple(str(event.get("type")) for event in materialized)
    task_ids = {str(event.get("task_id")) for event in materialized if str(event.get("task_id")) not in {"identity", "None"}}
    total_paid = 0.0
    for event in materialized:
        if event.get("type") == "settlement":
            payload = event.get("payload", {})
            if isinstance(payload, Mapping):
                total_paid += float(payload.get("amount", 0.0))
    values = tuple(float(value) for value in reputations.values()) or (0.0,)
    return EconomyMetrics(
        scenario=scenario,
        task_count=len(task_ids),
        settled_count=event_types.count("settlement"),
        slashing_count=event_types.count("slashing"),
        dispute_count=event_types.count("dispute_opened"),
        rejected_bid_count=event_types.count("bid_rejected"),
        detection_count=sum(1 for event_type in event_types if event_type.endswith("_detected")),
        collusion_detected=event_types.count("collusion_detected"),
        sybil_duplicates_detected=event_types.count("sybil_duplicate_detected"),
        reputation_farming_detected=event_types.count("reputation_farming_detected"),
        repeated_disputes_detected=event_types.count("repeated_dispute_detected"),
        total_paid=round(total_paid, 2),
        min_reputation=min(values),
        max_reputation=max(values),
    )
