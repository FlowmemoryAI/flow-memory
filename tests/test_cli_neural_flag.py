from flow_memory.cli import main
from typing import Any


def test_cli_accepts_neural_flag(capsys: Any) -> None:
    code = main(["--neural", "tiny_torch", "--json", "Explore and report"])
    out = capsys.readouterr().out
    assert code == 0
    assert '"neural"' in out
