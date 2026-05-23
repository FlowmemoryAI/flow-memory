"""Local API auth seams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ApiAuthConfig:
    api_key: str = ""
    require_signed_requests: bool = False


def require_api_key(headers: Mapping[str, str], config: ApiAuthConfig) -> bool:
    if not config.api_key:
        return True
    return headers.get("x-flow-memory-api-key") == config.api_key
