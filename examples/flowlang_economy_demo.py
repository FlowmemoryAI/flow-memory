from __future__ import annotations

from pathlib import Path

from flow_memory.flowlang import run_flowlang_agent


def main() -> None:
    path = Path(__file__).with_name("flowlang_economy_agent.flow")
    result = run_flowlang_agent(path, "settle verified marketplace work")
    print({"accepted": result["accepted"], "settlement": result["output"].get("settlement")})
    if not result["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
