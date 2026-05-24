"""Run a tiny optional torch-backed RL policy smoke trainer."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.rl.torch_trainer import TorchRLTrainerConfig, train_torch_actor_critic_smoke


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train optional torch RL smoke policy")
    parser.add_argument("--env", default="safety_gate")
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/rl/torch_smoke.json"))
    args = parser.parse_args(argv)
    result = dict(train_torch_actor_critic_smoke(TorchRLTrainerConfig(env_id=args.env, steps=args.steps, seed=args.seed, device=args.device)))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
