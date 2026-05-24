# Build Report: Flow Memory Production-Shaped Agent OS + Economy V3

Date: 2026-05-23

Target repo: `E:\FlowMemory\flow-memory`

GitHub: `https://github.com/FlowmemoryAI/flow-memory`

## Summary

This build upgrades Flow Memory beyond the Agent Economy V2 and FlowLang prototype into a production-shaped autonomous AI agent OS prototype. The implementation adds a first-class AI agent layer, FlowLang-to-Agent runtime integration, Agent Economy V3 lifecycles and receipts, durable SQLite storage, local development signing/provenance, production API seams, Base Sepolia/ERC-4337 dry-run adapters, sandbox profile/receipt interfaces, MCP/A2A/libp2p protocol seams, dashboard scaffold, CI workflows, and production readiness documentation.

This is not production-certified. Contracts remain unaudited, sandboxing is not hardened isolation, Web3 is dry-run only, and FlowLang remains a v0/prototype language layer.

## Major systems added

### AI agent layer

Created `src/flow_memory/agents/` with:

- `AgentProfile`, `RiskBudget`
- `AgentState`, `AgentHealth`
- `Goal`, `GoalStack`, priorities/status
- Autonomy modes: `manual`, `supervised`, `autonomous_local`, `autonomous_economic`, `disabled`
- `CognitivePlanner`, `Plan`, `PlanStep`
- `TaskGraph`, `TaskNode`, `TaskEdge`
- `AgentRunner`, `AgentRunResult`, `run_agent_cycle`
- Memory, skill, tool, policy, economy, swarm bindings
- Evaluation and reflection

### FlowLang runtime integration

Added:

- FlowIR adapters: `agent_adapter.py`, `skill_adapter.py`, `policy_adapter.py`, `economy_adapter.py`, `memory_adapter.py`, `runtime_adapter.py`
- `flowlang/runner.py`, `flowlang/compiler.py`, `flowlang/runtime.py`
- CLI support: `python -m flow_memory --flow examples/flowlang_agent.flow --json "Run the declared agent"`
- API endpoints: `/flowlang/compile`, `/flowlang/validate`, `/flowlang/run`, `/flowlang/examples`
- FlowLang examples for safe skill, economy, and policy-blocking paths

### Agent Economy V3

Added local/testnet-ready architecture in `src/flow_memory/economy/`:

- `economy_v3.py`
- `lifecycle.py`
- `verification.py`
- `settlement_v3.py`
- `escrow_v3.py`
- `reputation_v3.py`
- `task_receipts.py`
- `work_submission.py`
- `risk.py`
- `verifier_selection.py`

Implemented local success lifecycle:

```text
create task -> publish -> discover/bid -> assign -> escrow -> submit work -> verify -> settle -> reputation update -> audit receipt -> memory update
```

Implemented failure lifecycle:

```text
create task -> assign -> bad work -> verification fails -> dispute -> slashing -> reputation penalty -> audit receipt -> memory update
```

### Durable storage

Created SQLite-backed storage in `src/flow_memory/storage/`:

- schema version table
- migration bootstrap
- event store
- audit store
- agent profile/state store
- marketplace store
- reputation store
- memory store
- skill store
- JSONL export

### Signing and provenance

Created `src/flow_memory/crypto/` with local development HMAC signing:

- local test keys
- canonical JSON
- content hashes
- manifest signing
- receipt signing
- DID payload signing seam
- provenance hash chain

Also added versioned FlowIR manifest envelopes in `src/flow_memory/ir/manifest.py`.

### Audit replay and API snapshot hardening

Added:

