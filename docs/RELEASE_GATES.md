# Release Gates

Current offline release gates:

- API snapshot validation
- audit replay checkpoint validation
- Base Sepolia dry-run safety check
- SQLite storage schema verification
- secret pattern scan
- dependency policy gate
- release evidence bundle hash verification
- public-alpha decision gate

Commands:

```bash
python scripts/release_gate.py --root .
python scripts/export_release_evidence.py --root .
python scripts/verify_release_evidence.py
python scripts/release_decision.py --target local
python scripts/release_decision.py --target public-alpha
```

Production remains blocked until contracts are audited, sandbox isolation is hardened, production key custody exists, and mainnet deployment controls are reviewed.
