from flow_memory.rl.checkpoints import CheckpointStore
from flow_memory.rl.policies import TabularQPolicy


def test_rl_checkpoint_store_round_trip(tmp_path):
    store = CheckpointStore(tmp_path)
    policy = TabularQPolicy(q={"s": [1.0, 0.0]})
    store.save_policy("policy", policy)
    loaded = store.load_policy("policy")
    assert loaded.q["s"][0] == 1.0
