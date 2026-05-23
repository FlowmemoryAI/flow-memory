"""Built-in local memory consolidation skill."""
from flow_memory.skills.manifest import SkillManifest

manifest = SkillManifest(
    id="memory-consolidation",
    name="Memory Consolidation",
    description="Condense caller-provided memories into a local summary.",
    input_schema={"type": "object", "properties": {"memories": {"type": "array"}}},
    output_schema={"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}},
    permissions=("memory.read", "respond"),
    required_capabilities=("memory",),
)


def run(payload):
    memories = payload.get("memories") or []
    return {"summary": f"Consolidated {len(memories)} memory record(s)."}
