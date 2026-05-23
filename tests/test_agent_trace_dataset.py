from flow_memory.neural.training.agent_trace_dataset import AgentTraceDataset


def test_default_agent_trace_dataset_has_policy_and_economy_examples():
    dataset = AgentTraceDataset()
    assert len(dataset) >= 3
    assert any(trace.economy_receipts for trace in dataset.traces)
