# Neural Training

Training scripts are tiny CPU-safe smoke trainers:

- `python -m flow_memory.neural.training.train_tiny_dual_stream`
- `python -m flow_memory.neural.training.train_world_model`
- `python -m flow_memory.neural.training.train_agent_policy`

They use synthetic local data only and save smoke checkpoints under `.flow_memory/neural_artifacts`, which should not be committed. They are not production training runs and do not prove biological alignment or real-world perception quality.

Implemented losses include predictive latent, temporal consistency, motion equivariance, depth consistency, egomotion compensation, appearance suppression, plan success, skill routing, risk prediction, and memory retrieval losses.
