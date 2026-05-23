from flow_memory.runtime import AgentRuntimeManager, EconomyRuntimeManager, RuntimeOrchestrator, SkillRuntimeManager


runtime = RuntimeOrchestrator()
runtime.register("agent", AgentRuntimeManager())
runtime.register("skills", SkillRuntimeManager())
runtime.register("economy", EconomyRuntimeManager())
runtime.start_all()
runtime.tick()
print({name: status.running for name, status in runtime.status().items()})
print(runtime.health())
