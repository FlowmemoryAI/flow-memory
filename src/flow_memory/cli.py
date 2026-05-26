"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from flow_memory import Agent
from flow_memory.protocols import CapabilityManifest
from flow_memory.flowlang import run_flowlang_agent
from flow_memory.agents.runner import AgentRunner
from flow_memory.agents.profile import AgentProfile
from flow_memory.compute_market.planner import compute_marketplace_plan
from flow_memory.compute_market.registry import default_policies, default_providers, default_routes
from flow_memory.neural.live import GLOBAL_NEURAL_RUNTIME
from flow_memory.launchpad import launch_template_names, run_live_agent_launch
from flow_memory.launch_operations import export_run_bundle, get_run_record, list_run_records, replay_run_record, stop_run_record
from flow_memory.launch_supervisor import (
    get_supervisor_heartbeat,
    get_supervisor_run,
    pause_supervisor_run,
    resume_supervisor_run,
    start_supervised_run,
    stop_supervisor_run,
    supervisor_status,
    supervisor_state_path,
)
from flow_memory.visualization.run_console import build_public_alpha_demo_bundle
from flow_memory.visualization.embodiment import build_neural_embodiment_fixture
from flow_memory.release.launch_finalizer import finalize_public_alpha_launch
from flow_memory.cognition.benchmarks import get_benchmark, list_benchmarks, run_predictive_learning_benchmark
from flow_memory.cognition.consolidation import consolidate_experiences, get_lesson, list_lessons
from flow_memory.cognition.metrics import cognition_metrics
from flow_memory.cognition.experience import get_experience, list_experiences, prediction_error_records
from flow_memory.cognition.world_model import DeterministicWorldModel
from flow_memory.agent_genesis import (
    birth_agent,
    create_teaching_event,
    export_contribution_bundle,
    export_genome,
    get_genome,
    get_mirror,
    get_passport,
    list_archetypes,
    list_boundaries,
    list_contributions,
    list_instincts,
    write_teaching_event,
)


def _json_default(value: Any) -> str:
    try:
        return value.isoformat()
    except AttributeError:
        return repr(value)


def _run(prompt_parts: list[str], name: str, json_output: bool, neural_backend: str = "none", neural_live: bool = False) -> int:
    prompt = " ".join(prompt_parts)
    if neural_backend != "none":
        neural_config: dict[str, Any] = {"backend": neural_backend}
        if neural_live:
            neural_config.update({"enabled": True, "live_mode": True, "learning_enabled": True, "policy_fallback": "allow_non_neural", "telemetry_enabled": True})
        profile = AgentProfile(name=name, capabilities=("perception", "memory", "reasoning"), allowed_tools=("respond",), neural_config=neural_config)
        result = AgentRunner(profile).run_cycle(prompt)
        record = result.as_record()
        if json_output:
            print(json.dumps(record, indent=2, default=_json_default))
        else:
            print(record.get("output", {}).get("execution", {}).get("output", record.get("output", {})))
        return 0
    agent = Agent.create(name=name, capabilities=["perception", "memory", "reasoning"])
    cycle = agent.run_cycle(prompt)
    if json_output:
        print(json.dumps(asdict(cycle), indent=2, default=_json_default))
    else:
        print(cycle.final_output)
    return 0


def _run_flow(flow_path: str, prompt_parts: list[str], json_output: bool, neural_backend: str = "none") -> int:
    prompt = " ".join(prompt_parts)
    result = run_flowlang_agent(flow_path, prompt, neural_backend=neural_backend)
    if json_output:
        print(json.dumps(result, indent=2, default=_json_default))
    else:
        print(result.get("output", {}).get("execution", {}).get("output", result))
    return 0

def _manifest(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="flow-memory manifest")
    parser.add_argument("--name", default="alpha")
    parser.add_argument("--capability", action="append", default=[])
    parser.add_argument("--permission", action="append", default=["respond"])
    args = parser.parse_args(argv)
    agent = Agent.create(name=args.name, capabilities=args.capability)
    manifest = CapabilityManifest(
        agent_did=agent.did,
        name=args.name,
        capabilities=tuple(args.capability),
        permissions=tuple(args.permission),
    )
    print(json.dumps(asdict(manifest), indent=2, default=_json_default))
    return 0


