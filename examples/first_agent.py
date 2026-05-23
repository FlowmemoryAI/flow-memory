from flow_memory import Agent

agent = Agent.create(name="alpha", capabilities=["perception", "memory", "reasoning"])
print(agent.run("Explore the environment and report findings"))
