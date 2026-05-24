from flow_memory.rl.envs.verifier_env import VerifierEnv
from flow_memory.rl.policies import HeuristicPolicy


def test_verifier_rejects_bad_work_successfully():
    env = VerifierEnv(work_quality="bad", collusion=False)
    step = env.step(env.action_labels.index("reject"))
    assert step.reward > 0
    assert step.info["verifier_accuracy"] == 1.0
    assert step.done is True


def test_verifier_collusion_penalizes_false_approval_and_flags_slashing():
    env = VerifierEnv(work_quality="bad", collusion=True)
    step = env.step(env.action_labels.index("approve"))
    assert step.reward < 0
    assert step.info["collusion_risk"] is True
    assert step.observation["economy"]["slashing_events"] == 1
    assert step.observation["verification"]["collusion_risk"] == 1.0


def test_heuristic_policy_requests_evidence_for_unknown_work():
    env = VerifierEnv(work_quality="unknown")
    action = HeuristicPolicy().act(env.reset(), env)
    assert env.action_space.label(action) == "request_evidence"
    step = env.step(action)
    assert step.info["evidence_requested"] is True