- `src/flow_memory/storage/replay.py` for deterministic event replay chains.
- `AuditStore.append_chained()` and `AuditStore.verify_chained()` for local tamper-evident audit streams.
- `src/flow_memory/api/snapshot.py` for manifest/OpenAPI snapshot validation.
- `scripts/export_api_snapshot.py` and `docs/API_SNAPSHOT.json` for committed API drift artifacts.
- `src/flow_memory/storage/checkpoints.py` for signed local audit checkpoints.
- `scripts/replay_audit_log.py` for replaying and checkpointing SQLite audit logs.
- `src/flow_memory/release/gates.py` and `scripts/release_gate.py` for offline release gates, including dependency policy validation.
- `scripts/verify.sh` now runs the release gate after tests, CLI smoke, and perception benchmark.
- `src/flow_memory/storage/backup.py` for deterministic whole-store backup/restore bundles.
- `scripts/backup_storage.py` and `scripts/restore_storage.py` for local recovery workflows.
- `src/flow_memory/storage/retention.py` and `scripts/apply_retention_policy.py` for local retention/compaction hygiene.
- `src/flow_memory/storage/integrity.py` and `scripts/verify_storage_backup.py` for live-state-to-backup root-hash verification.
- `src/flow_memory/storage/migrations.py` and `scripts/verify_storage_schema.py` for schema fingerprints and migration metadata verification.
- `scripts/release_gate.py` now includes storage schema verification.
- `src/flow_memory/release/manifest.py` and `scripts/generate_release_manifest.py` for offline release manifest generation.
- `src/flow_memory/release/evidence.py` and `scripts/export_release_evidence.py` for exporting and strictly verifying a hashed release evidence bundle, including dependency inventory.
- `src/flow_memory/release/readiness.py` and `scripts/release_decision.py` for explicit local/testnet/production go-no-go decisions with dependency inventory evidence requirements.
- `src/flow_memory/release/dependencies.py` and `scripts/export_dependency_inventory.py` for offline dependency inventory and dependency policy checks.


### Production API seams

Added:

- local API-key auth seam with case-insensitive header matching
- signed request decision helper that binds method, path, and payload to the local signing seam
- optional server seam
- OpenAPI generation path
- endpoint modules for agents, FlowLang, economy, memory, skills, audit, swarm

### Base Sepolia / ERC-4337 dry-run seams

Created `src/flow_memory/web3/` and scripts:

- `scripts/generate_deployment_plan.py`
- `scripts/base_sepolia_dry_run.py`
- `scripts/export_contract_addresses.py`
- `scripts/verify_contract_config.py`
- Hardened `src/flow_memory/web3/contract_registry.py` with address, required-contract, zero-address, and unknown-contract validation.
- Upgraded `scripts/verify_contract_config.py` to validate optional registry JSON.

No real funds, private keys, providers, or deployments are required.

### Sandbox hardening interfaces

Added sandbox profiles, resource limits, container sandbox seam, sandbox policy checks, and sandbox receipts. Docker/container execution is not enabled by default.

### Protocol seams

Added MCP/A2A/libp2p gateway seams plus signed protocol envelopes. No network transport is required by default.

### Dashboard and CI

Added dashboard scaffold and CI workflows for contracts, docs, and release dry-run.

## Validation commands run

```text
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe -m pytest -q
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe examples/flowlang_compile_demo.py
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe examples/flowlang_runtime_demo.py
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe examples/flowlang_economy_demo.py
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe -m flow_memory --json "Explore and report"
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe -m flow_memory --flow examples/flowlang_agent.flow --json "Run the declared agent"
bash scripts/verify.sh
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/generate_deployment_plan.py
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/base_sepolia_dry_run.py
docker compose config
forge build
forge test
cargo test
git diff --check
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/export_api_snapshot.py --write docs/API_SNAPSHOT.json
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/replay_audit_log.py --db C:/tmp/flow-memory-audit-replay.sqlite3 --checkpoint --require-events
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/release_gate.py --root E:/FlowMemory/flow-memory
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/backup_storage.py --db C:/tmp/flow-memory-backup-source.sqlite3 --out C:/tmp/flow-memory-storage-backup.json
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/restore_storage.py --backup C:/tmp/flow-memory-storage-backup.json --db C:/tmp/flow-memory-backup-restored.sqlite3
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/apply_retention_policy.py --db C:/tmp/flow-memory-retention.sqlite3 --policy C:/tmp/flow-memory-retention-policy.json
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/verify_storage_backup.py --db C:/tmp/flow-memory-backup-source.sqlite3 --backup C:/tmp/flow-memory-storage-backup.json
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/verify_storage_schema.py
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/generate_release_manifest.py --root E:/FlowMemory/flow-memory --sign-local
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/verify_contract_config.py
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/export_release_evidence.py --root E:/FlowMemory/flow-memory --out C:/tmp/flow-memory-release-evidence
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/export_release_evidence.py --out C:/tmp/flow-memory-release-evidence --verify-only
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/release_decision.py --root E:/FlowMemory/flow-memory --target local
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/export_dependency_inventory.py --root E:/FlowMemory/flow-memory
E:/FlowMemory/flow-memory/.venv/Scripts/python.exe scripts/export_dependency_inventory.py --root E:/FlowMemory/flow-memory --policy
```

