# PufferLib cloud GPU path

PufferLib is not required for Flow Memory Neural Agent Layer v1. It should come after Flow Memory has its own RL environments.

Important constraints:
- PufferLib commonly expects CUDA or Docker-style setup paths.
- Do not add PufferLib to base dependencies.
- Do not vendor PufferLib code.

Future sequence:
1. Implement Flow Memory RL environments.
2. Add a Puffer adapter.
3. Convert hot environments to native C where justified.
4. Add CUDA backend experiments.
5. Build a browser demo after local metrics are meaningful.
