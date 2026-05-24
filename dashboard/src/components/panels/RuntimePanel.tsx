import type { VisualNetworkState } from "../../lib/visual-state";
import { describeStream } from "../../lib/event-stream";

export function RuntimePanel({ state }: { state: VisualNetworkState }) {
  const mode = state.provenance === "live" ? "live" : state.provenance === "replay" ? "replay" : "mock";
  const warnings = state.runtime.warnings ?? [];
  return (
    <section className="panel panel-runtime">
      <header><span>Runtime</span><strong>{state.runtime.status}</strong></header>
      <dl>
        <div><dt>Mode</dt><dd>{mode}</dd></div>
        <div><dt>Connection</dt><dd>{mode === "live" ? "local API polling" : "local API disconnected"}</dd></div>
        <div><dt>Events</dt><dd>{state.runtime.events}</dd></div>
        <div><dt>Ignored regressions</dt><dd>{state.runtime.ignored_regressions?.length ?? 0}</dd></div>
        <div><dt>Last refresh</dt><dd>{mode === "replay" ? "replay artifact" : "operator refresh"}</dd></div>
      </dl>
      <p>{describeStream({ mode, baseUrl: "http://127.0.0.1:8765", replayPath: "local-network-replay.json" })}</p>
      {warnings.length ? <p className="panel-warning">{warnings.join(" · ")}</p> : null}
    </section>
  );
}