## Validation results

| Command | Result |
| --- | --- |
| `python -m pytest -q` | Pass: `235 passed` |
| `python examples/flowlang_compile_demo.py` | Pass |
| `python examples/flowlang_runtime_demo.py` | Pass |
| `python examples/flowlang_economy_demo.py` | Pass |
| `python -m flow_memory --json "Explore and report"` | Pass |
| `python -m flow_memory --flow examples/flowlang_agent.flow --json "Run the declared agent"` | Pass |
| `bash scripts/verify.sh` | Pass |
| `python scripts/generate_deployment_plan.py` | Pass |
| `python scripts/base_sepolia_dry_run.py` | Pass |
| `python scripts/export_api_snapshot.py --write docs/API_SNAPSHOT.json` | Pass |
| `python scripts/replay_audit_log.py --db C:/tmp/flow-memory-audit-replay.sqlite3 --checkpoint --require-events` | Pass |
| `python scripts/release_gate.py --root E:/FlowMemory/flow-memory` | Pass |
| `python scripts/backup_storage.py --db C:/tmp/flow-memory-backup-source.sqlite3 --out C:/tmp/flow-memory-storage-backup.json` | Pass |
| `python scripts/restore_storage.py --backup C:/tmp/flow-memory-storage-backup.json --db C:/tmp/flow-memory-backup-restored.sqlite3` | Pass |
| `python scripts/apply_retention_policy.py --db C:/tmp/flow-memory-retention.sqlite3 --policy C:/tmp/flow-memory-retention-policy.json` | Pass |
| `python scripts/verify_storage_backup.py --db C:/tmp/flow-memory-backup-source.sqlite3 --backup C:/tmp/flow-memory-storage-backup.json` | Pass |
| `python scripts/verify_storage_schema.py` | Pass |
| `python scripts/generate_release_manifest.py --root E:/FlowMemory/flow-memory --sign-local` | Pass |
| `python scripts/verify_contract_config.py` | Pass |
| `python scripts/export_release_evidence.py --root E:/FlowMemory/flow-memory --out C:/tmp/flow-memory-release-evidence` | Pass |
| `python scripts/export_release_evidence.py --out C:/tmp/flow-memory-release-evidence --verify-only` | Pass |
| `python scripts/release_decision.py --root E:/FlowMemory/flow-memory --target local` | Pass |
| `python scripts/export_dependency_inventory.py --root E:/FlowMemory/flow-memory` | Pass |
| `python scripts/export_dependency_inventory.py --root E:/FlowMemory/flow-memory --policy` | Pass |
| `docker compose config` | Pass |
| `forge build` | Pass |
| `forge test` | Pass: `11 tests passed` |
| `cargo test` | Pass |
| `git diff --check` | Pass |
| secret scan | Pass: no obvious real secret patterns found |

## Current test count

`python -m pytest -q` currently passes with `287 passed, 1 skipped`.

## Public Alpha / Testnet Preflight RC1 update

RC1 adds public-alpha preflight hardening on top of the V3 build:

