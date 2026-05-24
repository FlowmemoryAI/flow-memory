import type { VisualNetworkState } from "./visual-state";

export type ReplayEventType = "agent" | "memory" | "economy" | "neural" | "rl" | "safety" | "audit" | "task";

export type ReplayControllerState = {
  playing: boolean;
  cursor: number;
  speed: number;
  filters: ReplayEventType[];
};

export type ReplayEvent = {
  event_id: string;
  event_type: ReplayEventType | string;
  source: string;
  created_at: string;
  payload: Record<string, unknown>;
};

export const replayEventTypes: ReplayEventType[] = ["agent", "memory", "economy", "neural", "rl", "safety", "audit", "task"];

export function initialReplayState(): ReplayControllerState {
  return { playing: false, cursor: 0, speed: 1, filters: [...replayEventTypes] };
}

export function visibleReplayEvents(events: ReplayEvent[], state: ReplayControllerState): ReplayEvent[] {
  const allowed = new Set(state.filters);
  return events.filter((event) => allowed.has(event.event_type as ReplayEventType));
}

export function stepReplay(state: ReplayControllerState, eventCount: number, direction: 1 | -1 = 1): ReplayControllerState {
  if (eventCount <= 0) return { ...state, cursor: 0 };
  const next = Math.max(0, Math.min(eventCount - 1, state.cursor + direction));
  return { ...state, cursor: next };
}

export function resetReplay(state: ReplayControllerState): ReplayControllerState {
  return { ...state, playing: false, cursor: 0 };
}

export function setReplayPlaying(state: ReplayControllerState, playing: boolean): ReplayControllerState {
  return { ...state, playing };
}

export function setReplaySpeed(state: ReplayControllerState, speed: number): ReplayControllerState {
  const normalized = Number.isFinite(speed) ? Math.max(0.25, Math.min(4, speed)) : 1;
  return { ...state, speed: normalized };
}

export function toggleReplayFilter(state: ReplayControllerState, filter: ReplayEventType): ReplayControllerState {
  const active = new Set(state.filters);
  if (active.has(filter)) {
    active.delete(filter);
  } else {
    active.add(filter);
  }
  return { ...state, filters: replayEventTypes.filter((type) => active.has(type)) };
}

export function replayProgress(state: ReplayControllerState, eventCount: number): number {
  if (eventCount <= 1) return 0;
  return Math.max(0, Math.min(1, state.cursor / (eventCount - 1)));
}

export function currentReplayEvent(events: ReplayEvent[], state: ReplayControllerState): ReplayEvent | undefined {
  return visibleReplayEvents(events, state)[Math.max(0, state.cursor)];
}

export function eventTimelineWindow(events: ReplayEvent[], state: ReplayControllerState, radius = 4): ReplayEvent[] {
  const visible = visibleReplayEvents(events, state);
  const start = Math.max(0, state.cursor - radius);
  return visible.slice(start, Math.min(visible.length, state.cursor + radius + 1));
}

export function summarizeReplay(state: VisualNetworkState, events: ReplayEvent[]): string {
  return `${events.length} events · ${state.agents.length} agents · ${state.economy.length} economy edges · ${state.provenance}`;
}
