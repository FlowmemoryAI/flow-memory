# Launch Neural Agents

Flow Memory public alpha lets a developer launch memory-bearing agents with an optional neural advisory layer. Neural scores never execute actions directly: PolicyEngine, ApprovalGate, autonomy mode, and economy risk controls remain authoritative.

## One-command local CPU

```bash
python -m flow_memory --json "Explore and report"
```

## Install optional ML dependencies

```bash
pip install -e ".[dev,ml]"
```

## Launch with tiny_torch neural advisory layer

```bash
python -m flow_memory --neural tiny_torch --json "Explore and report"
```

If Torch is missing, the command still returns a structured result and marks the neural backend as skipped.

## Run a FlowLang-declared agent

```bash
python -m flow_memory --flow examples/flowlang_agent.flow --json "Run the declared agent"
```

## Run the local API server

```bash
python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765
python scripts/run_local_api_server.py --api-key dev-local-only --require-scopes
```

## Demo script

```bash
python examples/launch_neural_agent_demo.py
```

The demo creates a Python agent, runs a FlowLang agent, prints the neural advisory metadata, and repeats the exact launch commands.
