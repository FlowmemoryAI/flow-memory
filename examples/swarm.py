from flow_memory.protocols import AgentMessage, CapabilityManifest, LocalA2ABus

bus = LocalA2ABus()
bus.register("did:key:a", CapabilityManifest("did:key:a", "alpha", ["memory"], ["respond"]))
bus.register("did:key:b", CapabilityManifest("did:key:b", "beta", ["perception"], ["respond"]))
print([m.name for m in bus.discover("perception")])
bus.send(AgentMessage(sender_did="did:key:a", recipient_did="did:key:b", kind="ping", payload={"hello": True}))
print(bus.receive("did:key:b"))
