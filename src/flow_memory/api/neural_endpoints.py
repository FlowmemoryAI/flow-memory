"""Neural metadata handlers for the local API router."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Mapping

from flow_memory.neural import is_torch_available
from flow_memory.neural.checkpoints import CheckpointRegistry
from flow_memory.neural.gpu_evidence import gpu_evidence_index, verify_gpu_run
from flow_memory.neural.torch_optional import is_numpy_available
from flow_memory.neural.training.train_tiny_dual_stream import train_smoke as train_dual_stream
from flow_memory.neural.training.train_world_model import train_smoke as train_world_model
from flow_memory.neural.training.train_agent_policy import train_smoke as train_agent_policy

from flow_memory.neural.live import GLOBAL_NEURAL_RUNTIME, neural_live_config_from_mapping

ROOT = Path(__file__).resolve().parents[3]

def neural_status(root: str | Path = ROOT) -> Mapping[str, Any]:
    return {
        "ok": True,
        "torch_available": is_torch_available(),
        "torch": {"available": is_torch_available()},
        "numpy_available": is_numpy_available(),
        "default_backend": "none",
        "safety_authority": "policy_engine_and_approval_gate",
        "live_runtime": {"sessions": len(GLOBAL_NEURAL_RUNTIME.sessions()), "local_only": True},
        "gpu_evidence": gpu_evidence_index(root),
    }

def neural_backends() -> Mapping[str, Any]:
    return {
        "backends": (
            {"name": "none", "status": "implemented", "requires_torch": False},
            {"name": "tiny_torch", "status": "functional_prototype", "requires_torch": True},
            {"name": "vjepa2", "status": "adapter_seam", "requires_torch": True, "requires_local_checkpoint": True},
            {"name": "videomae", "status": "adapter_seam", "requires_torch": True, "requires_local_checkpoint": True},
        )
    }

def neural_gpu_runs(root: str | Path = ROOT) -> Mapping[str, Any]:
    return gpu_evidence_index(root)

def neural_gpu_run(run_id: str, root: str | Path = ROOT) -> Mapping[str, Any]:
    path = Path(root) / "release_evidence" / "gpu_runs" / run_id
    if not path.exists():
        raise KeyError(f"Unknown GPU run: {run_id}")
    report = verify_gpu_run(path)
    runs = report.get("runs", ())
    return dict(runs[0]) if runs else {"run_id": run_id, "ok": False}

def neural_benchmarks(root: str | Path = ROOT) -> Mapping[str, Any]:
    artifact_dir = Path(root) / "artifacts"
    results = []
    if artifact_dir.exists():
        for path in sorted(artifact_dir.rglob("neural_*benchmark*.json")):
            results.append({"name": path.stem, "path": str(path.relative_to(root)), "kind": "ignored_local_artifact"})
    return {"benchmarks": tuple(results), "note": "metadata only; artifacts are gitignored"}

def neural_checkpoints() -> Mapping[str, Any]:
    registry=CheckpointRegistry()
    return {"checkpoints": registry.records(), "raw_weights_exposed": False}

def neural_validate_smoke() -> Mapping[str, Any]:
    return {"ok": True, "torch_available": is_torch_available(), "recommended_command": "python scripts/cloud_gpu_validate.py --smoke --json-out artifacts/cloud_gpu/latest/validation.json"}

def neural_train_smoke(out: str = "artifacts/neural/api_smoke") -> Mapping[str, Any]:
    # This intentionally runs only the tiny smoke trainers, which skip clearly when torch is absent.
    return {
        "ok": True,
        "local_only": True,
        "runs": {
            "tiny_dual_stream": train_dual_stream(steps=1, checkpoint_dir=str(Path(out)/"checkpoints")),
            "world_model": train_world_model(steps=1, checkpoint_dir=str(Path(out)/"checkpoints")),
            "agent_policy": train_agent_policy(steps=1, checkpoint_dir=str(Path(out)/"checkpoints")),
        },
        "raw_weights_exposed": False,
    }

def neural_live_create(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    agent_id = str(payload.get("agent_id", payload.get("agent", "api-neural-agent")))
    config_payload = payload.get("config", payload)
    config = neural_live_config_from_mapping(config_payload if isinstance(config_payload, Mapping) else {})
    session = GLOBAL_NEURAL_RUNTIME.create_session(agent_id, config)
    return {"ok": True, "session": session.as_record(), "local_only": True}


def neural_live_sessions() -> Mapping[str, Any]:
    return {"ok": True, "sessions": tuple(session.as_record() for session in GLOBAL_NEURAL_RUNTIME.sessions()), "local_only": True}


def neural_live_session(session_id: str) -> Mapping[str, Any]:
    return {"ok": True, "session": GLOBAL_NEURAL_RUNTIME.get_session(session_id).as_record(), "local_only": True}


def neural_live_step(session_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    context = payload.get("context", payload)
    if not isinstance(context, Mapping):
        context = {"input": context}
    return {
        "ok": True,
        "step": GLOBAL_NEURAL_RUNTIME.run_step(session_id, context),
        "session": GLOBAL_NEURAL_RUNTIME.get_session(session_id).as_record(),
        "local_only": True,
    }


def neural_live_learn(session_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    sample = payload.get("sample", payload)
    if not isinstance(sample, Mapping):
        sample = {"sample": sample}
    return {
        "ok": True,
        "learning": GLOBAL_NEURAL_RUNTIME.learn(session_id, sample),
        "session": GLOBAL_NEURAL_RUNTIME.get_session(session_id).as_record(),
        "local_only": True,
    }


def neural_live_checkpoint(session_id: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "ok": True,
        "checkpoint": GLOBAL_NEURAL_RUNTIME.checkpoint(session_id, str(payload.get("checkpoint_ref", ""))),
        "session": GLOBAL_NEURAL_RUNTIME.get_session(session_id).as_record(),
        "local_only": True,
        "raw_weights_exposed": False,
    }


def neural_live_stop(session_id: str) -> Mapping[str, Any]:
    return {
        "ok": True,
        "stop": GLOBAL_NEURAL_RUNTIME.stop(session_id),
        "session": GLOBAL_NEURAL_RUNTIME.get_session(session_id).as_record(),
        "local_only": True,
    }
