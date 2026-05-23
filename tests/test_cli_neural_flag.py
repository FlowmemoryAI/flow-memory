from flow_memory.cli import main


def test_cli_accepts_neural_flag(capsys):
    code = main(["--neural", "tiny_torch", "--json", "Explore and report"])
    out = capsys.readouterr().out
    assert code == 0
    assert '"neural"' in out
