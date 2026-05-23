from flow_memory.economy import AgentEconomyV2
from flow_memory.swarm import AgentCard, AgentDiscoveryRegistry, ReputationRouter


registry = AgentDiscoveryRegistry()
registry.register(AgentCard("did:agent:researcher", "Researcher", ("research",), reputation=5))
registry.register(AgentCard("did:agent:verifier", "Verifier", ("verify",), reputation=4))
selected = ReputationRouter().choose(registry.discover("research"), "research")

economy = AgentEconomyV2()
requester = "did:requester"
task = economy.create_task(requester, "multi-agent marketplace work", reward=4)
bid = economy.place_bid(task.task_id, selected.did, price=3)
economy.assign(task.task_id, bid.bid_id, actor=requester)
economy.fund_escrow(task.task_id, actor=requester)
economy.submit_work(task.task_id, selected.did, {"result": "completed by selected agent"})
economy.verify_work(task.task_id, requester, accepted=True)
print(economy.settle_task(task.task_id, requester))
