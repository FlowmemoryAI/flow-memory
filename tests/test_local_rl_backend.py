from flow_memory.rl.backends import create_rl_backend

def test_create_local_backend():
    assert create_rl_backend("local").name == "local"
