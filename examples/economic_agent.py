"""Economic-layer example."""

from flow_memory import Agent
from flow_memory.core.types import ActionResult, Plan, PlanStep

agent = Agent.create("market-alpha", capabilities=["marketplace", "reasoning"])
market = agent.loop.economy.marketplace

task_id = market.post_task("summarize local environment", reward=2.0, requester="requester")
bid_id = market.bid(task_id, agent.did, price=1.5)
market.accept_bid(task_id, bid_id)

plan = Plan(goal="complete task", steps=(PlanStep(action="respond", economic_value=1.5),))
settlement = agent.loop.economy.settle(plan, ActionResult(success=True, output="done"))
print({"task_id": task_id, "bid_id": bid_id, "settlement": settlement})
