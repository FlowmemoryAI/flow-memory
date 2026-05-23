from flow_memory.economy import EconomicLayer

layer = EconomicLayer()
task_id = layer.marketplace.post_task("summarize audit trace", reward=3.0, requester="did:key:requester")
layer.marketplace.bid(task_id, layer.identity.uri(), price=2.5)
layer.marketplace.assign_lowest_bid(task_id)
print(layer.marketplace.settle(task_id, success=True))
