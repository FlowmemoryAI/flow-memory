# Squire Goal Orchestrator

Flow Memory treats Squire as an agentic compute economy stack, not as a single model adapter or token-first workflow.

Status: public-alpha local integration seam. No real funds, private keys, token redemption, or live network calls are required by the base suite.

## Live-first model

The integration models these live/public surfaces as adapter contracts:

- Level5: self-funded agent billing/proxy path when a token is configured.
- UsePod: inference marketplace/register/fund/proxy path and route telemetry.
- agent-wallet: subprocess boundary for HTTP 402 / MPP paid APIs.
- usepod-agent: optional provider-side runtime path for hosts that want to serve inference.
- UsePod docs/skills: machine-readable docs sync targets through `pages.json`, `llms.txt`, `llms-full.txt`, and skill catalog URLs.

The integration explicitly does not claim these as live unless separately verified in the current environment:

- TEE attestation.
- On-chain slashing.
- Compute futures.
- Reserved throughput staking.
- Native SQUIRE redemption API.
- Native Dolphin/dphn UsePod upstream inventory.

## Command

```bash
python scripts/squire_goal.py --goal "UsePod routing with budget controls and no surprise fallback"
```

The command emits a JSON plan with the required `/goal squire` sections:

- Goal summary.
- Recommended operating mode.
- Live stack to use now.
- Optional roadmap extensions.
- System architecture.
- Required env vars and secrets.
- Memory writes.
- Budget and routing policy.
- Execution steps.
- Risks and unknowns.
- Success criteria.

## Skill bundle

The SKILL.md-style bundle lives at:

```text
skills/squire-goal/SKILL.md
```

Its description is front-loaded with `SQUIRE`, `Level5`, `UsePod`, `Solana`, `budget`, `routing`, `402`, `MPP`, `provider`, and `marketplace` so progressive-disclosure skill matching can select it without loading the entire workflow.

## API

Local dependency-free router endpoints:

- `GET /squire/status`
- `POST /squire/plan`
- `POST /squire/routes`
- `GET /squire/memory-schema`
- `GET /squire/docs-sources`
- `GET /squire/skill`

With scope enforcement enabled:

- Read endpoints require `squire:read`.
- Plan/route endpoints require `squire:plan`.

## Treasury object

`AgentTreasury` tracks:

- agent id
- wallet public key
- custody status
- Level5 token presence
- UsePod token presence/token id
- USDC balance
- max spend
- input/output price ceilings
- approved models
- preferred route mode

Token values are never emitted by the default status endpoint. The local environment inspection reports only presence flags.

## Economic memory

`EconomicMemoryRecord` captures:

- `goal_id`
- `wallet_pubkey`
- `treasury_source`
- `route_mode`
- `provider_class`
- `model_requested`
- `provider_model_id`
- `tokens_in`
- `tokens_out`
- `price_input_per_million`
- `price_output_per_million`
- `total_cost`
- `balance_before`
- `balance_after`
- `latency_ms`
- `fallback_used`
- `canary_risk`
- `quality_signal`
- `live_or_roadmap`
- `tool_mode`
- `usepod_token_id`

These fields are intentionally different from ordinary prompt memory; they preserve route, cost, balance, and trust context for future agent decisions.

## Routing policy

The default router chooses the cheapest eligible live route. For quality-sensitive goals it ranks quality first, then price and latency.

`marketplace_only` fails closed if no marketplace/key-relay route satisfies the policy. It never silently chooses centralized fallback.

## Tool commerce

HTTP 402 / MPP paid tools are represented as auditable subprocess plans for `agent-wallet`. Flow Memory does not execute wallet commands automatically and does not move funds in tests.

## Provider path

Provider monetization is optional. `build_provider_setup_plan()` produces a setup plan for usepod-agent, model server configuration, identity, bond approval, capabilities/prices, and telemetry. If no GPU is detected, provider mode remains setup/roadmap.

## Safety posture

- Never fabricate balances, wallets, tokens, deposits, or confirmations.
- Never assume SQUIRE redemption mechanics without an explicit environment-specific implementation.
- Keep external tools at plugin/subprocess boundaries.
- Keep policy, approval gates, spend ceilings, and local audit records authoritative.
