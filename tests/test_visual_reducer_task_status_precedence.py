from flow_memory.visualization import reduce_visual_events, visual_event


def _task_status(state, task_id="task-1"):
    tasks = {task.task_id: task for task in state.tasks}
    return tasks[task_id].status


def test_task_status_precedence_ignores_late_lower_priority_task_event():
    state = reduce_visual_events(
        (
            visual_event("task", "task-1", {"task_id": "task-1", "status": "created", "requester_id": "requester"}),
            visual_event("task", "task-1", {"task_id": "task-1", "status": "assigned", "worker_id": "worker"}),
            visual_event("task", "task-1", {"task_id": "task-1", "status": "settled", "reward": 4.0}),
            visual_event("task", "task-1", {"task_id": "task-1", "status": "assigned", "worker_id": "older-worker"}),
        ),
        provenance="replay",
    )

    assert _task_status(state) == "settled"
    task = next(task for task in state.tasks if task.task_id == "task-1")
    assert task.worker_id == "worker"
    assert state.runtime.ignored_regressions
    assert "settled->assigned" in state.runtime.ignored_regressions[0]
