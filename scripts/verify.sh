#!/usr/bin/env bash
set -euo pipefail
PYTHON_CMD=()

select_python() {
  local venv_python="${PWD}/.venv/Scripts/python.exe"
  if [[ -x "$venv_python" ]] && "$venv_python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    PYTHON_CMD=("$venv_python")
    return 0
  fi

  local candidate
  local -a command

  for candidate in python python3 "py -3"; do
    if [[ "$candidate" == "py -3" ]]; then
      command=(py -3)
    else
      command=("$candidate")
    fi

    if "${command[@]}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      PYTHON_CMD=("${command[@]}")
      return 0
    fi
  done

  printf 'Flow Memory verification requires Python 3.10+ (tried: python, python3, py -3).\n' >&2
  return 1
}

select_python

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "${PYTHON_CMD[@]}" -m pytest -q
"${PYTHON_CMD[@]}" -m flow_memory --json "Explore and report"
"${PYTHON_CMD[@]}" benchmarks/perception_benchmark.py
"${PYTHON_CMD[@]}" scripts/release_gate.py
