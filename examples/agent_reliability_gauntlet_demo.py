"""Run the local/offline agent reliability gauntlet and print JSON."""

from __future__ import annotations

import json

from flow_memory.agents.gauntlet import run_offline_reliability_gauntlet


if __name__ == "__main__":
    print(json.dumps(run_offline_reliability_gauntlet(), indent=2, sort_keys=True))
