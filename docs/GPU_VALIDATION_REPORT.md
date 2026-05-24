# GPU Validation Report

Flow Memory can import cloud GPU validation artifacts into release evidence. The expected manual RunPod artifact is `artifacts/incoming/flow-memory-cloud-gpu-run-001.tar.gz`; if it is absent, the importer writes a skipped evidence record instead of failing local validation.

Current manually reported run:

- GPU: NVIDIA GeForce RTX 4090
- Torch: 2.12.0+cu130
- CUDA available: true
- Observed pytest: 339 passed, 3 skipped
- Neural CLI: `tiny_torch` available
- Neural benchmarks: appearance-free motion, world model prediction, plan scoring, memory retrieval, and agent policy reported ok by the operator

The importer preserves only text/JSON/Markdown metadata and hashes; it does not commit raw checkpoints or weights.
