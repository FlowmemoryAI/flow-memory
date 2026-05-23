"""Built-in local economic task skill."""
from flow_memory.skills.manifest import SkillManifest

manifest = SkillManifest(
    id="economic-task",
    name="Economic Task",
    description="Prepare a local marketplace task proposal without real funds.",
    input_schema={"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}, "reward": {"type": "number"}}},
    output_schema={"type": "object", "required": ["proposal"], "properties": {"proposal": {"type": "string"}}},
    permissions=("marketplace.bid",),
    economic_value=1.0,
    required_capabilities=("economy",),
    risk_level="high",
)


def run(payload):
    return {"proposal": f"Local economic task: {payload['title']} reward={payload.get('reward', 0)}"}
