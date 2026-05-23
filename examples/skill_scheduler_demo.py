from flow_memory.skills import SkillManifest, SkillRegistry, SkillRunner, SkillScheduler


registry = SkillRegistry()
manifest = SkillManifest(
    id="hello-skill",
    name="Hello Skill",
    description="local demo",
    input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
    output_schema={"type": "object", "required": ["message"], "properties": {"message": {"type": "string"}}},
    schedule={"interval_seconds": 60},
)
registry.register(manifest)
runner = SkillRunner(registry)
runner.register_handler("hello-skill", lambda payload: {"message": f"hello {payload.get('name', 'agent')}"})
print([skill.skill_id for skill in SkillScheduler(registry).due_skills()])
print(runner.run("hello-skill", {"name": "FlowMemory"}))
