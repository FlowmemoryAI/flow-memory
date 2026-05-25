"use client";

import { useMemo, useState } from "react";
import { runConsoleFixtures, runStatusFields, summarizeRunFixture, type RunConsoleFixture, type RunConsoleSummary } from "../../lib/run-console";

type ReplayPayload = Record<string, unknown> & { events?: unknown[] };

export function RunSelector({ payloads }: { payloads: Record<string, ReplayPayload> }) {
  const [selectedId, setSelectedId] = useState("live-agent-supervisor");
  const selected = runConsoleFixtures.find((fixture) => fixture.fixture_id === selectedId) ?? runConsoleFixtures[0];
  const summary = useMemo<RunConsoleSummary>(() => summarizeRunFixture(selected, payloads[selected.fixture_id] ?? {}), [selected, payloads]);
  const categories = summary.event_category_counts ?? {};
  return (
    <section className="run-console" aria-label="Mission Control run selector">
      <header>
        <span>Local run console</span>
        <strong>Mission Control Run Selector</strong>
        <small>Choose a launch, operations, supervisor, or local-network replay fixture.</small>
      </header>
      <div className="run-selector-grid" role="listbox" aria-label="Replay fixture selector">
        {runConsoleFixtures.map((fixture: RunConsoleFixture) => (
          <button
            key={fixture.fixture_id}
            type="button"
            data-active={fixture.fixture_id === selected.fixture_id}
            onClick={() => setSelectedId(fixture.fixture_id)}
          >
            <strong>{fixture.label}</strong>
            <span>{fixture.description}</span>
            <small>{fixture.run_kind} · {fixture.path}</small>
          </button>
        ))}
      </div>
      <article className="run-status-card" aria-label="Selected run status">
        <header>
          <span>{selected.label}</span>
          <strong>{summary.status}</strong>
        </header>
        <dl>
          {runStatusFields(summary).map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <div className="event-category-counts" aria-label="Replay event category counts">
          {Object.entries(categories).map(([category, count]) => (
            <span key={category}>{category}: {count}</span>
          ))}
        </div>
        <footer>
          <span>Replay artifact: {summary.replay_artifact_path}</span>
          <span>Run record: {summary.run_record_path || "fixture only"}</span>
        </footer>
      </article>
    </section>
  );
}
