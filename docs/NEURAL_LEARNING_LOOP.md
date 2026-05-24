# Neural and Agent Learning Loop

Flow Memory public alpha makes learning explicit and local. It does not claim production neural training or biological alignment.

## Current loop

```text
observe -> plan -> policy decision -> action result -> evaluation -> memory write -> trace collection -> improvement report
```

`src/flow_memory/learning/` records agent traces and summarizes improvement through:

- memory learning: new episodic traces improve later retrieval context;
- RL Arena learning: local tabular policies improve in simulated environments;
- neural training lane: tiny PyTorch smoke scripts can train local prototype models when `flow-memory[ml]` is installed;
- evaluation history: success rate and reward summaries are tracked.

## Neural role

Neural models advise: plan scoring, risk scoring, memory retrieval, surprise/evaluation, and tiny dual-stream perception/world-model experiments. PolicyEngine and ApprovalGate remain authoritative.

## What is future work

- Production trace datasets.
- Real V-JEPA 2 / VideoMAE checkpoints.
- Learned risk and plan scorers trained from real outcomes.
- GPU-scale RL backends.
- Signed neural run attestations.
