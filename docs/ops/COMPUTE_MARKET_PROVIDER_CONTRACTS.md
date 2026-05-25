# Flow Memory Compute Market Provider Contracts

External quote providers must pass this contract before onboarding. The contract is for quote collection only; it does not authorize live settlement, signing, custody, or transaction broadcast.

## Required quote fields

A provider quote response must include:

- `provider_id`
- `route_id`
- `quote_id`
- `unit_type`
- `unit_price`
- `estimated_units`
- `estimated_total_cost`
- `currency_or_asset`
- `quote_ttl_seconds`
- `expires_at`
- `confidence`
- `capacity_available`
- `settlement_modes`
- `dry_run_supported`
- `assumptions`
- optional `signature` or `verification` metadata

## Safety requirements

Provider responses fail closed if they contain or imply:

- private keys, seed phrases, mnemonics, or custody requirements
- `broadcast=true`, `sendTransaction`, or `signTransaction`
- transfer, withdrawal, deposit, or mainnet settlement instructions
- `live_settlement=true` or a live-settlement requirement
- text attempting to override Flow Memory Compute Market policy
- missing, negative, expired, stale, or unknown pricing
- mismatched provider IDs or missing route IDs
- unsupported unit types, disallowed assets, or disallowed networks
- oversized responses

## Operational requirements

- Providers must be explicitly enabled and have an allowlisted base URL.
- Provider credentials must come from a secret manager or environment variable and must never be logged.
- HTTP quote calls must use bounded timeouts, bounded retries, SSRF protections, response-size limits, and circuit breakers.
- Quote TTLs must be short enough to prevent stale quote exploitation.
- Signed quotes are optional in production planning mode, but required if a future policy enables `require_signed_quote`.

## Conformance commands

```bash
flow-memory compute provider-contract validate tests/fixtures/compute_market/valid_quote.json --json
python -m pytest tests/test_compute_market_provider_contracts.py
```

## Onboarding checklist

1. Validate static sample quotes with the CLI contract validator.
2. Run adapter-level HTTP quote tests with provider sandbox responses.
3. Configure URL allowlist, timeout, retry, max response size, and auth header environment variables.
4. Verify provider text cannot alter policy decisions.
5. Confirm dry-run planning produces no fund movement and no broadcast.
6. Add provider health checks and circuit-breaker thresholds.
7. Document provider SLA, incident contact, retention requirements, and quote-signature metadata if supported.
