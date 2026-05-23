from flow_memory import Agent
from flow_memory.protocols import AgentMessage, CapabilityManifest, LocalA2ABus

alpha = Agent.create("alpha", capabilities=["perception"])
beta = Agent.create("beta", capabilities=["memory"])

bus = LocalA2ABus()
bus.register(alpha.did, CapabilityManifest(alpha.did, "alpha", ["perception"], ["respond"]))
bus.register(beta.did, CapabilityManifest(beta.did, "beta", ["memory"], ["respond", "memory.read"]))

bus.send(AgentMessage(sender_did=alpha.did, recipient_did=beta.did, kind="delegate", payload={"task": "recall"}))
print(bus.discover("memory"))
print(bus.receive(beta.did))
