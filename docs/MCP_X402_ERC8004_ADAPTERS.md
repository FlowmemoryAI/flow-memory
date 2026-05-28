# MCP, x402, and ERC-8004 Adapter Seams

This public-alpha slice adds local adapter seams for tool manifests, dry-run payment intents, and registry-style exports. These are not live production integrations.

## MCP-style tool manifests

Flow Memory stores local MCP-style tool manifests with endpoint refs, schemas, permissions, risk level, optional descriptor hash, policy approval status, and quarantine status.

Security rules:

- no arbitrary tool execution by default
- descriptor integrity hash can be recorded
- risky permissions require review
- poisoned descriptors are quarantined
- MCP manifests do not bypass PolicyEngine or ApprovalGate

## x402 dry-run flow

```mermaid
sequenceDiagram
  participant Client as Requester agent
  participant Provider as Provider agent
  participant Policy as Policy gate
  participant Intent as Payment intent record

  Client->>Provider: request resource
  Provider-->>Client: simulated 402 required
  Client->>Policy: validate dry-run permission
  Policy-->>Intent: write dry_run_x402 intent
  Intent-->>Client: access_granted_simulated
```

The record sets `settlement_state= dry_run_only`, `no_private_key_required=true`, `no_broadcast=true`, and `no_funds_moved=true`.

Flow Memory also exposes an x402 route-preparation seam for the Coinbase-compatible SDK. It records the Python install command `python -m pip install "x402[fastapi,httpx,evm]>=2.11.0"`, the x402.org Base Sepolia testnet facilitator, and the Coinbase CDP facilitator URL. Route preparation can mark a route as Base Sepolia testnet-ready, but Flow Memory still does not relay, broadcast, or move funds by default.

```mermaid
flowchart LR
  Agent[Agent node] --> Route[x402 Route Prepare]
  Route --> SDK[x402 SDK metadata]
  Route --> Testnet[x402.org facilitator eip155:84532]
  Route --> CDP[Coinbase CDP facilitator metadata]
  Route --> Policy[Policy Gate]
  Policy --> Block[Relay disabled by default]
```

```bash
python -m flow_memory x402 status --json
python -m flow_memory x402 route prepare --agent mira --resource skill_match --price 0.001 --pay-to 0x0000000000000000000000000000000000000000 --testnet-live --json
```

## ERC-8004 export-only adapter

```mermaid
flowchart LR
  Identity[Local identity]
  Skills[Skill manifest]
  Reputation[Local reputation]
  Export[ERC-8004-style export file]
  Chain[No on-chain call]

  Identity --> Export
  Skills --> Export
  Reputation --> Export
  Export -. disabled .-> Chain
```

The export file includes identity registry adapter data, reputation registry adapter data, validation registry adapter data, and explicit invariants: no on-chain call, no private key, and no broadcast.

## CLI examples

```bash
python -m flow_memory internet mcp manifests list --json
python -m flow_memory internet payment-intent simulate --from mira --to helper-agent --resource skill_match --amount 0.01 --json
python -m flow_memory internet erc8004 export --agent helper-agent --out artifacts/agent_internet/erc8004/helper-agent.json --json
```

## Optional upgrade adapter relation

BYOK, wallet identity, and on-chain upgrade intents reuse the same adapter-safety posture: local records first, policy gates before capability use, and no real payment settlement or transaction relay in public alpha.

```mermaid
sequenceDiagram
  participant Agent as Agent
  participant Adapter as Adapter Seam
  participant Policy as Policy Gate
  participant Record as Local Record
  Agent->>Adapter: Prepare optional capability
  Adapter->>Policy: Validate safety rules
  Policy->>Record: Write dry-run metadata
  Record-->>Agent: Return references only
```

The first agent does not require wallet/API key/funds.
