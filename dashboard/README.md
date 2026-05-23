# Flow Memory Dashboard

This directory is a minimal dashboard scaffold for future Flow Memory runtime and agent-economy API integration.

Current state:

- No application framework is installed.
- No live API calls are implemented.
- UI consumers should use `src/mock-data/runtime.json` only as static fixture data.
- This package is not part of the Python test suite and is not required to run Python tests.

The mock runtime fixture describes representative nodes, agents, tasks, treasury balances, and contract status fields. Values are illustrative and must not be treated as audited production telemetry, trained ML output, hardened sandbox evidence, or mainnet data.

Future integration work should replace the fixture with explicit API contracts and keep mock data clearly separated from live runtime data.
