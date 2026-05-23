# Clean Clone Validation

`python scripts/clean_clone_validation.py` is the public-alpha smoke check for a new developer checkout.

It validates a temporary copied checkout rather than the active working tree. The copy excludes local/generated state:

- `.git`
- `.venv`
- `__pycache__`
- `.pytest_cache`
- `.mypy_cache`
- `.ruff_cache`
- `node_modules`
- `target`
- `out`
- `cache`
- `dist`
- `build`

The script then runs:

1. `python -m venv .venv`
2. `.venv` Python `-m pip install -e .[dev]`
3. `python -m pytest -q`
4. FlowLang compile/runtime/economy demos
5. Agent Economy V3 demo
6. CLI smoke
7. CLI `--flow`
8. `bash scripts/verify.sh`

The report is written to `release_evidence/clean_clone_validation.json` and records each command, return code, elapsed seconds, and a bounded output tail.

Limitations:

- It does not prove production readiness.
- It does not run real network services.
- Editable install can fail in an offline environment if dev dependencies are not available in the local package cache; that blocker must be documented rather than bypassed.
