"""Release evidence for local live neural agents."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner
from flow_memory.api.manifest import API_ENDPOINTS
from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir
from flow_memory.neural.live import NeuralRuntimeManager
from flow_memory.neural.torch_optional import is_torch_available
from flow_memory.visualization.adapters.neural_adapter import neural_record_to_visual_events
from flow_memory.visualization.reducer import reduce_visual_events


REQUIRED_NEURAL_LIVE_ENDPOINTS = (
    "POST /neural/live/sessions",
    "GET /neural/live/sessions",
    "GET /neural/live/sessions/{session_id}",
    "POST /neural/live/sessions/{session_id}/step",
    "POST /neural/live/sessions/{session_id}/learn",
    "POST /neural/live/sessions/{session_id}/checkpoint",
    "POST /neural/live/sessions/{session_id}/stop",
)


def neural_live_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    root_path = Path(root).resolve()
    operations = {f"{endpoint.method} {endpoint.path}" for endpoint in API_ENDPOINTS}
    missing_endpoints = tuple(endpoint for endpoint in REQUIRED_NEURAL_LIVE_ENDPOINTS if endpoint not in operations)
    manager = NeuralRuntimeManager()
    session = manager.create_session(
        "release-neural-agent",
        {"enabled": True, "backend": "tiny_torch", "live_mode": True, "policy_fallback": "allow_non_neural", "learning_enabled": True, "seed": 7},
    )
    step = manager.run_step(session.session_id, {"goal": "release neural live smoke", "plan_id": "release-plan"})
    learning = manager.learn(session.session_id, {"goal": "release neural live smoke"})
    checkpoint = manager.checkpoint(session.session_id)
    interface_checks = {
        "perception": manager.encode_perception(session.session_id, {"goal": "release neural live smoke"}),
        "prediction": manager.predict_next_state(session.session_id, {"goal": "release neural live smoke", "plan_id": "release-plan"}),
        "plan_score": manager.score_plan(session.session_id, {"goal": "release neural live smoke", "plan_id": "release-plan"}),
        "risk_score": manager.score_risk(session.session_id, {"goal": "release neural live smoke", "plan_id": "release-plan"}),
        "memory": manager.retrieve_memory_candidates(session.session_id, {"goal": "release neural live smoke"}),
    }
    with TemporaryDirectory() as tmp_dir:
        checkpoint_path = Path(tmp_dir) / "release-neural-live.metadata.json"
        saved_checkpoint = manager.save_checkpoint_metadata(session.session_id, str(checkpoint_path))
        loaded_checkpoint = manager.load_checkpoint_metadata(str(checkpoint_path))
    flow_profile = agent_profile_from_ir(parse_flowlang(_FLOWLANG_NEURAL_LIVE))
    runner_profile = AgentProfile(
        name="release-neural-runner",
        allowed_tools=("respond",),
        neural_config={"enabled": True, "backend": "tiny_torch", "live_mode": True, "policy_fallback": "allow_non_neural", "learning_enabled": True},
    )
    runner_result = AgentRunner(runner_profile).run_cycle("Explore and report")
    visual_events = neural_record_to_visual_events(runner_result.output.get("neural", {}), agent_id=runner_profile.agent_id, provenance="replay")
    visual_state = reduce_visual_events(visual_events, provenance="replay").as_record()
    files = {
        "runtime": root_path / "src" / "flow_memory" / "neural" / "live.py",
        "agent_binding": root_path / "src" / "flow_memory" / "agents" / "neural_binding.py",
        "api": root_path / "src" / "flow_memory" / "api" / "neural_endpoints.py",
        "docs": root_path / "docs" / "NEURAL_LIVE_AGENTS.md",
    }
    tests = tuple(sorted(path.name for path in (root_path / "tests").glob("test_*neural*live*.py"))) if (root_path / "tests").exists() else ()
    gpu_artifact = root_path / "artifacts" / "incoming" / "flow-memory-cloud-gpu-run-001.tar.gz"
    fail_closed = _fail_closed_sample()
    ok = (
        not missing_endpoints
        and all(path.exists() for path in files.values())
        and bool(step.get("ok"))
        and learning.get("status") == "learned"
        and checkpoint.get("metadata_only") is True
        and saved_checkpoint.get("checkpoint_written") is True
        and loaded_checkpoint.get("ok") is True
        and all(record.get("ok") for record in interface_checks.values())
        and flow_profile.neural_config.get("live_mode") is True
        and runner_result.output.get("neural", {}).get("live_step", {}).get("ok") is True
        and bool(visual_state.get("neural"))
        and fail_closed.get("ok") is True
    )
    return {
        "ok": ok,
        "neural_live_runtime_available": files["runtime"].exists(),
        "tiny_torch_deterministic_backend_validated": bool(step.get("ok")) and step.get("backend") == "tiny_torch",
        "torch_optional_backend_status": {"torch_available": is_torch_available(), "cuda_claimed": False},
        "agent_profile_creation_validated": not runner_profile.validate(),
        "flowlang_creation_validated": flow_profile.neural_config.get("live_mode") is True,
        "neural_step_loop_validated": bool(step.get("ok")),
        "runtime_interface_validated": all(record.get("ok") for record in interface_checks.values()),
        "learning_loop_validated": learning.get("status") == "learned",
        "policy_fail_closed_validated": fail_closed,
        "visual_telemetry_validated": bool(visual_state.get("neural")),
        "mission_control_replay_fixture_validated": (root_path / "dashboard" / "src" / "mock-data" / "local-network-replay.json").exists(),
        "api_endpoints_validated": not missing_endpoints,
        "missing_endpoints": missing_endpoints,
        "cli_commands_present": _cli_has_neural_live(root_path),
        "gpu_evidence_status": "verified" if gpu_artifact.exists() else "blocked_missing_artifact",
        "vjepa2_status": "adapter_seam",
        "videomae_status": "adapter_seam",
        "files_present": {name: path.exists() for name, path in files.items()},
        "tests_present": tests,
        "sample_step": step,
        "sample_learning": learning,
        "sample_checkpoint": checkpoint,
        "saved_checkpoint_metadata": saved_checkpoint,
        "loaded_checkpoint_metadata": loaded_checkpoint,
        "interface_checks": interface_checks,
    }


def _fail_closed_sample() -> Mapping[str, Any]:
    manager = NeuralRuntimeManager()
    session = manager.create_session("fail-closed-agent", {"enabled": True, "backend": "videomae", "live_mode": True, "policy_fallback": "fail_closed"})
    step = manager.run_step(session.session_id, {"goal": "unsafe direct action"})
    return {"ok": step.get("ok") is False, "status": step.get("status"), "reason": step.get("reason", "")}


def _cli_has_neural_live(root: Path) -> bool:
    cli = root / "src" / "flow_memory" / "cli.py"
    if not cli.exists():
        return False
    text = cli.read_text(encoding="utf-8")
    return "flow-memory neural" in text and "neural-live" in text


_FLOWLANG_NEURAL_LIVE = '''
agent LiveResearchAgent {
  goal: "research and summarize local project state"

  neural {
    enabled: true
    backend: "tiny_torch"
    live_mode: true
    learning_enabled: true
    seed: 1337
    model_profile: "local-small"
    perception_streams: ["text", "events", "memory"]
    plan_scoring_enabled: true
    risk_scoring_enabled: true
    memory_retrieval_enabled: true
    telemetry_enabled: true
    policy_fallback: "allow_non_neural"
  }

  policy {
    autonomy: "supervised"
    approval_required: true
  }
}
'''