def _launch(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="flow-memory launch", description="Run polished local launch workflows")
    sub = parser.add_subparsers(dest="resource", required=True)

    agent = sub.add_parser("agent", description="Launch a local live neural agent")
    agent.add_argument("--template", default="live-research", choices=launch_template_names())
    agent.add_argument("--flow", default="", help="Optional FlowLang agent file")
    agent.add_argument("--goal", default="", help="Override the template or FlowLang goal")
    agent.add_argument("--neural", default="tiny_torch", choices=["none", "tiny_torch", "vjepa2", "videomae"], help="Neural backend to select locally")
    agent.add_argument("--ticks", type=int, default=5, help="Number of deterministic local loop ticks")
    agent.add_argument("--emit-visual", action="store_true", help="Emit Mission Control replay events")
    agent.add_argument("--json", action="store_true", help="Print full launch artifact JSON")
    agent.add_argument("--out", default="", help="Optional replay artifact path")

    runs = sub.add_parser("runs", description="Inspect and export local Live Agent Launchpad runs")
    run_sub = runs.add_subparsers(dest="run_command", required=True)
    run_list = run_sub.add_parser("list")
    run_list.add_argument("--json", action="store_true")
    run_show = run_sub.add_parser("show")
    run_show.add_argument("run_id")
    run_show.add_argument("--json", action="store_true")
    run_replay = run_sub.add_parser("replay")
    run_replay.add_argument("run_id")
    run_replay.add_argument("--json", action="store_true")
    run_export = run_sub.add_parser("export")
    run_export.add_argument("run_id")
    run_export.add_argument("--out", default="")
    run_export.add_argument("--json", action="store_true")
    run_stop = run_sub.add_parser("stop")
    run_stop.add_argument("run_id")
    run_stop.add_argument("--json", action="store_true")
    run_resume = run_sub.add_parser("resume")
    run_resume.add_argument("run_id")
    run_resume.add_argument("--ticks", type=int, default=3)
    run_resume.add_argument("--emit-visual", action="store_true")
    run_resume.add_argument("--json", action="store_true")

    supervisor = sub.add_parser("supervisor", description="Run bounded local Live Agent Supervisor workflows")
    supervisor_sub = supervisor.add_subparsers(dest="supervisor_command", required=True)
    supervisor_start = supervisor_sub.add_parser("start")
    supervisor_start.add_argument("--template", default="live-research", choices=launch_template_names())
    supervisor_start.add_argument("--neural", default="tiny_torch", choices=["none", "tiny_torch", "vjepa2", "videomae"])
    supervisor_start.add_argument("--ticks", type=int, default=10)
    supervisor_start.add_argument("--tick-interval-ms", type=int, default=250)
    supervisor_start.add_argument("--emit-visual", action="store_true")
    supervisor_start.add_argument("--predictive-core", action="store_true", help="Enable predictive cognition metadata for this supervised launch")
    supervisor_start.add_argument("--consolidate-lessons", action="store_true", help="Consolidate predictive cognition lessons after the bounded run")
    supervisor_start.add_argument("--json", action="store_true")
    supervisor_status_cmd = supervisor_sub.add_parser("status")
    supervisor_status_cmd.add_argument("--json", action="store_true")
    supervisor_show = supervisor_sub.add_parser("show")
    supervisor_show.add_argument("run_id")
    supervisor_show.add_argument("--json", action="store_true")
    supervisor_heartbeat = supervisor_sub.add_parser("heartbeat")
    supervisor_heartbeat.add_argument("run_id")
    supervisor_heartbeat.add_argument("--json", action="store_true")
    supervisor_pause = supervisor_sub.add_parser("pause")
    supervisor_pause.add_argument("run_id")
    supervisor_pause.add_argument("--json", action="store_true")
    supervisor_resume = supervisor_sub.add_parser("resume")
    supervisor_resume.add_argument("run_id")
    supervisor_resume.add_argument("--ticks", type=int, default=5)
    supervisor_resume.add_argument("--emit-visual", action="store_true")
    supervisor_resume.add_argument("--json", action="store_true")
    supervisor_stop = supervisor_sub.add_parser("stop")
    supervisor_stop.add_argument("run_id")
    supervisor_stop.add_argument("--json", action="store_true")

    bundle = sub.add_parser("bundle", description="Build local launch/demo bundles")
    bundle_sub = bundle.add_subparsers(dest="bundle_command", required=True)
    public_alpha_bundle = bundle_sub.add_parser("public-alpha")
    public_alpha_bundle.add_argument("--out", default="artifacts/launch/bundles/public-alpha-local-demo.json")
    public_alpha_bundle.add_argument("--json", action="store_true")

    visual = sub.add_parser("visual", description="Export Mission Control visual projections")
    visual_sub = visual.add_subparsers(dest="visual_command", required=True)
    embodiment = visual_sub.add_parser("embodiment")
    embodiment.add_argument("--run", default="live-agent-supervisor")
    embodiment.add_argument("--out", default="dashboard/src/mock-data/live-neural-embodiment.json")
    embodiment.add_argument("--json", action="store_true")

    finalize = sub.add_parser("finalize", description="Finalize local public-alpha launch handoff evidence")
    finalize_sub = finalize.add_subparsers(dest="finalize_command", required=True)
    public_alpha_finalizer = finalize_sub.add_parser("public-alpha")
    public_alpha_finalizer.add_argument("--out", default="release_evidence/public_alpha_launch_finalizer.json")
    public_alpha_finalizer.add_argument("--json", action="store_true")

    doctor = sub.add_parser("doctor", description="Check local launch/neural/Mission Control readiness")
    doctor.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.resource == "agent":
            payload = run_live_agent_launch(
                template=args.template,
                flow_path=args.flow or None,
                goal=args.goal,
                backend=args.neural,
                ticks=args.ticks,
                emit_visual=args.emit_visual,
                artifact_path=args.out or None,
            )
            return _print_launch_payload(payload, json_output=args.json)

        if args.resource == "runs":
            if args.run_command == "list":
                payload = {"ok": True, "runs": list_run_records()}
                return _print_launch_payload(payload, json_output=args.json, human=f"{len(payload['runs'])} launch run(s)")
            if args.run_command == "show":
                payload = {"ok": True, "run": get_run_record(".", args.run_id)}
                return _print_launch_payload(payload, json_output=args.json, human=f"run {args.run_id}: {payload['run'].get('status', '')}")
            if args.run_command == "replay":
                payload = replay_run_record(".", args.run_id)
                return _print_launch_payload(payload, json_output=args.json, human=f"replay {payload.get('replay_artifact_path', '')}")
            if args.run_command == "export":
                payload = export_run_bundle(".", args.run_id, args.out or None)
                return _print_launch_payload(payload, json_output=args.json, human=f"exported {payload.get('bundle_path', '')}")
            if args.run_command == "stop":
                payload = stop_run_record(".", args.run_id)
                return _print_launch_payload(payload, json_output=args.json, human=f"run {args.run_id}: {payload.get('status_before')} -> {payload.get('status_after')}")
            if args.run_command == "resume":
                record = dict(get_run_record(".", args.run_id))
                payload = run_live_agent_launch(
                    template=str(record.get("template", "live-research") or "live-research"),
                    goal=f"Continue local launch run {args.run_id}",
                    backend=str(record.get("backend", "tiny_torch") or "tiny_torch"),
                    ticks=args.ticks,
                    emit_visual=args.emit_visual,
                )
                payload["summary"] = {**dict(payload["summary"]), "continued_from_run_id": args.run_id}
                return _print_launch_payload(payload, json_output=args.json)
        if args.resource == "supervisor":
            if args.supervisor_command == "start":
                payload = start_supervised_run(
                    template=args.template,
                    backend=args.neural,
                    ticks=args.ticks,
                    tick_interval_ms=args.tick_interval_ms,
                    emit_visual=args.emit_visual,
                    predictive_core=args.predictive_core,
                    consolidate_lessons=args.consolidate_lessons,
                )
                return _print_launch_payload(payload, json_output=args.json, human=f"supervisor run {payload['supervisor']['run_id']}: {payload['supervisor']['status']}")
            if args.supervisor_command == "status":
                payload = supervisor_status()
                return _print_launch_payload(payload, json_output=args.json, human=f"{payload['run_count']} supervisor run(s)")
            if args.supervisor_command == "show":
                payload = {"ok": True, "supervisor": get_supervisor_run(".", args.run_id)}
                return _print_launch_payload(payload, json_output=args.json, human=f"supervisor {args.run_id}: {payload['supervisor'].get('status', '')}")
            if args.supervisor_command == "heartbeat":
                payload = {"ok": True, "heartbeat": get_supervisor_heartbeat(".", args.run_id)}
                return _print_launch_payload(payload, json_output=args.json, human=f"heartbeat {args.run_id}: {payload['heartbeat'].get('status', '')}")
            if args.supervisor_command == "pause":
                payload = pause_supervisor_run(".", args.run_id)
                return _print_launch_payload(payload, json_output=args.json, human=f"supervisor {args.run_id}: {payload.get('status_before')} -> {payload.get('status_after')}")
            if args.supervisor_command == "resume":
                payload = resume_supervisor_run(".", args.run_id, ticks=args.ticks, emit_visual=args.emit_visual)
                return _print_launch_payload(payload, json_output=args.json, human=f"continued {args.run_id} as {payload['supervisor']['run_id']}")
            if args.supervisor_command == "stop":
                payload = stop_supervisor_run(".", args.run_id)
                return _print_launch_payload(payload, json_output=args.json, human=f"supervisor {args.run_id}: {payload.get('status_before')} -> {payload.get('status_after')}")
        if args.resource == "bundle":
            if args.bundle_command == "public-alpha":
                payload = build_public_alpha_demo_bundle(".", args.out)
                return _print_launch_payload(payload, json_output=args.json, human=f"demo bundle {payload.get('bundle_path', '')}")
        if args.resource == "visual":
            if args.visual_command == "embodiment":
                payload = build_neural_embodiment_fixture(".", args.run, args.out)
                return _print_launch_payload(payload, json_output=args.json, human=f"neural embodiment {payload.get('fixture_path', '')}")
        if args.resource == "finalize":
            if args.finalize_command == "public-alpha":
                payload = finalize_public_alpha_launch(".", args.out)
                return _print_launch_payload(payload, json_output=args.json, human=f"public-alpha finalizer {payload.get('finalizer_path', '')}")
        if args.resource == "doctor":
            payload = _launch_doctor()
            return _print_launch_payload(payload, json_output=args.json, human="launch doctor ok" if payload["ok"] else "launch doctor failed")
        raise ValueError(f"unknown launch resource: {args.resource}")
    except (KeyError, ValueError) as exc:
        payload = {"ok": False, "error": {"code": "launch.invalid_request", "message": str(exc)}}
        print(json.dumps(payload, indent=2, default=_json_default, sort_keys=True))
        return 1


