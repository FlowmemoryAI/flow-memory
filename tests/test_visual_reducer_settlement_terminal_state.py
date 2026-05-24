from flow_memory.visualization import reduce_visual_events, visual_event


def test_settlement_terminal_state_requires_valid_source_for_dispute_override():
    state = reduce_visual_events(
        (
            visual_event("task", "task-1", {"task_id": "task-1", "status": "settled"}),
            visual_event("task", "task-1", {"task_id": "task-1", "status": "disputed"}),
        ),
        provenance="replay",
    )
    task = next(task for task in state.tasks if task.task_id == "task-1")
    assert task.status == "settled"

    sourced_state = reduce_visual_events(
        (
            visual_event("task", "task-1", {"task_id": "task-1", "status": "settled"}, source_event_id="settlement-receipt"),
            visual_event("task", "task-1", {"task_id": "task-1", "status": "disputed"}, source_event_id="dispute-receipt"),
            visual_event("task", "task-1", {"task_id": "task-1", "status": "slashed"}, source_event_id="slashing-receipt"),
        ),
        provenance="replay",
    )
    sourced_task = next(task for task in sourced_state.tasks if task.task_id == "task-1")
    assert sourced_task.status == "slashed"
    assert not sourced_state.runtime.ignored_regressions


def test_settled_task_ignores_late_created_duplicate_even_with_same_task_id():
    state = reduce_visual_events(
        (
            visual_event("task", "task-3", {"task_id": "task-3", "status": "created"}),
            visual_event("economy", "settle", {"edge_id": "settle", "task_id": "task-3", "kind": "settlement", "status": "settled", "amount": 2.0}, source_event_id="settlement-receipt"),
            visual_event("task", "task-3", {"task_id": "task-3", "status": "created"}),
        ),
        provenance="replay",
    )
    task = next(task for task in state.tasks if task.task_id == "task-3")
    assert task.status == "settled"
    assert state.runtime.ignored_regressions
