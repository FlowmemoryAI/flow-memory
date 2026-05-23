# Swarm and Delegation

Status: functional local prototype.

## Implemented

- `AgentCard`: local agent advertisement with DID, capabilities, reputation, endpoints, metadata.
- `AgentDiscoveryRegistry`: in-process discovery by capability.
- `DelegationContract`: assign, complete, verify lifecycle for delegated work.
- `ReputationRouter`: chooses capable agents by reputation.
- `MultiAgentVerifier`: threshold-based verification votes.
- `LocalSwarmBus`: in-process A2A-style message passing.

## Local demo path

Three local agents can advertise capabilities, route a task by reputation, delegate work, verify the result, and feed the local economy settlement path.

## Adapter seams

Networked A2A, MCP server, libp2p, authentication, replay protection, and cross-process delivery remain future integration work.
