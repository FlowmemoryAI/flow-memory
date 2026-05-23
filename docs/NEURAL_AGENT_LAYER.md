# Neural Agent Layer v1

Status: functional prototype unless explicitly marked as adapter seam. The neural layer is optional, CPU-safe, and does not run trained production models by default. PolicyEngine and ApprovalGate remain authoritative; neural modules only rank, score, suggest, or flag.


## Implemented
- Optional `flow_memory.neural` package that imports without PyTorch.
- Tiny synthetic motion and agent trace datasets.
- Tiny dorsal/ventral/dual-stream encoders behind the `ml` extra.
- Tiny JEPA-style world model, surprise scoring, and rollout helpers.
- Advisory plan scoring, skill routing, risk scoring, evaluation, and memory retrieval.
- Agent runner neural metadata binding and CLI `--neural` flag.

## Safety rule
Neural scores cannot authorize execution. Autonomy, policy, approval, sandbox, and economy gates still decide.
