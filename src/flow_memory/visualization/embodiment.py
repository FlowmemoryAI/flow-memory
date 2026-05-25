"""Neural embodiment projection for Mission Control.

This module turns existing local launch/replay artifacts into a compact,
dashboard-facing view of one policy-gated neural-live agent. It is deliberately
local-only: it reads artifacts, reduces visual events, and exposes state for
Mission Control without starting background work or contacting providers.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from flow_memory.neural.gpu_evidence import gpu_evidence_index
from flow_memory.visualization.reducer import reduce_visual_events
from flow_memory.visualization.run_console import get_run_console_run

NEURAL_EMBODIMENT_VERSION = "flow-memory-neural-embodiment-v1"

LOOP_PHASES = (
    "idle",
    "perceiving",
    "predicting",
    "remembering",
    "reasoning",
    "acting",
    "evaluating",
    "learning",
    "denied",
    "completed",
    "failed",
)

GRAPH_NODES: tuple[Mapping[str, str], ...] = (
    {"id": "agent", "label": "Agent", "kind": "agent"},
    {"id": "runtime", "label": "Neural Runtime", "kind": "neural"},
    {"id": "perception", "label": "Perception", "kind": "neural"},
    {"id": "prediction", "label": "Prediction", "kind": "neural"},
    {"id": "memory", "label": "Memory", "kind": "memory"},
    {"id": "planner", "label": "Planner", "kind": "planner"},
    {"id": "policy", "label": "Policy Gate", "kind": "safety"},
    {"id": "action", "label": "Action", "kind": "action"},
    {"id": "evaluation", "label": "Evaluation", "kind": "evaluation"},
    {"id": "learning", "label": "Learning", "kind": "learning"},
    {"id": "supervisor", "label": "Supervisor", "kind": "supervisor"},
    {"id": "gpu", "label": "GPU Evidence", "kind": "evidence"},
)

GRAPH_EDGES: tuple[Mapping[str, str], ...] = (
    {"source": "agent", "target": "runtime", "label": "attach session"},
    {"source": "runtime", "target": "perception", "label": "encode"},
    {"source": "perception", "target": "prediction", "label": "predict"},
    {"source": "prediction", "target": "memory", "label": "retrieve"},
    {"source": "memory", "target": "planner", "label": "remember"},
    {"source": "planner", "target": "policy", "label": "score + gate"},
    {"source": "policy", "target": "action", "label": "allow / deny"},
    {"source": "action", "target": "evaluation", "label": "evaluate"},
    {"source": "evaluation", "target": "learning", "label": "learn"},
    {"source": "supervisor", "target": "agent", "label": "bounded ticks"},
    {"source": "gpu", "target": "runtime", "label": "validation evidence"},
)


def neural_embodiment_state(root: str | Path = ".", run_id: str = "live-agent-supervisor") -> Mapping[str, Any]:
    """Return the dashboard-facing neural embodiment state for a run or fixture."""

    root_path = Path(root).resolve()
    console = get_run_console_run(root_path, run_id)
    run = dict(console.get("run", {})) if isinstance(console.get("run", {}), Mapping) else {}
    payload = _payload_for_console(root_path, console, run)
    events = _events(payload)
    state = _state_from_payload(events, payload)
    neural = _representative_neural_signal(state.get("neural", ()))
    latest_neural = _latest_mapping(state.get("neural", ()))
    supervisor = _latest_mapping(state.get("supervisor", ()))
    safety = _latest_mapping(state.get("safety", ()))
    agent = _agent_for(state, str(run.get("agent_id", "")))
    checkpoint = dict(payload.get("checkpoint_metadata", {})) if isinstance(payload.get("checkpoint_metadata", {}), Mapping) else {}
    gpu = gpu_evidence_status(root_path)
    phase = _phase(run, neural, supervisor, safety)
    policy_state = str(supervisor.get("policy_gate_state") or neural.get("policy_gate_state") or safety.get("decision") or run.get("policy_gate_state") or "applied")
    memory_items = state.get("memory", ())
    memory_item_count = len(memory_items) if isinstance(memory_items, (list, tuple)) else 0
    memory_count = max(_max_int(state.get("neural", ()), "memory_activation_count"), memory_item_count, int(run.get("memory_records_written", 0) or 0))
    learning_ticks = max(_max_int(state.get("neural", ()), "learning_tick_count"), int(run.get("learning_steps", 0) or 0))
    confidence = _clamp(max(_max_float(state.get("neural", ()), "prediction_confidence"), float(run.get("confidence_score", 0.0) or 0.0)))
    risk = _clamp(max(_max_float(state.get("neural", ()), "risk_score"), float(run.get("risk_score", 0.0) or 0.0)))
    action_state = str(neural.get("action_state") or _action_state_from_safety(safety) or "observed")
    embodiment = {
        "schema_version": NEURAL_EMBODIMENT_VERSION,
        "agent_id": str(run.get("agent_id") or agent.get("agent_id", "")),
        "session_id": str(run.get("session_id") or neural.get("session_id", "")),
        "run_id": str(run.get("run_id") or run_id),
        "supervisor_id": str(run.get("supervisor_id") or supervisor.get("supervisor_id", "")),
        "backend": str(run.get("backend") or neural.get("backend", "tiny_torch")),
        "gpu_evidence_status": gpu["status"],
        "gpu_evidence": gpu,
        "current_loop_phase": phase,
        "confidence_score": confidence,
        "risk_score": risk,
        "policy_gate_state": policy_state,
        "memory_activation_count": memory_count,
        "learning_tick_count": learning_ticks,
        "action_state": action_state,
        "heartbeat_state": _heartbeat_state(supervisor, run),
        "neural_runtime_status": str(latest_neural.get("status") or neural.get("status") or run.get("status", "observed")),
        "checkpoint_metadata_ref": str(checkpoint.get("checkpoint_ref", "")),
        "replay_event_index": max(0, len(events) - 1),
        "replay_artifact_path": str(run.get("replay_artifact_path", "")),
        "run_record_path": str(run.get("run_record_path", "")),
        "visual": _visual_metadata(str(run.get("agent_id") or agent.get("agent_id", "")), phase, risk, confidence),
        "loop_phases": LOOP_PHASES,
        "neural_advisory_only": True,
        "policy_authority": "policy_engine_and_approval_gate",
        "local_only": True,
        "no_external_model_calls": True,
        "no_live_provider_calls": True,
        "no_funds_moved": True,
        "no_live_settlement": True,
        "production_ml_claimed": False,
    }
    graph = _graph(embodiment, events)
    return {
        "ok": True,
        "schema_version": NEURAL_EMBODIMENT_VERSION,
        "embodiment": embodiment,
        "graph": graph,
        "events": events,
        "state": state,
        "source_run": run,
        "source": str(console.get("source", "")),
        "warnings": _warnings(gpu["status"]),
    }


def build_neural_embodiment_fixture(
    root: str | Path = ".",
    run_id: str = "live-agent-supervisor",
    out: str | Path = "dashboard/src/mock-data/live-neural-embodiment.json",
) -> Mapping[str, Any]:
    """Write a deterministic neural embodiment replay fixture."""

    root_path = Path(root).resolve()
    output = Path(out)
    if not output.is_absolute():
        output = root_path / output
    payload = dict(neural_embodiment_state(root_path, run_id))
    payload["fixture_id"] = "live-neural-embodiment"
    payload["fixture_label"] = "Live Neural Embodiment"
    payload["fixture_description"] = "3D-ready neural agent embodiment replay with GPU evidence, policy gates, memory activations, learning ticks, and supervisor heartbeat."
    payload["bundle_hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    return {**payload, "fixture_path": _rel(root_path, output)}


def gpu_evidence_status(root: str | Path = ".") -> Mapping[str, Any]:
    """Return a compact, honest GPU evidence status for Mission Control."""

    root_path = Path(root).resolve()
    index = gpu_evidence_index(root_path)
    verified = None
    for record in index.get("runs", ()):  # type: ignore[union-attr]
        if not isinstance(record, Mapping) or not bool(record.get("ok")):
            continue
        summary = dict(record.get("summary", {})) if isinstance(record.get("summary", {}), Mapping) else {}
        if summary.get("skipped"):
            continue
        if summary.get("cuda_available") is True or summary.get("cli_neural_status") == "available":
            verified = summary
            break
    if verified:
        return {
            "status": "verified",
            "run_id": str(verified.get("run_id", "")),
            "gpu_name": str(verified.get("gpu_name", "")),
            "cuda_available": bool(verified.get("cuda_available", False)),
            "cuda_version": str(verified.get("cuda_version", "")),
            "torch_version": str(verified.get("torch_version", "")),
            "pytest_summary": str(verified.get("pytest_summary", "")),
            "neural_backend": str(verified.get("cli_neural_backend", "")),
            "neural_status": str(verified.get("cli_neural_status", "")),
            "source_artifact_sha256": str(verified.get("source_artifact_sha256", "")),
        }
    artifact = root_path / "artifacts" / "incoming" / "flow-memory-cloud-gpu-run-001.tar.gz"
    return {
        "status": "artifact_present_not_verified" if artifact.exists() else "blocked_missing_artifact",
        "run_id": "",
        "gpu_name": "",
        "cuda_available": False,
        "cuda_version": "",
        "torch_version": "",
        "pytest_summary": "",
        "neural_backend": "",
        "neural_status": "",
        "source_artifact_sha256": "",
    }


def _payload_for_console(root: Path, console: Mapping[str, Any], run: Mapping[str, Any]) -> Mapping[str, Any]:
    fixture = dict(console.get("fixture", {})) if isinstance(console.get("fixture", {}), Mapping) else {}
    fixture_path = str(fixture.get("path", ""))
    if fixture_path:
        payload = _read_json(root / fixture_path)
        if payload:
            return payload
    replay_path = str(run.get("replay_artifact_path", ""))
    if replay_path:
        payload = _read_json(_resolve(root, replay_path))
        if payload:
            return payload
    return {}


def _events(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    events = payload.get("events", payload.get("visual_events", ()))
    if isinstance(events, (list, tuple)):
        return tuple(dict(item) for item in events if isinstance(item, Mapping))
    return ()


def _state_from_payload(events: Sequence[Mapping[str, Any]], payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if events:
        return reduce_visual_events(events, provenance=str(payload.get("provenance", "replay"))).as_record()
    state = payload.get("state", {})
    return dict(state) if isinstance(state, Mapping) else {}


def _latest_mapping(items: Any) -> Mapping[str, Any]:
    if isinstance(items, (list, tuple)) and items:
        for item in reversed(items):
            if isinstance(item, Mapping):
                return dict(item)
    return {}

def _representative_neural_signal(items: Any) -> Mapping[str, Any]:
    if not isinstance(items, (list, tuple)) or not items:
        return {}
    candidates = [dict(item) for item in items if isinstance(item, Mapping)]
    if not candidates:
        return {}
    return max(
        candidates,
        key=lambda item: (
            int(item.get("learning_tick_count", 0) or 0),
            int(item.get("memory_activation_count", 0) or 0),
            float(item.get("prediction_confidence", 0.0) or 0.0),
            float(item.get("risk_score", 0.0) or 0.0),
        ),
    )

def _max_int(items: Any, field: str) -> int:
    if not isinstance(items, (list, tuple)):
        return 0
    values = []
    for item in items:
        if isinstance(item, Mapping):
            values.append(int(item.get(field, 0) or 0))
    return max(values, default=0)


def _max_float(items: Any, field: str) -> float:
    if not isinstance(items, (list, tuple)):
        return 0.0
    values = []
    for item in items:
        if isinstance(item, Mapping):
            values.append(float(item.get(field, 0.0) or 0.0))
    return max(values, default=0.0)


def _agent_for(state: Mapping[str, Any], agent_id: str) -> Mapping[str, Any]:
    agents = state.get("agents", ())
    if isinstance(agents, (list, tuple)):
        for agent in agents:
            if isinstance(agent, Mapping) and (not agent_id or agent.get("agent_id") == agent_id):
                return dict(agent)
    return {}


def _phase(run: Mapping[str, Any], neural: Mapping[str, Any], supervisor: Mapping[str, Any], safety: Mapping[str, Any]) -> str:
    raw = str(supervisor.get("current_phase") or neural.get("phase") or run.get("current_phase") or run.get("status") or "idle").lower()
    if str(safety.get("decision", "")).lower() in {"denied", "blocked"}:
        return "denied"
    mapping = {
        "risk_scoring": "reasoning",
        "tick_started": "reasoning",
        "tick_completed": "evaluating",
        "heartbeat": "reasoning",
        "recommended": "acting",
        "learned": "learning",
        "observed": "idle",
    }
    return mapping.get(raw, raw if raw in LOOP_PHASES else "idle")


def _heartbeat_state(supervisor: Mapping[str, Any], run: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "status": str(supervisor.get("status") or run.get("status", "observed")),
        "current_phase": str(supervisor.get("current_phase") or run.get("current_phase", "")),
        "ticks_completed": int(supervisor.get("ticks_completed", run.get("ticks_completed", 0)) or 0),
        "max_ticks": int(supervisor.get("max_ticks", run.get("ticks_requested", 0)) or 0),
        "last_heartbeat_at": str(supervisor.get("last_heartbeat_at") or run.get("last_heartbeat_at", "")),
        "bounded": bool(supervisor.get("bounded", True)),
    }


def _action_state_from_safety(safety: Mapping[str, Any]) -> str:
    decision = str(safety.get("decision", "")).lower()
    if decision in {"blocked", "denied"}:
        return "denied"
    if decision in {"allowed", "approved"}:
        return "allowed"
    return ""


def _visual_metadata(agent_id: str, phase: str, risk: float, confidence: float) -> Mapping[str, Any]:
    seed = int(hashlib.sha256(agent_id.encode("utf-8")).hexdigest()[:8], 16) if agent_id else 0
    x = round(((seed % 9) - 4) * 0.8, 3)
    z = round((((seed // 9) % 9) - 4) * 0.8, 3)
    animation = {
        "idle": "idle_breathe",
        "perceiving": "scan_memory_streams",
        "predicting": "prediction_arc_pulse",
        "remembering": "memory_ribbon_pull",
        "reasoning": "planner_orbit",
        "acting": "action_pulse",
        "evaluating": "evaluation_ring",
        "learning": "learning_tick_glow",
        "denied": "safety_gate_lock",
        "completed": "completed_soft_pulse",
        "failed": "fail_closed_dim",
    }.get(phase, "idle_breathe")
    return {
        "position": [x, 0.0, z],
        "animation_state": animation,
        "node_scale": round(1.0 + confidence * 0.35, 3),
        "risk_halo": round(risk, 3),
        "neural_glow": round(confidence, 3),
        "memory_orbit_count": 3,
        "three_ready": True,
    }


def _graph(embodiment: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    active_phase = str(embodiment.get("current_loop_phase", "idle"))
    active_by_phase = {
        "idle": "agent",
        "perceiving": "perception",
        "predicting": "prediction",
        "remembering": "memory",
        "reasoning": "planner",
        "acting": "action",
        "evaluating": "evaluation",
        "learning": "learning",
        "denied": "policy",
        "completed": "agent",
        "failed": "policy",
    }
    active_node = active_by_phase.get(active_phase, "agent")
    event_names = {str(dict(event.get("payload", {})).get("event", "")) for event in events if isinstance(event.get("payload", {}), Mapping)}
    nodes = []
    for node in GRAPH_NODES:
        node_id = str(node["id"])
        nodes.append(
            {
                **dict(node),
                "active": node_id == active_node,
                "status": _node_status(node_id, embodiment, event_names),
                "source": _node_source(node_id),
            }
        )
    return {
        "nodes": tuple(nodes),
        "edges": GRAPH_EDGES,
        "loop": "perceive -> predict -> remember -> reason -> act -> evaluate -> learn",
        "active_phase": active_phase,
        "policy_gated": True,
        "neural_advisory_only": True,
    }


def _node_status(node_id: str, embodiment: Mapping[str, Any], event_names: set[str]) -> str:
    if node_id == "gpu":
        return str(embodiment.get("gpu_evidence_status", "unknown"))
    if node_id == "policy":
        return str(embodiment.get("policy_gate_state", "applied"))
    if node_id == "supervisor":
        heartbeat = dict(embodiment.get("heartbeat_state", {})) if isinstance(embodiment.get("heartbeat_state", {}), Mapping) else {}
        return str(heartbeat.get("status", "observed"))
    if node_id == "memory":
        return "active" if int(embodiment.get("memory_activation_count", 0) or 0) > 0 else "observed"
    if node_id == "learning":
        return "active" if int(embodiment.get("learning_tick_count", 0) or 0) > 0 or "neural_learning_step_completed" in event_names else "observed"
    return "observed"


def _node_source(node_id: str) -> str:
    return {
        "agent": "AgentProfile / launch run record",
        "runtime": "local neural runtime session",
        "perception": "neural_perception_encoded event",
        "prediction": "neural_prediction_generated event",
        "memory": "memory state / neural memory candidates",
        "planner": "neural_plan_scored event",
        "policy": "PolicyEngine / ApprovalGate visual safety event",
        "action": "policy-gated local action event",
        "evaluation": "agent evaluation / audit event",
        "learning": "neural_learning_step_completed event",
        "supervisor": "live supervisor heartbeat event",
        "gpu": "imported RunPod release evidence",
    }.get(node_id, "visual replay")


def _warnings(gpu_status: str) -> tuple[str, ...]:
    warnings = [
        "neural outputs are advisory and policy-gated",
        "Mission Control shows local runtime/replay telemetry, not AGI or consciousness",
        "no live provider calls, real funds, private keys, broadcasts, or live settlement",
    ]
    if gpu_status == "verified":
        warnings.append("RunPod RTX 4090 evidence is imported and verified for GPU-gated release checks; this is not production ML certification")
    else:
        warnings.append("GPU-gated release remains blocked until verified evidence exists")
    return tuple(warnings)


def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _resolve(root: Path, value: str) -> Path:
    if not value:
        return root / "__missing__"
    path = Path(value)
    return path if path.is_absolute() else root / path


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _clamp(value: float) -> float:
    if value != value:
        return 0.0
    return max(0.0, min(1.0, value))
