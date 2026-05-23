"""Built-in local repo audit skill."""
from flow_memory.skills.manifest import SkillManifest

manifest = SkillManifest(
    id="repo-audit",
    name="Repo Audit",
    description="Summarize local repository audit findings provided by the caller.",
    input_schema={"type": "object", "required": ["findings"], "properties": {"findings": {"type": "string"}}},
    output_schema={"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}},
    permissions=("respond", "memory.read"),
    required_capabilities=("code-review",),
)


def run(payload):
    findings = payload["findings"]
    return {"summary": f"Repo audit summary: {findings[:320]}"}
