"""Inspect local or cloud GPU environment for Flow Memory neural runs."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _git_commit(root: Path) -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _nvidia_smi() -> dict[str, Any]:
    path = shutil.which("nvidia-smi")
    if not path:
        return {"available": False, "path": "", "gpus": (), "error": "nvidia-smi not found"}
    try:
        result = subprocess.run(
            [path, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "path": path, "gpus": (), "error": str(exc)}
    rows = []
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = [part.strip() for part in line.split(",")]
            rows.append({"name": parts[0], "memory_total_mb": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None})
    return {"available": result.returncode == 0, "path": path, "gpus": tuple(rows), "error": result.stderr.strip()}


def collect_environment(root: Path = ROOT) -> dict[str, Any]:
    info: dict[str, Any] = {
        "ok": True,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": _git_commit(root),
        "package_location": "unknown",
        "torch_import": False,
        "torch_version": None,
        "cuda_available": False,
        "cuda_version": None,
        "gpu_name": None,
        "gpu_count": 0,
        "gpu_memory": (),
        "nvidia_smi": _nvidia_smi(),
        "messages": [],
    }
    try:
        import flow_memory

        info["package_location"] = str(Path(flow_memory.__file__).resolve())
    except Exception as exc:  # pragma: no cover - only hit in broken installs
        info["ok"] = False
        info["messages"].append(f"flow_memory import failed: {exc}")
    try:
        import torch

        info["torch_import"] = True
        info["torch_version"] = str(torch.__version__)
        info["cuda_available"] = bool(torch.cuda.is_available())
        info["cuda_version"] = str(torch.version.cuda) if torch.version.cuda else None
        info["gpu_count"] = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
        memories: list[dict[str, Any]] = []
        if torch.cuda.is_available():
            for index in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(index)
                memories.append({"index": index, "name": props.name, "total_memory_bytes": int(props.total_memory)})
            info["gpu_name"] = torch.cuda.get_device_name(0)
        info["gpu_memory"] = tuple(memories)
    except ImportError:
        info["messages"].append("torch is not installed; install with pip install -e '.[dev,ml]'")
    except Exception as exc:  # pragma: no cover - defensive around driver/runtime issues
        info["ok"] = False
        info["messages"].append(f"torch inspection failed: {exc}")
    if not info["torch_import"]:
        info["recommended_next_command"] = "pip install -e '.[dev,ml]'"
    elif not info["cuda_available"]:
        info["recommended_next_command"] = "Use a CUDA-enabled GPU image/pod, then run python scripts/gpu_env_check.py --require-cuda"
    else:
        info["recommended_next_command"] = "python scripts/cloud_gpu_validate.py --smoke --json-out artifacts/cloud_gpu/latest/validation.json"
    return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect Flow Memory GPU environment")
    parser.add_argument("--json", action="store_true", help="Print JSON; JSON is also the default output")
    parser.add_argument("--require-torch", action="store_true", help="Exit non-zero if torch is unavailable")
    parser.add_argument("--require-cuda", action="store_true", help="Exit non-zero if CUDA is unavailable")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root")
    args = parser.parse_args(argv)
    info = collect_environment(args.root)
    if args.require_torch and not info["torch_import"]:
        info["ok"] = False
        info["messages"].append("--require-torch requested but torch is unavailable")
    if args.require_cuda and not info["cuda_available"]:
        info["ok"] = False
        info["messages"].append("--require-cuda requested but CUDA is unavailable")
    print(json.dumps(info, indent=2, sort_keys=True))
    return 0 if info["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
