# V-JEPA 2 Adapter

`flow_memory.neural.backends.vjepa2.VJEPA2Adapter` is an adapter seam. It does not download checkpoints or claim V-JEPA performance.

Current behavior:
- Requires PyTorch optional dependency.
- Requires explicit local `checkpoint_path`.
- Raises a clear `OptionalDependencyError` if unavailable.

Future work: wire local Meta V-JEPA 2 code/checkpoints, add frozen-feature evaluation, and compare against the tiny world-model baseline.
