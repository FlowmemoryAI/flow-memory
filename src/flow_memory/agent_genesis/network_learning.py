"""Network learning helpers for consented structured experience."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.agent_genesis.consent import CONSENT_MODES, create_consent
from flow_memory.agent_genesis.contribution import create_contribution, sanitize_contribution, validate_contribution


def network_learning_summary(consent: Mapping[str, Any]) -> Mapping[str, Any]:
    mode = str(consent.get("mode", "private_only"))
    return {
        "mode": mode,
        "private_only_default": mode == "private_only",
        "raw_payload_allowed": False,
        "private_memory_allowed": False,
        "allowed_record_types": tuple(consent.get("allowed_record_types", ())),
        "revocable": bool(consent.get("revocable", True)),
    }


__all__ = ["CONSENT_MODES", "create_consent", "create_contribution", "network_learning_summary", "sanitize_contribution", "validate_contribution"]
