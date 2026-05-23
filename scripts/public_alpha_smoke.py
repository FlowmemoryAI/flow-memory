"""Run the local public-alpha smoke command set without external services."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Sequence


@dataclass(frozen=True)
class SmokeCommandResult:
    name: str
    command: tuple[str, ...]
    ok: bool
    returncode: int
    elapsed_seconds: float
    stdout_tail: str

    def as_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "command": self.command,
            "ok": self.ok,
            "returncode": self.returncode,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "stdout_tail": self.stdout_tail[-4000:],
        }


SMOKE_COMMANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pytest", ("-m", "pytest", "-q")),
    ("flowlang_compile_demo", ("examples/flowlang_compile_demo.py",)),
    ("flowlang_runtime_demo", ("examples/flowlang_runtime_demo.py",)),
    ("flowlang_economy_demo", ("examples/flowlang_economy_demo.py",)),
    ("agent_economy_v3_demo", ("examples/agent_economy_v3_demo.py",)),
    ("cli_smoke", ("-m", "flow_memory", "--json", "Explore and report")),
    ("cli_flow", ("-m", "flow_memory", "--flow", "examples/flowlang_agent.flow", "--json", "Run the declared agent")),
)


def run_command(root: Path, name: str, args: Sequence[str], python: str) -> SmokeCommandResult:
    command = (python, *args)
    started = perf_counter()
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    elapsed = perf_counter() - started
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return SmokeCommandResult(
        name=name,
        command=command,
        ok=completed.returncode == 0,
        returncode=completed.returncode,
        elapsed_seconds=elapsed,
        stdout_tail=output,
    )


def run_public_alpha_smoke(root: Path, *, python: str = sys.executable, include_verify: bool = True) -> dict[str, object]:
    results = [run_command(root, name, args, python) for name, args in SMOKE_COMMANDS]
    if include_verify:
        started = perf_counter()
        completed = subprocess.run(("bash", "scripts/verify.sh"), cwd=root, capture_output=True, text=True)
        results.append(
            SmokeCommandResult(
                name="verify_script",
                command=("bash", "scripts/verify.sh"),
                ok=completed.returncode == 0,
                returncode=completed.returncode,
                elapsed_seconds=perf_counter() - started,
                stdout_tail=(completed.stdout + "\n" + completed.stderr).strip(),
            )
        )
    return {"ok": all(result.ok for result in results), "results": [result.as_record() for result in results]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Flow Memory public-alpha smoke checks")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--python", default=sys.executable, help="Python executable to use")
    parser.add_argument("--skip-verify", action="store_true", help="Skip bash scripts/verify.sh")
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    report = run_public_alpha_smoke(args.root.resolve(), python=args.python, include_verify=not args.skip_verify)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
