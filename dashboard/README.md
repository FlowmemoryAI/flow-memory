# Flow Memory Dashboard

This directory is the public-alpha operator console scaffold for Flow Memory. It is intentionally dependency-light and uses typed mock data instead of live API calls.

Current state:

- No application framework is required for the base Python test suite.
- `src/lib/types.ts` defines the dashboard data model.
- `src/lib/mock-api.ts` exposes a typed mock API client.
- `src/lib/openapi-types.ts` mirrors the public-alpha endpoint groups.
- `src/app/screens.ts` enumerates operator-console screens for runtime health, agents, agent state, goals/plans, skills, marketplace, disputes, audit log, reputation, FlowLang compile/run, Base Sepolia dry-run status, and release evidence status.
- Live HTTP integration is deliberately not implemented yet.

Local checks when Node is available:

```bash
npm test
npm run build
```

These commands only validate the mock/API scaffold. Future work should add a real React or Next.js app, generated OpenAPI types, signed request support, and read-only API integration before any operator console is exposed beyond local development.

The mock values are illustrative and must not be treated as audited production telemetry, trained ML output, hardened sandbox evidence, contract deployment status, or mainnet data.
