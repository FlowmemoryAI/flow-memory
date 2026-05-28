# Agent Genesis

Agent Genesis is the product-facing agent creation path for Flow Memory. It creates a policy-gated local agent with a purpose, instincts, boundaries, a private memory seed, a portable genome, a first prediction, and a Mission Control passport.

This is a public-alpha local system. Agent Genesis does not claim AGI, consciousness, unbounded autonomy, production certification, real-funds operation, or arbitrary real-world future prediction.

## No-download first-agent path

The first agent can be represented as a local profile, genome, memory seed, consent record, passport, and mirror without requiring a separate node download. Local node download is optional for private tools, private compute, or compute contribution.

## Birth flow

1. Choose an agent name.
2. Choose an archetype.
3. Write the purpose.
4. Pick instincts.
5. Confirm boundaries.
6. Add a memory seed.
7. Choose network learning consent.
8. Generate the first prediction.
9. Open Mission Control.

Default mode is `private_only`.

## Commands

```bash
python -m flow_memory genesis archetypes list --json
python -m flow_memory genesis instincts list --json
python -m flow_memory genesis boundaries list --json
python -m flow_memory genesis birth --user local-user --name Mira --archetype research-builder --purpose "Help me build Flow Memory" --instinct careful --instinct builder --consent private_only --json
python -m flow_memory genesis passport show <agent_id> --json
python -m flow_memory genesis genome export <agent_id> --out artifacts/genesis/genomes/<agent_id>.json --json
python -m flow_memory genesis mirror show <agent_id> --json
python -m flow_memory genesis teaching add --agent <agent_id> --type correction --lesson "Check port 4173 before assuming dashboard is broken" --json
python -m flow_memory genesis contributions list --agent <agent_id> --json
```

After the agent has local experience records, build the proof layer:

```bash
python -m flow_memory graph build --json
python -m flow_memory graph agent <agent_id> --json
python -m flow_memory graph reputation show <agent_id> --json
```

## Mission Control

Mission Control shows:

- Agent Birth Flow
- Agent Genome
- Memory Seed
- Learning Consent
- First Prediction
- Agent Mirror
- Agent Passport
- contribution status
- optional Experience Graph / Proof of Learning status after the agent has prediction-error records

Dashboard fixture:

```text
dashboard/src/mock-data/agent-genesis-onboarding.json
```

## Public-alpha limits

- Neural and cognition output is advisory.
- PolicyEngine and ApprovalGate remain authoritative.
- Network learning is opt-in.
- Raw private payloads are excluded by default.
- No real funds, private keys, transaction broadcast, live settlement, or live provider calls are used.
## Agent Internet handoff

A born agent can be registered into the local Agent Internet after the user keeps or changes the default private-only consent. Registration publishes identity and skill metadata only; private memory seed content remains excluded.

```bash
python -m flow_memory internet agents register --agent <agent_id> --json
python -m flow_memory internet skills publish --agent <agent_id> --skill research --skill memory --skill verification --json
```

Agent Internet discovery never overrides the agent's boundaries, PolicyEngine decisions, ApprovalGate requirements, or private-memory consent.

## Optional upgrades after birth

Agent Genesis does not ask for wallet setup or provider credentials during first-agent creation. The first agent does not require wallet/API key/funds.

After the agent exists, Mission Control can show optional upgrades:

- BYOK model key reference, stored as secret ref plus fingerprint only.
- Wallet identity binding, address-only by default.
- On-chain dry-run upgrade intent with prepare/sign/relay separation.
- Emergency stop for every optional upgrade path.
