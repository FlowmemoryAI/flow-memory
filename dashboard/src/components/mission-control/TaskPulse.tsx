import type { VisualTaskNode } from "../../lib/visual-state";

export function TaskPulse({ task }: { task: VisualTaskNode }) {
  return <div className={`task-pulse task-${task.status}`} data-task-id={task.task_id}>{task.label}: {task.status}</div>;
}
