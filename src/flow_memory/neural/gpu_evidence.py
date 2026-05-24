"""Neural GPU validation artifact ingestion.

The importer is intentionally conservative: every archive member is hashed, but
only small UTF-8 text/JSON metadata is persisted under ``release_evidence``.
Weights, checkpoints, and other binary payloads remain in ignored artifacts and
are represented only by metadata hashes.
"""
from __future__ import annotations

import json
import re
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from flow_memory.neural.artifacts import (
    CHECKPOINT_SUFFIXES,
    MAX_METADATA_BYTES,
    hash_stream,
    is_checkpoint_name,
    is_safe_metadata_name,
    load_json,
    metadata_output_path,
    relative_posix,
    run_id_from_artifact,
    safe_archive_name,
    sha256_file,
    write_json,
)
from flow_memory.neural.model_cards import parse_model_card
from flow_memory.neural.run_records import GPU_RUN_SUMMARY_FORMAT

HASHES_FORMAT = "flow-memory-neural-gpu-run-hashes-v1"


def import_gpu_run_artifact(
    artifact_path: str | Path,
    evidence_root: str | Path = Path("release_evidence") / "gpu_runs",
    *,
    run_id: str | None = None,
) -> Mapping[str, Any]:
    artifact = Path(artifact_path)
    selected_run_id = run_id or run_id_from_artifact(artifact)
    run_dir = Path(evidence_root) / selected_run_id
    if not artifact.exists():
        return mark_gpu_run_skipped(
            run_dir,
            source_artifact=_display_path(artifact),
            reason="artifact not found; ingestion skipped without failing base tests",
        )
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir = run_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, Any] = {
        "format": HASHES_FORMAT,
        "run_id": selected_run_id,
        "created_at": _now(),
        "artifact": {
            "path": _display_path(artifact),
            "size_bytes": artifact.stat().st_size,
            "sha256": sha256_file(artifact),
        },
        "files": [],
        "metadata_files": [],
        "skipped_files": [],
    }
    if tarfile.is_tarfile(artifact):
        _import_tar_metadata(artifact, run_dir, metadata_dir, hashes)
    elif zipfile.is_zipfile(artifact):
        _import_zip_metadata(artifact, run_dir, metadata_dir, hashes)
    else:
        raise ValueError(f"unsupported GPU artifact archive format: {artifact}")
    summary = build_gpu_run_summary(
        run_dir,
        run_id=selected_run_id,
        source_artifact=_display_path(artifact),
        hashes=hashes,
        skipped=False,
        reason="",
    )
    write_json(run_dir / "hashes.json", hashes)
    write_json(run_dir / "summary.json", summary)
    (run_dir / "summary.md").write_text(summary_markdown(summary), encoding="utf-8", newline="\n")
    return summary


def mark_gpu_run_skipped(run_dir: str | Path, *, source_artifact: str, reason: str) -> Mapping[str, Any]:
    directory = Path(run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, Any] = {
        "format": HASHES_FORMAT,
        "run_id": directory.name,
        "created_at": _now(),
        "artifact": {"path": source_artifact, "size_bytes": 0, "sha256": ""},
        "files": [],
        "metadata_files": [],
        "skipped_files": [],
    }
    summary = build_gpu_run_summary(
        directory,
        run_id=directory.name,
        source_artifact=source_artifact,
        hashes=hashes,
        skipped=True,
        reason=reason,
    )
    write_json(directory / "hashes.json", hashes)
    write_json(directory / "summary.json", summary)
    (directory / "summary.md").write_text(summary_markdown(summary), encoding="utf-8", newline="\n")
    return summary


