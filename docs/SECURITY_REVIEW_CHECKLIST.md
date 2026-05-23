# Security Review Checklist

Before any public alpha announcement:

- [ ] Confirm no secrets are committed.
- [ ] Confirm `python -m pytest -q` passes.
- [ ] Confirm `forge test` passes.
- [ ] Confirm release evidence verifies.
- [ ] Confirm clean clone validation passes.
- [ ] Confirm public-alpha release decision passes.
- [ ] Confirm docs still state contracts are unaudited.
- [ ] Confirm no real deployment scripts run by default.
- [ ] Confirm sandbox docs state local/default sandboxing is not hardened isolation.
- [ ] Confirm dashboard remains mock-only unless a signed/authenticated API is explicitly wired.
