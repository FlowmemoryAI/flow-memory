# Verification Checklist

- [ ] Confirm contract sources match the release commit.
- [ ] Run `forge build` and `forge test`.
- [ ] Validate deployment order and constructor args.
- [ ] Verify no real private keys or RPC URLs are present.
- [ ] Re-run `python scripts/validate_base_sepolia_artifacts.py`.
