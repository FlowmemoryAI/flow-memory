# Realtime Event Streaming Roadmap

Flow Memory public alpha exposes visual state through dependency-free polling endpoints:

- `GET /visual/state`
- `GET /visual/events`
- `GET /network/state`

This avoids adding frontend/server dependencies to the base install.

## Why polling first

- Works in a clean clone.
- Keeps Python tests independent from Node and browser tooling.
- Keeps local/public-alpha auth and scopes simple.
- Avoids implying production streaming infrastructure.

## Next steps

1. Add an optional SSE endpoint for local event tails.
2. Add WebSocket support behind an optional API extra.
3. Persist event streams through SQLite storage.
4. Add dashboard live reconnect/backoff.
5. Add signed event envelopes for remote streams.

SSE/WebSocket should not bypass API auth, scope checks, rate limiting, or audit middleware.