def build_gpu_run_summary(
    run_dir: str | Path,
    *,
    run_id: str,
    source_artifact: str,
    hashes: Mapping[str, Any],
    skipped: bool,
    reason: str,
) -> Mapping[str, Any]:
    directory = Path(run_dir)
    metadata_files = tuple(hashes.get("metadata_files", ()))
    skipped_files = tuple(hashes.get("skipped_files", ()))
    parsed = _parse_metadata(directory, metadata_files)
    archive_files = tuple(hashes.get("files", ()))
    checkpoint_count = sum(1 for item in archive_files if is_checkpoint_name(str(item.get("path", ""))))
    summary: dict[str, Any] = {
        "format": GPU_RUN_SUMMARY_FORMAT,
        "run_id": run_id,
        "imported": not skipped,
        "skipped": skipped,
        "reason": reason,
        "imported_at": _now(),
        "source_artifact": source_artifact,
        "artifact": dict(hashes.get("artifact", {})),
        "environment": parsed["environment"],
        "statuses": parsed["statuses"],
        "counts": {
            "archive_files": len(archive_files),
            "metadata_files": len(metadata_files),
            "skipped_files": len(skipped_files),
            "checkpoints": checkpoint_count,
        },
        "evidence": {
            "metadata_files": metadata_files,
            "skipped_files": skipped_files,
            "model_cards": parsed["model_cards"],
        },
        "hashes_path": "hashes.json",
        "summary_md_path": "summary.md",
    }
    return summary


def summary_markdown(summary: Mapping[str, Any]) -> str:
    environment = summary.get("environment", {}) if isinstance(summary.get("environment"), Mapping) else {}
    statuses = summary.get("statuses", {}) if isinstance(summary.get("statuses"), Mapping) else {}
    counts = summary.get("counts", {}) if isinstance(summary.get("counts"), Mapping) else {}
    artifact = summary.get("artifact", {}) if isinstance(summary.get("artifact"), Mapping) else {}
    lines = [f"# Neural GPU run {summary.get('run_id', '')}", ""]
    lines.append(f"- Imported: {bool(summary.get('imported'))}")
    lines.append(f"- Skipped: {bool(summary.get('skipped'))}")
    if summary.get("reason"):
        lines.append(f"- Reason: {summary['reason']}")
    lines.append(f"- Source artifact: `{summary.get('source_artifact', '')}`")
    lines.append(f"- Artifact SHA-256: `{artifact.get('sha256', '')}`")
    lines.extend(
        [
            f"- GPU: {environment.get('gpu_name') or 'unknown'}",
            f"- Torch: {environment.get('torch_version') or 'unknown'}",
            f"- CUDA version: {environment.get('cuda_version') or 'unknown'}",
            f"- CUDA available: {environment.get('cuda_available')}",
            f"- Git commit: {environment.get('git_commit') or 'unknown'}",
            f"- CLI neural: {_status_label(statuses.get('cli_neural'))}",
            f"- Benchmarks: {_status_label(statuses.get('benchmarks'))}",
            f"- Pytest: {_status_label(statuses.get('pytest'))}",
            f"- Metadata files imported: {counts.get('metadata_files', 0)}",
            f"- Archive files hashed: {counts.get('archive_files', 0)}",
            f"- Checkpoints/weights hashed only: {counts.get('checkpoints', 0)}",
            "",
        ]
    )
    return "\n".join(lines)


def verify_gpu_run(run_dir: str | Path) -> Mapping[str, Any]:
    directory = Path(run_dir)
    summary_path = directory / "summary.json"
    hashes_path = directory / "hashes.json"
    errors: list[str] = []
    warnings: list[str] = []
    if not summary_path.exists():
        errors.append("summary.json missing")
    if not hashes_path.exists():
        errors.append("hashes.json missing")
    if errors:
        return {"ok": False, "run_dir": str(directory), "errors": tuple(errors), "warnings": tuple(warnings)}
    summary = load_json(summary_path)
    hashes = load_json(hashes_path)
    if summary.get("format") != GPU_RUN_SUMMARY_FORMAT:
        errors.append("unsupported summary format")
    if hashes.get("format") != HASHES_FORMAT:
        errors.append("unsupported hashes format")
    artifact = hashes.get("artifact", {}) if isinstance(hashes.get("artifact"), Mapping) else {}
    artifact_path = Path(str(artifact.get("path", ""))) if artifact.get("path") else None
    if summary.get("imported") and artifact_path and artifact_path.exists():
        observed = sha256_file(artifact_path)
        if observed != artifact.get("sha256"):
            errors.append("artifact hash mismatch")
    elif summary.get("imported") and artifact.get("path"):
        warnings.append("source artifact is not present; verified imported metadata hashes only")
    for record in hashes.get("metadata_files", ()):
        if not isinstance(record, Mapping):
            errors.append("metadata file hash record is not an object")
            continue
        stored = str(record.get("stored_path", ""))
        metadata_path = directory / stored
        if not stored or not metadata_path.exists():
            errors.append(f"metadata file missing: {stored}")
            continue
        if PurePosixPath(stored.replace("\\", "/")).suffix.lower() in CHECKPOINT_SUFFIXES:
            errors.append(f"checkpoint file was extracted into metadata: {stored}")
            continue
        if sha256_file(metadata_path) != record.get("sha256"):
            errors.append(f"metadata hash mismatch: {stored}")
    return {
        "ok": not errors,
        "run_dir": str(directory),
        "run_id": summary.get("run_id", directory.name),
        "skipped": bool(summary.get("skipped")),
        "errors": tuple(errors),
        "warnings": tuple(warnings),
    }


