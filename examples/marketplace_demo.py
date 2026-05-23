from flow_memory.economy import EconomicLayer

layer = EconomicLayer()
requester = "did:key:requester"
task_id = layer.marketplace.post_task("Summarize a document", reward=3.0, requester=requester)
bid_id = layer.marketplace.bid(task_id, layer.identity.uri(), price=2.5)
layer.marketplace.accept_bid(task_id, bid_id)
print(layer.marketplace.settle(task_id, success=True))