- `scripts/clean_clone_validation.py` and `scripts/public_alpha_smoke.py` for fresh-checkout validation.
- `release_evidence/clean_clone_validation.json` for recorded clean-clone evidence.
- `src/flow_memory/agents/gauntlet.py`, `scenarios.py`, and `reliability.py` for a 12-scenario offline reliability gauntlet.
- `src/flow_memory/crypto/asymmetric.py`, `canonical_json.py`, `did_keys.py`, `key_registry.py`, `signature_policy.py`, and `receipt_verifier.py` for local deterministic asymmetric signing, DID key mapping, canonical JSON, and public-alpha signature policy checks.
- `src/flow_memory/api/errors.py`, `request_context.py`, `scopes.py`, `rate_limits.py`, and `audit_middleware.py` for structured API errors, scope checks, local rate limiting, and request audit seams.
- `docs/openapi/flow-memory.openapi.json` for deterministic OpenAPI snapshot coverage.
- `dashboard/src/lib/*` and `dashboard/src/app/screens.ts` for typed mock dashboard API/client/screen scaffolding.
- `deployments/base-sepolia/*`, `scripts/validate_base_sepolia_artifacts.py`, and expanded `src/flow_memory/web3/*` dry-run helpers for Base Sepolia artifact preflight.
- `test/AgentEconomySecurity.t.sol` for additional unauthorized-call, double-settlement, invalid-input, and authority-check contract coverage.
- `src/flow_memory/action/docker_sandbox.py` and `sandbox_backends.py` for optional Docker sandbox backend selection and explicit disabled-by-default behavior.
- `scripts/export_event_log.py`, `scripts/replay_event_log.py`, and `scripts/verify_storage_integrity.py` for local audit event JSONL replay and integrity evidence.
- `src/flow_memory/simulation/*` and `examples/agent_economy_adversarial_sim_demo.py` for deterministic adversarial multi-agent economy simulation.
- Public-alpha docs: `docs/PUBLIC_ALPHA_QUICKSTART.md`, `docs/PUBLIC_ALPHA_READINESS.md`, `docs/CLEAN_CLONE_VALIDATION.md`, `docs/TESTNET_PREFLIGHT.md`, `docs/RELEASE_GATES.md`, `docs/SECURITY_REVIEW_CHECKLIST.md`, `docs/CONTRACT_SECURITY_TESTS.md`, `docs/DASHBOARD.md`, `docs/AUDIT_REPLAY.md`, and `docs/ADVERSARIAL_ECONOMY_SIMULATION.md`.

RC1 validation updates:

| Command | Result |
| --- | --- |
| `python -m pytest -q` | Pass: `287 passed, 1 skipped` |
| `python scripts/clean_clone_validation.py --root E:/FlowMemory/flow-memory --out release_evidence/clean_clone_validation.json` | Pass |
| `python scripts/public_alpha_smoke.py --root E:/FlowMemory/flow-memory` | Pass |
| `python examples/agent_reliability_gauntlet_demo.py` | Pass |
| `python examples/agent_economy_adversarial_sim_demo.py` | Pass |
| `python scripts/validate_base_sepolia_artifacts.py --dir deployments/base-sepolia` | Pass |
| `python scripts/export_event_log.py` | Pass |
| `python scripts/replay_event_log.py` | Pass |
| `python scripts/verify_storage_integrity.py` | Pass |
| `python scripts/sandbox_smoke_test.py` | Pass |
| `python scripts/export_release_evidence.py --root E:/FlowMemory/flow-memory` | Pass |
| `python scripts/verify_release_evidence.py` | Pass |
| `python scripts/release_decision.py --root E:/FlowMemory/flow-memory --target public-alpha` | Pass |
| `forge test` | Pass: `16 tests passed` |

## Honest limitations

- FlowLang remains v0 and is not stable production syntax.
- Signing includes local HMAC and deterministic asymmetric/DID seams, but not production key custody.
- SQLite storage is local and not a distributed persistence layer.
- API server/auth/scopes/rate limits are local seams; internal router remains the tested path.
- Base Sepolia and ERC-4337 are dry-run seams only.
- Sandbox profiles/receipts and optional Docker backend seams exist, but hardened container/VM isolation is not implemented.
- MCP/A2A/libp2p modules are adapter seams without live networking by default.
- Contracts are unaudited and not deployment-ready.


