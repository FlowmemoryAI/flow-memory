"""Run tiny Flow Memory neural training smoke jobs on CPU or GPU when torch is available."""

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

from flow_memory.neural.torch_optional import is_torch_available
from flow_memory.neural.training.train_agent_policy import train_smoke as train_agent_policy
from flow_memory.neural.training.train_tiny_dual_stream import train_smoke as train_dual_stream
from flow_memory.neural.training.train_world_model import train_smoke as train_world_model


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def run_smoke(*, out: Path, steps: int = 2, seed: int = 0) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = out / "checkpoints"
    info: dict[str, Any] = {
        "ok": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "torch_available": is_torch_available(),
        "seed": seed,
        "steps": steps,
        "runs": {},
    }
    if not is_torch_available():
        info["skipped"] = True
        info["reason"] = "torch not installed; install flow-memory[ml] on the GPU pod"
    else:
        info["runs"] = {
            "tiny_dual_stream": train_dual_stream(steps=steps, checkpoint_dir=str(checkpoint_dir)),
            "world_model": train_world_model(steps=steps, checkpoint_dir=str(checkpoint_dir)),
            "agent_policy": train_agent_policy(steps=steps, checkpoint_dir=str(checkpoint_dir)),
        }
        info["ok"] = all(bool(run.get("ok")) for run in info["runs"].values())
    _write_json(out / "metrics.json", info)
    _write_json(out / "gpu_info.json", {"torch_available": is_torch_available(), "note": "smoke runner does not require CUDA"})
    (out / "model_card.md").write_text(
        "# Flow Memory neural smoke model card\n\nThis smoke run uses tiny synthetic data and optional local PyTorch. It is not a production model.\n",
        encoding="utf-8",
    )
    return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run tiny neural training smoke jobs")
    parser.add_argument("--out", type=Path, default=Path("artifacts/neural/smoke"))
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    result = run_smoke(out=args.out, steps=args.steps, seed=args.seed)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
