"""Import, summarize, and verify cloud GPU run evidence."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Mapping
from flow_memory.neural.artifacts import find_text, load_json_if_present, safe_extract_metadata, sha256_file
from flow_memory.neural.model_cards import gpu_model_card
from flow_memory.neural.run_records import GpuRunSummary

DEFAULT_RUN_ID = "flow-memory-cloud-gpu-run-001"


def import_gpu_run_artifact(tarball: str | Path, out_root: str | Path = "release_evidence/gpu_runs", *, run_id: str = DEFAULT_RUN_ID) -> GpuRunSummary:
    tarball_path=Path(tarball)
    out_dir=Path(out_root)/run_id
    if not tarball_path.exists():
        out_dir.mkdir(parents=True, exist_ok=True)
        summary=GpuRunSummary(run_id=run_id, skipped=True, reason=f"artifact not present: {tarball_path}")
        _write_outputs(out_dir, summary, {"source_artifact.tar.gz": "missing"}, ())
        return summary
    hashes, skipped = safe_extract_metadata(tarball_path, out_dir)
    summary=summarize_gpu_run(out_dir, run_id=run_id, source_hash=hashes.get("source_artifact.tar.gz", ""))
    _write_outputs(out_dir, summary, hashes, skipped)
    return summary


def summarize_gpu_run(run_dir: str | Path, *, run_id: str | None = None, source_hash: str = "") -> GpuRunSummary:
    path=Path(run_dir)
    rid=run_id or path.name
    gpu_info=find_text(path, ("gpu_info.txt", "gpu_info.log"))
    commit=find_text(path, ("git_commit.txt", "commit.txt"))
    validation=find_text(path, ("validation_summary.txt", "pytest_summary.txt", "test_results.txt"))
    cli=load_json_if_present(path/"cli_neural.json")
    benchmarks=_collect_benchmarks(path)
    gpu_name=_match(gpu_info, r"gpu:\s*(.+)") or _match(gpu_info, r"NVIDIA[^\n]+")
    torch_version=_match(gpu_info, r"torch:\s*(.+)")
    python_version=_match(gpu_info, r"python:\s*(.+)")
    cuda_version=_match(gpu_info, r"cuda version:\s*(.+)") or _match(gpu_info, r"cuda:\s*(.+)")
    cuda_available=("cuda available: true" in gpu_info.lower()) or bool(_deep_find(cli, "cuda_available") is True)
    neural=_deep_find(cli, "neural")
    backend=""; status=""
    if isinstance(neural, Mapping):
        backend=str(neural.get("backend", "")); status=str(neural.get("status", ""))
    if not source_hash and (path/"source_artifact.tar.gz").exists():
        source_hash=sha256_file(path/"source_artifact.tar.gz")
    summary=GpuRunSummary(
        run_id=rid, source_artifact_sha256=source_hash, gpu_name=gpu_name, python_version=python_version,
        torch_version=torch_version, cuda_version=cuda_version, cuda_available=cuda_available,
        git_commit=commit.splitlines()[0] if commit else "", cli_neural_backend=backend,
        cli_neural_status=status, pytest_summary=_pytest_summary(validation), benchmarks=benchmarks,
    )
    return summary


def verify_gpu_run(run_root: str | Path) -> Mapping[str, Any]:
    root=Path(run_root)
    if root.is_dir() and (root/"summary.json").exists():
        dirs=(root,)
    elif root.is_dir():
        dirs=tuple(sorted(path for path in root.iterdir() if path.is_dir()))
    else:
        dirs=()
    records=[]
    for directory in dirs:
        summary=load_json_if_present(directory/"summary.json")
        hashes=load_json_if_present(directory/"hashes.json")
        ok=bool(summary.get("ok")) and bool(hashes)
        records.append({"run_id": directory.name, "ok": ok, "summary": summary})
    return {"ok": all(record["ok"] for record in records) if records else False, "runs": tuple(records)}


def compare_gpu_runs(run_root: str | Path) -> Mapping[str, Any]:
    verification=verify_gpu_run(run_root)
    runs=verification.get("runs", ())
    return {"ok": bool(runs), "run_count": len(runs), "runs": runs}


def gpu_evidence_index(root: str | Path = ".") -> Mapping[str, Any]:
    path=Path(root)/"release_evidence"/"gpu_runs"
    if not path.exists():
        return {"ok": True, "skipped": True, "reason": "gpu evidence directory absent", "runs": ()}
    verification=verify_gpu_run(path)
    if not verification.get("runs"):
        return {"ok": True, "skipped": True, "reason": "no gpu runs imported", "runs": ()}
    return verification


def _write_outputs(out_dir: Path, summary: GpuRunSummary, hashes: Mapping[str,str], skipped: tuple[str,...]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir/"summary.json").write_text(json.dumps(summary.as_record(), indent=2, sort_keys=True)+"\n", encoding='utf-8')
    (out_dir/"hashes.json").write_text(json.dumps({"hashes": dict(sorted(hashes.items())), "skipped_members": tuple(skipped)}, indent=2, sort_keys=True)+"\n", encoding='utf-8')
    (out_dir/"summary.md").write_text(gpu_model_card(summary), encoding='utf-8')


def _collect_benchmarks(path: Path) -> Mapping[str, Any]:
    output={}
    for file in sorted(path.glob("*benchmark*.json")):
        output[file.stem]=dict(load_json_if_present(file))
    return output


def _match(text: str, pattern: str) -> str:
    match=re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match and match.groups() else (match.group(0).strip() if match else "")


def _pytest_summary(text: str) -> str:
    return _match(text, r"(\d+\s+passed(?:,\s*\d+\s+skipped)?)") or text[:200]


def _deep_find(obj: Any, key: str) -> Any:
    if isinstance(obj, Mapping):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found=_deep_find(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found=_deep_find(value, key)
            if found is not None:
                return found
    return None