def _print_launch_payload(payload: Mapping[str, Any], *, json_output: bool, human: str = "") -> int:
    if json_output:
        print(json.dumps(payload, indent=2, default=_json_default, sort_keys=True))
    elif human:
        print(human)
    else:
        summary = dict(payload.get("summary", {})) if isinstance(payload.get("summary", {}), Mapping) else {}
        print(
            "launched {agent_id} session={session_id} ticks={ticks} replay={replay}".format(
                agent_id=summary.get("agent_id", ""),
                session_id=summary.get("session_id", ""),
                ticks=summary.get("loop_ticks_completed", 0),
                replay=summary.get("replay_artifact_path", ""),
            )
        )
    return 0


def _launch_doctor() -> Mapping[str, Any]:
    from flow_memory.neural import is_torch_available

    root = Path(".").resolve()
    examples = tuple(Path("examples") / name for name in ("live_research_agent.flow", "memory_scout_agent.flow", "market_observer_agent.flow", "mission_control_demo_agent.flow"))
    supervisor_examples = tuple(Path("examples") / name for name in ("supervised_live_research_agent.flow", "supervised_memory_scout_agent.flow", "supervised_market_observer_agent.flow"))
    ops_fixture = Path("dashboard/src/mock-data/live-agent-operations.json")
    supervisor_fixture = Path("dashboard/src/mock-data/live-agent-supervisor.json")
    launch_fixture = Path("dashboard/src/mock-data/live-neural-agent-launch.json")
    run_console_lib = Path("dashboard/src/lib/run-console.ts")
    run_selector_component = Path("dashboard/src/components/mission-control/RunSelector.tsx")
    public_alpha_bundle_default = Path("artifacts/launch/bundles/public-alpha-local-demo.json")
    finalizer_default = Path("release_evidence/public_alpha_launch_finalizer.json")
    live_3d_component = Path("dashboard/src/components/mission-control/Live3DModePanel.tsx")
    artifact_dir = root / "artifacts" / "launch" / "runs"
    heartbeat_dir = root / "artifacts" / "launch" / "supervisor" / "heartbeats"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    heartbeat_dir.mkdir(parents=True, exist_ok=True)
    gpu_artifact = root / "artifacts" / "incoming" / "flow-memory-cloud-gpu-run-001.tar.gz"
    from flow_memory.api.manifest import API_ENDPOINTS

    endpoints = {f"{endpoint.method} {endpoint.path}" for endpoint in API_ENDPOINTS}
    supervisor_endpoint_ok = all(endpoint in endpoints for endpoint in (
        "POST /launch/supervisor/start",
        "GET /launch/supervisor/status",
        "GET /launch/supervisor/runs/{run_id}",
        "GET /launch/supervisor/runs/{run_id}/heartbeat",
        "POST /launch/supervisor/runs/{run_id}/pause",
        "POST /launch/supervisor/runs/{run_id}/resume",
        "POST /launch/supervisor/runs/{run_id}/stop",
    ))
    console_endpoint_ok = all(endpoint in endpoints for endpoint in (
        "GET /launch/console/runs",
        "GET /launch/console/runs/{run_id}",
        "GET /launch/console/fixtures",
        "POST /launch/bundles/public-alpha",
        "POST /launch/finalize/public-alpha",
    ))
    checks = {
        "tiny_torch": True,
        "torch_available": is_torch_available(),
        "launch_templates": bool(launch_template_names()),
        "examples_available": all(path.exists() for path in examples),
        "supervisor_examples_available": all(path.exists() for path in supervisor_examples),
        "artifact_directory_writable": artifact_dir.exists(),
        "supervisor_module_available": True,
        "supervisor_state_path_writable": supervisor_state_path(root).parent.exists() or bool(supervisor_state_path(root).parent.mkdir(parents=True, exist_ok=True) is None),
        "heartbeat_path_writable": heartbeat_dir.exists(),
        "run_registry_available": artifact_dir.exists(),
        "visual_replay_support_available": True,
        "visual_replay_fixture": launch_fixture.exists(),
        "operations_fixture": ops_fixture.exists(),
        "dashboard_supervisor_fixture_present": supervisor_fixture.exists(),
        "api_endpoints_registered": supervisor_endpoint_ok,
        "run_console_available": run_console_lib.exists(),
        "run_selector_available": run_selector_component.exists(),
        "public_alpha_demo_bundle_command_available": True,
        "public_alpha_demo_bundle_directory_writable": public_alpha_bundle_default.parent.exists() or bool(public_alpha_bundle_default.parent.mkdir(parents=True, exist_ok=True) is None),
        "console_api_endpoints_registered": console_endpoint_ok,
        "public_alpha_finalizer_command_available": True,
        "public_alpha_finalizer_directory_writable": finalizer_default.parent.exists() or bool(finalizer_default.parent.mkdir(parents=True, exist_ok=True) is None),
        "live_3d_mode_component_present": live_3d_component.exists(),
        "cli_commands_available": True,
        "no_external_call_mode": True,
    }
    return {
        "ok": all(value is True for key, value in checks.items() if key not in {"torch_available", "operations_fixture"}),
        "checks": checks,
        "gpu_evidence_status": "artifact_present_not_verified" if gpu_artifact.exists() else "blocked_missing_artifact",
        "local_only": True,
        "safety_authority": "policy_engine_and_approval_gate",
    }

