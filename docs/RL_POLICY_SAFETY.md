# RL Policy Safety

Flow Arena policies may rank or suggest actions, but they cannot execute actions directly. The runner records RL metadata and then still uses the existing policy, approval, autonomy, and economy risk boundaries.

Safety invariants:

- RL cannot bypass PolicyEngine.
- RL cannot bypass ApprovalGate.
- RL cannot bypass autonomy mode.
- RL cannot settle or spend funds directly.
- RL cannot access raw checkpoints through the API.
