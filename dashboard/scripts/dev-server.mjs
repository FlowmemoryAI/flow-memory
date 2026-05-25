import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const projectRoot = path.resolve(root, '..');
const port = Number(process.env.PORT || 4173);
const host = process.env.HOST || '127.0.0.1';
const mockDataDir = path.join(root, 'src', 'mock-data');
const stylePath = path.join(root, 'src', 'styles', 'mission-control.css');

const fixtureSpecs = [
  {
    fixture_id: 'live-neural-agent-launch',
    label: 'Live Neural Agent Launch',
    description: 'One-shot local neural-live agent replay with policy-gated advisory neural steps.',
    path: 'live-neural-agent-launch.json',
    run_kind: 'launchpad',
  },
  {
    fixture_id: 'live-agent-operations',
    label: 'Live Agent Operations',
    description: 'Run registry replay showing inspect, replay, export, stop, and continuation metadata.',
    path: 'live-agent-operations.json',
    run_kind: 'operations',
  },
  {
    fixture_id: 'live-agent-supervisor',
    label: 'Live Agent Supervisor',
    description: 'Bounded supervisor heartbeat/tick replay for local neural-live operations.',
    path: 'live-agent-supervisor.json',
    run_kind: 'supervisor',
  },
  {
    fixture_id: 'live-neural-embodiment',
    label: 'Live Neural Embodiment',
    description: '3D-ready neural runtime, loop phase, policy gate, memory, learning, heartbeat, and GPU evidence replay.',
    path: 'live-neural-embodiment.json',
    run_kind: 'embodiment',
  },
  {
    fixture_id: 'local-network-replay',
    label: 'Local Network Replay',
    description: 'Requester, worker, verifier, auditor, economy, safety, memory, RL, and compute replay.',
    path: 'local-network-replay.json',
    run_kind: 'local_network',
  },
];

const safeLiveReadEndpoints = [
  'GET /visual/state',
  'GET /visual/events',
  'GET /launch/console/runs',
  'GET /launch/console/fixtures',
  'GET /visual/embodiment/{run_id}',
  'GET /launch/console/runs/{run_id}/embodiment',
  'GET /release/decision/public-alpha-launch-finalizer',
];


function send(res, status, contentType, body) {
  res.writeHead(status, { 'content-type': contentType });
  res.end(body);
}

function readJson(filePath) {
  if (!fs.existsSync(filePath)) return {};
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return {};
  }
}

function readFixture(spec) {
  return readJson(path.join(mockDataDir, spec.path));
}

function readProjectJson(relativePath) {
  return readJson(path.join(projectRoot, relativePath));
}

