from flow_memory.economy.economy_v3 import EconomyV3

economy = EconomyV3()
result = economy.run_failure_lifecycle("did:flow:requester", "did:flow:worker", "bad task", 2.0)
print({"status": result["status"], "receipts": len(result["receipts"])})
