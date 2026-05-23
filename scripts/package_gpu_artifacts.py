"""Package Flow Memory cloud GPU artifacts into a tarball with hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CHECKPOINT_SUFFIXES = {".pt", ".pth", ".ckpt", ".safetensors", ".onnx"}
EXPECTED_FILES = ("validation.json", "gpu_info.json", "metrics.json", "training_log.jsonl", "model_card.md")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(input_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    for path in sorted(item for item in input_dir.rglob("*") if item.is_file()):
        rel = path.relative_to(input_dir).as_posix()
        record = {"path": rel, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
        files.append(record)
        if path.suffix in CHECKPOINT_SUFFIXES:
            checkpoints.append(record)
    missing = [name for name in EXPECTED_FILES if not (input_dir / name).exists()]
    return {
        "format": "flow-memory-cloud-gpu-artifacts-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "missing_expected_files": tuple(missing),
        "files": tuple(files),
        "checkpoint_manifest": tuple(checkpoints),
    }


def package_artifacts(input_dir: Path, out: Path) -> dict[str, Any]:
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"artifact input directory not found: {input_dir}")
    input_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(input_dir)
    (input_dir / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    (input_dir / "checkpoint_manifest.json").write_text(json.dumps({"checkpoints": manifest["checkpoint_manifest"]}, indent=2, sort_keys=True), encoding="utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as tar:
        tar.add(input_dir, arcname=input_dir.name)
    return {"ok": True, "input": str(input_dir), "out": str(out), "manifest": manifest, "tar_sha256": sha256_file(out)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package cloud GPU artifacts")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = package_artifacts(args.input, args.out)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
