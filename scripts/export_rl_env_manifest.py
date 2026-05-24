"""Export a machine-readable Flow Arena environment manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.rl.registry import env_names, make_env


def export_rl_env_manifest() -> dict[str, object]:
    envs = []
    for name in env_names():
        env = make_env(name, seed=0)
        obs = env.reset(seed=0)
        envs.append(
            {
                "env_id": env.env_id,
                "action_count": env.action_space.n,
                "actions": tuple(env.action_labels),
                "observation_keys": tuple(sorted(obs)),
                "vectorizable": True,
                "requires_torch": False,
                "requires_network": False,
                "advisory_only": True,
            }
        )
    return {
        "ok": True,
        "env_count": len(envs),
        "envs": tuple(envs),
        "safety_authority": "PolicyEngine and ApprovalGate remain authoritative outside RL suggestions",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Flow Arena environment manifest")
    parser.add_argument("--out", type=Path, default=Path("artifacts/rl/rl_env_manifest.json"))
    args = parser.parse_args()
    payload = export_rl_env_manifest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
