"""Signed protocol messages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import SignatureEnvelope, sign_payload, verify_payload
from flow_memory.protocols.envelopes import ProtocolEnvelope


@dataclass(frozen=True)
class SignedMessage:
    envelope: ProtocolEnvelope
    signature: SignatureEnvelope

    def as_record(self) -> Mapping[str, object]:
        return {"envelope": self.envelope.as_record(), "signature": self.signature.as_record()}


def sign_message(envelope: ProtocolEnvelope, key: LocalKeyPair) -> SignedMessage:
    return SignedMessage(envelope, sign_payload(envelope.as_record(), key))


def verify_message(message: SignedMessage, key: LocalKeyPair) -> bool:
    return verify_payload(message.envelope.as_record(), message.signature, key)
