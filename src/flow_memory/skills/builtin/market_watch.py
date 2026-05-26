"""Built-in local market watch skill."""
from typing import Any, Mapping

from flow_memory.skills.manifest import SkillManifest

manifest = SkillManifest(
    id="market-watch",
    name="Market Watch",
    description="Evaluate caller-provided market signals without network calls.",
    input_schema={"type": "object", "properties": {"signals": {"type": "array"}}},
    output_schema={"type": "object", "required": ["signals_seen"], "properties": {"signals_seen": {"type": "integer"}}},
    permissions=("respond",),
    required_capabilities=("market-analysis",),
    risk_level="medium",
)


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    signals = payload.get("signals") or []
    return {"signals_seen": len(signals), "mode": "local_only"}
