import type { VisualTaskNode } from "../../lib/visual-state";

export function TaskPulse({ task, index }: { task: VisualTaskNode; index: number }) {
  const status = (task.status || "observed").toLowerCase();
  const reward = Number(task.reward ?? 0);
  return (
    <div
      className={`task-pulse task-${status}`}
      data-task-id={task.task_id}
      style={{ "--pulse-index": index, "--pulse-value": Math.max(1, reward) } as Record<string, number>}
    >
      <span className="task-pulse-line" />
      <span className="task-pulse-dot" />
      <strong>{status}</strong>
      <small>{task.requester_id || "requester"} → {task.worker_id || "worker"}</small>
    </div>
  );
}
