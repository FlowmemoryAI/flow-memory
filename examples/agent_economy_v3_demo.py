from flow_memory.economy.economy_v3 import EconomyV3

economy = EconomyV3()
result = economy.run_success_lifecycle("did:flow:requester", "did:flow:worker", "local task", 2.0)
print({"status": result["status"], "receipts": len(result["receipts"])})
