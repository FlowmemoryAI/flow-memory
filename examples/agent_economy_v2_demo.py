from flow_memory.economy import AgentEconomyV2


economy = AgentEconomyV2()
requester = "did:flow:requester"
agent = "did:flow:agent"

task = economy.create_task(requester=requester, title="produce local research brief", reward=3.0)
bid = economy.place_bid(task.task_id, agent_did=agent, price=2.5)
economy.assign(task.task_id, bid.bid_id, actor=requester)
economy.fund_escrow(task.task_id, actor=requester)
economy.submit_work(task.task_id, agent_did=agent, artifact={"brief": "local/offline result"})
economy.verify_work(task.task_id, actor=requester, accepted=True, notes="accepted")
settlement = economy.settle_task(task.task_id, actor=requester)

print(settlement)
print({"reputation": economy.reputation_for(agent).score, "audit_events": len(economy.audit_log)})
