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
                "task_id": record.get("task_id", ""),
                "reputation_delta": record.get("reputation_delta", 0.0),
            }, provenance=provenance))
    return tuple(events)


def economy_receipts_to_visual_events(receipts: Iterable[Mapping[str, Any]], *, provenance: str = "live") -> tuple[VisualEvent, ...]:
    """Convert Economy V3 receipts into lifecycle-level visual edges.

    This preserves the public-alpha payment story in replay data without exposing
    raw funds, private keys, or chain transactions.
    """

    events: list[VisualEvent] = []
    escrow_amount_by_task: dict[str, float] = {}
    assignment_by_task: dict[str, str] = {}
    for receipt in receipts:
        task_id = str(receipt.get("task_id") or "")
        receipt_id = str(receipt.get("receipt_id") or receipt.get("id") or task_id or "economy")
        actor = str(receipt.get("actor") or "")
        receipt_type = str(receipt.get("receipt_type") or receipt.get("type") or "")
        payload = dict(receipt.get("payload", {}))
        if not task_id:
            continue
        if receipt_type == "task_created":
            events.append(visual_event("task", task_id, {
                "task_id": task_id,
                "label": payload.get("title", task_id),
                "status": "created",
                "requester_id": actor,
                "reward": payload.get("reward", 0.0),
            }, provenance=provenance))
        elif receipt_type == "bid_submitted":
            events.append(_edge(receipt_id, actor, task_id, "bid", payload.get("price", 0.0), "submitted", provenance, task_id=task_id))
        elif receipt_type == "task_assigned":
            worker = str(payload.get("agent") or "")
            assignment_by_task[task_id] = worker
            events.append(_edge(receipt_id, actor, worker, "task_assignment", 0.0, "assigned", provenance, task_id=task_id))
        elif receipt_type == "escrow_created":
            amount = float(payload.get("amount", 0.0) or 0.0)
            escrow_amount_by_task[task_id] = amount
            events.append(_edge(receipt_id, actor, assignment_by_task.get(task_id, task_id), "escrow", amount, "locked", provenance, task_id=task_id))
        elif receipt_type == "work_submitted":
            events.append(_edge(receipt_id, actor, task_id, "work_submission", 0.0, "submitted", provenance, task_id=task_id))
        elif receipt_type == "verification":
            status = str(payload.get("status", "verified"))
            events.append(_edge(receipt_id, actor, assignment_by_task.get(task_id, task_id), "verification", 0.0, status, provenance, task_id=task_id))
        elif receipt_type == "settlement":
            events.append(_edge(receipt_id, actor, payload.get("worker", assignment_by_task.get(task_id, task_id)), "settlement", escrow_amount_by_task.get(task_id, 0.0), "settled", provenance, task_id=task_id))
        elif receipt_type == "dispute":
            events.append(_edge(receipt_id, actor, assignment_by_task.get(task_id, task_id), "dispute", 0.0, str(payload.get("status", "open")), provenance, task_id=task_id))
        elif receipt_type == "slashing":
            events.append(_edge(receipt_id, actor, task_id, "slashing", abs(float(payload.get("delta", 0.0) or 0.0)), "slashed", provenance, task_id=task_id, reputation_delta=float(payload.get("delta", 0.0) or 0.0)))
        elif receipt_type == "reputation_update":
            events.append(_edge(receipt_id, task_id, actor, "reputation", float(payload.get("delta", 0.0) or 0.0), "updated", provenance, task_id=task_id, reputation_delta=float(payload.get("delta", 0.0) or 0.0)))
    return tuple(events)


def _edge(edge_id: str, from_id: str, to_id: Any, kind: str, amount: Any, status: str, provenance: str, *, task_id: str = "", reputation_delta: float = 0.0) -> VisualEvent:
    return visual_event("economy", edge_id, {
        "edge_id": edge_id,
        "from_id": from_id,
        "to_id": str(to_id or ""),
        "kind": kind,
        "amount": amount,
        "currency": "LOCAL_CREDITS",
        "status": status,
        "task_id": task_id,
        "reputation_delta": reputation_delta,
    }, provenance=provenance, source_event_id=edge_id)
