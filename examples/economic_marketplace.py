from flow_memory.economy import EconomicLayer

layer = EconomicLayer()
task_id = layer.marketplace.post_task("Summarize document", reward=2.0, requester="human")
bid_id = layer.marketplace.bid(task_id, layer.identity.uri(), price=1.5)
settled = layer.marketplace.settle(task_id, success=True, evidence={"result": "ok"})
print(task_id, bid_id, settled)
