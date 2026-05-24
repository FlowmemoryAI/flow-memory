"""Export tiny tabular policies for the static browser demo."""
from __future__ import annotations

import json
from pathlib import Path

from flow_memory.rl.policies import TabularQPolicy


def export_tabular_policy(policy: TabularQPolicy, out: str | Path) -> Path:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"format": "flow-memory-tabular-q-v1", "policy": policy.as_record()},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