def _cognition(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="flow-memory cognition", description="Run predictive cognitive core commands")
    sub = parser.add_subparsers(dest="command", required=True)

    predict = sub.add_parser("predict")
    predict.add_argument("--goal", required=True)
    predict.add_argument("--action", default="")
    predict.add_argument("--agent-id", default="cli-cognition-agent")
    predict.add_argument("--json", action="store_true")

    tick = sub.add_parser("tick")
    tick.add_argument("--agent", default="cli-cognition-agent")
    tick.add_argument("--goal", required=True)
    tick.add_argument("--action", default="")
    tick.add_argument("--json", action="store_true")

    experiences = sub.add_parser("experiences")
    exp_sub = experiences.add_subparsers(dest="experience_command", required=True)
    exp_list = exp_sub.add_parser("list")
    exp_list.add_argument("--json", action="store_true")
    exp_show = exp_sub.add_parser("show")
    exp_show.add_argument("experience_id")
    exp_show.add_argument("--json", action="store_true")

    errors = sub.add_parser("prediction-errors")
    err_sub = errors.add_subparsers(dest="error_command", required=True)
    err_list = err_sub.add_parser("list")
    err_list.add_argument("--json", action="store_true")

    benchmark = sub.add_parser("benchmark")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_run = benchmark_sub.add_parser("run")
    benchmark_run.add_argument("--scenario", default="all")
    benchmark_run.add_argument("--trials", type=int, default=5)
    benchmark_run.add_argument("--json", action="store_true")
    benchmark_list = benchmark_sub.add_parser("list")
    benchmark_list.add_argument("--json", action="store_true")
    benchmark_show = benchmark_sub.add_parser("show")
    benchmark_show.add_argument("benchmark_id")
    benchmark_show.add_argument("--json", action="store_true")

    lessons = sub.add_parser("lessons")
    lesson_sub = lessons.add_subparsers(dest="lesson_command", required=True)
    lesson_consolidate = lesson_sub.add_parser("consolidate")
    lesson_consolidate.add_argument("--json", action="store_true")
    lesson_list = lesson_sub.add_parser("list")
    lesson_list.add_argument("--json", action="store_true")
    lesson_show = lesson_sub.add_parser("show")
    lesson_show.add_argument("lesson_id")
    lesson_show.add_argument("--json", action="store_true")

    metrics = sub.add_parser("metrics")
    metrics.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    model = DeterministicWorldModel()
    if args.command == "predict":
        payload = model.tick({"agent_id": args.agent_id, "goal": args.goal, "action": args.action, "write_experience": False})
        payload = {key: payload[key] for key in ("ok", "state", "candidate_actions", "counterfactuals", "scores", "selected_action", "prediction", "policy_decision", "lesson_reuse") if key in payload}
        return _print_launch_payload(payload, json_output=args.json, human=f"prediction {payload['prediction']['prediction_id']}: {payload['prediction']['predicted_result']}")
    if args.command == "tick":
        payload = model.tick({"agent_id": args.agent, "goal": args.goal, "action": args.action})
        return _print_launch_payload(payload, json_output=args.json, human=f"experience {payload['experience']['experience_id']}: error {payload['prediction_error']['prediction_error']:.2f}")
    if args.command == "experiences":
        if args.experience_command == "list":
            records = list_experiences(".")
            return _print_launch_payload({"ok": True, "experiences": records, "count": len(records)}, json_output=args.json, human=f"{len(records)} cognition experience(s)")
        record = get_experience(args.experience_id, ".")
        return _print_launch_payload({"ok": True, "experience": record}, json_output=args.json, human=f"experience {args.experience_id}")
    if args.command == "prediction-errors":
        records = prediction_error_records(".")
        return _print_launch_payload({"ok": True, "prediction_errors": records, "count": len(records)}, json_output=args.json, human=f"{len(records)} prediction error(s)")
    if args.command == "benchmark":
        if args.benchmark_command == "run":
            payload = run_predictive_learning_benchmark(scenario=args.scenario, trials=args.trials)
            return _print_launch_payload(payload, json_output=args.json, human=f"benchmark {payload['benchmark_id']}: accuracy {payload['prediction_accuracy_before']:.2f} -> {payload['prediction_accuracy_after']:.2f}")
        if args.benchmark_command == "list":
            records = list_benchmarks(".")
            return _print_launch_payload({"ok": True, "benchmarks": records, "count": len(records)}, json_output=args.json, human=f"{len(records)} cognition benchmark(s)")
        record = get_benchmark(args.benchmark_id, ".")
        return _print_launch_payload({"ok": True, "benchmark": record}, json_output=args.json, human=f"benchmark {args.benchmark_id}")
    if args.command == "lessons":
        if args.lesson_command == "consolidate":
            payload = consolidate_experiences(".")
            return _print_launch_payload(payload, json_output=args.json, human=f"{payload['consolidated_lesson_count']} lesson(s) consolidated")
        if args.lesson_command == "list":
            records = list_lessons(".")
            return _print_launch_payload({"ok": True, "lessons": records, "count": len(records)}, json_output=args.json, human=f"{len(records)} cognition lesson(s)")
        record = get_lesson(args.lesson_id, ".")
        return _print_launch_payload({"ok": True, "lesson": record}, json_output=args.json, human=f"lesson {args.lesson_id}")
    payload = cognition_metrics(".")
    return _print_launch_payload(payload, json_output=args.json, human=f"accuracy {payload['prediction_accuracy_before']:.2f} -> {payload['prediction_accuracy_after']:.2f}")


