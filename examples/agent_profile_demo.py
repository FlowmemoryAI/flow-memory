from flow_memory.agents import create_agent_profile, run_agent_cycle

profile = create_agent_profile("demo", goals=("Explore safely",), allowed_tools=("respond",), autonomy_mode="autonomous_local")
result = run_agent_cycle(profile, "Explore safely")
print({"agent_id": profile.agent_id, "accepted": result.accepted})
