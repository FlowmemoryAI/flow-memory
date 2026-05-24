import type { VisualNetworkState } from "../../lib/visual-state";
import { initialReplayState, replayEventTypes, replayProgress, summarizeReplay, type ReplayEvent } from "../../lib/replay-controller";

export function ReplayControls({ state, events }: { state: VisualNetworkState; events: ReplayEvent[] }) {
  const replay = initialReplayState();
  const progress = replayProgress({ ...replay, cursor: Math.max(0, Math.min(events.length - 1, Math.floor(events.length * 0.62))) }, events.length);
  return (
    <section className="replay-controls" aria-label="Mission Control replay controls">
      <header>
        <span>Replay controller</span>
        <strong>{summarizeReplay(state, events)}</strong>
      </header>
      <div className="replay-buttons" role="group" aria-label="Replay actions">
        <button type="button">Play</button>
        <button type="button">Pause</button>
        <button type="button">Reset</button>
        <button type="button">Step forward</button>
      </div>
      <label className="speed-control">
        <span>Speed</span>
        <input type="range" min="0.25" max="3" step="0.25" defaultValue="1" />
      </label>
      <div className="replay-progress" style={{ "--replay-progress": progress } as Record<string, number>}>
        <span />
      </div>
      <div className="event-filters" aria-label="event filters">
        {replayEventTypes.map((type) => <label key={type}><input type="checkbox" defaultChecked />{type}</label>)}
      </div>
      <ol className="event-timeline">
        {events.slice(0, 8).map((event) => <li key={event.event_id}><b>{event.event_type}</b><span>{event.source}</span></li>)}
      </ol>
    </section>
  );
}
