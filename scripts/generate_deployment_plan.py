from __future__ import annotations

import json

from flow_memory.web3 import generate_deployment_plan


if __name__ == "__main__":
    print(json.dumps(generate_deployment_plan(), indent=2, sort_keys=True))
