"""High-level local launchpad for live neural Flow Memory agents.

The launchpad is a local/public-alpha workflow. It creates a policy-gated
AgentProfile, attaches it to a deterministic neural live runtime session, runs a
small number of local agent-loop ticks, emits Mission Control visual telemetry,
and writes replay/evidence metadata. It never calls external providers, moves
funds, broadcasts transactions, or claims GPU validation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from flow_memory.agents.neural_binding import AgentNeuralBinding
from flow_memory.agents.profile import AgentProfile, RiskBudget
from flow_memory.agents.runner import AgentRunner
from flow_memory.flowlang.parser import parse_flowlang, parse_flowlang_file
from flow_memory.ir.agent_adapter import agent_profile_from_ir
from flow_memory.neural.live import NeuralRuntimeManager
from flow_memory.visualization.events import VISUAL_SCHEMA_VERSION, VisualEvent
from flow_memory.visualization.reducer import reduce_visual_events
from flow_memory.launch_operations import upsert_run_from_launch_payload


@dataclass(frozen=True)
class LaunchTemplate:
    name: str
    description: str
    goal: str
    autonomy_mode: str
    capabilities: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    allowed_skills: tuple[str, ...]
    neural: Mapping[str, Any]
    memory: Mapping[str, Any]
    compute: Mapping[str, Any]
    risk_budget: RiskBudget = RiskBudget(max_risk_level="medium", max_spend=0.0)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "goal": self.goal,
            "autonomy_mode": self.autonomy_mode,
            "capabilities": self.capabilities,
            "allowed_tools": self.allowed_tools,
            "allowed_skills": self.allowed_skills,
            "neural": dict(self.neural),
            "memory": dict(self.memory),
            "compute": dict(self.compute),
            "risk_budget": self.risk_budget.as_record(),
            "local_only": True,
            "no_external_calls": True,
        }


LAUNCH_TEMPLATES: Mapping[str, LaunchTemplate] = {
    "live-research": LaunchTemplate(
        name="live-research",
        description="Policy-gated local research agent with neural perception/prediction/scoring telemetry.",
        goal="inspect local repo status and summarize project state",
        autonomy_mode="supervised",
        capabilities=("local_reasoning", "memory", "neural_advisory"),
        allowed_tools=("respond", "observe_environment"),
        allowed_skills=(),
        neural={
            "enabled": True,
            "backend": "tiny_torch",
            "live_mode": True,
            "learning_enabled": True,
            "seed": 1337,
            "model_profile": "local-small",
            "perception_streams": ("text", "events", "memory"),
            "plan_scoring_enabled": True,
            "risk_scoring_enabled": True,
            "memory_retrieval_enabled": True,
            "policy_fallback": "allow_non_neural",
            "telemetry_enabled": True,
        },
        memory={"episodic": True, "semantic": True, "procedural": True},
        compute={},
    ),
    "memory-scout": LaunchTemplate(
        name="memory-scout",
        description="Local memory retrieval scout with neural memory candidate telemetry.",
        goal="retrieve and summarize relevant memory records",
        autonomy_mode="supervised",
        capabilities=("memory", "local_reasoning", "neural_memory_retrieval"),
        allowed_tools=("respond",),
        allowed_skills=(),
        neural={
            "enabled": True,
            "backend": "tiny_torch",
            "live_mode": True,
            "learning_enabled": True,
            "seed": 2026,
            "model_profile": "local-memory-scout",
            "perception_streams": ("text", "memory"),
            "memory_retrieval_enabled": True,
            "policy_fallback": "allow_non_neural",
            "telemetry_enabled": True,
        },
        memory={"episodic": True, "semantic": True, "procedural": True, "working_capacity": 9},
        compute={},
    ),
    "market-observer": LaunchTemplate(
        name="market-observer",
        description="Dry-run Compute Market observer that simulates route choice without live providers or settlement.",
        goal="simulate compute market routing and explain the selected local route",
        autonomy_mode="supervised",
        capabilities=("local_reasoning", "compute_market", "neural_advisory"),
        allowed_tools=("respond",),
        allowed_skills=(),
        neural={
            "enabled": True,
            "backend": "tiny_torch",
            "live_mode": True,
            "learning_enabled": True,
            "seed": 4242,
            "model_profile": "local-market-observer",
            "perception_streams": ("text", "events", "memory"),
            "plan_scoring_enabled": True,
            "risk_scoring_enabled": True,
            "policy_fallback": "allow_non_neural",
            "telemetry_enabled": True,
        },
        memory={"economic": True, "episodic": True, "semantic": True},
        compute={
            "enabled": True,
            "model": "small-general",
            "expected_input_tokens": 1000,
            "expected_output_tokens": 400,
            "budget_policy": {
                "max_total_cost": 0.01,
                "max_quote": 0.01,
                "strategy": "cheapest_eligible",
                "dry_run_required": True,
                "payment_rail": "local_credits",
            },
        },
    ),
    "mission-control-demo": LaunchTemplate(
        name="mission-control-demo",
        description="Rich replay demo showing neural, memory, policy, and local action phases for Mission Control.",
        goal="emit a rich local Mission Control replay for a neural live agent",
        autonomy_mode="supervised",
        capabilities=("local_reasoning", "memory", "neural_advisory", "mission_control"),
        allowed_tools=("respond", "observe_environment"),
        allowed_skills=(),
        neural={
            "enabled": True,
            "backend": "tiny_torch",
            "live_mode": True,
            "learning_enabled": True,
            "seed": 9001,
            "model_profile": "local-mission-control-demo",
            "perception_streams": ("text", "events", "memory"),
            "plan_scoring_enabled": True,
            "risk_scoring_enabled": True,
            "memory_retrieval_enabled": True,
            "policy_fallback": "allow_non_neural",
            "telemetry_enabled": True,
        },
        memory={"episodic": True, "semantic": True, "procedural": True, "working_capacity": 12},
        compute={},
    ),
}


def launch_template_names() -> tuple[str, ...]:
    return tuple(sorted(LAUNCH_TEMPLATES))


def get_launch_template(name: str) -> LaunchTemplate:
    try:
        return LAUNCH_TEMPLATES[name]
    except KeyError as exc:
        raise ValueError(f"unknown launch template: {name}") from exc


def launch_templates_manifest() -> Mapping[str, Any]:
    return {"templates": tuple(template.as_record() for template in LAUNCH_TEMPLATES.values())}


def run_live_agent_launch(
    *,
    template: str = "live-research",
    flow_path: str | Path | None = None,
    flow_source: str = "",
    goal: str = "",
    backend: str = "tiny_torch",
    ticks: int = 5,
    emit_visual: bool = True,
    root: str | Path = ".",
    artifact_path: str | Path | None = None,
    write_artifact: bool = True,
    write_checkpoint: bool = True,
    write_run_record: bool = True,
) -> Mapping[str, Any]:
    if ticks < 1:
        raise ValueError("ticks must be >= 1")
    root_path = Path(root).resolve()
    selected_template = get_launch_template(template)
    requested_goal = goal or selected_template.goal
    run_id = _stable_id("live_agent", template, str(flow_path or ""), flow_source, requested_goal, backend, str(ticks))
    session_id = _stable_id("neural_session", run_id)
    profile = _profile_for_launch(
        selected_template,
        run_id=run_id,
        session_id=session_id,
        backend=backend,
        goal=requested_goal,
        flow_path=flow_path,
        flow_source=flow_source,
    )

    manager = NeuralRuntimeManager()
    neural_binding = AgentNeuralBinding()
    neural_binding.live_runtime = manager
    runner = AgentRunner(profile, neural=neural_binding)
    session = manager.create_session(profile.agent_id, profile.neural_config)

    events: list[VisualEvent] = []
    if emit_visual:
        events.extend(_initial_events(run_id, profile, session.as_record(), selected_template))

    counts = {
        "perceptions_encoded": 0,
        "predictions_generated": 0,
        "plans_scored": 0,
        "risks_scored": 0,
        "actions_allowed": 0,
        "actions_denied": 0,
        "learning_steps": 0,
    }
    tick_results: list[Mapping[str, Any]] = []
    checkpoint_metadata: Mapping[str, Any] = {}
    checkpoint_metadata_path = ""

    for tick in range(1, ticks + 1):
        tick_goal = requested_goal if tick == 1 else f"{requested_goal} (local tick {tick})"
        result = runner.run_cycle(tick_goal)
        output = dict(result.output)
        neural = dict(output.get("neural", {})) if isinstance(output.get("neural", {}), Mapping) else {}
        live_step = dict(neural.get("live_step", {})) if isinstance(neural.get("live_step", {}), Mapping) else {}
        policy_allowed = bool(result.accepted) and not bool(result.requires_approval)
        counts["perceptions_encoded"] += 1 if dict(live_step.get("perception", {})).get("encoded") else 0
        counts["predictions_generated"] += 1 if dict(live_step.get("prediction", {})).get("prediction_id") else 0
        counts["plans_scored"] += 1 if "plan_score" in live_step else 0
        counts["risks_scored"] += 1 if "risk_score" in live_step else 0
        counts["actions_allowed"] += 1 if policy_allowed else 0
        counts["actions_denied"] += 0 if policy_allowed else 1
        if emit_visual:
            events.extend(_tick_events(run_id, tick, profile, result.as_record(), live_step, policy_allowed=policy_allowed))
        if bool(profile.neural_config.get("learning_enabled", False)):
            learning = manager.learn(session.session_id, {"goal": tick_goal, "tick": tick, "accepted": result.accepted})
            runner.memory.write("neural_learning_update", dict(learning))
            if learning.get("status") == "learned":
                counts["learning_steps"] += 1
            if emit_visual:
                events.append(_event(run_id, tick, 90, "neural", profile.agent_id, _neural_payload(profile, session.session_id, learning, phase="learning", event="neural_learning_step_completed")))
        tick_results.append({
            "tick": tick,
            "accepted": result.accepted,
            "requires_approval": result.requires_approval,
            "neural_status": neural.get("status", live_step.get("status", "observed")),
            "policy_allowed": policy_allowed,
            "memory_records_total": len(runner.memory.records),
        })

    if write_checkpoint:
        checkpoint_ref = root_path / "artifacts" / "launch" / f"{run_id}.metadata.json"
        checkpoint_metadata = manager.save_checkpoint_metadata(session.session_id, str(checkpoint_ref))
        checkpoint_metadata_path = _rel(root_path, checkpoint_ref)
        runner.memory.write("neural_checkpoint_metadata", dict(checkpoint_metadata))
        if emit_visual:
            events.append(_event(run_id, ticks + 1, 10, "neural", profile.agent_id, _neural_payload(profile, session.session_id, checkpoint_metadata, phase="checkpoint", event="neural_checkpoint_written")))
    stop = manager.stop(session.session_id)
    if emit_visual:
        events.append(_event(run_id, ticks + 1, 20, "neural", profile.agent_id, _neural_payload(profile, session.session_id, stop, phase="completed", event="neural_session_stopped")))

    visual_state = reduce_visual_events(events, provenance="replay").as_record() if emit_visual else reduce_visual_events((), provenance="replay").as_record()
    artifact = Path(artifact_path) if artifact_path is not None else root_path / "artifacts" / "launch" / f"{run_id}.json"
    if not artifact.is_absolute():
        artifact = root_path / artifact
    run_record_path = root_path / "artifacts" / "launch" / "runs" / f"{run_id}.json"
    summary = {
        "ok": True,
        "run_id": run_id,
        "template": selected_template.name,
        "agent_id": profile.agent_id,
        "session_id": session.session_id,
        "backend": backend,
        "policy_mode": profile.autonomy_mode,
        "loop_ticks_completed": ticks,
        **counts,
        "memory_records_written": len(runner.memory.records),
        "visual_events_emitted": len(events),
        "replay_artifact_path": _rel(root_path, artifact),
        "checkpoint_metadata_path": checkpoint_metadata_path,
        "run_record_path": _rel(root_path, run_record_path),
        "gpu_evidence_status": _gpu_evidence_status(root_path),
        "release_gate_status": {
            "local_public_alpha": "not_evaluated",
            "gpu_gated": _gpu_evidence_status(root_path),
        },
        "no_external_calls": True,
        "no_live_provider_calls": True,
        "no_private_keys": True,
        "no_funds_moved": True,
        "raw_model_weights_written": False,
        "safety_authority": "policy_engine_and_approval_gate",
    }
    payload = {
        "ok": True,
        "schema_version": VISUAL_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "template": selected_template.as_record(),
        "agent": profile.as_record(),
        "ticks": tuple(tick_results),
        "memory_records": tuple(dict(record) for record in runner.memory.records),
        "events": tuple(event.as_record() for event in events),
        "visual_events": tuple(event.as_record() for event in events),
        "state": visual_state,
        "checkpoint_metadata": dict(checkpoint_metadata),
        "provenance": "replay" if emit_visual else "local",
    }
    if write_artifact:
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    if write_run_record:
        record = upsert_run_from_launch_payload(root_path, payload)
        payload["run_record"] = dict(record)
        payload["summary"] = {**dict(payload["summary"]), "run_record_path": record.get("run_record_path", "")}
        if write_artifact:
            artifact.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return payload


def _profile_for_launch(
    template: LaunchTemplate,
    *,
    run_id: str,
    session_id: str,
    backend: str,
    goal: str,
    flow_path: str | Path | None,
    flow_source: str,
) -> AgentProfile:
    if flow_path is not None or flow_source:
        spec = parse_flowlang_file(flow_path) if flow_path is not None else parse_flowlang(flow_source)
        base = agent_profile_from_ir(spec)
        neural = _merge_neural(base.neural_config, template.neural, backend=backend, session_id=session_id)
        return replace(
            base,
            agent_id=_stable_id("agent", run_id),
            goals=(goal or (base.goals[0] if base.goals else template.goal),),
            neural_config=neural,
            metadata={**dict(base.metadata), "launchpad_run_id": run_id, "launch_template": template.name, "flow_path": str(flow_path or "inline")},
        )
    neural = _merge_neural({}, template.neural, backend=backend, session_id=session_id)
    return AgentProfile(
        agent_id=_stable_id("agent", run_id),
        name=f"Flow Memory {template.name.replace('-', ' ').title()} Agent",
        identity=f"did:flow:{template.name}:{run_id[-12:]}",
        goals=(goal,),
        capabilities=template.capabilities,
        allowed_tools=template.allowed_tools,
        allowed_skills=template.allowed_skills,
        memory_config=dict(template.memory),
        compute_config=dict(template.compute),
        neural_config=neural,
        autonomy_mode=template.autonomy_mode,
        risk_budget=template.risk_budget,
        metadata={"launchpad_run_id": run_id, "launch_template": template.name, "public_alpha": True},
    )


def _merge_neural(base: Mapping[str, Any], template: Mapping[str, Any], *, backend: str, session_id: str) -> dict[str, Any]:
    merged = {**dict(template), **dict(base)}
    merged.update({
        "enabled": True,
        "backend": backend,
        "live_mode": True,
        "session_id": session_id,
        "telemetry_enabled": True,
    })
    merged.setdefault("learning_enabled", True)
    merged.setdefault("policy_fallback", "allow_non_neural")
    merged.setdefault("perception_streams", ("text", "events", "memory"))
    return merged


def _initial_events(run_id: str, profile: AgentProfile, session: Mapping[str, Any], template: LaunchTemplate) -> tuple[VisualEvent, ...]:
    return (
        _event(run_id, 0, 10, "agent", profile.agent_id, {
            "agent_id": profile.agent_id,
            "label": profile.name,
            "role": "live_neural_agent",
            "status": "idle",
            "capabilities": profile.capabilities,
            "reputation": profile.reputation,
            "template": template.name,
        }),
        _event(run_id, 0, 20, "neural", profile.agent_id, {
            "agent_id": profile.agent_id,
            "session_id": session.get("session_id", ""),
            "backend": dict(session.get("config", {})).get("backend", "tiny_torch"),
            "status": session.get("status", "observed"),
            "phase": "idle",
            "event": "neural_session_created",
            "policy_gate_state": "pending_policy_gate",
            "action_state": "idle",
            "safety_authority": "policy_engine_and_approval_gate",
        }),
    )


def _tick_events(run_id: str, tick: int, profile: AgentProfile, result: Mapping[str, Any], live_step: Mapping[str, Any], *, policy_allowed: bool) -> tuple[VisualEvent, ...]:
    session_id = str(live_step.get("session_id", profile.neural_config.get("session_id", "")))
    payload_base = _neural_payload(profile, session_id, live_step, phase=str(live_step.get("phase", "evaluated")), event="neural_step")
    events = [
        _event(run_id, tick, 10, "neural", profile.agent_id, {**payload_base, "phase": "perceiving", "event": "neural_perception_encoded"}),
        _event(run_id, tick, 20, "neural", profile.agent_id, {**payload_base, "phase": "predicting", "event": "neural_prediction_generated"}),
        _event(run_id, tick, 30, "neural", profile.agent_id, {**payload_base, "phase": "reasoning", "event": "neural_plan_scored"}),
        _event(run_id, tick, 40, "neural", profile.agent_id, {**payload_base, "phase": "risk_scoring", "event": "neural_risk_scored"}),
        _event(run_id, tick, 50, "safety", profile.agent_id, {
            "agent_id": profile.agent_id,
            "gate_id": _stable_id("safety_gate", run_id, str(tick)),
            "decision": "allowed" if policy_allowed else "denied",
            "risk_level": str(dict(result.get("state", {})).get("current_plan", {}).get("risk_level", "low")),
            "requires_approval": not policy_allowed,
            "reason": "policy gate applied to neural advisory recommendation",
            "source_event_id": _stable_id("neural_policy", run_id, str(tick)),
        }),
    ]
    if live_step.get("memory_candidates"):
        events.append(_event(run_id, tick, 60, "memory", profile.agent_id, {
            "memory_id": _stable_id("memory", run_id, str(tick)),
            "agent_id": profile.agent_id,
            "kind": "neural_live_trace",
            "summary": f"neural live tick {tick} memory candidates: {live_step.get('memory_activation_count', 0)}",
            "importance": float(live_step.get("prediction_confidence", 0.0) or 0.0),
        }))
    compute = dict(dict(result.get("output", {})).get("compute", {})) if isinstance(dict(result.get("output", {})).get("compute", {}), Mapping) else {}
    if compute.get("status") == "planned":
        decision = dict(compute.get("decision", {}))
        quote = dict(compute.get("quote", {}))
        events.append(_event(run_id, tick, 70, "compute", profile.agent_id, {
            "agent_id": profile.agent_id,
            "task_id": decision.get("task_id", ""),
            "event": "route_decision_selected",
            "status": compute.get("status", "planned"),
            "provider_id": decision.get("provider_id", ""),
            "route_id": decision.get("route_id", ""),
            "quote_total": quote.get("total_cost", 0.0),
            "payment_rail": dict(compute.get("payment_intent", {})).get("rail", "local_credits"),
            "dry_run_only": True,
            "no_funds_moved": True,
        }))
    return tuple(events)


def _neural_payload(profile: AgentProfile, session_id: str, record: Mapping[str, Any], *, phase: str, event: str) -> dict[str, Any]:
    return {
        "agent_id": profile.agent_id,
        "session_id": session_id,
        "backend": record.get("backend", profile.neural_config.get("backend", "tiny_torch")),
        "status": record.get("status", "observed"),
        "phase": phase,
        "event": event,
        "plan_score": float(record.get("plan_score", 0.0) or 0.0),
        "risk_score": float(record.get("risk_score", 0.0) or 0.0),
        "surprise_score": float(record.get("surprise_score", 0.0) or 0.0),
        "prediction_confidence": float(record.get("prediction_confidence", record.get("after_metric", 0.0)) or 0.0),
        "uncertainty": float(record.get("uncertainty", record.get("loss", 0.0)) or 0.0),
        "learning_tick_count": int(record.get("learning_tick_count", 0) or 0),
        "memory_activation_count": int(record.get("memory_activation_count", 0) or 0),
        "action_state": str(record.get("action_state", "completed" if event.endswith("stopped") else "recommended")),
        "policy_gate_state": str(record.get("policy_gate_state", "applied")),
        "safety_authority": "policy_engine_and_approval_gate",
        "local_only": True,
        "external_model_calls": False,
    }


def _event(run_id: str, tick: int, ordinal: int, event_type: str, source: str, payload: Mapping[str, Any]) -> VisualEvent:
    event_id = _stable_id("visual_event", run_id, str(tick), str(ordinal), event_type, str(payload.get("event", "")))
    return VisualEvent(
        event_type=event_type,
        source=source,
        payload=dict(payload),
        provenance="replay",
        source_event_id=str(payload.get("source_event_id", "")),
        event_id=event_id,
        created_at=_stable_timestamp(tick, ordinal),
    )


def _stable_timestamp(tick: int, ordinal: int) -> str:
    return f"2026-01-01T00:{tick % 60:02d}:{ordinal % 60:02d}+00:00"


def _gpu_evidence_status(root: Path) -> str:
    artifact = root / "artifacts" / "incoming" / "flow-memory-cloud-gpu-run-001.tar.gz"
    if not artifact.exists():
        return "blocked_missing_artifact"
    gpu_runs = root / "release_evidence" / "gpu_runs"
    for summary in gpu_runs.glob("*/summary.json") if gpu_runs.exists() else ():
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("ok") is True and data.get("skipped") is not True and data.get("cuda_available") is True:
            return "verified"
    return "artifact_present_not_verified"


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"
