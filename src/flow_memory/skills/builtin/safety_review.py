"""Built-in local safety review skill."""
from typing import Any, Mapping

from flow_memory.skills.manifest import SkillManifest

manifest = SkillManifest(
    id="safety-review",
    name="Safety Review",
    description="Review a proposed action for local Flow Memory safety risks.",
    input_schema={"type": "object", "required": ["action"], "properties": {"action": {"type": "string"}}},
    output_schema={"type": "object", "required": ["risk"], "properties": {"risk": {"type": "string"}}},
    permissions=("respond",),
    required_capabilities=("safety",),
)


def run(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    action = payload["action"].lower()
    high = any(word in action for word in ("private key", "transfer", "delete", "browser"))
    return {"risk": "high" if high else "low", "reviewed": True}
