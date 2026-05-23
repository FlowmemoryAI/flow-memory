# Public Alpha Readiness

Status: public-alpha preflight candidate, not production-certified.

Implemented for RC1:

| Area | Status | Evidence |
| --- | --- | --- |
| Clean clone validation | Implemented | `scripts/clean_clone_validation.py`, `release_evidence/clean_clone_validation.json` |
| Public alpha smoke | Implemented | `scripts/public_alpha_smoke.py` |
| Agent reliability gauntlet | Functional prototype | `src/flow_memory/agents/gauntlet.py`, 12 scenarios |
| Asymmetric signing path | Functional prototype | local deterministic asymmetric seam, DID key mapping, signature policy |
| API auth/scope/error seams | Functional prototype | `docs/API_AUTH.md`, `docs/API_ERROR_CONTRACT.md` |
| Dashboard mock API client | Scaffold | `dashboard/src/lib/mock-api.ts` |
| Base Sepolia artifacts | Dry-run implemented | `deployments/base-sepolia/*` |
| Contract security tests | Expanded unaudited coverage | `test/AgentEconomySecurity.t.sol` |
| Docker sandbox backend | Optional adapter seam | disabled by default, Docker required for real execution |
| Storage replay | Implemented local prototype | `scripts/export_event_log.py`, `scripts/replay_event_log.py` |
| Adversarial economy simulation | Functional prototype | `src/flow_memory/simulation/*` |

Public alpha means local/demo/testnet-preflight only. It does not mean mainnet readiness, audited contracts, hardened sandboxing, production auth, or safe handling of real funds.
