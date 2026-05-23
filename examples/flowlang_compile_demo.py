from __future__ import annotations

from pathlib import Path

from flow_memory.flowlang import compile_flowlang_file


def main() -> None:
    example_path = Path(__file__).with_name("flowlang_agent.flow")
    result = compile_flowlang_file(example_path)
    print(result.to_json(indent=2))
    if not result.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
