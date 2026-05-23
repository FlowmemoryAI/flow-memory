# PufferLib notes

PufferLib can be useful for high-throughput RL environments, but it typically expects CUDA or a Docker path for serious throughput. Flow Memory should not depend on it until the project has stable environment APIs.

Do not add PufferLib to base dependencies. Do not vendor PufferLib code. Keep the first integration optional and isolated.