function text(value) {
  return escapeHtml(value == null ? '' : String(value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function className(value) {
  return String(value || '').replace(/[^a-z0-9_-]/gi, '-').toLowerCase();
}

function eventsFrom(payload) {
  return Array.isArray(payload?.events) ? payload.events : [];
}

function eventCategoryCounts(events) {
  const counts = {
    neural: 0,
    policy: 0,
    memory: 0,
    action: 0,
    supervisor: 0,
    'compute/economy': 0,
    'audit/safety': 0,
  };
  for (const event of events) {
    const payloadEvent = typeof event?.payload?.event === 'string' ? event.payload.event : '';
    if (event?.event_type === 'neural') counts.neural += 1;
    else if (event?.event_type === 'memory') counts.memory += 1;
    else if (event?.event_type === 'supervisor') counts.supervisor += 1;
    else if (event?.event_type === 'economy' || event?.event_type === 'compute') counts['compute/economy'] += 1;
    else if (event?.event_type === 'audit' || event?.event_type === 'safety') counts['audit/safety'] += 1;
    else counts.action += 1;
    if (event?.event_type === 'safety' || payloadEvent.includes('policy')) counts.policy += 1;
  }
  return counts;
}


function firstState(payloads) {
  return payloads['local-network-replay']?.state || {};
}

function firstNeural(state) {
  const neural = Array.isArray(state?.neural) ? state.neural : [];
  return neural.length ? neural[neural.length - 1] : {};
}

function summarizeRunFixture(spec, payload) {
  const summary = payload?.summary || {};
  const runRecord = payload?.run_record || {};
  const supervisor = payload?.supervisor || {};
  const embodiment = payload?.embodiment || {};
  const source = Object.keys(embodiment).length ? embodiment : Object.keys(supervisor).length ? supervisor : Object.keys(runRecord).length ? runRecord : summary;
  const state = payload?.state || {};
  const latestNeural = firstNeural(state);
  const events = eventsFrom(payload);
  return {
    run_id: source.run_id || spec.fixture_id,
    run_kind: spec.run_kind,
    agent_id: source.agent_id || summary.agent_id || '',
    session_id: source.session_id || summary.session_id || latestNeural.session_id || '',
    supervisor_id: source.supervisor_id || supervisor.supervisor_id || '',
    template: source.template || summary.template || '',
    backend: source.backend || summary.backend || latestNeural.backend || 'tiny_torch',
    status: source.status || (payload?.ok ? 'completed' : 'missing'),
    current_phase: source.current_loop_phase || supervisor.current_phase || latestNeural.phase || source.status || 'observed',
    ticks_requested: source.tick_count_requested || supervisor.max_ticks || source.heartbeat_state?.max_ticks || summary.loop_ticks_completed || 0,
    ticks_completed: source.tick_count_completed || supervisor.ticks_completed || source.heartbeat_state?.ticks_completed || summary.loop_ticks_completed || 0,
    policy_gate_state: source.policy_gate_state || supervisor.policy_gate_state || latestNeural.policy_gate_state || 'applied',
    risk_score: Number(source.risk_score ?? latestNeural.risk_score ?? 0),
    confidence_score: Number(source.confidence_score ?? latestNeural.prediction_confidence ?? 0),
    learning_steps: Number(source.learning_tick_count ?? summary.learning_steps ?? events.filter((event) => event?.payload?.event === 'neural_learning_step_completed').length),
    memory_records_written: Number(source.memory_activation_count ?? source.memory_records_written ?? summary.memory_records_written ?? (Array.isArray(state.memory) ? state.memory.length : 0)),
    visual_events_emitted: Number(source.visual_events_emitted ?? summary.visual_events_emitted ?? events.length),
    replay_artifact_path: source.replay_artifact_path || `dashboard/src/mock-data/${spec.path}`,
    run_record_path: source.run_record_path || '',
    bundle_path: source.bundle_path || '',
    gpu_evidence_status: source.gpu_evidence_status || summary.gpu_evidence_status || 'blocked_missing_artifact',
    event_category_counts: eventCategoryCounts(events),
  };
}

function runStatusFields(summary) {
  return [
    ['Run', summary.run_id],
    ['Kind', summary.run_kind],
    ['Agent', summary.agent_id],
    ['Backend', summary.backend],
    ['Status', summary.status],
    ['Phase', summary.current_phase],
    ['Ticks', `${summary.ticks_completed}/${summary.ticks_requested}`],
    ['Policy', summary.policy_gate_state],
    ['Risk', summary.risk_score.toFixed(3)],
    ['Confidence', summary.confidence_score.toFixed(3)],
    ['Memory', summary.memory_records_written],
    ['Events', summary.visual_events_emitted],
    ['GPU evidence', summary.gpu_evidence_status],
  ];
}

function renderRunSelector(payloads) {
  const selected = fixtureSpecs.find((fixture) => fixture.fixture_id === 'live-agent-supervisor') || fixtureSpecs[0];
  const selectedSummary = summarizeRunFixture(selected, payloads[selected.fixture_id] || {});
  const buttons = fixtureSpecs.map((fixture) => `
    <button type="button" data-active="${fixture.fixture_id === selected.fixture_id}">
      <strong>${text(fixture.label)}</strong>
      <span>${text(fixture.description)}</span>
      <small>${text(fixture.run_kind)} · dashboard/src/mock-data/${text(fixture.path)}</small>
    </button>`).join('');
  const fields = runStatusFields(selectedSummary).map(([label, value]) => `<div><dt>${text(label)}</dt><dd>${text(value)}</dd></div>`).join('');
  const categories = Object.entries(selectedSummary.event_category_counts).map(([category, count]) => `<span>${text(category)}: ${text(count)}</span>`).join('');
  return `
    <section id="runs" class="run-console mission-surface mission-surface-wide" aria-label="Mission Control run selector">
      <header class="surface-header">
        <span>Run selector</span>
        <strong>Mission Control Run Selector</strong>
        <small>Replay fixtures convert verified agent work into reusable operator context.</small>
      </header>
      <div class="run-console-layout">
        <div class="run-selector-grid" role="listbox" aria-label="Replay fixture selector">${buttons}</div>
        <article class="run-status-card" aria-label="Selected run status">
          <header><span>${text(selected.label)}</span><strong>${text(selectedSummary.status)}</strong></header>
          <dl>${fields}</dl>
          <div class="event-category-counts" aria-label="Replay event category counts">${categories}</div>
          <footer>
            <span>Replay artifact: ${text(selectedSummary.replay_artifact_path)}</span>
            <span>Run record: ${text(selectedSummary.run_record_path || 'fixture only')}</span>
          </footer>
        </article>
      </div>
    </section>`;
}

function renderReplaySummary(payloads) {
  const replay = payloads['local-network-replay'] || {};
  const events = eventsFrom(replay);
  const progress = events.length ? Math.min(1, 8 / events.length) : 0;
  const latest = events.slice(-6).reverse().map((event) => `
    <li data-event-type="${text(event.event_type || 'event')}">
      <b>${text(event.event_type || 'event')}</b>
      <span>${text(event.payload?.event || event.event_id || 'observed')}</span>
      <small>${text(event.source_event_id || event.event_id || '')}</small>
    </li>`).join('');
  return `
    <section id="replay" class="replay-controls mission-surface" aria-label="Mission Control replay controls">
      <header class="surface-header">
        <span>Local Network Replay</span>
        <strong>${text(events.length)} replay events loaded</strong>
        <small>Scrub through requester, worker, verifier, auditor, economy, safety, memory, and neural events.</small>
      </header>
      <div class="replay-buttons"><button type="button">Play</button><button type="button">Pause</button><button type="button">Reset</button><button type="button">Step forward</button><button type="button">Step backward</button></div>
      <div class="replay-progress" aria-label="Replay progress"><span style="--replay-progress: ${progress}"></span></div>
      <div class="event-filters"><label>neural</label><label>policy</label><label>memory</label><label>compute/economy</label><label>audit/safety</label></div>
      <ol class="event-timeline">${latest}</ol>
    </section>`;
}

function renderEmbodimentPanel(payload) {
  const embodiment = payload?.embodiment || {};
  const heartbeat = embodiment.heartbeat_state || {};
  const graph = payload?.graph || { nodes: [], loop: '' };
  const fields = [
    ['Run', embodiment.run_id],
    ['Agent', embodiment.agent_id],
    ['Session', embodiment.session_id],
    ['Backend', embodiment.backend],
    ['GPU evidence', embodiment.gpu_evidence_status],
    ['Phase', embodiment.current_loop_phase],
    ['Policy', embodiment.policy_gate_state],
    ['Runtime', embodiment.neural_runtime_status],
    ['Heartbeat', heartbeat.status || 'observed'],
    ['Ticks', `${heartbeat.ticks_completed || 0}/${heartbeat.max_ticks || 0}`],
    ['Confidence', Number(embodiment.confidence_score || 0).toFixed(3)],
    ['Risk', Number(embodiment.risk_score || 0).toFixed(3)],
    ['Memory', embodiment.memory_activation_count || 0],
    ['Learning', embodiment.learning_tick_count || 0],
  ].map(([label, value]) => `<div><dt>${text(label)}</dt><dd>${text(value)}</dd></div>`).join('');
  const nodes = Array.isArray(graph.nodes) ? graph.nodes.map((node) => `
    <div class="loop-node loop-node-${className(node.kind)}" data-active="${Boolean(node.active)}" title="${text(node.source || '')}">
      <span>${text(node.label)}</span><small>${text(node.status)}</small>
    </div>`).join('') : '';
  return `
    <section id="embodiment" class="neural-embodiment-panel mission-surface mission-surface-wide" aria-label="Neural embodiment state">
      <header><span>Visible neural embodiment</span><strong>${text(embodiment.current_loop_phase)}</strong></header>
      <div class="embodiment-hero" data-phase="${text(embodiment.current_loop_phase)}" data-gpu="${text(embodiment.gpu_evidence_status)}">
        <div class="embodiment-avatar" style="--confidence: ${Number(embodiment.confidence_score || 0)}; --risk: ${Number(embodiment.risk_score || 0)}"><i></i><b>${text(embodiment.current_loop_phase)}</b></div>
        <div>
          <h2>Policy-gated local neural agent</h2>
          <p>This is replay/local API Mission Control state from local neural runtime and supervisor artifacts. Neural outputs are advisory; PolicyEngine and ApprovalGate remain authoritative.</p>
          <small>Animation state: ${text(embodiment.visual?.animation_state || '3d-ready')}</small>
        </div>
      </div>
      <dl class="embodiment-metrics">${fields}</dl>
      <div class="neural-loop-graph" aria-label="${text(graph.loop || '')}">${nodes}</div>
      <footer><span>${text(graph.loop || '')}</span><span>Replay event index ${text(embodiment.replay_event_index || 0)}</span><span>${text(embodiment.replay_artifact_path || '')}</span></footer>
    </section>`;
}

function renderLive3DPanel(payload, state) {
  const embodiment = payload?.embodiment || {};
  const graph = payload?.graph || { nodes: [] };
  const visual = embodiment.visual || {};
  const heartbeat = embodiment.heartbeat_state || {};
  const ready = Boolean(payload?.ok && visual.three_ready && graph.policy_gated && embodiment.local_only && embodiment.neural_advisory_only);
  const nodes = Array.isArray(graph.nodes) ? graph.nodes.map((node) => `
    <span class="live-3d-loop-node live-3d-loop-node-${className(node.kind)}" data-active="${Boolean(node.active)}" title="${text(node.source || '')}">
      ${text(node.label)}<small>${text(node.status)}</small>
    </span>`).join('') : '';
  return `
    <section id="live-3d" class="live-3d-mode-panel mission-surface mission-surface-wide" aria-label="Mission Control Live 3D Mode" data-live-3d-mode="${ready ? 'ready' : 'blocked'}" data-source="${text(state?.provenance || 'replay')}" data-gpu="${text(embodiment.gpu_evidence_status)}">
      <header>
        <div><span>Mission Control Live 3D Mode</span><strong>${ready ? '3D telemetry ready' : '3D telemetry blocked'}</strong></div>
        <small>${text(state?.provenance || 'replay')} · ${text(embodiment.backend)} · GPU evidence ${text(embodiment.gpu_evidence_status)}</small>
      </header>
      <div class="live-3d-mode-body">
        <div class="live-3d-scene" style="--confidence: ${Number(embodiment.confidence_score || 0)}; --risk: ${Number(embodiment.risk_score || 0)}; --node-scale: ${Number(visual.node_scale || 1)}; --memory-orbits: ${Number(visual.memory_orbit_count || 0)}" aria-label="Read-only live 3D neural scene preview">
          <div class="live-3d-grid"></div>
          <div class="live-3d-agent-body"><i class="live-3d-risk-shell"></i><i class="live-3d-neural-core"></i><b>${text(embodiment.current_loop_phase)}</b></div>
          <div class="live-3d-memory-orbit live-3d-memory-orbit-a"></div>
          <div class="live-3d-memory-orbit live-3d-memory-orbit-b"></div>
          <div class="live-3d-policy-gate">Policy gate: ${text(embodiment.policy_gate_state)}</div>
        </div>
        <div class="live-3d-readout">
          <h2>Local neural embodiment, rendered as a read-only 3D operations mode.</h2>
          <p>The scene is driven by replay/local API telemetry from the bounded local supervisor and neural runtime. It does not start agents, contact providers, move funds, or bypass approval gates.</p>
          <dl>
            <div><dt>Run</dt><dd>${text(embodiment.run_id)}</dd></div>
            <div><dt>Session</dt><dd>${text(embodiment.session_id)}</dd></div>
            <div><dt>Heartbeat</dt><dd>${text(heartbeat.status || 'observed')} · ${text(heartbeat.ticks_completed || 0)}/${text(heartbeat.max_ticks || 0)}</dd></div>
            <div><dt>Confidence / risk</dt><dd>${Number(embodiment.confidence_score || 0).toFixed(3)} / ${Number(embodiment.risk_score || 0).toFixed(3)}</dd></div>
            <div><dt>Memory / learning</dt><dd>${text(embodiment.memory_activation_count || 0)} / ${text(embodiment.learning_tick_count || 0)}</dd></div>
            <div><dt>Replay index</dt><dd>${text(embodiment.replay_event_index || 0)}</dd></div>
          </dl>
        </div>
      </div>
      <div class="live-3d-loop-strip" aria-label="${text(graph.loop || '')}">${nodes}</div>
      <footer><span>Authority: ${text(embodiment.policy_authority)}</span><span>Provider calls: ${embodiment.no_live_provider_calls ? 'disabled' : 'blocked'}</span><span>Funds: ${embodiment.no_funds_moved ? 'not moved' : 'blocked'}</span><span>Settlement: ${embodiment.no_live_settlement ? 'disabled' : 'blocked'}</span></footer>
    </section>`;
}

function renderFinalizerStatus(finalizer) {
  const live3D = finalizer?.mission_control_live_3d || {};
  const launch = finalizer?.release_decisions?.['public-alpha-launch'] || {};
  const local = finalizer?.release_decisions?.['public-alpha-local-launch'] || {};
  const ctmp = finalizer?.invariants?.ctmp_backup_not_tracked === true;
  return `
    <section id="finalizer" class="panel public-alpha-finalizer mission-surface" aria-label="Public Alpha Finalizer Status">
      <header class="surface-header">
        <span>Public-alpha finalizer status</span>
        <strong>${finalizer?.ok ? 'ready' : 'pending'}</strong>
        <small>Evidence-only launch gate for the branded operator console.</small>
      </header>
      <p>Mission Control Live 3D Mode, GPU evidence, release decisions, demo bundle status, and C:\\tmp backup exclusion are checked before handoff.</p>
      <dl>
        <div><dt>Finalizer</dt><dd>${finalizer?.ok ? 'ok' : 'missing'}</dd></div>
        <div><dt>Hash</dt><dd>${text(finalizer?.hash || 'not generated')}</dd></div>
        <div><dt>Live 3D</dt><dd>${live3D.ok ? 'ok' : 'pending'}</dd></div>
        <div><dt>GPU launch</dt><dd>${launch.ok ? text(launch.classification) : 'pending'}</dd></div>
        <div><dt>Local launch</dt><dd>${local.ok ? text(local.classification) : 'pending'}</dd></div>
        <div><dt>C:\\tmp backup</dt><dd>${ctmp ? 'not tracked' : 'review required'}</dd></div>
      </dl>
    </section>`;
}

function renderSafeLiveApiPanel() {
  const endpoints = safeLiveReadEndpoints.map((endpoint) => `<span>${text(endpoint)}</span>`).join('');
  return `
    <section class="mission-control-endpoints mission-proof-strip" aria-label="Optional local API read mode">
      <div>
        <strong>Replay/mock mode works without API</strong>
        <small>Optional local API mode is read-only from this dashboard.</small>
      </div>
      <div class="safe-endpoint-list">${endpoints}</div>
    </section>`;
}

function renderOperatorMarquee() {
  const terms = ['Human compute', 'Device signal', 'Signed receipt', 'Memory capsule', 'Proof root', 'Verified recall'];
  const row = terms.map((term) => `<span>${text(term)}</span>`).join('');
  return `
    <section class="mission-marquee" aria-label="Flow Memory network primitives">
      <div>${row}</div>
      <div aria-hidden="true">${row}</div>
    </section>`;
}

function renderProofNarrative() {
  return `
    <section class="mission-proof-narrative" aria-label="Proof-carrying memory narrative">
      <div class="mission-proof-copy">
        <h2>Every run leaves an evidence trail the next agent can reuse.</h2>
        <p class="mission-scrub-copy" data-motion="scrub-text">Replay events, neural heartbeat state, GPU validation, policy gates, memory activations, and release finalizer status resolve into a single operator view. Nothing in this dashboard starts agents or writes to unsafe control endpoints.</p>
      </div>
      <div class="mission-proof-bento" aria-label="Mission Control proof bento">
        <article class="mission-bento-card mission-bento-wide" data-motion="image-scale">
          <strong>Run selector</strong>
          <span>Five checked-in fixtures, one verified path from local replay to public-alpha evidence.</span>
        </article>
        <article class="mission-bento-card" data-motion="image-scale">
          <strong>Embodiment</strong>
          <span>Policy-gated neural state stays visible without claiming autonomous authority.</span>
        </article>
        <article class="mission-bento-card" data-motion="image-scale">
          <strong>Live 3D</strong>
          <span>GPU evidence and local-only constraints are rendered as read-only operator context.</span>
        </article>
        <article class="mission-bento-card mission-bento-tall" data-motion="image-scale">
          <strong>Finalizer</strong>
          <span>Launch gates, demo bundle status, and C:\\tmp backup exclusion stay attached to the handoff.</span>
        </article>
      </div>
    </section>`;
}

function renderActionFooter() {
  return `
    <section class="mission-action-footer" aria-label="Mission Control action">
      <div>
        <h2>Review the launch handoff with proof in view.</h2>
        <p>The dashboard is intentionally read-only: replay/mock mode works offline, local API mode is optional, and unsafe write/control routes stay out of the frontend.</p>
        <div class="mission-hero-actions">
          <a class="mission-button mission-button-primary" href="#runs">Inspect run evidence <span aria-hidden="true">→</span></a>
          <a class="mission-button mission-button-ghost mission-button-light" href="#finalizer">Review finalizer</a>
        </div>
      </div>
      <figure class="mission-operator-quote">
        <div aria-hidden="true"><span></span><span></span><span></span></div>
        <blockquote>Mission Control reads like an evidence room, not a cockpit toy: state, proof, and launch gates stay legible in one pass.</blockquote>
        <figcaption>Public-alpha operator review</figcaption>
      </figure>
    </section>`;
}

function renderMotionScript() {
  return `<script>
(() => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const scrubBlocks = Array.from(document.querySelectorAll('[data-motion="scrub-text"]'));
  for (const block of scrubBlocks) {
    const words = block.textContent.trim().split(/\\s+/);
    block.textContent = '';
    for (const word of words) {
      const span = document.createElement('span');
      span.className = 'mission-scrub-word';
      span.textContent = word + ' ';
      block.appendChild(span);
    }
  }

  const animated = Array.from(document.querySelectorAll('[data-motion="image-scale"], .mission-scrub-word'));
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  function update() {
    const viewport = window.innerHeight || 1;
    for (const element of animated) {
      const rect = element.getBoundingClientRect();
      const progress = clamp(1 - Math.abs((rect.top + rect.height * 0.5 - viewport * 0.52) / viewport), 0, 1);
      if (element.classList.contains('mission-scrub-word')) {
        element.style.opacity = String(0.16 + progress * 0.84);
      } else {
        element.style.opacity = String(0.52 + progress * 0.48);
        element.style.transform = \`scale(\${0.94 + progress * 0.06}) translateY(\${(1 - progress) * 18}px)\`;
      }
    }
  }

  let ticking = false;
  const requestUpdate = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      update();
    });
  };

  window.addEventListener('scroll', requestUpdate, { passive: true });
  window.addEventListener('resize', requestUpdate);
  update();
})();
</script>`;
}

function renderMissionControlHtml(payloads, finalizer) {
  const state = firstState(payloads);
  const embodimentPayload = payloads['live-neural-embodiment'] || {};
  const css = fs.existsSync(stylePath) ? fs.readFileSync(stylePath, 'utf8') : '';
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Flow Memory Mission Control</title>
  <style>${css}</style>
</head>
<body>
  <main class="mission-control-page" data-mode="${text(state?.provenance || 'replay')}">
    <header class="mission-brand-nav" aria-label="Flow Memory Mission Control navigation">
      <a class="mission-brand" href="/mission-control" aria-label="Flow Memory Mission Control home">
        <span class="mission-brand-orb" aria-hidden="true"></span>
        <span>FlowMemory</span>
      </a>
      <nav aria-label="Mission Control sections">
        <a href="#runs">Runs</a>
        <a href="#replay">Replay</a>
        <a href="#embodiment">Embodiment</a>
        <a href="#live-3d">Live 3D</a>
      </nav>
      <a class="mission-status-pill" href="#finalizer">Public alpha ready</a>
    </header>

    <section class="mission-control-hero mission-hero-editorial" aria-labelledby="mission-control-title">
      <div class="mission-hero-copy">
        <h1 id="mission-control-title">Verified work becomes living memory.</h1>
        <p class="mission-hero-lede" data-motion="scrub-text">FlowMemory turns local agent runs, replay evidence, neural embodiment, and launch gates into a human-scale memory layer for AI systems.</p>
        <div class="mission-hero-actions">
          <a class="mission-button mission-button-primary" href="#runs">Inspect runs <span aria-hidden="true">→</span></a>
          <a class="mission-button mission-button-ghost" href="#live-3d">Open Live 3D</a>
        </div>
      </div>

      <aside class="mission-media-stage" aria-label="Mission Control editorial media">
        <div class="mission-media-image" data-motion="image-scale" aria-hidden="true"></div>
        <div class="mission-horizontal-accordion" aria-label="Mission Control view modes">
          <article>
            <strong>Receipt</strong>
            <span>signed work signals</span>
          </article>
          <article>
            <strong>Memory</strong>
            <span>reusable context</span>
          </article>
          <article>
            <strong>Proof</strong>
            <span>launch evidence</span>
          </article>
        </div>
        <div class="mode-switcher" aria-label="Mission Control mode switcher">
          <strong>replay artifact</strong>
          <small>Checked-in replay/mock fixtures load without API. Local API mode remains optional and read-only.</small>
          <div><button type="button" data-active="false">mock</button><button type="button" data-active="true">replay</button><button type="button" data-active="false">live local API</button></div>
        </div>
      </aside>
    </section>

    ${renderSafeLiveApiPanel()}
    ${renderOperatorMarquee()}
    ${renderRunSelector(payloads)}
    <div class="mission-stack-grid">
      ${renderReplaySummary(payloads)}
      ${renderFinalizerStatus(finalizer)}
    </div>
    ${renderProofNarrative()}
    ${renderEmbodimentPanel(embodimentPayload)}
    ${renderLive3DPanel(embodimentPayload, state)}
    ${renderActionFooter()}
  </main>
  ${renderMotionScript()}
</body>
</html>`;
}

export function dashboardHtml() {
  const payloads = Object.fromEntries(fixtureSpecs.map((spec) => [spec.fixture_id, readFixture(spec)]));
  const finalizer = readProjectJson('release_evidence/public_alpha_launch_finalizer.json');
  return renderMissionControlHtml(payloads, finalizer);
}

export function createMissionControlDevServer() {
  return http.createServer((req, res) => {
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      send(res, 405, 'application/json', JSON.stringify({ ok: false, error: 'method_not_allowed' }));
      return;
    }
    const url = new URL(req.url || '/', `http://${req.headers.host || '127.0.0.1'}`);
    if (url.pathname === '/' || url.pathname === '/mission-control') {
      send(res, 200, 'text/html; charset=utf-8', dashboardHtml());
      return;
    }
    if (url.pathname.startsWith('/mock-data/')) {
      const name = path.basename(url.pathname);
      const filePath = path.join(mockDataDir, name);
      if (!name.endsWith('.json') || !filePath.startsWith(mockDataDir) || !fs.existsSync(filePath)) {
        send(res, 404, 'application/json', JSON.stringify({ ok: false, error: 'mock_data_not_found' }));
        return;
      }
      send(res, 200, 'application/json', fs.readFileSync(filePath));
      return;
    }
    send(res, 404, 'application/json', JSON.stringify({ ok: false, error: 'not_found' }));
  });
}

export function startMissionControlDevServer(options = {}) {
  const preferredPort = Number(options.port ?? port);
  const listenHost = String(options.host ?? host);
  const maxAttempts = Number(options.maxAttempts ?? 20);
  const log = typeof options.log === 'function' ? options.log : console.log;

  return new Promise((resolve, reject) => {
    const tryListen = (candidatePort, attemptIndex) => {
      const server = createMissionControlDevServer();

      server.once('error', (error) => {
        if (
          error?.code === 'EADDRINUSE' &&
          Number.isInteger(candidatePort) &&
          candidatePort > 0 &&
          candidatePort < 65535 &&
          attemptIndex + 1 < maxAttempts
        ) {
          const nextPort = candidatePort + 1;
          log(`Port ${candidatePort} is already in use; trying ${nextPort}.`);
          tryListen(nextPort, attemptIndex + 1);
          return;
        }
        reject(error);
      });

      server.once('listening', () => {
        const address = server.address();
        const actualPort = typeof address === 'object' && address ? address.port : candidatePort;
        const url = `http://${listenHost}:${actualPort}/mission-control`;
        log(`Flow Memory Mission Control dev server: ${url}`);
        resolve({ server, host: listenHost, port: actualPort, url });
      });

      server.listen(candidatePort, listenHost);
    };

    tryListen(preferredPort, 0);
  });
}

const entryPoint = process.argv[1] ? path.resolve(process.argv[1]) : '';
if (entryPoint === fileURLToPath(import.meta.url)) {
  startMissionControlDevServer().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
