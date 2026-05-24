"""Economy-to-visual telemetry adapter."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from flow_memory.visualization.events import VisualEvent, visual_event


def economy_records_to_visual_events(records: Iterable[Mapping[str, Any]], *, provenance: str = "live") -> tuple[VisualEvent, ...]:
    events: list[VisualEvent] = []
    for record in records:
        if "task_id" in record:
            events.append(visual_event("task", str(record.get("task_id")), {
                "task_id": record.get("task_id"),
                "label": record.get("title") or record.get("task") or record.get("task_id"),
                "status": record.get("status", "observed"),
                "requester_id": record.get("requester") or record.get("requester_id", ""),
                "worker_id": record.get("worker") or record.get("worker_id", ""),
                "verifier_id": record.get("verifier") or record.get("verifier_id", ""),
                "reward": record.get("reward", record.get("amount", 0.0)),
            }, provenance=provenance))
        if "amount" in record or "worker_net_amount" in record:
            events.append(visual_event("economy", str(record.get("entry_id") or record.get("escrow_id") or record.get("task_id", "economy")), {
                "edge_id": record.get("entry_id") or record.get("escrow_id") or record.get("task_id"),
                "from_id": record.get("requester_id") or record.get("counterparty_id") or record.get("requester", ""),
                "to_id": record.get("worker_id") or record.get("verifier_id") or record.get("account_id", ""),
                "kind": record.get("entry_type") or record.get("kind", "payment"),
                "amount": record.get("amount", record.get("worker_net_amount", 0.0)),
                "currency": record.get("currency", "LOCAL_CREDITS"),
                "status": record.get("status", "observed"),
            }, provenance=provenance))
    return tuple(events)
