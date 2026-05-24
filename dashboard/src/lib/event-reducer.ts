import type { VisualNetworkState } from "./visual-state";

export type VisualEvent = {
  event_id: string;
  event_type: string;
  source: string;
  provenance: "live" | "replay" | "mock" | "synthetic";
  payload: Record<string, unknown>;
};

export function eventCountByType(events: VisualEvent[]): Record<string, number> {
  return events.reduce<Record<string, number>>((acc, event) => {
    acc[event.event_type] = (acc[event.event_type] ?? 0) + 1;
    return acc;
  }, {});
}

export function stateHasRealSignals(state: VisualNetworkState): boolean {
  return state.agents.length > 0 && (state.tasks.length > 0 || state.neural.length > 0 || state.rl.length > 0 || state.safety.length > 0);
}
