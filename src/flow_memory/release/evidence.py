"""Release evidence bundle export helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from flow_memory.api.snapshot import api_snapshot
from flow_memory.crypto.hashes import content_hash
from flow_memory.release.gates import run_release_gates
from flow_memory.release.manifest import build_release_manifest
from flow_memory.release.dependencies import build_dependency_inventory
from flow_memory.storage.migrations import migration_plan
from flow_memory.web3.deployment_plan import generate_deployment_plan
from flow_memory.web3.verification import validate_base_sepolia_artifacts
from flow_memory.neural.gpu_evidence import gpu_evidence_index

BUNDLE_FORMAT = "flow-memory-release-evidence-v1"


@dataclass(frozen=True)
class ReleaseEvidenceBundle:
    directory: str
    index: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {"directory": self.directory, "index": dict(self.index)}


def build_evidence_documents(root: str | Path = ".") -> Mapping[str, Mapping[str, Any]]:
    """Build the deterministic release evidence documents."""

    root_path = Path(root).resolve()
    documents: dict[str, Mapping[str, Any]] = {
        "release_manifest.json": build_release_manifest(root_path).as_record(),
        "release_gates.json": run_release_gates(root_path).as_record(),
        "api_snapshot.json": dict(api_snapshot()),
        "storage_schema.json": migration_plan().as_record(),
        "base_deployment_plan.json": dict(generate_deployment_plan()),
        "dependency_inventory.json": build_dependency_inventory(root_path).as_record(),
        "base_artifacts.json": validate_base_sepolia_artifacts(root_path / "deployments" / "base-sepolia").as_record(),
    }
    documents["gpu_evidence.json"] = gpu_evidence_index(root_path)
    clean_clone = root_path / "release_evidence" / "clean_clone_validation.json"
    documents["clean_clone_validation.json"] = _json_file_or_missing(clean_clone)
    return documents


def _json_file_or_missing(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {"ok": False, "missing": str(path)}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        return {
            "ok": False,
            "error": "evidence file is not a JSON object",
            "path": str(path),
        }
    return dict(payload)


def export_release_evidence(root: str | Path, output_dir: str | Path) -> ReleaseEvidenceBundle:
    """Write release evidence files and a deterministic index."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for existing in output.iterdir():
        if existing.is_file():
            existing.unlink()
    documents = build_evidence_documents(root)
    file_hashes: dict[str, str] = {}
    for name, payload in documents.items():
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        (output / name).write_text(text, encoding="utf-8", newline="\n")
        file_hashes[name] = content_hash(payload)

    index_without_hash = {
        "format": BUNDLE_FORMAT,
        "files": tuple(sorted(file_hashes)),
        "file_hashes": dict(sorted(file_hashes.items())),
    }
    bundle_hash = content_hash(index_without_hash)
    index = {**index_without_hash, "bundle_hash": bundle_hash}
    (output / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return ReleaseEvidenceBundle(directory=str(output), index=index)


def verify_release_evidence(output_dir: str | Path) -> ReleaseEvidenceBundle:
    """Verify a previously exported evidence bundle."""

    output = Path(output_dir)
    index_path = output / "index.json"
    if not index_path.exists():
        raise ValueError("release evidence index.json missing")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("format") != BUNDLE_FORMAT:
        raise ValueError("unsupported release evidence bundle format")
    expected_hashes = index.get("file_hashes", {})
    if not isinstance(expected_hashes, Mapping):
        raise ValueError("release evidence file_hashes must be an object")
    files = index.get("files", ())
    if not isinstance(files, (list, tuple)):
        raise ValueError("release evidence files must be a list")
    expected_names = tuple(str(name) for name in files)
    hash_names = tuple(str(name) for name in expected_hashes)
    if tuple(sorted(expected_names)) != tuple(sorted(hash_names)):
        raise ValueError("release evidence index files do not match file_hashes")
    for name in expected_names:
        if Path(name).name != name:
            raise ValueError(f"release evidence file path must be a simple file name: {name}")
    actual_files = tuple(
        sorted(path.name for path in output.iterdir() if path.is_file() and path.name != "index.json")
    )
    if actual_files != tuple(sorted(expected_names)):
        raise ValueError("release evidence directory file set does not match index")
    for name, expected_hash in expected_hashes.items():
        path = output / str(name)
        if not path.exists():
            raise ValueError(f"release evidence file missing: {name}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        observed_hash = content_hash(payload)
        if observed_hash != expected_hash:
            raise ValueError(f"release evidence hash mismatch: {name}")
    index_without_hash = {key: value for key, value in index.items() if key != "bundle_hash"}
    if index.get("bundle_hash") != content_hash(index_without_hash):
        raise ValueError("release evidence bundle hash mismatch")
    return ReleaseEvidenceBundle(directory=str(output), index=index)
