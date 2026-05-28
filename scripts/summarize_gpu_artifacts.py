"""Summarize Flow Memory cloud GPU artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return cast(dict[str, Any], data)


def summarize(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"artifact path not found: {path}")
    validation = _load_json(path / "validation.json")
    metrics = _load_json(path / "metrics.json")
    gpu_info = _load_json(path / "gpu_info.json")
    manifest = _load_json(path / "artifact_manifest.json")
    lines = [f"Flow Memory GPU artifact summary: {path}"]
    if validation:
        lines.append(f"validation ok: {validation.get('ok')}")
        lines.append(f"validation mode: {validation.get('mode')}")
        lines.append(f"validation commands: {len(validation.get('results', ()))})")
    if metrics:
        lines.append(f"metrics ok: {metrics.get('ok')}")
        if metrics.get("skipped"):
            lines.append(f"metrics skipped: {metrics.get('reason')}")
    if gpu_info:
        lines.append(f"cuda available: {gpu_info.get('cuda_available')}")
        lines.append(f"gpu: {gpu_info.get('gpu_name')}")
    if manifest:
        lines.append(f"files packaged: {len(manifest.get('files', ())) }")
        lines.append(f"checkpoints: {len(manifest.get('checkpoint_manifest', ())) }")
        missing = manifest.get("missing_expected_files", ())
        if missing:
            lines.append(f"missing optional expected files: {', '.join(missing)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize cloud GPU artifact directory")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    print(summarize(args.path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
