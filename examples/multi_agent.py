from flow_memory.protocols import AgentMessage, LocalA2ABus

bus = LocalA2ABus()
bus.send(AgentMessage(sender_did="did:key:alpha", recipient_did="did:key:beta", kind="task.offer", payload={"task": "observe"}))
print(bus.receive("did:key:beta"))
