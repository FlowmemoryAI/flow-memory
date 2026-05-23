from __future__ import annotations

import json

from flow_memory.web3.contract_registry import ContractRegistry


if __name__ == "__main__":
    print(json.dumps(ContractRegistry().as_record(), indent=2, sort_keys=True))
