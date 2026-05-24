from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_doc(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_start_here_contains_windows_and_unix_quickstarts():
    text = read_doc("docs/START_HERE.md")
    assert "git clone https://github.com/FlowmemoryAI/flow-memory.git" in text
    assert ".venv\\Scripts\\activate" in text
    assert "source .venv/bin/activate" in text
    assert "python -m flow_memory --json \"Explore and report\"" in text


def test_neural_launch_doc_marks_torch_optional_and_safety_authoritative():
    text = read_doc("docs/LAUNCH_NEURAL_AGENTS.md").lower()
    assert "pip install -e \".[dev,ml]\"" in text
    assert "python -m flow_memory --neural tiny_torch --json \"explore and report\"" in text
    assert "torch" in text and "optional" in text
    assert "policyengine" in text
    assert "approvalgate" in text
    assert "authoritative" in text


def test_mission_control_quickstart_contains_real_replay_path():
    text = read_doc("docs/MISSION_CONTROL_QUICKSTART.md")
    assert "--emit-visual-events" in text
    assert "scripts/export_visual_replay.py" in text
    assert "dashboard/src/mock-data/local-network-replay.json" in text
    assert "npm install" in text
    assert "npm run dev" in text


def test_payment_docs_answer_who_pays_and_real_funds_default():
    text = read_doc("docs/PAYMENTS_AND_AGENT_ECONOMY.md").lower()
    assert "who pays" in text
    assert "who earns" in text
    assert "escrow" in text
    assert "verifier" in text
    assert "simulated" in text
    assert "no real funds" in text
    assert "base" in text and "web3" in text


def test_public_alpha_readiness_marks_gpu_and_mainnet_limits():
    text = read_doc("docs/PUBLIC_ALPHA_READINESS.md").lower()
    assert "local public alpha" in text
    assert "neural gpu" in text
    assert "blocked" in text
    assert "not ready" in text
    assert "unaudited" in text
    assert "sandbox" in text and "not hardened" in text
    assert "dry-run" in text


def test_faq_answers_launch_money_dashboard_and_gpu_questions():
    text = read_doc("docs/FAQ.md").lower()
    for phrase in (
        "how do i launch an agent",
        "how do i launch a neural agent",
        "how do agents learn",
        "are agents paid",
        "who pays whom",
        "real money",
        "mainnet-ready",
        "dashboard real data or mock",
        "mission control",
        "blocked by gpu evidence",
    ):
        assert phrase in text
