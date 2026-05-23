# API Error Contract

Flow Memory public-alpha API errors use a deterministic local JSON shape:

```json
{
  "ok": false,
  "error": {
    "code": "request.invalid",
    "message": "Invalid request",
    "status": 400,
    "details": {},
    "request_id": "req-1"
  }
}
```

`details` and `request_id` are omitted when empty. Detail keys are sorted by string form before serialization so tests and release evidence are stable.

## Standard local codes

| Code | HTTP status | Meaning |
| --- | ---: | --- |
| `request.invalid` | 400 | Payload or request metadata failed local validation. |
| `auth.invalid` | 401 | API-key or auth material is missing/invalid. |
| `auth.invalid_scope` | 401 | A provided scope is not one of the known public-alpha scopes. |
| `auth.forbidden` | 403 | The caller is authenticated enough to inspect, but lacks a required scope. |
| `rate_limit.exceeded` | 429 | The local fixed-window limiter denied the request. |
| `internal.error` | 500 | Local audit wrapper observed an unexpected handler exception. |

## Status

This contract is a local/public-alpha seam. It gives tests, in-process tools, optional server adapters, and preflight evidence one stable shape to share. It is not a claim that the API is production-ready or externally hardened.
