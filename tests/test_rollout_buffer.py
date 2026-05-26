from flow_memory.rl.rollout import RolloutBuffer

def test_rollout_buffer_records_steps() -> None:
    buf=RolloutBuffer()
    buf.add({"s":0}, 1, 1.0, False, {"ok": True})
    assert buf.size == 1
    assert buf.as_record()["rewards"] == (1.0,)
