# Flow Arena RL

Flow Arena is Flow Memory's dependency-light RL layer for training advisory decision policies in simulated agent-economy situations. It is not a PufferLib/CUDA backend yet.

Core APIs:

- `FlowEnv.reset(seed=None)`
- `FlowEnv.step(action)`
- `FlowVectorEnv` for in-process vectorization
- `RolloutBuffer` for observations, actions, rewards, dones, policy decisions, economy receipts, and audit event ids
- `RewardSpec` for safety, task success, reputation, dispute, slashing, memory, and delegation weights

RL outputs are advisory suggestions. PolicyEngine, ApprovalGate, autonomy mode, and economic risk controls remain authoritative.


## Structured observations

Flow Arena observations now include nested `agent`, `economy`, `safety`, and `memory` features in addition to `step`, `score`, and `env_id`. These features track local prototype signals such as reputation, risk budget, disputes, slashing events, approval requests, delegation count, and memory relevance.

The adversarial environment set now includes reputation gaming, sybil-risk, and colluding-verifier simulations. They are local deterministic fixtures for training and testing advisory policies against abuse patterns; they are not proof of production Sybil resistance or fraud prevention.