## Neural Agent Layer v1 build update — 2026-05-23

Added optional neural subsystem, synthetic datasets, tiny dual-stream perception, predictive world model, advisory plan/skill/risk/evaluation scoring, neural memory retrieval, tiny training smoke scripts, V-JEPA 2 / VideoMAE adapter seams, CLI `--neural`, FlowLang neural config, neural examples, neural benchmarks, and documentation. PyTorch remains optional and default tests skip torch-only behavior when absent.


## Dependency-free local HTTP API server update — 2026-05-23

Added `src/flow_memory/api/http_server.py` and `scripts/run_local_api_server.py` to expose the internal API router through a standard-library local HTTP server. The gateway covers JSON parsing, API-key checks, optional scope enforcement, local fixed-window rate limiting, request audit events, and structured API errors. Added `tests/test_api_http_server.py` for direct gateway behavior plus an ephemeral localhost request. This remains a local/public-alpha server boundary, not production internet auth or deployment infrastructure.


## RL Arena + Neural GPU Evidence Integration

Baseline commit before this build: `34c67f1`.

### Implementation summary

- Added importable cloud GPU evidence records under `src/flow_memory/neural/gpu_evidence.py`, `run_records.py`, `artifacts.py`, and `model_cards.py`.
- Added scripts for GPU artifact import, summary, verification, and comparison: `scripts/import_gpu_run_artifact.py`, `scripts/summarize_gpu_run.py`, `scripts/verify_gpu_run_artifact.py`, and `scripts/compare_gpu_runs.py`.
- Added `neural-gpu-smoke` release decision target and included GPU evidence metadata in release evidence bundles.
- Added dependency-free neural API endpoints for status, backend metadata, GPU run evidence, benchmark metadata, checkpoint metadata, smoke validation, and local-only tiny training.
- Added Flow Arena RL core under `src/flow_memory/rl/`: spaces, env interface, vector env, rewards, rollout buffer, registry, metrics, baseline policies, Q-learning trainer, evaluator, checkpoint store, local backend, PufferLib adapter seam, and browser policy export.
- Added Flow Memory RL environments: ToolUseEnv, MemoryRetrievalEnv, EconomyMarketEnv, VerifierEnv, SwarmDelegationEnv, SafetyGateEnv, SelfRepairEnv, and GridWorld.
- Added advisory RL binding to `AgentProfile`, `AgentRunner`, FlowLang parsing, and FlowIR-to-AgentProfile mapping. RL suggestions cannot bypass PolicyEngine, ApprovalGate, autonomy mode, or economy policy.
- Added RL examples, RL benchmarks, static browser demo path, PufferLib experiment notes, and RL/neural evidence docs.
- Hardened several scripts to import local `src/` code instead of stale installed packages, and made release evidence export clean stale bundle files before writing a new bundle.

### Validation results for this build

