from __future__ import annotations

import json

from flow_memory.web3 import base_sepolia_dry_run


if __name__ == "__main__":
    print(json.dumps(base_sepolia_dry_run(), indent=2, sort_keys=True))