def compare_gpu_runs(left: str | Path, right: str | Path) -> Mapping[str, Any]:
    left_summary = load_json(Path(left) / "summary.json")
    right_summary = load_json(Path(right) / "summary.json")
    fields = (
        ("gpu_name", "environment"),
        ("torch_version", "environment"),
        ("cuda_version", "environment"),
        ("git_commit", "environment"),
    )
    differences: dict[str, Mapping[str, Any]] = {}
    for field, group in fields:
        left_value = _mapping(left_summary.get(group)).get(field)
        right_value = _mapping(right_summary.get(group)).get(field)
        if left_value != right_value:
            differences[field] = {"left": left_value, "right": right_value}
    left_statuses = _mapping(left_summary.get("statuses"))
    right_statuses = _mapping(right_summary.get("statuses"))
    for field in ("cli_neural", "benchmarks", "pytest"):
        left_value = _status_label(left_statuses.get(field))
        right_value = _status_label(right_statuses.get(field))
        if left_value != right_value:
            differences[field] = {"left": left_value, "right": right_value}
    return {
        "ok": True,
        "left": left_summary.get("run_id"),
        "right": right_summary.get("run_id"),
        "differences": differences,
        "same": not differences,
    }


def _import_tar_metadata(artifact: Path, run_dir: Path, metadata_dir: Path, hashes: dict[str, Any]) -> None:
    with tarfile.open(artifact, "r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            safe_name = safe_archive_name(member.name)
            if safe_name is None:
                _record_skipped(hashes, member.name, member.size, "unsafe_path")
                continue
            handle = archive.extractfile(member)
            if handle is None:
                _record_skipped(hashes, safe_name, member.size, "unreadable")
                continue
            _ingest_member(handle, safe_name, member.size, run_dir, metadata_dir, hashes)


def _import_zip_metadata(artifact: Path, run_dir: Path, metadata_dir: Path, hashes: dict[str, Any]) -> None:
    with zipfile.ZipFile(artifact) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            safe_name = safe_archive_name(info.filename)
            if safe_name is None:
                _record_skipped(hashes, info.filename, info.file_size, "unsafe_path")
                continue
            with archive.open(info, "r") as handle:
                _ingest_member(handle, safe_name, info.file_size, run_dir, metadata_dir, hashes)


def _ingest_member(
    handle,
    safe_name: str,
    size_hint: int,
    run_dir: Path,
    metadata_dir: Path,
    hashes: dict[str, Any],
) -> None:
    may_capture = is_safe_metadata_name(safe_name, size_bytes=size_hint)
    sha256, size_bytes, captured, over_limit = hash_stream(
        handle,
        capture_limit=MAX_METADATA_BYTES if may_capture else 0,
    )
    file_record = {"path": safe_name, "size_bytes": size_bytes, "sha256": sha256}
    hashes["files"].append(file_record)
    if not may_capture:
        reason = "metadata_too_large" if size_hint > MAX_METADATA_BYTES else "non_metadata_or_binary"
        _record_skipped(hashes, safe_name, size_bytes, reason, sha256=sha256)
        return
    if over_limit or captured is None:
        _record_skipped(hashes, safe_name, size_bytes, "metadata_too_large", sha256=sha256)
        return
    try:
        text = captured.decode("utf-8")
    except UnicodeDecodeError:
        _record_skipped(hashes, safe_name, size_bytes, "metadata_not_utf8", sha256=sha256)
        return
    output_path = metadata_output_path(metadata_dir, safe_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8", newline="\n")
    hashes["metadata_files"].append(
        {
            **file_record,
            "stored_path": relative_posix(output_path, run_dir),
        }
    )


def _record_skipped(
    hashes: dict[str, Any],
    path: str,
    size_bytes: int,
    reason: str,
    *,
    sha256: str = "",
) -> None:
    hashes["skipped_files"].append(
        {"path": path, "size_bytes": size_bytes, "sha256": sha256, "reason": reason}
    )


def _parse_metadata(run_dir: Path, metadata_files: Iterable[Mapping[str, Any]]) -> Mapping[str, Any]:
    json_docs: list[tuple[str, Any]] = []
    text_parts: list[str] = []
    model_cards: list[Mapping[str, Any]] = []
    for record in metadata_files:
        stored_path = str(record.get("stored_path", ""))
        if not stored_path:
            continue
        path = run_dir / stored_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        text_parts.append(text)
        suffix = path.suffix.lower()
        if suffix == ".json":
            try:
                json_docs.append((stored_path, json.loads(text)))
            except json.JSONDecodeError:
                pass
        elif suffix == ".jsonl":
            for line in text.splitlines():
                if line.strip():
                    try:
                        json_docs.append((stored_path, json.loads(line)))
                    except json.JSONDecodeError:
                        pass
        if path.name.lower() == "model_card.md":
            model_cards.append({"path": stored_path, **parse_model_card(path)})
    combined_text = "\n".join(text_parts)
    validation = _validation_status(json_docs)
    return {
        "environment": {
            "gpu_name": _find_gpu_name(json_docs, combined_text),
            "torch_version": _find_string(json_docs, combined_text, ("torch_version",), r"Torch:\s*([^\s,]+)"),
            "cuda_version": _find_string(json_docs, combined_text, ("cuda_version",), r"CUDA(?: version)?:\s*([^\s,]+)"),
            "cuda_available": _find_bool(json_docs, combined_text, ("cuda_available",), r"CUDA available:\s*(true|false)"),
            "git_commit": _find_string(json_docs, combined_text, ("git_commit",), r"git(?: commit|_commit)?[:=]\s*([0-9a-fA-F]{7,40}|unknown)"),
        },
        "statuses": {
            "validation": validation,
            "cli_neural": _cli_status(json_docs, combined_text),
            "benchmarks": _benchmark_status(json_docs, combined_text),
            "pytest": _pytest_status(json_docs, combined_text),
            "training": _training_status(json_docs),
        },
        "model_cards": tuple(model_cards),
    }


def _validation_status(json_docs: Iterable[tuple[str, Any]]) -> Mapping[str, Any]:
    for path, value in json_docs:
        if path.endswith("validation.json") and isinstance(value, Mapping):
            results = value.get("results", ())
            return {
                "ok": value.get("ok") if isinstance(value.get("ok"), bool) else None,
                "mode": str(value.get("mode", "")),
                "result_count": len(results) if isinstance(results, list) else 0,
            }
    return {"ok": None, "mode": "", "result_count": 0}


def _cli_status(json_docs: Iterable[tuple[str, Any]], text: str) -> Mapping[str, Any]:
    status = _result_status(json_docs, lambda name: name == "cli_neural" or "cli_neural" in name)
    if status["ok"] is not None:
        return status
    lowered = text.lower()
    if "tiny_torch available" in lowered or "cli neural" in lowered and "ok" in lowered:
        return {"ok": True, "status": "ok", "detail": "text evidence reports neural CLI available"}
    if "cli_neural" in lowered and "failed" in lowered:
        return {"ok": False, "status": "failed", "detail": "text evidence reports neural CLI failure"}
    return {"ok": None, "status": "unknown", "detail": "CLI neural status not found"}


def _benchmark_status(json_docs: Iterable[tuple[str, Any]], text: str) -> Mapping[str, Any]:
    benchmark_results = tuple(_matching_results(json_docs, lambda name: "benchmark" in name))
    if benchmark_results:
        ok = all(bool(result.get("ok")) for result in benchmark_results)
        return {"ok": ok, "status": "ok" if ok else "failed", "count": len(benchmark_results)}
    lowered = text.lower()
    if "benchmarks returned ok" in lowered or "benchmark status: ok" in lowered:
        return {"ok": True, "status": "ok", "count": 0}
    if "benchmark" in lowered and "failed" in lowered:
        return {"ok": False, "status": "failed", "count": 0}
    return {"ok": None, "status": "unknown", "count": 0}


def _pytest_status(json_docs: Iterable[tuple[str, Any]], text: str) -> Mapping[str, Any]:
    status = _result_status(json_docs, lambda name: name in {"full_pytest", "pytest"})
    match = re.search(r"(\d+)\s+passed(?:,\s*(\d+)\s+skipped)?", text, re.IGNORECASE)
    if match:
        return {
            "ok": True,
            "status": "ok",
            "passed": int(match.group(1)),
            "skipped": int(match.group(2) or 0),
        }
    return status


def _training_status(json_docs: Iterable[tuple[str, Any]]) -> Mapping[str, Any]:
    for path, value in json_docs:
        if path.endswith("metrics.json") and isinstance(value, Mapping):
            ok = value.get("ok")
            return {"ok": ok if isinstance(ok, bool) else None, "status": "ok" if ok else "failed"}
    return {"ok": None, "status": "unknown"}


def _result_status(json_docs: Iterable[tuple[str, Any]], predicate) -> Mapping[str, Any]:
    results = tuple(_matching_results(json_docs, predicate))
    if not results:
        return {"ok": None, "status": "unknown", "detail": "status not found"}
    ok = all(bool(result.get("ok")) for result in results)
    return {"ok": ok, "status": "ok" if ok else "failed", "count": len(results)}


def _matching_results(json_docs: Iterable[tuple[str, Any]], predicate) -> Iterable[Mapping[str, Any]]:
    for _path, value in json_docs:
        if not isinstance(value, Mapping):
            continue
        results = value.get("results", ())
        if not isinstance(results, list):
            continue
        for result in results:
            if isinstance(result, Mapping):
                name = str(result.get("name", "")).lower()
                if predicate(name):
                    yield result


def _find_gpu_name(json_docs: Iterable[tuple[str, Any]], text: str) -> str:
    value = _find_json_key(json_docs, ("gpu_name",))
    if isinstance(value, str) and value:
        return value
    for _path, doc in json_docs:
        for mapping in _walk_mappings(doc):
            gpus = mapping.get("gpus")
            if isinstance(gpus, list):
                for gpu in gpus:
                    if isinstance(gpu, Mapping) and isinstance(gpu.get("name"), str):
                        return str(gpu["name"])
    match = re.search(r"(NVIDIA[^\n,;]*(?:RTX|A100|H100|L40|4090)[^\n,;]*)", text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _find_string(json_docs: Iterable[tuple[str, Any]], text: str, keys: tuple[str, ...], pattern: str) -> str:
    value = _find_json_key(json_docs, keys)
    if isinstance(value, (str, int, float)) and str(value):
        return str(value)
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _find_bool(json_docs: Iterable[tuple[str, Any]], text: str, keys: tuple[str, ...], pattern: str) -> bool | None:
    value = _find_json_key(json_docs, keys)
    if isinstance(value, bool):
        return value
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).lower() == "true"
    return None


def _find_json_key(json_docs: Iterable[tuple[str, Any]], keys: tuple[str, ...]) -> Any:
    wanted = set(keys)
    for _path, doc in json_docs:
        for mapping in _walk_mappings(doc):
            for key in wanted:
                if key in mapping and mapping[key] not in (None, ""):
                    return mapping[key]
    return None


def _walk_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for item in value.values():
            yield from _walk_mappings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_mappings(item)


def _status_label(value: Any) -> str:
    if isinstance(value, Mapping):
        status = value.get("status")
        if status:
            return str(status)
        ok = value.get("ok")
        if ok is True:
            return "ok"
        if ok is False:
            return "failed"
    return "unknown"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _display_path(path: Path) -> str:
    return path.as_posix()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
