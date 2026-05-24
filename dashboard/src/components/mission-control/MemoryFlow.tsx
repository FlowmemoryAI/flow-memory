import type { VisualMemoryNode } from "../../lib/visual-state";

export function MemoryFlow({ memory, index }: { memory: VisualMemoryNode; index: number }) {
  const importance = Math.max(0.1, Math.min(1, Number(memory.importance || 0.2)));
  return (
    <div
      className="memory-flow"
      aria-label={`memory ${memory.kind}`}
      style={{ "--flow-index": index, "--flow-intensity": importance } as Record<string, number>}
    >
      <span className="memory-flow-ribbon" />
      <span className="memory-flow-particle" />
      <small>{memory.kind}</small>
    </div>
  );
}