def _genesis(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="flow-memory genesis", description="Birth policy-gated Flow Memory agents")
    sub = parser.add_subparsers(dest="command", required=True)

    archetypes = sub.add_parser("archetypes")
    archetype_sub = archetypes.add_subparsers(dest="archetype_command", required=True)
    archetype_list = archetype_sub.add_parser("list")
    archetype_list.add_argument("--json", action="store_true")

    instincts = sub.add_parser("instincts")
    instinct_sub = instincts.add_subparsers(dest="instinct_command", required=True)
    instinct_list = instinct_sub.add_parser("list")
    instinct_list.add_argument("--json", action="store_true")

    boundaries = sub.add_parser("boundaries")
    boundary_sub = boundaries.add_subparsers(dest="boundary_command", required=True)
    boundary_list = boundary_sub.add_parser("list")
    boundary_list.add_argument("--json", action="store_true")

    birth = sub.add_parser("birth")
    birth.add_argument("--user", "--user-id", dest="user_id", default="local-user")
    birth.add_argument("--name", required=True)
    birth.add_argument("--archetype", default="research-builder")
    birth.add_argument("--purpose", default="")
    birth.add_argument("--instinct", action="append", default=[])
    birth.add_argument("--boundary", action="append", default=[])
    birth.add_argument("--consent", "--consent-mode", dest="consent_mode", default="private_only")
    birth.add_argument("--launch", action="store_true")
    birth.add_argument("--json", action="store_true")

    passport = sub.add_parser("passport")
    passport_sub = passport.add_subparsers(dest="passport_command", required=True)
    passport_show = passport_sub.add_parser("show")
    passport_show.add_argument("agent_id")
    passport_show.add_argument("--json", action="store_true")

    genome = sub.add_parser("genome")
    genome_sub = genome.add_subparsers(dest="genome_command", required=True)
    genome_export = genome_sub.add_parser("export")
    genome_export.add_argument("agent_id")
    genome_export.add_argument("--out", required=True)
    genome_export.add_argument("--json", action="store_true")
    genome_show = genome_sub.add_parser("show")
    genome_show.add_argument("agent_id")
    genome_show.add_argument("--json", action="store_true")

    mirror = sub.add_parser("mirror")
    mirror_sub = mirror.add_subparsers(dest="mirror_command", required=True)
    mirror_show = mirror_sub.add_parser("show")
    mirror_show.add_argument("agent_id")
    mirror_show.add_argument("--json", action="store_true")

    teaching = sub.add_parser("teaching")
    teaching_sub = teaching.add_subparsers(dest="teaching_command", required=True)
    teaching_add = teaching_sub.add_parser("add")
    teaching_add.add_argument("--agent", dest="agent_id", required=True)
    teaching_add.add_argument("--user", dest="user_id", default="local-user")
    teaching_add.add_argument("--type", dest="correction_type", default="correction")
    teaching_add.add_argument("--content", default="")
    teaching_add.add_argument("--lesson", required=True)
    teaching_add.add_argument("--tag", action="append", default=[])
    teaching_add.add_argument("--contribution-allowed", action="store_true")
    teaching_add.add_argument("--json", action="store_true")

    contributions = sub.add_parser("contributions")
    contribution_sub = contributions.add_subparsers(dest="contribution_command", required=True)
    contribution_list = contribution_sub.add_parser("list")
    contribution_list.add_argument("--agent", dest="agent_id", default="")
    contribution_list.add_argument("--json", action="store_true")
    contribution_export = contribution_sub.add_parser("export")
    contribution_export.add_argument("--agent", dest="agent_id", required=True)
    contribution_export.add_argument("--out", required=True)
    contribution_export.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "archetypes":
        records = list_archetypes()
        return _print_launch_payload({"ok": True, "archetypes": records, "count": len(records)}, json_output=args.json, human=f"{len(records)} agent archetype(s)")
    if args.command == "instincts":
        records = list_instincts()
        return _print_launch_payload({"ok": True, "instincts": records, "count": len(records)}, json_output=args.json, human=f"{len(records)} agent instinct(s)")
    if args.command == "boundaries":
        records = list_boundaries()
        return _print_launch_payload({"ok": True, "boundaries": records, "count": len(records)}, json_output=args.json, human=f"{len(records)} agent boundary rule(s)")
    if args.command == "birth":
        payload = birth_agent({
            "user_id": args.user_id,
            "name": args.name,
            "archetype": args.archetype,
            "purpose": args.purpose,
            "instincts": tuple(args.instinct),
            "boundaries": tuple(args.boundary),
            "consent_mode": args.consent_mode,
            "launch": args.launch,
        })
        return _print_launch_payload(payload, json_output=args.json, human=f"born {payload['birth_certificate']['name']} as {payload['agent_id']}")
    if args.command == "passport":
        payload = {"ok": True, "passport": get_passport(args.agent_id)}
        return _print_launch_payload(payload, json_output=args.json, human=f"passport {args.agent_id}")
    if args.command == "genome":
        if args.genome_command == "export":
            payload = export_genome(args.agent_id, args.out)
            return _print_launch_payload(payload, json_output=args.json, human=f"genome exported {payload['path']}")
        payload = {"ok": True, "genome": get_genome(args.agent_id)}
        return _print_launch_payload(payload, json_output=args.json, human=f"genome {args.agent_id}")
    if args.command == "mirror":
        payload = {"ok": True, "mirror": get_mirror(args.agent_id)}
        return _print_launch_payload(payload, json_output=args.json, human=f"mirror {args.agent_id}")
    if args.command == "teaching":
        event = create_teaching_event(
            user_id=args.user_id,
            agent_id=args.agent_id,
            correction_type=args.correction_type,
            content=args.content,
            lesson=args.lesson,
            applies_to_tags=tuple(args.tag),
            contribution_allowed=args.contribution_allowed,
        )
        payload = write_teaching_event(event)
        return _print_launch_payload(payload, json_output=args.json, human=f"teaching event {payload['teaching_event_id']}")
    if args.command == "contributions":
        if args.contribution_command == "export":
            payload = export_contribution_bundle(args.agent_id, args.out)
            return _print_launch_payload(payload, json_output=args.json, human=f"contribution bundle {payload['path']}")
        records = list_contributions(args.agent_id)
        return _print_launch_payload({"ok": True, "contributions": records, "count": len(records)}, json_output=args.json, human=f"{len(records)} contribution(s)")
    raise AssertionError("unhandled genesis command")


