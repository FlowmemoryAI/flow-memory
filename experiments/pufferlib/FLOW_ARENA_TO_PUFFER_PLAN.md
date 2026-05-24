# Flow Arena to PufferLib Plan

Status: experiment-only roadmap. PufferLib is not installed, vendored, or required by Flow Memory public alpha.

## Integration order

1. Keep Flow Arena authoritative Python reference environments.
2. Define deterministic observation/action/reward contracts for `SafetyGateEnv`, `EconomyMarketEnv`, `SwarmDelegationEnv`, and adversarial envs.
3. Build thin Puffer adapter wrappers only after the reference env contract is stable.
4. Add native C candidates for high-throughput environments with pure data observations.
5. Add CUDA backend only after native C envs pass parity tests.
6. Keep PolicyEngine and ApprovalGate outside the RL backend; RL policy outputs remain suggestions.

## Candidate mappings

| Flow Arena env | Puffer/Ocean candidate | Native C candidate | Notes |
| --- | --- | --- | --- |
| `SafetyGateEnv` | single-agent policy env | yes | Small discrete action space and safety penalties. |
| `EconomyMarketEnv` | single/multi-agent market env | yes | Needs deterministic accounting parity. |
| `VerifierEnv` | verifier policy env | yes | Useful for false approval/rejection training. |
| `SwarmDelegationEnv` | multi-agent env | later | Requires local bus/agent-card parity. |
| `ReputationGamingEnv` | adversarial policy env | later | Prototype abuse fixture only. |
| `SybilRiskEnv` | adversarial policy env | later | Not production Sybil defense. |
| `ColludingVerifierEnv` | adversarial verifier env | later | Not production fraud detection. |

## Explicit non-goals

- No PufferLib performance claims.
- No CUDA training claim.
- No vendored Puffer code.
- No browser/WASM neural inference claim.
- No bypass of Flow Memory policy or approval gates.