| Command | Result |
| --- | --- |
| `python -m pytest -q` | Pass: `373 passed, 17 skipped` |
| `bash scripts/verify.sh` | Pass: includes pytest, CLI smoke, perception benchmark, and release gate |
| `python -m flow_memory --json "Explore and report"` | Pass |
| `python scripts/gpu_env_check.py --json` | Pass; local machine has no torch/CUDA, reports next command clearly |
| `python scripts/cloud_gpu_validate.py --smoke --json-out artifacts/cloud_gpu/local_smoke/validation.json` | Pass |
| `python scripts/train_neural_smoke.py --out artifacts/neural/smoke` | Pass; skipped torch work locally because torch is absent |
| `python scripts/package_gpu_artifacts.py --input artifacts/cloud_gpu/local_smoke --out artifacts/cloud_gpu/local_smoke.tar.gz` | Pass |
| `python scripts/summarize_gpu_artifacts.py artifacts/cloud_gpu/local_smoke` | Pass |
| `python scripts/import_gpu_run_artifact.py artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz` | Pass; imported explicit skipped record because the RunPod artifact was not present locally |
| `python scripts/summarize_gpu_run.py release_evidence/gpu_runs` | Pass |
| `python scripts/verify_gpu_run_artifact.py release_evidence/gpu_runs` | Pass |
| RL examples (`examples/rl_*_demo.py`) | Pass |
| RL benchmarks (`benchmarks/rl_*_benchmark.py`) | Pass; safety training improves reward, economy benchmark reports prototype metric limitation |
| `python scripts/export_dependency_inventory.py` | Pass |
| `python scripts/export_dependency_inventory.py --policy` | Pass |
| `python scripts/export_release_evidence.py` | Pass |
| `python scripts/verify_release_evidence.py` | Pass |
| `python scripts/release_decision.py --target local` | Pass: `local_release_candidate` |
| `python scripts/release_decision.py --target neural-gpu-smoke` | Pass: `neural_gpu_smoke_candidate`; actual RunPod tarball ingestion skipped locally because artifact was absent |
| `docker compose config` | Pass |
| `forge build` | Pass |
| `forge test` | Pass: `16 tests passed` |
| `cargo test` in `rust/flow-memory-core` | Pass: `2 passed` |
| `git diff --check` | Pass |
| Secret scan | Pass via release gate: no obvious real secret patterns found |

### Honest limitations

- The RunPod RTX 4090 artifact tarball was not present at `artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz`, so this build records a skipped GPU evidence entry locally rather than verified imported RunPod metadata.
- Flow Arena is a local deterministic RL prototype, not a PufferLib/CUDA high-throughput backend.
- RL policies are advisory only and intentionally cannot execute actions or bypass safety/economy policy.
- V-JEPA 2, VideoMAE, production neural training scale, browser/WASM neural inference, and PufferLib native backend remain adapter seams/future work.


## RunPod GPU evidence launch attempt

Attempted the launch evidence import path for `flow-memory-cloud-gpu-run-001.tar.gz`. The expected source file `C:\Users\ntrap\Downloads\flow-memory-cloud-gpu-run-001.tar.gz` was not present on this workstation, so `scripts/import_gpu_run_artifact.py` created an explicit skipped record under `release_evidence/gpu_runs/flow-memory-cloud-gpu-run-001/`.

Validation outcome:

- `python scripts/import_gpu_run_artifact.py artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz`: completed with `skipped: true`.
- `python scripts/verify_gpu_run_artifact.py flow-memory-cloud-gpu-run-001`: pass for record integrity.
- `python scripts/summarize_gpu_run.py flow-memory-cloud-gpu-run-001`: shows artifact-missing skipped record.
- `python scripts/export_release_evidence.py`: pass.
- `python scripts/verify_release_evidence.py`: pass.
- `python scripts/release_decision.py --target neural-gpu-smoke`: blocked with `gpu_evidence_verified_run_missing`.

No public launch tag was created because the actual RunPod tarball is still missing locally. Copy the artifact into `artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz` and rerun the same commands before tagging `v0.3.0-alpha`.


## Slice: neural agent launch quickstart

Added `examples/launch_neural_agent_demo.py`, `docs/LAUNCH_NEURAL_AGENTS.md`, and `tests/test_launch_neural_agent_demo.py` so developer-alpha users can launch a local CPU agent, optional `tiny_torch` neural advisory mode, FlowLang agent, and local API server from one documented path.


## Slice: structured Flow Arena observations

Expanded `FlowEnv` observations from toy scalar fields to nested agent/economy/safety/memory features, added transition-driven feature updates, and covered the behavior in `tests/test_rl_structured_observations.py`.


## Slice: long EconomyMarketEnv episodes

Added `episode_mode="long"` to `EconomyMarketEnv` with bid, verifier, settlement, dispute, and slashing-aware phases. Covered success, dispute, and vectorized long episodes in `tests/test_economy_market_long_episode.py`.


## Slice: adversarial verifier scenario

Expanded `VerifierEnv` with bad/good/unknown work quality and collusion-risk behavior, including false approval, false rejection, dispute, and slashing signals. Added `tests/test_verifier_adversarial_env.py`.
