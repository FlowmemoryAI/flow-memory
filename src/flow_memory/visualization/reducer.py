"""Reduce visual events into Mission Control state."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable, Mapping

from flow_memory.visualization.events import VisualEvent
from flow_memory.visualization.state import (
    VisualAgentNode,
    VisualAuditTrailItem,
    VisualEconomyEdge,
    VisualMemoryNode,
    VisualNetworkState,
    VisualNeuralSignal,
    VisualCognitivePrediction,
    VisualComputeMarketSignal,
    VisualRLEpisode,
    VisualRuntimeHealth,
    VisualSupervisorSignal,
    VisualSafetyGate,
    VisualTaskNode,
)

TASK_STATUS_PRECEDENCE: Mapping[str, int] = {
    "observed": 0,
    "open": 5,
    "created": 10,
    "bid": 15,
    "bid_submitted": 20,
    "submitted_bid": 20,
    "assigned": 30,
    "escrow": 35,
    "escrowed": 40,
    "locked": 40,
    "submitted": 45,
    "work_submitted": 50,
    "verifying": 60,
    "verification": 60,
    "verified": 70,
    "rejected": 75,
    "disputed": 80,
    "settled": 90,
    "slashed": 100,
}

TASK_TERMINAL_STATUSES = frozenset({"settled", "slashed"})
TASK_TERMINAL_OVERRIDE_STATUSES = frozenset({"disputed", "slashed"})

ECONOMY_KIND_TO_TASK_STATUS: Mapping[str, str] = {
    "bid": "bid_submitted",
    "task_assignment": "assigned",
    "escrow": "escrowed",
    "work_submission": "work_submitted",
    "verification": "verified",
    "settlement": "settled",
    "payment": "settled",
    "dispute": "disputed",
    "slashing": "slashed",
}

ECONOMY_STATUS_PRECEDENCE: Mapping[str, int] = {
    "observed": 0,
    "submitted": 20,
    "assigned": 30,
    "locked": 40,
    "verified": 70,
    "open": 80,
    "disputed": 80,
    "settled": 90,
    "slashed": 100,
    "updated": 100,
}


def reduce_visual_events(events: Iterable[VisualEvent | Mapping[str, Any]], *, provenance: str = "live") -> VisualNetworkState:
    agents: dict[str, VisualAgentNode] = {}
    tasks: dict[str, VisualTaskNode] = {}
    memory: dict[str, VisualMemoryNode] = {}
    economy: dict[str, VisualEconomyEdge] = {}
    neural: dict[str, VisualNeuralSignal] = {}
    cognitive: dict[str, VisualCognitivePrediction] = {}
    compute: dict[str, VisualComputeMarketSignal] = {}
    supervisor: dict[str, VisualSupervisorSignal] = {}
    rl: dict[str, VisualRLEpisode] = {}
    safety: dict[str, VisualSafetyGate] = {}
    audit: list[VisualAuditTrailItem] = []
    ignored_regressions: list[str] = []
    count = 0

    for event in events:
        record = event.as_record() if isinstance(event, VisualEvent) else dict(event)
        payload = dict(record.get("payload", {}))
        event_id = str(record.get("event_id", ""))
        source_event_id = str(record.get("source_event_id", "") or payload.get("source_event_id", ""))
        event_type = str(record.get("event_type", ""))
        event_provenance = str(record.get("provenance", provenance))
        count += 1

        if event_type == "agent":
            agent_id = str(payload.get("agent_id") or payload.get("did") or payload.get("identity") or event_id)
            agents[agent_id] = VisualAgentNode(
                agent_id=agent_id,
                label=str(payload.get("label") or payload.get("name") or agent_id),
                role=str(payload.get("role", "agent")),
                status=str(payload.get("status", "idle")),
                reputation=float(payload.get("reputation", 0.0) or 0.0),
                capabilities=tuple(str(item) for item in payload.get("capabilities", ())),
                provenance=event_provenance,
                source_event_id=event_id,
            )
        elif event_type == "task":
            candidate = _task_from_payload(payload, event_id=event_id, provenance=event_provenance)
            _merge_task(tasks, candidate, source_event_id=source_event_id, ignored_regressions=ignored_regressions)
        elif event_type == "memory":
            memory_id = str(payload.get("memory_id") or event_id)
            memory[memory_id] = VisualMemoryNode(
                memory_id=memory_id,
                agent_id=str(payload.get("agent_id", "")),
                kind=str(payload.get("kind", "episode")),
                summary=str(payload.get("summary") or payload.get("text") or "memory event"),
                importance=float(payload.get("importance", 0.0) or 0.0),
                provenance=event_provenance,
                source_event_id=event_id,
            )
        elif event_type == "economy":
            edge_id = str(payload.get("edge_id") or event_id)
            candidate = VisualEconomyEdge(
                edge_id=edge_id,
                from_id=str(payload.get("from_id") or payload.get("requester_id") or ""),
                to_id=str(payload.get("to_id") or payload.get("worker_id") or payload.get("verifier_id") or ""),
                kind=str(payload.get("kind", "payment")),
                amount=float(payload.get("amount", 0.0) or 0.0),
                currency=str(payload.get("currency", "LOCAL_CREDITS")),
                status=str(payload.get("status", "observed")),
                provenance=event_provenance,
                source_event_id=event_id,
                task_id=str(payload.get("task_id", "")),
                reputation_delta=float(payload.get("reputation_delta", 0.0) or 0.0),
            )
            _merge_economy_edge(economy, candidate, ignored_regressions=ignored_regressions)
            _advance_task_from_economy(tasks, candidate, ignored_regressions=ignored_regressions)
        elif event_type == "neural":
            signal_id = str(payload.get("signal_id") or event_id)
            neural[signal_id] = VisualNeuralSignal(
                signal_id=signal_id,
                agent_id=str(payload.get("agent_id", "")),
                backend=str(payload.get("backend", "none")),
                status=str(payload.get("status", "observed")),
                plan_score=float(payload.get("plan_score", 0.0) or 0.0),
                risk_score=float(payload.get("risk_score", 0.0) or 0.0),
                surprise_score=float(payload.get("surprise_score", 0.0) or 0.0),
                session_id=str(payload.get("session_id", "")),
                phase=str(payload.get("phase", "")),
                prediction_confidence=float(payload.get("prediction_confidence", 0.0) or 0.0),
                uncertainty=float(payload.get("uncertainty", 0.0) or 0.0),
                learning_tick_count=int(payload.get("learning_tick_count", 0) or 0),
                memory_activation_count=int(payload.get("memory_activation_count", 0) or 0),
                action_state=str(payload.get("action_state", "")),
                policy_gate_state=str(payload.get("policy_gate_state", "")),
                provenance=event_provenance,
                source_event_id=event_id,
            )
        elif event_type == "cognitive":
            prediction = dict(payload.get("prediction", {})) if isinstance(payload.get("prediction", {}), Mapping) else {}
            actual = dict(payload.get("actual_result", {})) if isinstance(payload.get("actual_result", {}), Mapping) else {}
            prediction_id = str(payload.get("prediction_id") or prediction.get("prediction_id") or event_id)
            cognitive[prediction_id] = VisualCognitivePrediction(
                prediction_id=prediction_id,
                agent_id=str(payload.get("agent_id") or prediction.get("agent_id", "")),
                goal=str(payload.get("goal") or prediction.get("goal", "")),
                chosen_action=str(payload.get("chosen_action") or prediction.get("chosen_action", "")),
                predicted_outcome=str(payload.get("predicted_outcome") or prediction.get("predicted_outcome", "")),
                actual_result=str(payload.get("actual_summary") or actual.get("output") or actual.get("reason") or actual.get("success", "")),
                confidence=float(payload.get("confidence", prediction.get("confidence", 0.0)) or 0.0),
                prediction_error=float(payload.get("prediction_error", 0.0) or 0.0),
                success=bool(payload.get("success", False)),
                lesson=str(payload.get("lesson", "")),
                future_policy=str(payload.get("future_policy", "")),
                provenance=event_provenance,
                source_event_id=event_id,
            )
        elif event_type == "compute":
            signal_id = str(payload.get("signal_id") or event_id)
            compute[signal_id] = VisualComputeMarketSignal(
                signal_id=signal_id,
                agent_id=str(payload.get("agent_id", "")),
                task_id=str(payload.get("task_id", "")),
                event=str(payload.get("event", "observed")),
                status=str(payload.get("status", "observed")),
                provider_id=str(payload.get("provider_id", "")),
                route_id=str(payload.get("route_id", "")),
                quote_total=float(payload.get("quote_total", payload.get("total_cost", 0.0)) or 0.0),
                payment_rail=str(payload.get("payment_rail", "local_credits")),
                dry_run_only=bool(payload.get("dry_run_only", True)),
                no_funds_moved=bool(payload.get("no_funds_moved", True)),
                provenance=event_provenance,
                source_event_id=event_id,
            )
        elif event_type == "supervisor":
            signal_id = str(payload.get("signal_id") or event_id)
            supervisor[signal_id] = VisualSupervisorSignal(
                signal_id=signal_id,
                supervisor_id=str(payload.get("supervisor_id", "")),
                run_id=str(payload.get("run_id", "")),
                parent_run_id=str(payload.get("parent_run_id", "")),
                agent_id=str(payload.get("agent_id", "")),
                session_id=str(payload.get("session_id", "")),
                backend=str(payload.get("backend", "tiny_torch")),
                status=str(payload.get("status", "observed")),
                current_phase=str(payload.get("current_phase", "")),
                ticks_completed=int(payload.get("ticks_completed", payload.get("tick", 0)) or 0),
                max_ticks=int(payload.get("max_ticks", 0) or 0),
                policy_gate_state=str(payload.get("policy_gate_state", "")),
                last_heartbeat_at=str(payload.get("last_heartbeat_at", "")),
                bounded=bool(payload.get("bounded", True)),
                provenance=event_provenance,
                source_event_id=event_id,
            )
        elif event_type == "rl":
            episode_id = str(payload.get("episode_id") or event_id)
            rl[episode_id] = VisualRLEpisode(
                episode_id=episode_id,
                agent_id=str(payload.get("agent_id", "")),
                env_id=str(payload.get("env_id", "unknown")),
                mean_reward=float(payload.get("mean_reward", 0.0) or 0.0),
                success_rate=float(payload.get("success_rate", 0.0) or 0.0),
                safety_violation_rate=float(payload.get("safety_violation_rate", 0.0) or 0.0),
                policy=str(payload.get("policy", "local_tabular")),
                provenance=event_provenance,
                source_event_id=event_id,
            )
        elif event_type == "safety":
            gate_id = str(payload.get("gate_id") or event_id)
            safety[gate_id] = VisualSafetyGate(
                gate_id=gate_id,
                agent_id=str(payload.get("agent_id", "")),
                decision=str(payload.get("decision", "observed")),
                risk_level=str(payload.get("risk_level", "low")),
                requires_approval=bool(payload.get("requires_approval", False)),
                reason=str(payload.get("reason", "")),
                provenance=event_provenance,
                source_event_id=event_id,
            )
        audit.append(VisualAuditTrailItem(event_id or f"audit-{count}", event_type or "unknown", str(record.get("source", "unknown")), f"{event_type or 'event'} observed", True, event_provenance, event_id))

    warnings = tuple(f"ignored {len(ignored_regressions)} visual state regression event(s)" for _ in (0,) if ignored_regressions)
    runtime = VisualRuntimeHealth(status="ok", agents=len(agents), tasks=len(tasks), events=count, warnings=warnings, ignored_regressions=tuple(ignored_regressions))
    return VisualNetworkState(
        agents=tuple(agents.values()),
        tasks=tuple(tasks.values()),
        memory=tuple(memory.values()),
        economy=tuple(economy.values()),
        neural=tuple(neural.values()),
        cognitive=tuple(cognitive.values()),
        compute=tuple(compute.values()),
        supervisor=tuple(supervisor.values()),
        rl=tuple(rl.values()),
        safety=tuple(safety.values()),
        audit=tuple(audit),
        runtime=runtime,
        provenance=provenance,
    )


def _task_from_payload(payload: Mapping[str, Any], *, event_id: str, provenance: str) -> VisualTaskNode:
    task_id = str(payload.get("task_id") or event_id)
    ignored = payload.get("ignored_regressions", ())
    return VisualTaskNode(
        task_id=task_id,
        label=str(payload.get("label") or payload.get("title") or task_id),
        status=_normalize_task_status(str(payload.get("status", "observed"))),
        requester_id=str(payload.get("requester_id") or payload.get("requester", "")),
        worker_id=str(payload.get("worker_id") or payload.get("worker", "")),
        verifier_id=str(payload.get("verifier_id") or payload.get("verifier", "")),
        reward=float(payload.get("reward", payload.get("amount", 0.0)) or 0.0),
        provenance=provenance,
        source_event_id=event_id,
        ignored_regressions=tuple(str(item) for item in ignored) if isinstance(ignored, (list, tuple)) else (),
    )


def _merge_task(tasks: dict[str, VisualTaskNode], candidate: VisualTaskNode, *, source_event_id: str, ignored_regressions: list[str]) -> None:
    existing = tasks.get(candidate.task_id)
    if existing is None:
        tasks[candidate.task_id] = candidate
        return
    if _task_transition_allowed(existing.status, candidate.status, source_event_id=source_event_id):
        tasks[candidate.task_id] = _merge_task_fields(existing, candidate)
        return
    ignored_regressions.append(f"task:{candidate.task_id}:{existing.status}->{candidate.status}:{candidate.source_event_id}")
    tasks[candidate.task_id] = replace(existing, ignored_regressions=existing.ignored_regressions + (ignored_regressions[-1],))


def _merge_task_fields(existing: VisualTaskNode, candidate: VisualTaskNode) -> VisualTaskNode:
    return VisualTaskNode(
        task_id=existing.task_id,
        label=candidate.label or existing.label,
        status=candidate.status,
        requester_id=candidate.requester_id or existing.requester_id,
        worker_id=candidate.worker_id or existing.worker_id,
        verifier_id=candidate.verifier_id or existing.verifier_id,
        reward=candidate.reward or existing.reward,
        provenance=candidate.provenance or existing.provenance,
        source_event_id=candidate.source_event_id or existing.source_event_id,
        ignored_regressions=existing.ignored_regressions + candidate.ignored_regressions,
    )


def _task_transition_allowed(existing_status: str, candidate_status: str, *, source_event_id: str) -> bool:
    existing = _normalize_task_status(existing_status)
    candidate = _normalize_task_status(candidate_status)
    if existing in TASK_TERMINAL_STATUSES:
        if existing == "settled" and candidate in TASK_TERMINAL_OVERRIDE_STATUSES and source_event_id:
            return True
        return candidate == existing
    return _task_rank(candidate) >= _task_rank(existing)


def _advance_task_from_economy(tasks: dict[str, VisualTaskNode], edge: VisualEconomyEdge, *, ignored_regressions: list[str]) -> None:
    if not edge.task_id:
        return
    status = _status_from_economy_edge(edge)
    if not status:
        return
    existing = tasks.get(edge.task_id)
    base = existing or VisualTaskNode(
        task_id=edge.task_id,
        label=edge.task_id,
        status="observed",
        requester_id=edge.from_id,
        worker_id=edge.to_id if edge.to_id != edge.task_id else "",
        reward=edge.amount if edge.kind.lower() in {"bid", "escrow", "settlement", "payment"} else 0.0,
        provenance=edge.provenance,
        source_event_id=edge.source_event_id,
    )
    worker_id = edge.to_id if edge.to_id and edge.to_id != edge.task_id else base.worker_id
    reward = base.reward or (edge.amount if edge.kind.lower() in {"bid", "escrow", "settlement", "payment"} else 0.0)
    candidate = replace(base, status=status, worker_id=worker_id, reward=reward, source_event_id=edge.source_event_id, provenance=edge.provenance)
    _merge_task(tasks, candidate, source_event_id=edge.source_event_id, ignored_regressions=ignored_regressions)


def _merge_economy_edge(economy: dict[str, VisualEconomyEdge], candidate: VisualEconomyEdge, *, ignored_regressions: list[str]) -> None:
    existing = economy.get(candidate.edge_id)
    if existing is None:
        economy[candidate.edge_id] = candidate
        return
    if _economy_rank(candidate) >= _economy_rank(existing):
        economy[candidate.edge_id] = candidate
        return
    ignored_regressions.append(f"economy:{candidate.edge_id}:{existing.kind}/{existing.status}->{candidate.kind}/{candidate.status}:{candidate.source_event_id}")


def _status_from_economy_edge(edge: VisualEconomyEdge) -> str:
    kind = edge.kind.lower()
    if kind == "verification" and edge.status.lower() not in {"verified", "accepted", "settled"}:
        return "verifying"
    return ECONOMY_KIND_TO_TASK_STATUS.get(kind, "")


def _task_rank(status: str) -> int:
    return TASK_STATUS_PRECEDENCE.get(_normalize_task_status(status), 0)


def _economy_rank(edge: VisualEconomyEdge) -> int:
    kind_rank = TASK_STATUS_PRECEDENCE.get(ECONOMY_KIND_TO_TASK_STATUS.get(edge.kind.lower(), "observed"), 0)
    status_rank = ECONOMY_STATUS_PRECEDENCE.get(edge.status.lower(), 0)
    return max(kind_rank, status_rank)


def _normalize_task_status(status: str) -> str:
    normalized = status.strip().lower().replace("-", "_") or "observed"
    if normalized == "locked":
        return "escrowed"
    if normalized == "submitted":
        return "work_submitted"
    if normalized == "accepted":
        return "verified"
    return normalized
