# RL Environments

Implemented local Flow Arena environments:

| Environment | Training focus |
| --- | --- |
| ToolUseEnv | safe tool use versus risky/approval choices |
| MemoryRetrievalEnv | relevant retrieval and consolidation choices |
| EconomyMarketEnv | bid/decline/verifier behavior under dispute/slashing risk |
| VerifierEnv | approve/reject/evidence/escalation choices |
| SwarmDelegationEnv | delegation, coalition, and verification choices |
| SafetyGateEnv | execute/approval/deny/defer/safer-plan choices |
| SelfRepairEnv | retry, switch skill, ask human, write repair plan, disable failing skill |
| GridWorld | tiny sanity environment |

All are deterministic with seeds and can be vectorized in process.


## EconomyMarketEnv long episode mode

`EconomyMarketEnv(episode_mode="long")` now models a multi-step local lifecycle: open task -> bid submitted -> verifier selected -> settled or disputed. The default `single_step` mode remains for fast smoke tests and benchmarks.


## Adversarial verifier scenario

`VerifierEnv` now supports `work_quality` and `collusion` parameters. Bad work plus collusive approval produces dispute/slashing signals, while evidence requests remain the safe default for unknown work quality.
