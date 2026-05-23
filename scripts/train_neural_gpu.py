"""Run tiny Flow Memory neural training on a CUDA GPU."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.neural.torch_optional import OptionalDependencyError, require_torch
from flow_memory.neural.training.train_agent_policy import train_smoke as train_agent_policy
from flow_memory.neural.training.train_tiny_dual_stream import train_smoke as train_dual_stream
from flow_memory.neural.training.train_world_model import train_smoke as train_world_model


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _gpu_info(torch: Any, device: str) -> dict[str, Any]:
    return {
        "torch_version": str(torch.__version__),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_version": str(torch.version.cuda) if torch.version.cuda else None,
        "device": device,
        "gpu_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


def run_gpu_training(*, steps: int, batch_size: int, device: str, out: Path, seed: int, profile: str) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    try:
        torch = require_torch()
    except OptionalDependencyError as exc:
        result = {"ok": False, "reason": str(exc), "created_at": datetime.now(timezone.utc).isoformat()}
        _write_json(out / "metrics.json", result)
        return result
    if device != "cpu" and not torch.cuda.is_available():
        result = {
            "ok": False,
            "reason": "CUDA is unavailable; choose a GPU pod/image or pass --device cpu for local debugging",
            "gpu_info": _gpu_info(torch, device),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(out / "metrics.json", result)
        _write_json(out / "gpu_info.json", result["gpu_info"])
        return result
    torch.manual_seed(seed)
    checkpoint_dir = out / "checkpoints"
    log_path = out / "training_log.jsonl"
    runs = {
        "tiny_dual_stream": train_dual_stream(steps=steps, checkpoint_dir=str(checkpoint_dir)),
        "world_model": train_world_model(steps=steps, checkpoint_dir=str(checkpoint_dir)),
        "agent_policy": train_agent_policy(steps=steps, checkpoint_dir=str(checkpoint_dir)),
    }
    for name, record in runs.items():
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"name": name, "record": record}, sort_keys=True) + "\n")
    result = {
        "ok": all(bool(run.get("ok")) for run in runs.values()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
        "batch_size": batch_size,
        "device": device,
        "seed": seed,
        "profile": profile,
        "runs": runs,
    }
    _write_json(out / "metrics.json", result)
    _write_json(out / "gpu_info.json", _gpu_info(torch, device))
    (out / "model_card.md").write_text(
        "# Flow Memory tiny GPU training model card\n\nThis run trains tiny synthetic prototypes only. It is not V-JEPA, VideoMAE, or production ML.\n",
        encoding="utf-8",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run tiny neural GPU training lane")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--out", type=Path, default=Path("artifacts/neural/gpu_smoke"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--profile", default="smoke")
    args = parser.parse_args(argv)
    result = run_gpu_training(steps=args.steps, batch_size=args.batch_size, device=args.device, out=args.out, seed=args.seed, profile=args.profile)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
