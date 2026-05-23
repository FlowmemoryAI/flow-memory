"""Local test keys for Flow Memory signing."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Mapping

from flow_memory.crypto.asymmetric import DEV_HMAC_ALGORITHM

@dataclass(frozen=True)
class LocalKeyPair:
    key_id: str
    secret: str = field(repr=False)

    def public_id(self) -> str:
        return self.key_id

    def as_public_record(self) -> Mapping[str, str]:
        return {"key_id": self.key_id, "algorithm": DEV_HMAC_ALGORITHM}


def generate_local_keypair(key_id: str = "local-dev") -> LocalKeyPair:
    return LocalKeyPair(key_id=key_id, secret=secrets.token_hex(32))
