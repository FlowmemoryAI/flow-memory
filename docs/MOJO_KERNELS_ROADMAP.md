# Mojo Kernels Roadmap

Mojo is a candidate for optional AI-native kernels in Flow Memory, not a core dependency.

## Use case

Flow Memory may eventually need fast local kernels for:

- Perception feature extraction.
- Latent-state transforms.
- Similarity scoring.
- Memory consolidation ranking.
- Small learned world-model components.
- Vector post-processing.

Mojo could be useful if it provides Python-friendly ergonomics with lower-level performance control. Today, Flow Memory should keep Mojo experimental because packaging, contributor availability, CI support, and Windows developer experience are not yet proven for this project.

## Current status

- No Mojo code is required.
- No Mojo dependency is added.
- Python deterministic proxies remain the default.
- PyTorch/V-JEPA/VideoMAE remain optional adapter seams.

## Candidate milestones

1. Identify one hot kernel with a real benchmark need.
2. Keep the Python implementation as reference behavior.
3. Add an optional Mojo prototype behind an extra or sidecar boundary.
4. Verify bit-for-bit or tolerance-bounded equivalence against Python fixtures.
5. Add CI only when the toolchain is stable in the target environment.
6. Reject Mojo for core if installation or contribution friction outweighs performance benefit.

## Hard rules

- Do not require Mojo for local tests.
- Do not claim trained model performance from a Mojo kernel.
- Do not introduce separate memory semantics that bypass Flow Memory audit or policy gates.
- Keep all Mojo experiments behind explicit optional paths.

## Decision

Classification: experiment only.

Mojo is promising for future neural kernels, but it is not part of the core Flow Memory runtime today.
