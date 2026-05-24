import flow_memory.rl as rl

def test_rl_imports_without_optional_backends():
    assert rl.FlowEnv is not None
    assert rl.PUFFERLIB_AVAILABLE in {True, False}
