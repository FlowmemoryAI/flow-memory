# VideoMAE Adapter

`flow_memory.neural.backends.videomae.VideoMAEAdapter` is an adapter seam. It does not download checkpoints or claim VideoMAE performance.

Current behavior:
- Requires PyTorch optional dependency.
- Requires explicit local `checkpoint_path`.
- Raises a clear `OptionalDependencyError` if unavailable.

Future work: wire local VideoMAE model code/checkpoints, expose masked-pretraining features, and benchmark on synthetic plus real video tasks.
