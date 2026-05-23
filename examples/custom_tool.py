from flow_memory import Agent
from flow_memory.action import Tool
from flow_memory.core.types import Plan, PlanStep


def reverse_tool(args):
    return {"reversed": str(args.get("text", ""))[::-1]}


agent = Agent.create("tool-user")
agent.loop.executor.tool_registry.register(
    Tool(
        name="reverse",
        description="Reverse a string",
        handler=reverse_tool,
        required_permission="tool.invoke",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
    )
)

plan = Plan(
    goal="reverse text",
    steps=(PlanStep(action="tool", args={"name": "reverse", "args": {"text": "flow"}}, required_permission="tool.invoke"),),
)
decision = agent.loop.safety.approve(plan)
print(decision)
print(agent.loop.executor.execute(plan))
