# Public Alpha Readiness

Flow Memory is ready for **local public alpha** when local launch, FlowLang launch, neural advisory/live launch, local network scenarios, Mission Control replay, RL Arena examples, API help, release evidence, and docs checks pass.

Run:

```bash
python scripts/test_full_system.py --quick --json-out artifacts/full_system/quick_report.json
python scripts/test_public_alpha_launch.py
python scripts/export_public_alpha_launch_evidence.py
python scripts/verify_public_alpha_launch_evidence.py
python scripts/finalize_public_alpha_launch.py
python scripts/verify_public_alpha_launch_finalizer.py
python scripts/release_decision.py --target local-public-alpha
python scripts/release_decision.py --target public-alpha-local-launch
python scripts/release_decision.py --target public-alpha-launch-finalizer
```

## Current maturity

| Area | Status |
| --- | --- |
| Local public alpha | Ready if `public-alpha-local-launch` passes. |
| Local agent launch | Implemented. |
| FlowLang launch | Implemented. |
| Neural advisory/live launch | Functional local prototype; Torch optional; neural-live runtime sessions and telemetry are local/advisory. |
| Live Agent Launchpad | Implemented for local neural-live demos; writes replay/evidence metadata and remains GPU-honest. |
| Live Agent Operations | Implemented for local run records, replay lookup, bundle export, safe completed-run stop/no-op behavior, and launch doctor checks. |
| Mission Control run console | Implemented for launchpad, operations, supervisor, and local-network replay fixture selection/status summaries. |
| Public-alpha demo bundle | Implemented as local JSON bundle with replay references, docs, commands, release evidence, GPU status, and honest limitations. |
| Mission Control Live 3D Mode | Implemented as a read-only CSS 3D/WebGL-ready view over local/replay neural embodiment telemetry; no agent launch, provider calls, settlement, or policy bypass. |
| Public Alpha Launch Finalizer | Implemented as evidence-only handoff for launch evidence, Live 3D mode, demo bundle, release decisions, and C:\tmp backup exclusion. |
| Mission Control | Local replay/live API scaffold connected to real local state. |
| Agent economy | Local simulated accounting and lifecycle prototype. |
| RL Arena | Local prototype environments and tabular training. |
| Compute Market | Local dry-run provider/route/quote/payment-intent/settlement simulation; no settlement execution. |
| Neural GPU public alpha | Ready when `neural-gpu-smoke` and `public-alpha-neural` pass with imported RunPod evidence. |
| Base/Web3 | Dry-run only. |
| Mainnet | Not ready. |
| Contracts | Unaudited. |
| Sandbox | Not hardened. |
| Neural/RL | Prototype/advisory. |

## GPU-gated release status

The RunPod RTX 4090 artifact has been imported and verified in release evidence. GPU-gated targets may pass when the evidence bundle remains valid:

```bash
python scripts/release_decision.py --target neural-gpu-smoke
python scripts/release_decision.py --target public-alpha-neural
python scripts/release_decision.py --target public-alpha-launch
python scripts/release_decision.py --target public-alpha-launch-finalizer
```

Do not fake GPU evidence. If the release evidence directory is regenerated from a checkout without `artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz` or imported `release_evidence/gpu_runs/flow-memory-cloud-gpu-run-001`, GPU-gated launch state must be treated as blocked again.

Do not claim production certification, audited contracts, mainnet readiness, hardened sandboxing, real-funds custody, or production ML performance.

## Live Agent Supervisor readiness

Local public alpha includes a bounded Live Agent Supervisor for neural-live runs. It writes local supervisor state, heartbeat artifacts, run records, Mission Control replay telemetry, and exportable run bundles. It is finite by default, stoppable, inspectable, and policy-gated.

GPU-gated neural release targets are separate from local public alpha and depend on the imported RunPod evidence remaining verified.

## Mission Control run console readiness

Local public alpha includes a Mission Control run selector/status card over these fixtures:

- `live-neural-agent-launch`
- `live-agent-operations`
- `live-agent-supervisor`
- `local-network-replay`
- `live-neural-embodiment`

Generate the local public-alpha demo bundle:

```bash
python -m flow_memory launch bundle public-alpha --out artifacts/launch/bundles/public-alpha-local-demo.json --json
```

The bundle is reference-oriented and local-only. It must keep GPU status honest, neural outputs advisory, policy gates authoritative, and real-funds/provider behavior disabled.

## Visible neural embodiment readiness

Mission Control includes a neural embodiment fixture and local API projection:

```bash
python -m flow_memory launch visual embodiment --run live-agent-supervisor --out dashboard/src/mock-data/live-neural-embodiment.json --json
```

```text
GET /visual/embodiment/{run_id}
GET /launch/console/runs/{run_id}/embodiment
```

This shows the local neural runtime/session, loop phase, confidence/risk, policy gate, memory activations, learning ticks, supervisor heartbeat, replay artifact, and imported GPU evidence status. It remains a public-alpha visual/replay layer, not AGI, sentience, settlement execution, or production ML certification.

## Mission Control Live 3D Mode and finalizer

Live 3D Mode reads the visible neural embodiment fixture and local API projection. It renders a read-only 3D operations view over run id, session id, heartbeat, confidence/risk, memory activations, learning ticks, policy gate state, and imported GPU evidence status. It does not start agents, contact providers, move funds, broadcast transactions, execute settlement, or bypass PolicyEngine/ApprovalGate.

Finalize the public-alpha handoff:

```bash
python -m flow_memory launch finalize public-alpha --out release_evidence/public_alpha_launch_finalizer.json --json
python scripts/verify_public_alpha_launch_finalizer.py
python scripts/release_decision.py --target public-alpha-launch-finalizer
```

The finalizer is evidence-only. It records the local demo bundle, public-alpha launch evidence, `public-alpha-local-launch` and GPU-backed `public-alpha-launch` decisions, Mission Control Live 3D Mode readiness, neural embodiment readiness, and the invariant that the C:\tmp backup is not tracked.
