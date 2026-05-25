import json
from pathlib import Path

from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import LAUNCH_EXPORT_SCOPE, required_scopes_for
from flow_memory.cli import main as cli_main
from flow_memory.release import decide_release_readiness
from flow_memory.release.launch_finalizer import finalize_public_alpha_launch, verify_public_alpha_launch_finalizer
from flow_memory.release.live_3d_evidence import mission_control_live_3d_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_mission_control_live_3d_evidence_is_ready_and_honest():
    evidence = mission_control_live_3d_evidence(ROOT)
    assert evidence["ok"] is True
    assert evidence["mission_control_live_3d_mode_available"] is True
    assert evidence["mission_control_live_3d_data_ready"] is True
    assert evidence["mission_control_live_3d_no_overclaim_invariant"] is True
    sample = evidence["sample"]
    assert sample["three_ready"] is True
    assert sample["policy_gated"] is True
    assert sample["neural_advisory_only"] is True
    assert sample["local_only"] is True


def test_public_alpha_launch_finalizer_cli_api_and_release_target(tmp_path, capsys):
    out = tmp_path / "public_alpha_launch_finalizer.json"
    finalizer = finalize_public_alpha_launch(ROOT, out)
    assert finalizer["ok"] is True
    assert finalizer["mission_control_live_3d"]["ok"] is True
    assert finalizer["public_alpha_demo_bundle"]["ok"] is True
    assert finalizer["invariants"]["ctmp_backup_not_tracked"] is True
    assert finalizer["ctmp_backup_tracked_paths"] == ()

    verified = verify_public_alpha_launch_finalizer(out)
    assert verified.ok is True
    assert verified.blockers == ()

    cli_out = tmp_path / "public_alpha_launch_finalizer_cli.json"
    assert cli_main(["launch", "finalize", "public-alpha", "--out", str(cli_out), "--json"]) == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["ok"] is True
    assert cli_payload["finalizer_path"].endswith("public_alpha_launch_finalizer_cli.json")

    router = create_default_router()
    api_out = tmp_path / "public_alpha_launch_finalizer_api.json"
    api_payload = router.dispatch("POST", "/launch/finalize/public-alpha", {"out": str(api_out)})
    assert api_payload["ok"] is True
    assert api_payload["finalizer_path"].endswith("public_alpha_launch_finalizer_api.json")
    assert required_scopes_for("POST", "/launch/finalize/public-alpha") == (LAUNCH_EXPORT_SCOPE,)

    decision = decide_release_readiness(ROOT, target="public-alpha-launch-finalizer")
    assert decision.ok is True
    assert "mission_control_live_3d" in decision.required_evidence
    assert "public_alpha_launch_finalizer" in decision.required_evidence
