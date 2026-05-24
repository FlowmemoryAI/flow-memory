from flow_memory.visualization import reduce_visual_events, visual_event


def test_duplicate_economy_events_do_not_regress_settled_task_or_edge():
    state = reduce_visual_events(
        (
            visual_event("task", "task-1", {"task_id": "task-1", "status": "created", "reward": 3.0}),
            visual_event("economy", "settlement-edge", {"edge_id": "edge-1", "task_id": "task-1", "kind": "settlement", "status": "settled", "amount": 3.0}),
            visual_event("economy", "old-bid-edge", {"edge_id": "edge-1", "task_id": "task-1", "kind": "bid", "status": "submitted", "amount": 1.0}),
        ),
        provenance="replay",
    )

    task = next(task for task in state.tasks if task.task_id == "task-1")
    edge = next(edge for edge in state.economy if edge.edge_id == "edge-1")

    assert task.status == "settled"
    assert edge.kind == "settlement"
    assert edge.status == "settled"
    assert edge.amount == 3.0
    assert state.runtime.ignored_regressions


def test_duplicate_task_events_at_same_status_can_fill_missing_fields_without_regression():
    state = reduce_visual_events(
        (
            visual_event("task", "task-2", {"task_id": "task-2", "status": "assigned", "requester_id": "requester"}),
            visual_event("task", "task-2", {"task_id": "task-2", "status": "assigned", "worker_id": "worker", "reward": 5.0}),
        ),
        provenance="replay",
    )

    task = next(task for task in state.tasks if task.task_id == "task-2")
    assert task.status == "assigned"
    assert task.requester_id == "requester"
    assert task.worker_id == "worker"
    assert task.reward == 5.0
    assert not state.runtime.ignored_regressions
