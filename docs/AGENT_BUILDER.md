# Flow Memory Agent Builder

Flow Memory Agent Builder is the browser entry point for creating a Flow Memory agent and composing optional capabilities after the agent exists.

The simple path is intentionally boring and safe: the first agent requires no wallet/API key/funds, uses private memory by default, launches supervised, and stays policy-gated. BYOK, wallet identity, on-chain dry-run upgrade, x402 route simulation, Agent Internet publication, and collaborator matching are optional advanced capabilities.

## Agent Builder architecture

```mermaid
flowchart LR
  Browser[Agent Builder browser route] --> Plan[Agent Builder assembly plan]
  Plan --> Genesis[Agent Genesis]
  Genesis --> Genome[Genome seed passport mirror]
  Genesis --> Mission[Mission Control handoff]
  Plan --> Composer[Capability Composer]
  Composer --> Internet[Agent Internet optional]
  Composer --> Byok[BYOK secret refs optional]
  Composer --> Wallet[Wallet address binding optional]
  Composer --> Onchain[Onchain dry run optional]
  Composer --> Stop[Emergency stop]
  Internet --> Matcher[Skill Matcher]
  Byok --> Redaction[Fingerprint only]
  Wallet --> NoKeys[No private keys]
  Onchain --> DryRun[No funds no broadcast]
```

## First-agent birth sequence

```mermaid
sequenceDiagram
  participant User
  participant Builder
  participant Genesis
  participant Mission
  User->>Builder: Enter name purpose instincts boundaries
  Builder->>Builder: Build simple assembly plan
  Builder->>Genesis: Birth supervised agent
  Genesis-->>Builder: Birth certificate genome seed passport mirror
  Builder-->>User: First prediction and local artifact summary
  Builder->>Mission: Link to Mission Control for the new agent
```

## Optional upgrade lifecycle

```mermaid
stateDiagram-v2
  [*] --> Born
  Born --> SimpleAgent: supervised private default
  SimpleAgent --> AdvancedRequested: user opens capability composer
  AdvancedRequested --> Simulated: BYOK wallet onchain x402 dry run
  Simulated --> ApprovalRequired: risky capability needs review
  ApprovalRequired --> ActiveMetadata: approved metadata only
  ApprovalRequired --> Denied: denied by policy or user
  ActiveMetadata --> EmergencyStopped: emergency stop activated
  Denied --> SimpleAgent
  EmergencyStopped --> SimpleAgent
```

## Agent Builder to Agent Internet skill match flow

```mermaid
sequenceDiagram
  participant Builder
  participant Agent
  participant Registry
  participant Matcher
  participant Workspace
  Builder->>Agent: Optional publish identity request
  Agent->>Registry: Register local identity and skill manifest
  Builder->>Matcher: Match task against local helper agents
  Matcher-->>Builder: Ranked policy-compatible collaborators
  Builder->>Workspace: Optional structured shared workspace
  Workspace-->>Builder: Audit-safe summaries only
```

## Browser route

Run the dashboard and open:

```bash
cd dashboard
npm run dev
```

Then visit `/agents/new` on the local dashboard server.

The route shows:

- Simple mode for first-agent birth.
- Advanced mode for optional upgrades after birth.
- Capability Composer cards for local runtime, predictive cognition, Agent Internet identity, skill manifest, skill matcher, BYOK model key, wallet identity, on-chain dry run, x402 dry-run route, and emergency stop.
- A first prediction, birth certificate placeholder, Agent Passport/Mirror handoff, and Mission Control link.
- A read-only demo mode backed by `dashboard/src/mock-data/agent-builder.json`.

## CLI examples

```bash
python -m flow_memory agent-builder defaults --json
python -m flow_memory agent-builder plan --name Mira --archetype research-builder --purpose "Help me build Flow Memory" --json
python -m flow_memory agent-builder birth --name Mira --archetype research-builder --purpose "Help me build Flow Memory" --json
python -m flow_memory agent-builder simulate-upgrades --agent genesis_agent_11b7e7b435abc729711373b0 --byok --wallet --onchain-dry-run --json
```

## API examples

```text
GET /agent-builder/defaults
POST /agent-builder/assembly-plan
POST /agent-builder/birth
POST /agent-builder/simulate-upgrades
```

Scopes are local public-alpha scopes: `agent-builder:read`, `agent-builder:create`, and `agent-builder:simulate`.

## Safety boundaries

- first agent requires no wallet/API key/funds
- BYOK is optional
- wallet identity is optional
- on-chain upgrade is dry-run only
- x402 route is dry-run/simulated unless future explicit audited mode exists
- network learning is opt-in
- private memory is default
- no private keys
- no seed phrases
- no funds moved
- no broadcast
- no mainnet writes
- relay disabled by default
- PolicyEngine and ApprovalGate remain authoritative

Agent Builder is public-alpha software. It is not production autonomous intelligence, not audited wallet infrastructure, not live settlement, and not a provider-calling console by default.
