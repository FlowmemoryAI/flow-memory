"""ERC-4337 account abstraction dry-run seam."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class UserOperationDraft:
    sender: str
    call_data: str
    nonce: int = 0
    init_code: str = "0x"
    call_gas_limit: int = 0
    verification_gas_limit: int = 0
    pre_verification_gas: int = 0
    max_fee_per_gas: int = 0
    max_priority_fee_per_gas: int = 0
    paymaster_and_data: str = "0x"
    signature: str = "0x"

    def as_record(self) -> Mapping[str, object]:
        return {
            "sender": self.sender,
            "nonce": self.nonce,
            "initCode": self.init_code,
            "callData": self.call_data,
            "callGasLimit": self.call_gas_limit,
            "verificationGasLimit": self.verification_gas_limit,
            "preVerificationGas": self.pre_verification_gas,
            "maxFeePerGas": self.max_fee_per_gas,
            "maxPriorityFeePerGas": self.max_priority_fee_per_gas,
            "paymasterAndData": self.paymaster_and_data,
            "signature": self.signature,
            "dryRun": True,
        }

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.sender.startswith("0x"):
            errors.append("sender must be a hex address placeholder")
        if not self.call_data.startswith("0x"):
            errors.append("callData must be hex")
        for name, value in (
            ("nonce", self.nonce),
            ("callGasLimit", self.call_gas_limit),
            ("verificationGasLimit", self.verification_gas_limit),
            ("preVerificationGas", self.pre_verification_gas),
            ("maxFeePerGas", self.max_fee_per_gas),
            ("maxPriorityFeePerGas", self.max_priority_fee_per_gas),
        ):
            if value < 0:
                errors.append(f"{name} must be non-negative")
        return tuple(errors)
