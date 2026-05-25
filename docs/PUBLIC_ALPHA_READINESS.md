# Public Alpha Readiness

Flow Memory is ready for **local public alpha** when local launch, FlowLang launch, neural advisory/live launch, local network scenarios, Mission Control replay, RL Arena examples, API help, release evidence, and docs checks pass.

Run:

```bash
python scripts/test_full_system.py --quick --json-out artifacts/full_system/quick_report.json
python scripts/test_public_alpha_launch.py
python scripts/export_public_alpha_launch_evidence.py
python scripts/verify_public_alpha_launch_evidence.py
python scripts/release_decision.py --target local-public-alpha
python scripts/release_decision.py --target public-alpha-local-launch
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
| Mission Control | Local replay/live API scaffold connected to real local state. |
| Agent economy | Local simulated accounting and lifecycle prototype. |
| RL Arena | Local prototype environments and tabular training. |
| Compute Market | Local dry-run provider/route/quote/payment-intent/settlement simulation; no live settlement. |
| Neural GPU public alpha | Blocked until real RunPod artifact is imported and verified. |
| Base/Web3 | Dry-run only. |
| Mainnet | Not ready. |
| Contracts | Unaudited. |
| Sandbox | Not hardened. |
| Neural/RL | Prototype/advisory. |

## GPU-gated release status

The following targets must remain blocked when `artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz` has not been imported:

```bash
python scripts/release_decision.py --target neural-gpu-smoke
python scripts/release_decision.py --target public-alpha-neural
python scripts/release_decision.py --target public-alpha-launch
```

Do not fake GPU evidence. Import the real artifact with `scripts/import_gpu_run_artifact.py` before claiming the GPU-gated launch state.

Do not claim production certification, audited contracts, mainnet readiness, hardened sandboxing, real-funds custody, or production ML performance.

## Live Agent Supervisor readiness

Local public alpha includes a bounded Live Agent Supervisor for neural-live runs. It writes local supervisor state, heartbeat artifacts, run records, Mission Control replay telemetry, and exportable run bundles. It is finite by default, stoppable, inspectable, and policy-gated.

GPU-gated neural release targets are still separate and require the real RunPod artifact to be imported and verified.
