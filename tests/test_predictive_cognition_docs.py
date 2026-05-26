from pathlib import Path


DOC_PATHS = (
    Path("README.md"),
    Path("docs/PREDICTIVE_COGNITIVE_CORE.md"),
    Path("docs/NEURAL_LIVE_AGENTS.md"),
    Path("docs/MISSION_CONTROL_QUICKSTART.md"),
    Path("docs/PUBLIC_ALPHA_READINESS.md"),
    Path("docs/START_HERE.md"),
    Path("BUILD_REPORT.md"),
    Path("FLOW_MEMORY_STATUS.md"),
)


def test_predictive_cognition_docs_contain_commands_and_limits():
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in DOC_PATHS)

    assert "python -m flow_memory cognition predict" in text
    assert "python -m flow_memory cognition tick" in text
    assert "post /cognition/predict" in text
    assert "get /cognition/experiences" in text
    assert "dashboard/src/mock-data/predictive-cognitive-core.json" in text
    assert "policyengine" in text.lower()
    assert "approvalgate" in text.lower()


def test_predictive_cognition_docs_avoid_overclaim_phrases():
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in DOC_PATHS)
    banned_claims = (
        "is agi",
        "achieves agi",
        "artificial general intelligence",
        "is conscious",
        "has consciousness",
        "production autonomous intelligence",
        "guaranteed future",
        "predicts arbitrary real-world future",
    )

    for claim in banned_claims:
        assert claim not in text
