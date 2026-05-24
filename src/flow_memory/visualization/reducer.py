"""Reduce visual events into Mission Control state."""
from __future__ import annotations

from typing import Iterable, Mapping, Any

from flow_memory.visualization.events import VisualEvent
from flow_memory.visualization.state import (
    VisualAgentNode,
    VisualAuditTrailItem,
    VisualEconomyEdge,
    VisualMemoryNode,
    VisualNetworkState,
    VisualNeuralSignal,
    VisualRLEpisode,
    VisualRuntimeHealth,
    VisualSafetyGate,
    VisualTaskNode,
)


def reduce_visual_events(events: Iterable[VisualEvent | Mapping[str, Any]], *, provenance: str = "live") -> VisualNetworkState:
    agents: dict[str, VisualAgentNode] = {}
    tasks: dict[str, VisualTaskNode] = {}
    memory: dict[str, VisualMemoryNode] = {}
    economy: dict[str, VisualEconomyEdge] = {}
    neural: dict[str, VisualNeuralSignal] = {}
    rl: dict[str, VisualRLEpisode] = {}
    safety: dict[str, VisualSafetyGate] = {}
    audit: list[VisualAuditTrailItem] = []
    count = 0
    for event in events:
        record = event.as_record() if isinstance(event, VisualEvent) else dict(event)
        payload = dict(record.get("payload", {}))
        event_id = str(record.get("event_id", ""))
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
            task_id = str(payload.get("task_id") or event_id)
            tasks[task_id] = VisualTaskNode(
                task_id=task_id,
                label=str(payload.get("label") or payload.get("title") or task_id),
                status=str(payload.get("status", "observed")),
                requester_id=str(payload.get("requester_id") or payload.get("requester", "")),
                worker_id=str(payload.get("worker_id") or payload.get("worker", "")),
                verifier_id=str(payload.get("verifier_id") or payload.get("verifier", "")),
                reward=float(payload.get("reward", payload.get("amount", 0.0)) or 0.0),
                provenance=event_provenance,
                source_event_id=event_id,
            )
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
            economy[edge_id] = VisualEconomyEdge(
                edge_id=edge_id,
                from_id=str(payload.get("from_id") or payload.get("requester_id") or ""),
                to_id=str(payload.get("to_id") or payload.get("worker_id") or payload.get("verifier_id") or ""),
                kind=str(payload.get("kind", "payment")),
                amount=float(payload.get("amount", 0.0) or 0.0),
                currency=str(payload.get("currency", "LOCAL_CREDITS")),
                status=str(payload.get("status", "observed")),
                provenance=event_provenance,
                source_event_id=event_id,
            )
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
    runtime = VisualRuntimeHealth(status="ok", agents=len(agents), tasks=len(tasks), events=count)
    return VisualNetworkState(
        agents=tuple(agents.values()),
        tasks=tuple(tasks.values()),
        memory=tuple(memory.values()),
        economy=tuple(economy.values()),
        neural=tuple(neural.values()),
        rl=tuple(rl.values()),
        safety=tuple(safety.values()),
        audit=tuple(audit),
        runtime=runtime,
        provenance=provenance,
    )
