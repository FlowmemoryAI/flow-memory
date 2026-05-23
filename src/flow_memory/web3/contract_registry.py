"""Contract registry JSON seam with dry-run validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from flow_memory.web3.deployment_plan import CONTRACTS

_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


@dataclass(frozen=True)
class ContractRegistryValidation:
    ok: bool
    missing_contracts: tuple[str, ...] = ()
    invalid_addresses: tuple[str, ...] = ()
    zero_addresses: tuple[str, ...] = ()

    def as_record(self) -> Mapping[str, object]:
        return {
            "ok": self.ok,
            "missing_contracts": self.missing_contracts,
            "invalid_addresses": self.invalid_addresses,
            "zero_addresses": self.zero_addresses,
        }


@dataclass
class ContractRegistry:
    chain: str = "base-sepolia"
    addresses: dict[str, str] = field(default_factory=dict)

    def register(self, name: str, address: str) -> None:
        if name not in CONTRACTS:
            raise ValueError(f"unknown contract: {name}")
        if not is_address(address):
            raise ValueError(f"invalid contract address for {name}")
        self.addresses[name] = address

    def missing_contracts(self) -> tuple[str, ...]:
        return tuple(name for name in CONTRACTS if name not in self.addresses)

    def validate(self, *, allow_zero: bool = False, require_all: bool = True) -> ContractRegistryValidation:
        missing = self.missing_contracts() if require_all else ()
        invalid = tuple(name for name, address in self.addresses.items() if name not in CONTRACTS or not is_address(address))
        zero = tuple(name for name, address in self.addresses.items() if address.lower() == ZERO_ADDRESS.lower())
        if allow_zero:
            zero = ()
        return ContractRegistryValidation(ok=not missing and not invalid and not zero, missing_contracts=missing, invalid_addresses=invalid, zero_addresses=zero)

    def as_record(self) -> Mapping[str, object]:
        return {"chain": self.chain, "addresses": dict(self.addresses), "required_contracts": CONTRACTS}


def is_address(address: str) -> bool:
    return bool(_ADDRESS_RE.fullmatch(address))


def registry_from_mapping(value: Mapping[str, object]) -> ContractRegistry:
    registry = ContractRegistry(chain=str(value.get("chain", "base-sepolia")))
    addresses = value.get("addresses", {})
    if not isinstance(addresses, Mapping):
        raise ValueError("registry addresses must be an object")
    for name, address in addresses.items():
        registry.register(str(name), str(address))
    return registry


def load_registry(path: str | Path) -> ContractRegistry:
    return registry_from_mapping(json.loads(Path(path).read_text(encoding="utf-8")))


def write_registry(registry: ContractRegistry, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(registry.as_record(), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return output
