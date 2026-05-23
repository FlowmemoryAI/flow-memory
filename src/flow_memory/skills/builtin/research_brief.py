"""Built-in local research brief skill."""
from flow_memory.skills.manifest import SkillManifest

manifest = SkillManifest(
    id="research-brief",
    name="Research Brief",
    description="Create a concise local research brief from provided notes.",
    input_schema={"type": "object", "required": ["topic"], "properties": {"topic": {"type": "string"}, "notes": {"type": "string"}}},
    output_schema={"type": "object", "required": ["brief"], "properties": {"brief": {"type": "string"}}},
    permissions=("respond", "memory.read"),
    required_capabilities=("research",),
)


def run(payload):
    topic = payload["topic"]
    notes = payload.get("notes", "")
    return {"brief": f"Research brief for {topic}: {notes[:240] or 'no notes supplied'}"}