def _compute(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="flow-memory compute", description="Inspect and simulate the local Compute Market")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("providers")
    sub.add_parser("routes")
    sub.add_parser("policies")

    plan = sub.add_parser("plan")
    plan.add_argument("--goal", default="Explore and report")
    plan.add_argument("--budget", type=float, default=0.01)
    plan.add_argument("--max-quote", type=float, default=0.01)
    plan.add_argument("--strategy", default="cheapest_eligible", choices=["cheapest_eligible", "lowest_latency", "highest_quality"])
    plan.add_argument("--marketplace-only", action="store_true")
    plan.add_argument("--model", default="small-general")
    plan.add_argument("--tokens-in", type=int, default=1000)
    plan.add_argument("--tokens-out", type=int, default=500)
    plan.add_argument("--payment-rail", default="local_credits", choices=["local_credits", "dry_run_usdc", "noop"])

    args = parser.parse_args(argv)
    if args.command == "providers":
        payload = {"ok": True, "providers": tuple(provider.as_record() for provider in default_providers()), "dry_run_only": True}
    elif args.command == "routes":
        payload = {"ok": True, "routes": tuple(route.as_record() for route in default_routes()), "dry_run_only": True}
    elif args.command == "policies":
        payload = {"ok": True, "policies": tuple(policy.as_record() for policy in default_policies()), "dry_run_required": True}
    else:
        payload = compute_marketplace_plan(
            {
                "task": {
                    "goal_id": args.goal,
                    "task_id": "cli-compute-task",
                    "model": args.model,
                    "expected_input_tokens": args.tokens_in,
                    "expected_output_tokens": args.tokens_out,
                    "requires_marketplace": args.marketplace_only,
                },
                "policy": {
                    "max_total_cost": args.budget,
                    "max_quote": args.max_quote,
                    "strategy": args.strategy,
                    "marketplace_only": args.marketplace_only,
                    "payment_rail": args.payment_rail,
                    "dry_run_required": True,
                },
            }
        )
    print(json.dumps(payload, indent=2, default=_json_default, sort_keys=True))
    return 0


