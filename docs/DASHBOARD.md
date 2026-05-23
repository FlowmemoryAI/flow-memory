# Dashboard

The dashboard is an optional public-alpha operator console scaffold.

Current state:

- typed mock API client in `dashboard/src/lib/mock-api.ts`
- shared mock types in `dashboard/src/lib/types.ts`
- endpoint-shape constants in `dashboard/src/lib/openapi-types.ts`
- screen inventory in `dashboard/src/app/screens.ts`
- no live API calls by default

Node checks, when available:

```bash
cd dashboard
npm test
npm run build
```

Future work: real React/Next UI, generated OpenAPI types, signed request client, read-only API mode, and operator authentication.
