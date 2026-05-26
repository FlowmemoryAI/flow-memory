"""Run the Compute Market production-readiness quality gate.

This intentionally gates the production Compute Market/API surface separately from
legacy research modules whose full-repo mypy cleanup is tracked independently.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]

RUFF_TARGETS: tuple[str, ...] = (
    "src/flow_memory/compute_market",
    "src/flow_memory/api",
    "scripts/deploy_compute_market_render_level1.py",
    "scripts/validate_compute_market_public_buildout.py",
    "scripts/run_compute_market_provider_sandbox.py",
    "tests/test_compute_market_audit.py",
    "tests/test_compute_market_provider_contracts.py",
    "tests/test_compute_market_production_buildout.py",
    "tests/test_compute_market_observability.py",
    "tests/test_compute_market_live_deployment.py",
    "tests/test_api_auth.py",
    "tests/test_api_http_server.py",
    "tests/test_api_compute_endpoints.py",
    "tests/test_api_manifest.py",
    "tests/test_api_openapi_generation.py",
    "tests/test_api_openapi_snapshot.py",
    "tests/test_api_snapshot.py",
    "tests/test_compute_market_storage.py",
    "tests/test_compute_market_provider_adapters.py",
    "tests/test_compute_market_production.py",
    "tests/test_compute_market_rate_limits.py",
    "tests/test_compute_market_settlement_simulator.py",
    "tests/test_compute_market_core.py",
    "tests/test_compute_market_public_validation_script.py",
    "tests/test_compute_market_live_integration.py",
    "tests/test_cli.py",
)

MYPY_TARGETS: tuple[str, ...] = (
    "src/flow_memory/compute_market",
    "src/flow_memory/api",
    "tests/test_compute_market_core.py",
)

PYTEST_TARGETS: tuple[str, ...] = (
    "tests/test_compute_market_audit.py",
    "tests/test_compute_market_provider_contracts.py",
    "tests/test_compute_market_production_buildout.py",
    "tests/test_compute_market_observability.py",
    "tests/test_api_auth.py",
    "tests/test_api_http_server.py",
    "tests/test_compute_market_live_deployment.py",
    "tests/test_api_compute_endpoints.py",
    "tests/test_api_manifest.py",
    "tests/test_api_openapi_generation.py",
    "tests/test_api_openapi_snapshot.py",
    "tests/test_api_snapshot.py",
    "tests/test_compute_market_storage.py",
    "tests/test_compute_market_provider_adapters.py",
    "tests/test_compute_market_production.py",
    "tests/test_compute_market_rate_limits.py",
    "tests/test_compute_market_settlement_simulator.py",
    "tests/test_compute_market_core.py",
    "tests/test_compute_market_public_validation_script.py",
    "tests/test_compute_market_live_integration.py",
    "tests/test_cli.py",
)


def _run(label: str, args: Sequence[str]) -> int:
    print(f"==> {label}", flush=True)
    return subprocess.run(args, cwd=ROOT, check=False).returncode


def main() -> int:
    commands: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("ruff", (sys.executable, "-m", "ruff", "check", *RUFF_TARGETS)),
        ("mypy", (sys.executable, "-m", "mypy", *MYPY_TARGETS, "--config-file", "pyproject.toml")),
        ("pytest", (sys.executable, "-m", "pytest", *PYTEST_TARGETS, "-q")),
    )
    for label, args in commands:
        return_code = _run(label, args)
        if return_code != 0:
            return return_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
