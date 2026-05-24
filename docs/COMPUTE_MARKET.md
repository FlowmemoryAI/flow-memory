# Flow Memory Compute Market

Flow Memory Compute Market is the local/dry-run economic control plane for agentic compute. It models providers, routes, quotes, capacity windows, reservation intents, payment intents, settlement simulation, route decisions, and economic memory records.

It replaces public Squire-branded surfaces with Flow Memory-native Compute Market surfaces.

## Safety and maturity

- Dry-run only by default.
- No private keys.
- No real funds moved.
- No transaction broadcast.
- No live provider calls.
- No live settlement implied.
- PolicyEngine and ApprovalGate remain authoritative.
- Public-alpha prototype; not production settlement infrastructure.

## CLI

```bash
python -m flow_memory compute providers
python -m flow_memory compute routes
python -m flow_memory compute policies
python -m flow_memory compute plan --goal "Explore and report" --budget 0.01 --max-quote 0.01
```

## Local API

- `POST /compute/plan`
- `POST /compute/marketplace-plan`
- `POST /compute/quote`
- `POST /compute/route`
- `POST /compute/payment-plan`
- `POST /compute/simulate-settlement`
- `GET /compute/providers`
- `GET /compute/routes`
- `GET /compute/policies`
- `GET /compute/economic-memory`
- `POST /compute/economic-memory/query`

Read endpoints use `compute:read` when scope enforcement is enabled. Planning/mutation-style dry-run endpoints use `compute:plan`.

## FlowLang

FlowLang agents can declare compute requirements:

```yaml
compute:
  enabled: true
  budget_limit: 0.01
  max_quote: 0.01
  preferred_strategy: cheapest_eligible
  allowed_providers: [local-cpu, market-sim-small]
  allowed_routes: [local-cpu-small, market-small]
  dry_run_required: true
  payment_rail_preference: local_credits
  model: small-general
  expected_input_tokens: 1000
  expected_output_tokens: 500
```

The parser stores this as `metadata.compute_market`; `agent_profile_from_ir` converts it into `AgentProfile.compute_config`.

## Agent integration

When `AgentProfile.compute_config` is present and enabled, `AgentRunner` asks `AgentComputeBinding` for a deterministic dry-run quote and route. Successful decisions are written to local agent memory as `compute_economic_memory`. Missing policy, invalid policy, over-budget quotes, unsafe live-payment settings, or no eligible route fail closed.

## Mission Control telemetry

Compute Market visual events include:

- compute plan requested
- quote generated
- route decision selected
- capacity/reservation simulated
- payment plan generated
- settlement simulated
- policy denied/fail-closed
- economic memory record written

Mission Control treats these as real local/replay telemetry. Mock data remains explicitly labeled.

## Release evidence

`export_release_evidence.py` includes `compute_market.json` with:

- API endpoint presence
- CLI command presence
- dry-run-only settlement invariant
- no-private-key/no-funds/no-broadcast invariant
- policy fail-closed sample
- deterministic simulation, FlowLang/agent, visual telemetry, and naming-cleanup test presence

## Migration note

Older Squire/UsePod/Level5 research remains useful context, but public Flow Memory launch surfaces should use Flow Memory Compute Market terminology. Do not imply SQUIRE redemption, live UsePod/Level5 calls, live provider settlement, or mainnet payments.
