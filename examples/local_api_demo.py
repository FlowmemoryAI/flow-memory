from flow_memory.api import create_default_router
from flow_memory.swarm import AgentCard


router = create_default_router()
router.register_agent(AgentCard("did:agent:1", "Agent One", ("research",), reputation=3))
print(router.dispatch("GET", "/health"))
print(router.dispatch("GET", "/agents"))
print(router.dispatch("POST", "/marketplace/tasks", {"title": "demo task", "requester": "did:agent:1", "reward": 1}))
