import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOCK_DATA = ROOT / "dashboard" / "src" / "mock-data"


def load(name: str):
    return json.loads((MOCK_DATA / name).read_text(encoding="utf-8"))


def test_dashboard_public_alpha_mock_data_files_are_parseable():
    required = {
        "runtime.json",
        "neural-status.json",
        "rl-benchmarks.json",
        "agent-launch.json",
        "local-network.json",
        "payments.json",
    }
    assert required <= {path.name for path in MOCK_DATA.glob("*.json")}
    for name in required:
        assert load(name)["source"] == "mock-data-only"


def test_dashboard_mocks_preserve_safety_and_no_real_funds_claims():
    neural = load("neural-status.json")
    payments = load("payments.json")
    network = load("local-network.json")
    assert neural["safetyAuthority"] == "policy-and-approval-gates"
    assert payments["realFundsUsed"] is False
    assert network["realFundsUsed"] is False
