"""Release-safe records for imported neural GPU validation runs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from flow_memory.neural.artifacts import load_json

GPU_RUNS_FORMAT = "flow-memory-neural-gpu-runs-v1"
GPU_RUN_SUMMARY_FORMAT = "flow-memory-neural-gpu-run-summary-v1"


@dataclass(frozen=True)
class NeuralGpuSmokeEvaluation:
    ok: bool
    blockers: tuple[str, ...]
    evidence: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {"ok": self.ok, "blockers": self.blockers, "evidence": dict(self.evidence)}


def gpu_runs_root(root: str | Path = ".") -> Path:
    return Path(root) / "release_evidence" / "gpu_runs"


def load_gpu_run_summary(run_dir: str | Path) -> dict[str, Any]:
    path = Path(run_dir) / "summary.json"
    return load_json(path)


def list_gpu_runs(root: str | Path = ".") -> tuple[Mapping[str, Any], ...]:
    runs_dir = gpu_runs_root(root)
    if not runs_dir.exists():
        return ()
    records: list[Mapping[str, Any]] = []
    for summary_path in sorted(runs_dir.glob("*/summary.json")):
        try:
            records.append(_public_summary(load_json(summary_path)))
        except (OSError, ValueError):
            records.append(
                {
                    "run_id": summary_path.parent.name,
                    "imported": False,
                    "skipped": False,
                    "ok": False,
                    "error": "summary could not be loaded",
                }
            )
    return tuple(records)


def get_gpu_run(root: str | Path, run_id: str) -> Mapping[str, Any]:
    summary_path = gpu_runs_root(root) / run_id / "summary.json"
    if not summary_path.exists():
        raise KeyError(f"neural GPU run not found: {run_id}")
    return _public_summary(load_json(summary_path), include_details=True)


def build_gpu_runs_evidence(root: str | Path = ".") -> Mapping[str, Any]:
    runs = list_gpu_runs(root)
    imported = tuple(run for run in runs if bool(run.get("imported")) and not bool(run.get("skipped")))
    skipped = tuple(run for run in runs if bool(run.get("skipped")))
    return {
        "format": GPU_RUNS_FORMAT,
        "run_count": len(runs),
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "runs": runs,
    }


def evaluate_neural_gpu_smoke(root: str | Path = ".") -> NeuralGpuSmokeEvaluation:
    evidence = build_gpu_runs_evidence(root)
    runs = tuple(evidence.get("runs", ()))
    if not runs:
        return NeuralGpuSmokeEvaluation(False, ("neural_gpu_evidence_missing",), evidence)
    imported = tuple(run for run in runs if bool(run.get("imported")) and not bool(run.get("skipped")))
    if not imported:
        return NeuralGpuSmokeEvaluation(False, ("neural_gpu_ingestion_skipped",), evidence)
    blockers: list[str] = []
    passing = tuple(run for run in imported if _run_satisfies_neural_gpu_smoke(run))
    if not passing:
        latest = imported[-1]
        environment = latest.get("environment", {}) if isinstance(latest.get("environment"), Mapping) else {}
        statuses = latest.get("statuses", {}) if isinstance(latest.get("statuses"), Mapping) else {}
        if not environment.get("gpu_name"):
            blockers.append("gpu_name_missing")
        if environment.get("cuda_available") is not True:
            blockers.append("cuda_not_confirmed")
        if not environment.get("torch_version"):
            blockers.append("torch_version_missing")
        if _status_ok(statuses.get("cli_neural")) is not True:
            blockers.append("cli_neural_not_ok")
        if _status_ok(statuses.get("benchmarks")) is not True:
            blockers.append("neural_benchmarks_not_ok")
    return NeuralGpuSmokeEvaluation(not blockers, tuple(blockers), evidence)


def _public_summary(summary: Mapping[str, Any], *, include_details: bool = False) -> Mapping[str, Any]:
    keys = (
        "format",
        "run_id",
        "imported",
        "skipped",
        "reason",
        "imported_at",
        "source_artifact",
        "artifact",
        "environment",
        "statuses",
        "counts",
    )
    record = {key: summary[key] for key in keys if key in summary}
    if include_details:
        for key in ("evidence", "hashes_path", "summary_md_path"):
            if key in summary:
                record[key] = summary[key]
    return record


def _run_satisfies_neural_gpu_smoke(run: Mapping[str, Any]) -> bool:
    environment = run.get("environment", {})
    statuses = run.get("statuses", {})
    if not isinstance(environment, Mapping) or not isinstance(statuses, Mapping):
        return False
    return (
        bool(environment.get("gpu_name"))
        and environment.get("cuda_available") is True
        and bool(environment.get("torch_version"))
        and _status_ok(statuses.get("cli_neural")) is True
        and _status_ok(statuses.get("benchmarks")) is True
    )


def _status_ok(value: Any) -> bool | None:
    if isinstance(value, Mapping):
        ok = value.get("ok")
        return ok if isinstance(ok, bool) else None
    return None
