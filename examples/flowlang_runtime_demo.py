from __future__ import annotations

from pathlib import Path

from flow_memory.flowlang import run_flowlang_agent


def main() -> None:
    path = Path(__file__).with_name("flowlang_skill_agent.flow")
    result = run_flowlang_agent(path, "Run a safe local skill")
    print({"accepted": result["accepted"], "requires_approval": result["requires_approval"]})
    if not result["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
