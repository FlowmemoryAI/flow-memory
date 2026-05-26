"""Optional Web3 adapter skeleton.

The dependency is imported lazily so the core package remains installable without Web3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class Web3ContractAdapter:
    rpc_url: str
    contract_address: str
    abi: list[Mapping[str, Any]]

    def connect(self) -> Any:
        try:
            from web3 import Web3
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install flow-memory[web3] to use Web3ContractAdapter") from exc
        web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        return web3.eth.contract(address=self.contract_address, abi=self.abi)
