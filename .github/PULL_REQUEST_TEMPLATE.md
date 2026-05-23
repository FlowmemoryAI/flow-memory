## Summary

- TBD

## Classification

Choose all that apply:

- [ ] local implementation
- [ ] functional prototype
- [ ] adapter seam
- [ ] scaffold
- [ ] production hardening
- [ ] documentation

## Safety / security review

- [ ] No secrets, API keys, private keys, browser auth artifacts, or credentials are committed.
- [ ] Policy, sandbox, audit, wallet, marketplace, and contract impacts are described.
- [ ] New side effects require explicit permission and auditability.
- [ ] Production claims are backed by validation evidence.

## Validation

Paste exact commands and results:

```bash
python -m pytest -q
python -m flow_memory --json "Explore and report"
bash scripts/verify.sh
```

If contracts changed:

```bash
forge build
forge test
```

If Docker changed:

```bash
docker compose config --quiet
```

## Known limitations

- TBD

## Follow-up work

- TBD
