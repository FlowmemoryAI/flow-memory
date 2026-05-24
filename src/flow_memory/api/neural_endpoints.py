"""Dependency-free neural API endpoint handlers."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from flow_memory.api.errors import ApiError, validation_error
from flow_memory.neural.artifacts import is_checkpoint_name, list_checkpoint_metadata, load_json
from flow_memory.neural.config import SUPPORTED_BACKENDS
from flow_memory.neural.run_records import (
    evaluate_neural_gpu_smoke,
    get_gpu_run,
    gpu_runs_root,
    list_gpu_runs,
)
from flow_memory.neural.torch_optional import is_torch_available

REPO_ROOT = Path(__file__).resolve().parents[3]


def register_neural_routes(router: Any) -> None:
    router.register("GET", "/neural/status", neural_status, "neural_status")
    router.register("GET", "/neural/backends", neural_backends, "neural_backends")
    router.register("GET", "/neural/gpu-runs", neural_gpu_runs, "neural_gpu_runs")
    router.register("GET", "/neural/gpu-runs/{run_id}", neural_gpu_run_detail, "neural_gpu_run_detail")
    router.register("GET", "/neural/benchmarks", neural_benchmarks, "neural_benchmarks")
    router.register("GET", "/neural/checkpoints", neural_checkpoints, "neural_checkpoints")
    router.register("POST", "/neural/validate-smoke", neural_validate_smoke, "neural_validate_smoke")
    router.register("POST", "/neural/train-smoke", neural_train_smoke, "neural_train_smoke")


def neural_status(_params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    env = _torch_environment()
    evidence = evaluate_neural_gpu_smoke(REPO_ROOT).as_record()
    return {
        "ok": True,
        "torch_available": env["torch_available"],
        "cuda_available": env["cuda_available"],
        "gpu_name": env["gpu_name"],
        "gpu_evidence_ok": evidence["ok"],
        "gpu_evidence_blockers": evidence["blockers"],
    }


def neural_backends(_params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    torch_available = is_torch_available()
    records = []
    for name in sorted(SUPPORTED_BACKENDS):
        records.append(
            {
                "name": name,
                "available": _backend_available(name, torch_available),
                "requires_torch": name != "none",
            }
        )
    return {"backends": tuple(records)}


def neural_gpu_runs(_params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return {"runs": list_gpu_runs(REPO_ROOT)}


def neural_gpu_run_detail(params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    run_id = params.get("run_id", "")
    try:
        return {"run": get_gpu_run(REPO_ROOT, run_id)}
    except KeyError as exc:
        raise ApiError(
            "neural.gpu_run_not_found",
            "Neural GPU run evidence was not found",
            404,
            {"run_id": run_id},
        ) from exc


def neural_benchmarks(_params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    benchmark_runs = []
    for run in list_gpu_runs(REPO_ROOT):
        statuses = run.get("statuses", {}) if isinstance(run.get("statuses"), Mapping) else {}
        benchmark_runs.append(
            {
                "run_id": run.get("run_id", ""),
                "imported": bool(run.get("imported")),
                "skipped": bool(run.get("skipped")),
                "benchmarks": statuses.get("benchmarks", {"ok": None, "status": "unknown"}),
            }
        )
    return {
        "benchmarks": tuple(benchmark_runs),
        "scripts": (
            "benchmarks/neural_appearance_free_motion_benchmark.py",
            "benchmarks/neural_world_model_prediction_benchmark.py",
            "benchmarks/neural_plan_scoring_benchmark.py",
            "benchmarks/neural_memory_retrieval_benchmark.py",
            "benchmarks/neural_agent_policy_benchmark.py",
        ),
    }


def neural_checkpoints(_params: Mapping[str, str], _payload: Mapping[str, Any]) -> Mapping[str, Any]:
    records = list(list_checkpoint_metadata(REPO_ROOT / "artifacts" / "neural"))
    for run_dir in sorted(gpu_runs_root(REPO_ROOT).glob("*")) if gpu_runs_root(REPO_ROOT).exists() else ():
        hashes_path = run_dir / "hashes.json"
        if not hashes_path.exists():
            continue
        hashes = load_json(hashes_path)
        for record in hashes.get("files", ()):
            if isinstance(record, Mapping) and is_checkpoint_name(str(record.get("path", ""))):
                records.append(
                    {
                        "name": Path(str(record.get("path", ""))).name,
                        "path": str(record.get("path", "")),
                        "size_bytes": int(record.get("size_bytes", 0)),
                        "sha256": str(record.get("sha256", "")),
                        "source": "gpu_run_artifact",
                        "run_id": run_dir.name,
                        "extracted": False,
                    }
                )
    return {"checkpoints": tuple(records), "raw_weights_returned": False}


def neural_validate_smoke(_params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
    require_cuda = bool(payload.get("require_cuda", False))
    backend = str(payload.get("backend", "tiny_torch"))
    if backend not in SUPPORTED_BACKENDS:
        raise validation_error("Unknown neural backend", details={"backend": backend})
    env = _torch_environment()
    if require_cuda and env["cuda_available"] is not True:
        raise ApiError(
            "neural.cuda_required",
            "CUDA was required for neural smoke validation but is not available",
            400,
            {"backend": backend, "cuda_available": env["cuda_available"]},
        )
    return {
        "ok": True,
        "backend": backend,
        "environment": env,
        "gpu_evidence": evaluate_neural_gpu_smoke(REPO_ROOT).as_record(),
    }


def neural_train_smoke(_params: Mapping[str, str], payload: Mapping[str, Any]) -> Mapping[str, Any]:
    steps = _bounded_int(payload.get("steps", 1), name="steps", minimum=1, maximum=5)
    seed = _bounded_int(payload.get("seed", 0), name="seed", minimum=0, maximum=2**31 - 1)
    out = _safe_neural_artifact_dir(str(payload.get("out", "artifacts/neural/api_train_smoke")))
    command = [
        sys.executable,
        "scripts/train_neural_smoke.py",
        "--out",
        str(out.relative_to(REPO_ROOT)),
        "--steps",
        str(steps),
        "--seed",
        str(seed),
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise ApiError(
            "neural.train_smoke_failed",
            "Neural train smoke failed",
            500,
            {"returncode": completed.returncode, "stderr_tail": completed.stderr[-2000:]},
        )
    metrics = _load_train_smoke_stdout(completed.stdout)
    return {
        "ok": bool(metrics.get("ok", True)),
        "out": out.relative_to(REPO_ROOT).as_posix(),
        "steps": steps,
        "seed": seed,
        "skipped": bool(metrics.get("skipped", False)),
        "reason": str(metrics.get("reason", "")),
        "runs": _sanitize_training_runs(metrics.get("runs", {})),
        "checkpoints": list_checkpoint_metadata(out / "checkpoints"),
        "raw_weights_returned": False,
    }


def _torch_environment() -> Mapping[str, Any]:
    info: dict[str, Any] = {
        "torch_available": is_torch_available(),
        "torch_version": None,
        "cuda_available": False,
        "cuda_version": None,
        "gpu_name": None,
        "gpu_count": 0,
    }
    if not info["torch_available"]:
        return info
    try:
        import torch

        info["torch_version"] = str(torch.__version__)
        info["cuda_available"] = bool(torch.cuda.is_available())
        info["cuda_version"] = str(torch.version.cuda) if torch.version.cuda else None
        if torch.cuda.is_available():
            info["gpu_count"] = int(torch.cuda.device_count())
            info["gpu_name"] = torch.cuda.get_device_name(0)
    except Exception as exc:  # pragma: no cover - driver/runtime defensive boundary
        info["torch_error"] = str(exc)
    return info


def _backend_available(name: str, torch_available: bool) -> bool:
    if name == "none":
        return True
    return torch_available


def _bounded_int(value: Any, *, name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise validation_error(f"{name} must be an integer", details={name: value}) from exc
    if parsed < minimum or parsed > maximum:
        raise validation_error(f"{name} out of range", details={name: parsed, "minimum": minimum, "maximum": maximum})
    return parsed


def _safe_neural_artifact_dir(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise validation_error("out must be a relative artifacts/neural path", details={"out": value})
    parts = path.parts
    if len(parts) < 2 or parts[0] != "artifacts" or parts[1] != "neural" or ".." in parts:
        raise validation_error("out must stay under artifacts/neural", details={"out": value})
    return REPO_ROOT / path


def _load_train_smoke_stdout(stdout: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ApiError("neural.train_smoke_invalid_output", "Neural train smoke output was not JSON", 500) from exc
    if not isinstance(payload, Mapping):
        raise ApiError("neural.train_smoke_invalid_output", "Neural train smoke output was not an object", 500)
    return payload


def _sanitize_training_runs(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    sanitized: dict[str, Any] = {}
    for name, record in value.items():
        if not isinstance(record, Mapping):
            sanitized[str(name)] = record
            continue
        sanitized[str(name)] = {
            key: item
            for key, item in record.items()
            if key not in {"checkpoint", "checkpoint_path", "weights", "state_dict"}
        }
    return sanitized
