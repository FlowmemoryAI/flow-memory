# Public Alpha Quickstart

Status: public-alpha / local-testnet preflight candidate. Flow Memory is not production-certified, contracts are unaudited, sandboxing is not hardened isolation, and no real funds or private keys are required.

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m pytest -q
python -m flow_memory --json "Explore and report"
python -m flow_memory --flow examples/flowlang_agent.flow --json "Run the declared agent"
```

Git Bash alternative:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
bash scripts/verify.sh
```

## Public-alpha smoke

```bash
python scripts/public_alpha_smoke.py --root .
```

## Clean clone validation

```bash
python scripts/clean_clone_validation.py --root . --out release_evidence/clean_clone_validation.json
```

The clean-clone script copies the repository into a temporary directory while excluding `.venv`, caches, node modules, Foundry outputs, and Python bytecode. It then creates a fresh venv, installs the package in editable dev mode, and runs the local smoke checks.

## Base Sepolia dry-run artifacts

```bash
python scripts/generate_deployment_plan.py --out deployments/base-sepolia/deployment-plan.json
python scripts/base_sepolia_dry_run.py --out deployments/base-sepolia/dry-run-transactions.json
python scripts/validate_base_sepolia_artifacts.py --dir deployments/base-sepolia
```

These commands do not deploy, do not sign transactions, do not require RPC, and do not use funds.
