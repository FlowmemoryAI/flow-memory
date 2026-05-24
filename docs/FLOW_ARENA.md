# Flow Arena RL

Flow Arena is Flow Memory's dependency-light RL layer for training advisory decision policies in simulated agent-economy situations. It is not a PufferLib/CUDA backend yet.

Core APIs:

- `FlowEnv.reset(seed=None)`
- `FlowEnv.step(action)`
- `FlowVectorEnv` for in-process vectorization
- `RolloutBuffer` for observations, actions, rewards, dones, policy decisions, economy receipts, and audit event ids
- `RewardSpec` for safety, task success, reputation, dispute, slashing, memory, and delegation weights

RL outputs are advisory suggestions. PolicyEngine, ApprovalGate, autonomy mode, and economic risk controls remain authoritative.
