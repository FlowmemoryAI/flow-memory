# Testnet Preflight

Flow Memory RC1 can generate Base Sepolia dry-run artifacts without private keys, RPC providers, or funds.

Commands:

```bash
python scripts/generate_deployment_plan.py --out deployments/base-sepolia/deployment-plan.json
python scripts/base_sepolia_dry_run.py --out deployments/base-sepolia/dry-run-transactions.json
python scripts/validate_base_sepolia_artifacts.py --dir deployments/base-sepolia
python scripts/release_decision.py --target public-alpha
```

The artifacts include deployment order, constructor placeholders, dependency graph, zero-address expected-address placeholders, dry-run transaction payloads, risk notes, and verification checklist.

No deployment is performed by default. A real testnet deployment still requires reviewed constructor arguments, wallet/key custody, RPC configuration, contract verification, and manual approval.
