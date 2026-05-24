"""Compute Market visual telemetry adapters."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.visualization.events import VisualEvent, visual_event


def compute_record_to_visual_events(record: Mapping[str, Any], *, agent_id: str = "", provenance: str = "live") -> tuple[VisualEvent, ...]:
    events: list[VisualEvent] = []
    decision = dict(record.get("decision", {}))
    task = dict(record.get("task", decision.get("task", {})))
    quote = dict(record.get("quote", decision.get("quote", {})))
    payment = dict(record.get("payment_intent", {}))
    settlement = dict(record.get("settlement_simulation", {}))
    memory = dict(record.get("economic_memory", {}))
    base = {
        "agent_id": agent_id,
        "task_id": str(task.get("task_id", memory.get("task_id", ""))),
        "provider_id": str(memory.get("provider_id", quote.get("provider_id", ""))),
        "route_id": str(memory.get("route_id", quote.get("route_id", ""))),
        "quote_total": float(quote.get("total_cost", memory.get("total_cost", 0.0)) or 0.0),
        "payment_rail": str(payment.get("rail", "local_credits")),
        "dry_run_only": True,
        "no_funds_moved": True,
    }
    lifecycle = (
        ("compute_plan_requested", record.get("status", "planned")),
        ("quote_generated", "quoted" if quote else "skipped"),
        ("route_decision_selected", decision.get("status", record.get("status", "observed"))),
        ("capacity_reservation_simulated", "simulated" if record.get("reservation") else "skipped"),
        ("payment_plan_generated", payment.get("status", "dry_run_planned") if payment else "skipped"),
        ("settlement_simulated", settlement.get("status", "simulated") if settlement else "skipped"),
        ("economic_memory_record_written", "written" if memory else "skipped"),
    )
    if not record.get("ok", False):
        lifecycle = (("policy_denied_fail_closed", str(record.get("reason", "denied"))),)
    for event_name, status in lifecycle:
        events.append(visual_event("compute", base["task_id"] or agent_id or "compute-market", {**base, "event": event_name, "status": str(status)}, provenance=provenance, source_event_id=str(record.get("record_id", ""))))
    return tuple(events)
