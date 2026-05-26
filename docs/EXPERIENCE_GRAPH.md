# Experience Graph

The Experience Graph is the local cause/effect map for Flow Memory learning traces.

It connects structured records from Predictive Cognition, Predictive Learning, Agent Genesis, human teaching events, and opt-in network contributions into one inspectable graph:

- agents
- genomes
- goals
- predictions
- selected actions
- observed outcomes
- prediction errors
- lessons
- policy decisions
- teaching events
- sanitized contributions
- proof records

Edges show what happened:

- `predicted`
- `selected_action`
- `caused`
- `failed_because`
- `learned`
- `contributed`
- `policy_applied`
- `policy_denied`
- `improved`
- `taught`

The graph is local and deterministic for public-alpha evidence. It does not share raw private memory by default, does not bypass PolicyEngine or ApprovalGate, and does not claim arbitrary future prediction.

## Commands

```powershell
python -m flow_memory graph build --json
python -m flow_memory graph proofs list --json
python -m flow_memory graph reputation list --json
python -m flow_memory graph agent <agent_id> --json
```

Artifacts are written under:

- `artifacts/experience_graph/graphs/`
- `artifacts/experience_graph/proofs/`
- `artifacts/experience_graph/reputation/`

## API

Read-only API routes are available for local inspection:

- `GET /experience-graph`
- `GET /experience-graph/{graph_id}`
- `GET /experience-graph/agents/{agent_id}`
- `GET /proof-of-learning`
- `GET /proof-of-learning/{proof_id}`
- `GET /learning-reputation`
- `GET /learning-reputation/{agent_id}`

`POST /experience-graph/build` builds local graph artifacts and requires write scope. The Mission Control dashboard only exposes read-mode fixture/API views.

## Mission Control

Mission Control includes a Proof of Learning panel backed by `dashboard/src/mock-data/experience-graph-proof-of-learning.json`. It shows graph counts, proof records, learning reputation, graph events, and artifact paths.

## Limits

The Experience Graph is not AGI, not consciousness, not a production autonomy claim, and not a guarantee that predictions will be correct. It is a local structured-memory ledger for observable Flow Memory domains.
