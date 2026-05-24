import type { VisualNetworkState } from "../../lib/visual-state";
import { currentReplayEvent, eventTimelineWindow, initialReplayState, replayEventTypes, replayProgress, summarizeReplay, type ReplayEvent } from "../../lib/replay-controller";

export function ReplayControls({ state, events }: { state: VisualNetworkState; events: ReplayEvent[] }) {
  const replay = { ...initialReplayState(), cursor: Math.max(0, Math.min(events.length - 1, Math.floor(events.length * 0.62))) };
  const progress = replayProgress(replay, events.length);
  const current = currentReplayEvent(events, replay);
  const timeline = eventTimelineWindow(events, replay, 4);
  return (
    <section className="replay-controls" aria-label="Mission Control replay controls">
      <header>
        <span>Replay controller</span>
        <strong>{summarizeReplay(state, events)}</strong>
      </header>
      <div className="replay-buttons" role="group" aria-label="Replay actions">
        <button type="button" data-action="play">Play</button>
        <button type="button" data-action="pause">Pause</button>
        <button type="button" data-action="reset">Reset</button>
        <button type="button" data-action="step-backward">Step backward</button>
        <button type="button" data-action="step-forward">Step forward</button>
      </div>
      <label className="speed-control">
        <span>Speed</span>
        <input type="range" min="0.25" max="4" step="0.25" defaultValue={String(replay.speed)} aria-label="Replay speed control" />
      </label>
      <div className="replay-progress" style={{ "--replay-progress": progress } as Record<string, number>} aria-label={`Replay progress ${(progress * 100).toFixed(0)} percent`}>
        <span />
      </div>
      <div className="event-filters" aria-label="event filters">
        {replayEventTypes.map((type) => <label key={type}><input type="checkbox" defaultChecked />{type}</label>)}
      </div>
      <div className="current-event-readout">
        <span>Current event</span>
        <strong>{current ? current.event_type : "none"}</strong>
        <small>{current ? current.source : "no replay events"}</small>
      </div>
      <ol className="event-timeline">
        {timeline.map((event) => <li key={event.event_id} data-event-type={event.event_type}><b>{event.event_type}</b><span>{event.source}</span></li>)}
      </ol>
    </section>
  );
}
