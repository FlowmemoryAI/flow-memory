# Agent Ownership Model

An agent may be owned by an individual, team, DAO, service operator, or research group.

`src/flow_memory/economy/agent_ownership.py` defines local ownership records with:

- `agent_id`
- `owner_id`
- optional `operator_id`
- optional `governance_id`

The owner/operator can request payment for the agent. The owner/governance path can change high-level policy. This is a local model today; production custody, key management, and governance are future work.