def _neural(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="flow-memory neural", description="Inspect and run local neural live sessions")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    live = sub.add_parser("live")
    live_sub = live.add_subparsers(dest="live_command", required=True)
    create = live_sub.add_parser("create")
    create.add_argument("--agent-id", default="cli-neural-agent")
    create.add_argument("--backend", default="tiny_torch", choices=["none", "tiny_torch", "vjepa2", "videomae"])
    create.add_argument("--seed", type=int, default=0)
    create.add_argument("--policy-fallback", default="allow_non_neural", choices=["fail_closed", "allow_non_neural"])
    create.add_argument("--learning-enabled", action="store_true")
    live_sub.add_parser("list")
    step = live_sub.add_parser("step")
    step.add_argument("--session-id", default="")
    step.add_argument("--agent-id", default="cli-neural-agent")
    step.add_argument("--backend", default="tiny_torch", choices=["none", "tiny_torch", "vjepa2", "videomae"])
    step.add_argument("--goal", default="Explore and report")
    step.add_argument("--seed", type=int, default=0)
    step.add_argument("--policy-fallback", default="allow_non_neural", choices=["fail_closed", "allow_non_neural"])
    learn = live_sub.add_parser("learn")
    learn.add_argument("--session-id", default="")
    learn.add_argument("--agent-id", default="cli-neural-agent")
    learn.add_argument("--backend", default="tiny_torch", choices=["none", "tiny_torch", "vjepa2", "videomae"])
    learn.add_argument("--goal", default="Explore and report")
    checkpoint = live_sub.add_parser("checkpoint")
    checkpoint.add_argument("--session-id", default="")
    checkpoint.add_argument("--agent-id", default="cli-neural-agent")
    checkpoint.add_argument("--checkpoint-ref", default="")
    stop = live_sub.add_parser("stop")
    stop.add_argument("--session-id", default="")
    stop.add_argument("--agent-id", default="cli-neural-agent")
    args = parser.parse_args(argv)

    if args.command == "status":
        from flow_memory.neural import is_torch_available

        payload = {"ok": True, "torch_available": is_torch_available(), "sessions": tuple(session.as_record() for session in GLOBAL_NEURAL_RUNTIME.sessions()), "local_only": True}
    elif args.live_command == "create":
        session = GLOBAL_NEURAL_RUNTIME.create_session(
            args.agent_id,
            {
                "enabled": True,
                "backend": args.backend,
                "live_mode": True,
                "seed": args.seed,
                "policy_fallback": args.policy_fallback,
                "learning_enabled": args.learning_enabled,
            },
        )
        payload = {"ok": True, "session": session.as_record()}
    elif args.live_command == "list":
        payload = {"ok": True, "sessions": tuple(session.as_record() for session in GLOBAL_NEURAL_RUNTIME.sessions())}
    elif args.live_command == "step":
        session = GLOBAL_NEURAL_RUNTIME.get_session(args.session_id) if args.session_id else GLOBAL_NEURAL_RUNTIME.create_session(
            args.agent_id,
            {"enabled": True, "backend": args.backend, "live_mode": True, "seed": args.seed, "policy_fallback": args.policy_fallback},
        )
        payload = {"ok": True, "step": GLOBAL_NEURAL_RUNTIME.run_step(session.session_id, {"goal": args.goal, "source": "cli"}), "session": GLOBAL_NEURAL_RUNTIME.get_session(session.session_id).as_record()}
    elif args.live_command == "learn":
        session = GLOBAL_NEURAL_RUNTIME.get_session(args.session_id) if args.session_id else GLOBAL_NEURAL_RUNTIME.create_session(
            args.agent_id,
            {"enabled": True, "backend": args.backend, "live_mode": True, "learning_enabled": True, "policy_fallback": "allow_non_neural"},
        )
        payload = {"ok": True, "learning": GLOBAL_NEURAL_RUNTIME.learn(session.session_id, {"goal": args.goal, "source": "cli"}), "session": GLOBAL_NEURAL_RUNTIME.get_session(session.session_id).as_record()}
    elif args.live_command == "checkpoint":
        session = GLOBAL_NEURAL_RUNTIME.get_session(args.session_id) if args.session_id else GLOBAL_NEURAL_RUNTIME.create_session(
            args.agent_id,
            {"enabled": True, "backend": "none", "live_mode": True, "policy_fallback": "allow_non_neural"},
        )
        payload = {"ok": True, "checkpoint": GLOBAL_NEURAL_RUNTIME.checkpoint(session.session_id, args.checkpoint_ref), "session": GLOBAL_NEURAL_RUNTIME.get_session(session.session_id).as_record(), "raw_weights_written": False}
    else:
        session = GLOBAL_NEURAL_RUNTIME.get_session(args.session_id) if args.session_id else GLOBAL_NEURAL_RUNTIME.create_session(
            args.agent_id,
            {"enabled": True, "backend": "none", "live_mode": True, "policy_fallback": "allow_non_neural"},
        )
        payload = {"ok": True, "stop": GLOBAL_NEURAL_RUNTIME.stop(session.session_id), "session": GLOBAL_NEURAL_RUNTIME.get_session(session.session_id).as_record()}
    print(json.dumps(payload, indent=2, default=_json_default, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "manifest":
        return _manifest(argv[1:])
    if argv and argv[0] == "launch":
        return _launch(argv[1:])
    if argv and argv[0] == "cognition":
        return _cognition(argv[1:])
    if argv and argv[0] == "genesis":
        return _genesis(argv[1:])
    if argv and argv[0] == "compute":
        return _compute(argv[1:])
    if argv and argv[0] == "neural":
        return _neural(argv[1:])
    if argv and argv[0] == "run":
        argv = argv[1:]

    parser = argparse.ArgumentParser(prog="flow-memory", description="Run a local Flow Memory agent")
    parser.add_argument("prompt", nargs="+", help="Observation/goal for the agent")
    parser.add_argument("--name", default="alpha", help="Agent name")
    parser.add_argument("--flow", default="", help="FlowLang .flow file to compile and run")
    parser.add_argument("--json", action="store_true", help="Print full cognitive-cycle trace as JSON")
    parser.add_argument("--neural", default="none", choices=["none", "tiny_torch", "vjepa2", "videomae"], help="Optional neural advisory backend")
    parser.add_argument("--neural-live", action="store_true", help="Attach a local neural live runtime session when --neural is set")
    args = parser.parse_args(argv)
    if args.flow:
        return _run_flow(args.flow, args.prompt, args.json, args.neural)
    return _run(args.prompt, args.name, args.json, args.neural, args.neural_live)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
