import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const projectRoot = path.resolve(root, '..');
const port = Number(process.env.PORT || 4173);
const host = process.env.HOST || '127.0.0.1';
const mockDataDir = path.join(root, 'src', 'mock-data');
const stylePath = path.join(root, 'src', 'styles', 'mission-control.css');
const gsapDistDir = path.join(root, 'node_modules', 'gsap', 'dist');
const threeDistDir = path.join(root, 'node_modules', 'three', 'build');
const vendorScripts = new Map([
  ['gsap.min.js', path.join(gsapDistDir, 'gsap.min.js')],
  ['ScrollTrigger.min.js', path.join(gsapDistDir, 'ScrollTrigger.min.js')],
  ['three.module.js', path.join(threeDistDir, 'three.module.js')],
  ['three.core.js', path.join(threeDistDir, 'three.core.js')],
]);

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
  {
    fixture_id: 'predictive-cognitive-core',
    label: 'Predictive Cognitive Core',
    description: 'Prediction, counterfactual, policy, outcome, error, and lesson replay.',
    path: 'predictive-cognitive-core.json',
    run_kind: 'cognition',
  },
  {
    fixture_id: 'predictive-learning-benchmark',
    label: 'Predictive Learning Benchmark',
    description: 'Repeated local scenarios proving prediction error drops after lesson consolidation.',
    path: 'predictive-learning-benchmark.json',
    run_kind: 'cognition_benchmark',
  },
  {
    fixture_id: 'agent-genesis-onboarding',
    label: 'Agent Genesis',
    description: 'Private-by-default agent birth, genome, memory seed, consent, first prediction, mirror, and passport replay.',
    path: 'agent-genesis-onboarding.json',
    run_kind: 'genesis',
  },
  {
    fixture_id: 'agent-internet-skill-network',
    label: 'Agent Internet',
    description: 'Local agent identity registry, skill matcher, collaboration graph, reputation, MCP manifest gate, and x402 dry-run intent.',
    path: 'agent-internet-skill-network.json',
    run_kind: 'agent_internet',
  },
  {
    fixture_id: 'byok-onchain-upgrades',
    label: 'BYOK + On-chain Upgrades',
    description: 'Optional model-key references, wallet identity binding, on-chain dry-run upgrade intents, and emergency stop.',
    path: 'byok-onchain-upgrades.json',
    run_kind: 'agent_upgrades',
  },
  {
    fixture_id: 'agent-builder',
    label: 'Flow Memory Agent Builder',
    description: 'Browser agent builder and capability composer for safe first-agent birth plus optional upgrades.',
    path: 'agent-builder.json',
    run_kind: 'agent-builder',
  },
  {
    fixture_id: 'experience-graph-proof-of-learning',
    label: 'Proof of Learning',
    description: 'Experience graph, proof-of-learning ledger, reputation, and privacy-preserving contribution replay.',
    path: 'experience-graph-proof-of-learning.json',
    run_kind: 'proof_of_learning',
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
  'GET /cognition/experiences',
  'GET /cognition/prediction-errors',
  'GET /launch/console/runs/{run_id}/predictions',
  'GET /cognition/benchmarks',
  'GET /cognition/lessons',
  'GET /cognition/metrics',
  'GET /genesis/archetypes',
  'GET /genesis/instincts',
  'GET /genesis/boundaries',
  'GET /genesis/agents/{agent_id}/passport',
  'GET /genesis/agents/{agent_id}/genome',
  'GET /genesis/agents/{agent_id}/mirror',
  'GET /genesis/contributions',
  'GET /internet/agents',
  'GET /internet/agents/{agent_id}',
  'GET /internet/collaborations',
  'GET /internet/collaborations/{session_id}',
  'GET /internet/workspaces/{workspace_id}',
  'GET /internet/reputation/{agent_id}',
  'GET /internet/erc8004/{agent_id}',
  'GET /internet/mcp/manifests',
  'GET /byok/providers',
  'GET /byok/credentials',
  'GET /wallet/bindings',
  'GET /emergency-stop/{agent_id}',
  'GET /agent-builder/defaults',
  'GET /experience-graph',
  'GET /experience-graph/agents/{agent_id}',
  'GET /proof-of-learning',
  'GET /learning-reputation',
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

function sendJson(res, status, body) {
  send(res, status, 'application/json; charset=utf-8', JSON.stringify(body, null, 2));
}

function readRequestJson(req, maxBytes = 65_536) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > maxBytes) {
        reject(new Error('request body exceeds maximum size'));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      if (!chunks.length) {
        resolve({});
        return;
      }
      try {
        const payload = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
          reject(new Error('JSON request body must be an object'));
          return;
        }
        resolve(payload);
      } catch (error) {
        reject(error);
      }
    });
    req.on('error', reject);
  });
}

function sanitizeString(value, fallback = '') {
  return String(value == null ? fallback : value).replace(/[\u0000-\u001f\u007f]/g, ' ').trim().slice(0, 1200);
}

function sanitizeStringList(value, limit = 12) {
  const source = Array.isArray(value) ? value : typeof value === 'string' ? value.split('\n') : [];
  return [...new Set(source.map((item) => sanitizeString(item)).filter(Boolean))].slice(0, limit);
}

function sanitizeGenesisBirthPayload(payload) {
  const memorySeed = payload.memory_seed && typeof payload.memory_seed === 'object' && !Array.isArray(payload.memory_seed)
    ? payload.memory_seed
    : {};
  const agentName = sanitizeString(payload.agent_name || payload.name || 'Mira', 'Mira').slice(0, 80);
  if (!agentName) throw new Error('agent name is required');
  return {
    user_id: sanitizeString(payload.user_id || payload.user || 'dashboard-user', 'dashboard-user').slice(0, 80),
    agent_name: agentName,
    archetype_id: sanitizeString(payload.archetype_id || payload.archetype || 'research-builder', 'research-builder').slice(0, 80),
    purpose: sanitizeString(payload.purpose || 'Help me build and remember Flow Memory', 'Help me build Flow Memory').slice(0, 500),
    instincts: sanitizeStringList(payload.instincts, 10),
    boundaries: sanitizeStringList(payload.boundaries, 12),
    memory_seed: {
      user_preferences: sanitizeStringList(memorySeed.user_preferences, 12),
      project_context: sanitizeStringList(memorySeed.project_context, 12),
      behavior_rules: sanitizeStringList(memorySeed.behavior_rules, 12),
      initial_lessons: sanitizeStringList(memorySeed.initial_lessons, 8),
      raw_private_content: sanitizeString(memorySeed.raw_private_content || '').slice(0, 2000),
    },
    consent_mode: sanitizeString(payload.consent_mode || payload.consent || 'private_only', 'private_only').slice(0, 80),
    launch_immediately: false,
    open_mission_control: true,
  };
}

function runGenesisBirth(payload) {
  const safePayload = sanitizeGenesisBirthPayload(payload);
  const python = process.env.PYTHON || 'python';
  const pythonPath = path.join(projectRoot, 'src');
  const code = [
    'import json, sys',
    'from pathlib import Path',
    'ROOT = Path.cwd()',
    'SRC = ROOT / "src"',
    'if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))',
    'from flow_memory.agent_genesis import birth_agent',
    'payload = json.load(sys.stdin)',
    'print(json.dumps(birth_agent(payload, root=ROOT), sort_keys=True, default=str))',
  ].join('\n');
  const result = spawnSync(python, ['-c', code], {
    cwd: projectRoot,
    input: JSON.stringify(safePayload),
    encoding: 'utf8',
    env: {
      ...process.env,
      PYTHONPATH: process.env.PYTHONPATH ? `${pythonPath}${path.delimiter}${process.env.PYTHONPATH}` : pythonPath,
    },
    maxBuffer: 8 * 1024 * 1024,
    timeout: 20_000,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || `python exited with ${result.status}`).trim());
  }
  return JSON.parse(result.stdout);
}

function runAgentBuilderBirth(payload) {
  const safePayload = sanitizeGenesisBirthPayload(payload);
  const python = process.env.PYTHON || 'python';
  const pythonPath = path.join(projectRoot, 'src');
  const code = [
    'import json, sys',
    'from pathlib import Path',
    'ROOT = Path.cwd()',
    'SRC = ROOT / "src"',
    'if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))',
    'from flow_memory.agent_builder import birth_agent_from_builder',
    'payload = json.load(sys.stdin)',
    'print(json.dumps(birth_agent_from_builder(payload, root=ROOT), sort_keys=True, default=str))',
  ].join('\n');
  const result = spawnSync(python, ['-c', code], {
    cwd: projectRoot,
    input: JSON.stringify(safePayload),
    encoding: 'utf8',
    env: {
      ...process.env,
      PYTHONPATH: process.env.PYTHONPATH ? `${pythonPath}${path.delimiter}${process.env.PYTHONPATH}` : pythonPath,
    },
    maxBuffer: 8 * 1024 * 1024,
    timeout: 20_000,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || `python exited with ${result.status}`).trim());
  }
  return JSON.parse(result.stdout);
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
  const cognitive = Array.isArray(replay?.state?.cognitive) ? replay.state.cognitive[0] : null;
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
      ${cognitive ? `<article class="predictive-cognitive-readout" aria-label="Predictive Cognitive Core"><strong>Predictive Cognitive Core</strong><span>${text(cognitive.chosen_action)} → error ${Number(cognitive.prediction_error || 0).toFixed(2)}</span><small>${text(cognitive.lesson || '')}</small></article>` : ''}
    </section>`;
}
function renderPredictiveCognitionPanel(payload) {
  const tick = payload?.tick || {};
  const state = tick.state || {};
  const prediction = tick.prediction || {};
  const selectedAction = tick.selected_action || {};
  const policy = tick.policy_decision || {};
  const actual = tick.actual_outcome || {};
  const error = tick.prediction_error || {};
  const experience = tick.experience || {};
  const learning = tick.learning_update || {};
  const memories = Array.isArray(tick.retrieved_memories) ? tick.retrieved_memories : [];
  const candidates = Array.isArray(tick.candidate_actions) ? tick.candidate_actions : [];
  const scores = Array.isArray(tick.scores) ? tick.scores : [];
  const scoreByAction = new Map(scores.map((score) => [score.candidate_action_id, score]));
  const counterfactuals = tick.counterfactuals || {};
  const predictions = Array.isArray(counterfactuals.candidate_predictions) ? counterfactuals.candidate_predictions : [];

  const metric = (label, value) => `<div><dt>${text(label)}</dt><dd>${text(value)}</dd></div>`;
  const scoreText = (value) => Number(value || 0).toFixed(2);
  const candidateRows = candidates.slice(0, 4).map((candidate) => {
    const score = scoreByAction.get(candidate.action_id) || {};
    const selected = candidate.action_id === selectedAction.action_id;
    return `
      <li data-selected="${selected}">
        <strong>${text(candidate.description)}</strong>
        <span>${text(candidate.action_type)} · ${text(candidate.expected_domain)}</span>
        <small>score ${scoreText(score.overall_score)} · risk ${scoreText(score.risk_score)}</small>
      </li>`;
  }).join('');
  const predictionRows = predictions.slice(0, 4).map((item) => `
    <li>
      <strong>${text(item.predicted_result)}</strong>
      <span>confidence ${scoreText(item.confidence)} · risk ${scoreText(item.risk)} · reward ${scoreText(item.expected_reward)}</span>
      <small>${text((item.possible_failure_modes || []).slice(0, 3).join(' / '))}</small>
    </li>`).join('');
  const memoryRows = memories.length ? memories.slice(0, 3).map((memory) => `
    <li>
      <strong>${text(memory.experience_id || memory.memory_id || 'memory')}</strong>
      <span>${text(memory.lesson || memory.goal || 'similar local experience')}</span>
    </li>`).join('') : '<li><strong>No prior matching lessons</strong><span>First deterministic local observation for this goal.</span></li>';
  const matched = Number(error.prediction_error || 0) <= 0.25;
  return `
    <section id="cognition" class="predictive-cognition-panel mission-surface mission-surface-wide" aria-label="Predictive Cognition panel">
      <header class="surface-header">
        <span>Predictive Cognition</span>
        <strong>Prediction before action, lesson after outcome</strong>
        <small>Local deterministic world-model replay. Neural outputs stay advisory; PolicyEngine and ApprovalGate remain authoritative.</small>
      </header>
      <div class="cognition-grid">
        <article class="cognition-summary">
          <p class="cognition-state">${text(state.human_readable_summary || 'state encoded')}</p>
          <h2>${text(prediction.predicted_result || 'No prediction loaded')}</h2>
          <dl>
            ${metric('confidence', scoreText(prediction.confidence))}
            ${metric('risk', scoreText(prediction.risk))}
            ${metric('reward', scoreText(prediction.expected_reward))}
            ${metric('prediction error', scoreText(error.prediction_error))}
            ${metric('policy', policy.allowed === false ? 'denied' : 'allowed')}
            ${metric('experience', experience.experience_id || 'not written')}
          </dl>
          <div class="cognition-match" data-matched="${matched}">${matched ? 'prediction matched reality' : 'prediction produced a lesson'}</div>
        </article>
        <article class="cognition-flow">
          <h3>Selected action</h3>
          <p>${text(selectedAction.description || 'No selected action')}</p>
          <h3>Actual outcome</h3>
          <p>${text(actual.reason || (actual.success ? 'served Mission Control panels without placeholder text' : 'observed mismatch'))}</p>
          <h3>Lesson learned</h3>
          <p>${text(error.lesson || experience.lesson || 'No lesson recorded yet')}</p>
          <h3>Learning update</h3>
          <p>${text(learning.mode || 'local_deterministic')} · loss ${scoreText(learning.loss_before)} → ${scoreText(learning.loss_after)}</p>
        </article>
        <article class="cognition-list">
          <h3>Candidate actions</h3>
          <ol>${candidateRows}</ol>
        </article>
        <article class="cognition-list">
          <h3>Counterfactual predictions</h3>
          <ol>${predictionRows}</ol>
        </article>
        <article class="cognition-list cognition-memory">
          <h3>Retrieved memories</h3>
          <ol>${memoryRows}</ol>
        </article>
      </div>
    </section>`;
}

function renderPredictiveLearningPanel(payload) {
  const benchmark = payload?.benchmark || payload || {};
  const metrics = benchmark.metrics || {};
  const scenarios = Array.isArray(benchmark.scenario_results) ? benchmark.scenario_results : [];
  const trials = Array.isArray(benchmark.trial_results) ? benchmark.trial_results : [];
  const lessons = Array.isArray(benchmark.consolidated_lessons) ? benchmark.consolidated_lessons : [];
  const scoreText = (value) => Number(value || 0).toFixed(2);
  const metric = (label, value) => `<div><dt>${text(label)}</dt><dd>${text(value)}</dd></div>`;
  const scenarioRows = scenarios.map((item) => {
    const scenario = item.scenario || {};
    const itemMetrics = item.metrics || {};
    return `
      <li>
        <strong>${text(scenario.title || scenario.scenario_id || 'benchmark scenario')}</strong>
        <span>accuracy ${scoreText(itemMetrics.prediction_accuracy_before)} → ${scoreText(itemMetrics.prediction_accuracy_after)} · error ${scoreText(itemMetrics.prediction_error_mean_before)} → ${scoreText(itemMetrics.prediction_error_mean_after)}</span>
        <small>${text(scenario.correct_lesson || '')}</small>
      </li>`;
  }).join('');
  const trendRows = trials.slice(0, 10).map((trial) => `
    <li style="--accuracy:${Number(trial.match_score || 0)}; --error:${Number(trial.prediction_error || 0)}">
      <strong>${text(trial.scenario_id)} · trial ${text(trial.trial)}</strong>
      <span><i class="trend-accuracy"></i><b>${scoreText(trial.match_score)}</b><i class="trend-error"></i><b>${scoreText(trial.prediction_error)}</b></span>
      <small>${text(trial.lesson_reused ? 'lesson reused before prediction' : 'fresh prediction')}</small>
    </li>`).join('');
  const lessonRows = lessons.slice(0, 4).map((lesson) => `
    <li>
      <strong>${text(lesson.title || lesson.lesson_id)}</strong>
      <span>${text(lesson.recommended_future_action || '')}</span>
      <small>usefulness ${scoreText(lesson.usefulness_score)} · sources ${(lesson.source_experience_ids || []).length}</small>
    </li>`).join('');
  return `
    <section id="learning" class="predictive-learning-panel mission-surface mission-surface-wide" aria-label="Predictive Learning Benchmark panel">
      <header class="surface-header">
        <span>Predictive Learning Benchmark</span>
        <strong>Prediction error drops after lessons consolidate</strong>
        <small>Five deterministic local scenarios repeat the predict → observe → consolidate → reuse loop. Lessons never bypass PolicyEngine or ApprovalGate.</small>
      </header>
      <div class="learning-grid">
        <article class="learning-summary">
          <p class="cognition-state">${text(benchmark.benchmark_id || 'predictive_learning_smoke')}</p>
          <h2>${scoreText(metrics.prediction_accuracy_before)} → ${scoreText(metrics.prediction_accuracy_after)} accuracy</h2>
          <dl>
            ${metric('trials', benchmark.runs || trials.length)}
            ${metric('error mean', `${scoreText(metrics.prediction_error_mean_before)} → ${scoreText(metrics.prediction_error_mean_after)}`)}
            ${metric('lessons consolidated', metrics.consolidated_lesson_count || benchmark.consolidated_lesson_count || lessons.length)}
            ${metric('lesson reuse', scoreText(metrics.lesson_reuse_rate))}
            ${metric('repeated mistakes', scoreText(metrics.repeated_mistake_rate))}
            ${metric('policy overrides', scoreText(metrics.policy_override_rate))}
            ${metric('unsafe recommendations', scoreText(metrics.unsafe_recommendation_rate))}
            ${metric('experiences', metrics.experience_count || trials.length)}
          </dl>
          <div class="cognition-match" data-matched="${Number(metrics.prediction_error_delta || 0) >= 0}">repeated mistakes reduced</div>
        </article>
        <article class="learning-list">
          <h3>Benchmark scenarios</h3>
          <ol>${scenarioRows}</ol>
        </article>
        <article class="learning-list">
          <h3>Accuracy and error trend</h3>
          <ol class="learning-trend">${trendRows}</ol>
        </article>
        <article class="learning-list learning-lessons">
          <h3>Selected lesson details</h3>
          <ol>${lessonRows}</ol>
        </article>
      </div>
    </section>`;
}
function renderAgentGenesisPanel(payload) {
  const summary = payload?.summary || {};
  const birth = payload?.birth || {};
  const prediction = payload?.first_prediction || birth.first_prediction || {};
  const genome = payload?.genome || {};
  const memorySeed = payload?.memory_seed || {};
  const consent = payload?.learning_consent || {};
  const passport = payload?.passport || {};
  const mirror = payload?.mirror || {};
  const archetypes = Array.isArray(payload?.archetypes) ? payload.archetypes : [];
  const instincts = Array.isArray(payload?.instincts) ? payload.instincts : [];
  const boundaries = Array.isArray(payload?.boundaries) ? payload.boundaries : [];
  const contribution = payload?.contribution_status || {};
  const selectedInstincts = Array.isArray(birth.instincts) ? birth.instincts : [];
  const selectedBoundaries = Array.isArray(birth.boundaries) ? birth.boundaries : [];
  const cards = archetypes.slice(0, 4).map((item) => `
    <article>
      <strong>${text(item.display_name || item.archetype_id)}</strong>
      <span>${text(item.description || '')}</span>
      <small>${text((item.default_instincts || []).slice(0, 3).join(' · '))}</small>
    </article>`).join('');
  const instinctRows = instincts.slice(0, 6).map((item) => `
    <li data-active="${selectedInstincts.includes(item.instinct_id)}">
      <strong>${text(item.display_name || item.instinct_id)}</strong>
      <span>${text(item.description || item.instinct_id)}</span>
    </li>`).join('');
  const boundaryRows = boundaries.slice(0, 7).map((item) => `
    <li data-active="${selectedBoundaries.includes(item.boundary_id)}">
      <strong>${text(item.display_name || item.boundary_id)}</strong>
      <span>${text(item.description || item.boundary_id)}</span>
    </li>`).join('');
  const metrics = [
    ['stage', passport.stage || 'seed'],
    ['prediction accuracy', Number(passport.prediction_accuracy || 0).toFixed(2)],
    ['policy compliance', Number(passport.policy_compliance || 0).toFixed(2)],
    ['lessons learned', passport.lessons_learned || 0],
    ['contributions', passport.contributions_made || 0],
    ['benchmarks', passport.benchmarks_passed || 0],
  ].map(([label, value]) => `<div><dt>${text(label)}</dt><dd>${text(value)}</dd></div>`).join('');
  return `
    <section id="genesis" class="agent-genesis-panel mission-surface mission-surface-wide" aria-label="Agent Genesis onboarding panel">
      <header class="surface-header">
        <span>Agent Genesis</span>
        <strong>${text(summary.headline || 'Birth an agent into the network')}</strong>
        <small>${text(summary.description || 'Create a policy-gated agent with instincts, boundaries, private memory seed, first prediction, and opt-in network learning.')}</small>
      </header>
      <div class="genesis-grid">
        <article class="genesis-birth-card">
          <p class="cognition-state">Agent Birth Flow</p>
          <h2>${text(birth.name || 'Mira')}</h2>
          <p>${text(birth.purpose || genome.purpose || 'Help me build and remember Flow Memory')}</p>
          <dl>
            <div><dt>archetype</dt><dd>${text(birth.archetype || genome.archetype_id || 'research-builder')}</dd></div>
            <div><dt>privacy</dt><dd>${text(consent.default_mode || birth?.privacy?.mode || 'private_only')}</dd></div>
            <div><dt>network learning</dt><dd>${text(consent.network_learning_is_opt_in ? 'opt-in only' : 'disabled')}</dd></div>
            <div><dt>raw private payload</dt><dd>${text(consent.raw_private_payload_excluded ? 'excluded' : 'not allowed')}</dd></div>
          </dl>
        </article>
        <article class="genesis-first-prediction">
          <p class="cognition-state">First Prediction</p>
          <h3>${text(prediction.prediction || 'I can map project state before acting.')}</h3>
          <dl>
            <div><dt>confidence</dt><dd>${Number(prediction.confidence || 0).toFixed(2)}</dd></div>
            <div><dt>risk</dt><dd>${Number(prediction.risk || 0).toFixed(2)}</dd></div>
            <div><dt>policy</dt><dd>${text(prediction.policy || 'supervised; approval required')}</dd></div>
          </dl>
          <small>${text(prediction.verification_plan || 'Compare the predicted state to observed first run evidence.')}</small>
        </article>
        <article class="genesis-genome-card">
          <p class="cognition-state">Agent Genome</p>
          <h3>${text(genome.genome_id || birth.genome_id || 'agent-genome-v1')}</h3>
          <p>Portable profile for purpose, instincts, boundaries, cognition, neural runtime, memory, policy, privacy, and contribution settings. Private memory is excluded by default.</p>
          <div class="genesis-chip-row">${selectedInstincts.map((item) => `<span>${text(item)}</span>`).join('')}</div>
        </article>
        <article class="genesis-memory-card">
          <p class="cognition-state">Memory Seed</p>
          <h3>Private starting context</h3>
          <p>${text(memorySeed.summary || 'exact commands, honest status, visible proof')}</p>
          <small>raw private content shared: ${text(memorySeed.raw_private_content_shared ? 'yes' : 'no')}</small>
        </article>
        <article class="genesis-picker">
          <h3>Instinct picker</h3>
          <ol>${instinctRows}</ol>
        </article>
        <article class="genesis-picker">
          <h3>Boundary checklist</h3>
          <ol>${boundaryRows}</ol>
        </article>
        <article class="genesis-passport-card">
          <p class="cognition-state">Agent Passport</p>
          <h3>${text(passport.stage || 'seed')}</h3>
          <dl>${metrics}</dl>
        </article>
        <article class="genesis-mirror-card">
          <p class="cognition-state">Agent Mirror</p>
          <h3>${text(mirror.surprise || 'prediction matched observed first outcome')}</h3>
          <p>${text(mirror.lesson || 'Check observable state before reporting success.')}</p>
          <small>${text(mirror.next_time || 'reuse this verified pattern')}</small>
        </article>
        <article class="genesis-contribution-card">
          <p class="cognition-state">Learning Consent</p>
          <h3>Network learning is opt-in</h3>
          <p>${text(contribution.offer || 'Sanitized lessons can be contributed only after explicit opt-in.')}</p>
          <small>${text(summary.optional_node_path || 'Node download is optional for private tools, private compute, or compute contribution.')}</small>
        </article>
        <article class="genesis-archetypes">
          <h3>Available archetypes</h3>
          <div>${cards}</div>
        </article>
      </div>
    </section>`;
}

function renderProofOfLearningPanel(payload) {
  const summary = payload?.summary || {};
  const graph = payload?.graph || {};
  const metrics = graph.metrics || {};
  const proofLedger = payload?.proof_ledger || {};
  const proofs = Array.isArray(proofLedger.proofs) ? proofLedger.proofs : [];
  const reputation = payload?.reputation || {};
  const reputations = Array.isArray(reputation.reputations) ? reputation.reputations : [];
  const events = Array.isArray(payload?.events) ? payload.events : [];
  const top = reputations[0] || {};
  const artifacts = payload?.artifact_paths || {};
  const scoreText = (value) => Number(value || 0).toFixed(2);
  const metric = (label, value) => `<div><dt>${text(label)}</dt><dd>${text(value)}</dd></div>`;
  const proofRows = proofs.slice(0, 4).map((proof) => `
    <li>
      <strong>${text(proof.lesson_id || proof.proof_id)}</strong>
      <span>error ${scoreText(proof.prediction_error_before)} → ${scoreText(proof.prediction_error_after)} · score ${scoreText(proof.score)}</span>
      <small>${text(proof.agent_id)} · private payload excluded</small>
    </li>`).join('');
  const reputationRows = reputations.slice(0, 4).map((item) => `
    <li>
      <strong>${text(item.agent_id)}</strong>
      <span>accuracy ${scoreText(item.prediction_accuracy)} · policy ${scoreText(item.policy_compliance)} · reputation ${scoreText(item.reputation_score)}</span>
      <small>${text(item.proof_count)} proof records · safety authority ${text(item.safety_authority || 'policy_engine_and_approval_gate')}</small>
    </li>`).join('');
  const eventRows = events.slice(0, 5).map((event) => `
    <li>
      <strong>${text(event.payload?.event || event.event_type || 'graph event')}</strong>
      <span>${text(event.payload?.summary || event.run_id || event.event_id || '')}</span>
    </li>`).join('');
  return `
    <section id="proof" class="proof-learning-panel mission-surface mission-surface-wide" aria-label="Proof of Learning and Experience Graph panel">
      <header class="surface-header">
        <span>Proof of Learning</span>
        <strong>${text(summary.headline || 'Every prediction becomes experience')}</strong>
        <small>Experience Graph connects agents, goals, predictions, actions, outcomes, prediction errors, lessons, policy gates, contributions, and reputation. Private payloads are excluded.</small>
      </header>
      <div class="proof-learning-grid">
        <article class="proof-learning-summary">
          <p class="cognition-state">Experience Graph</p>
          <h2>${text(summary.graph_loop || 'agent → predicted → acted → observed → learned → reused → improved')}</h2>
          <dl>
            ${metric('nodes', metrics.node_count || summary.node_count || 0)}
            ${metric('edges', metrics.edge_count || summary.edge_count || 0)}
            ${metric('proof records', proofLedger.proof_count || summary.proof_count || proofs.length)}
            ${metric('agents', reputation.agent_count || summary.agent_count || reputations.length)}
            ${metric('top agent', top.agent_id || summary.top_agent || 'network')}
            ${metric('private payload', payload?.private_payload_excluded ? 'excluded' : 'not shared')}
          </dl>
          <div class="cognition-match" data-matched="${payload?.private_payload_excluded === true}">private payload excluded</div>
        </article>
        <article class="proof-learning-ledger">
          <h3>Proof ledger</h3>
          <ol>${proofRows}</ol>
        </article>
        <article class="proof-learning-reputation">
          <h3>Learning reputation</h3>
          <ol>${reputationRows}</ol>
        </article>
        <article class="proof-learning-events">
          <h3>Visual graph events</h3>
          <ol>${eventRows}</ol>
        </article>
        <article class="proof-learning-artifacts">
          <h3>Artifact paths</h3>
          <p>${text(artifacts.graphs || 'artifacts/experience_graph/graphs/')}</p>
          <p>${text(artifacts.proofs || 'artifacts/experience_graph/proofs/')}</p>
          <p>${text(artifacts.reputation || 'artifacts/experience_graph/reputation/')}</p>
          <small>PolicyEngine and ApprovalGate remain authoritative. This ledger does not grant autonomous control.</small>
        </article>
      </div>
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

function renderInteractive3DHero(payload) {
  const embodiment = payload?.embodiment || {};
  const gpuStatus = embodiment.gpu_evidence_status || 'verified';
  const phase = embodiment.current_loop_phase || 'observed';
  const stories = [
    {
      mode: 'swarm',
      visual: 'Signal field',
      title: 'Signals appear',
      copy: 'Human work enters as separate fibers with direction, weight, and provenance.',
    },
    {
      mode: 'contact',
      visual: 'Neural braid',
      title: 'Fibers converge',
      copy: 'The strands pull into a shared proof knot instead of orbiting a single toy object.',
    },
    {
      mode: 'manim',
      visual: 'Memory loom',
      title: 'Memory is woven',
      copy: 'Verified strands settle into a replayable weave operators can inspect later.',
    },
  ];
  const steps = stories.map((story, index) => `
          <li>
            <button type="button" data-3d-mode="${story.mode}" data-active="${index === 0}" data-story-title="${text(story.title)}" data-story-copy="${text(story.copy)}" data-story-label="${text(story.visual)}">
              <span>${text(story.visual)}</span>
              <strong>${text(story.title)}</strong>
            </button>
          </li>`).join('');
  return `
    <aside class="mission-3d-visualizer" aria-label="Interactive Flow Memory neural loom visualization">
      <div class="mission-3d-canvas-frame" data-3d-ready="pending" data-story-mode="swarm" data-neural-strands="loom">
        <canvas id="mission-3d-canvas" aria-label="Interactive neural loom. Drag to rotate and scroll to zoom."></canvas>
        <div class="mission-3d-fallback">Loading neural loom</div>
        <div class="mission-3d-overlay">
          <strong>Neural memory field</strong>
          <span>Replay trace · proof mesh · memory knot</span>
        </div>
        <div class="mission-3d-status">
          <span>GPU evidence ${text(gpuStatus)}</span>
          <span>Phase ${text(phase)}</span>
        </div>
        <div class="mission-3d-story-readout" aria-live="polite">
          <span data-story-label>${text(stories[0].visual)}</span>
          <strong data-story-title>${text(stories[0].title)}</strong>
          <p data-story-copy>${text(stories[0].copy)}</p>
        </div>
        <div class="mission-3d-callout mission-3d-callout-source">Human signal fibers</div>
        <div class="mission-3d-callout mission-3d-callout-proof">Proof knot tension</div>
        <div class="mission-3d-callout mission-3d-callout-weave">Neural braid forming</div>
        <div class="mission-3d-callout mission-3d-callout-memory">Memory weave</div>
        <ol class="mission-story-steps mission-loom-rail" aria-label="Neural loom story controls">${steps}
        </ol>
      </div>
      <p class="mission-3d-caption">A calmer neural strand visualization: separate work fibers braid into proof, then resolve into durable Flow Memory.</p>
    </aside>`;
}


function renderActionFooter() {
  return `
    <section class="mission-action-footer" aria-label="Mission Control action">
      <div>
        <h2>Review the launch handoff with proof in view.</h2>
        <p data-motion="scrub-text">The dashboard is intentionally read-only: replay/mock mode works offline, local API mode is optional, and unsafe write/control routes stay out of the frontend.</p>
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
function renderReferenceStatusBar() {
  return `
    <footer class="fm-status-bar" aria-label="Local Mission Control status">
      <span><i class="fm-dot"></i>Connected</span>
      <span><i class="fm-globe"></i>Region <strong>US East</strong></span>
      <span><i class="fm-code"></i>Version <strong>v0.9.4-alpha</strong></span>
    </footer>`;
}

function renderReferenceIcon(kind) {
  return `<span class="fm-icon fm-icon-${className(kind)}" aria-hidden="true"><i></i></span>`;
}

function renderHeroHighlights() {
  const cards = [
    ['play', 'Replay lane', 'Step through the run timeline without changing live state.'],
    ['shield', 'Proof lane', 'Keep receipts, GPU evidence, and policy gates visible.'],
    ['brain', 'Memory lane', 'Watch agent strands attach to the shared field over time.'],
  ];
  return `<div class="fm-hero-highlights">${cards.map(([kind, title, copy]) => `
    <article>
      ${renderReferenceIcon(kind)}
      <strong>${text(title)}</strong>
      <p>${text(copy)}</p>
    </article>`).join('')}</div>`;
}

function renderMissionCommandDeck(state, embodimentPayload, finalizer) {
  const embodiment = embodimentPayload?.embodiment || {};
  const agents = state?.runtime?.agents || state?.agents?.length || 12;
  const memories = state?.runtime?.memories || state?.memory?.length || embodiment.memory_activation_count || 18;
  const events = Array.isArray(state?.events) ? state.events.length : embodiment.visual_events_emitted || 64;
  const proofState = finalizer?.ok ? 'ready' : 'review';
  const metrics = [
    ['Live agents', agents, 'agent strands can attach to the top field'],
    ['Memory signals', memories, 'private payload stays outside the shared graph'],
    ['Visual events', events, 'compact replay state feeds the page'],
    ['Launch gate', proofState, 'public-alpha evidence remains explicit'],
  ];
  const lanes = [
    ['Agent creation', 'Genesis and Agent Builder emit a new local strand before any network publishing.'],
    ['Policy and proof', 'ApprovalGate, PolicyEngine, GPU evidence, and receipts stay in the operator path.'],
    ['Learning loop', 'Prediction error, lessons, and proof-of-learning update the memory field.'],
  ];
  return `
    <section class="mission-command-deck mission-surface mission-surface-wide" aria-label="Mission Control operating deck">
      <div class="mission-command-copy">
        <span>Operating Deck</span>
        <h2>One page for agents, memory, proof, and live visualization.</h2>
        <p>The redesign keeps the dashboard read-only while making the neural map the primary spatial surface. Agent creation, replay, proof, and learning panels now read as one connected system.</p>
      </div>
      <div class="mission-command-metrics" aria-label="Mission Control metrics">
        ${metrics.map(([label, value, detail], index) => `
          <article style="--metric-index:${index}">
            <small>${text(label)}</small>
            <strong>${text(value)}</strong>
            <span>${text(detail)}</span>
          </article>`).join('')}
      </div>
      <div class="mission-command-lanes">
        ${lanes.map(([label, copy], index) => `
          <article style="--lane-index:${index}">
            <i aria-hidden="true"></i>
            <strong>${text(label)}</strong>
            <p>${text(copy)}</p>
          </article>`).join('')}
      </div>
    </section>`;
}

function renderTopNeuralMemoryField(state, payload) {
  const embodiment = payload?.embodiment || {};
  const agentCount = state?.runtime?.agents || state?.agents?.length || 4;
  const memoryCount = state?.runtime?.memories || state?.memory?.length || 12;
  const columns = [
    ['Agent intake', 'new agent births'],
    ['Memory seed', 'private context'],
    ['Policy gate', 'approval rails'],
    ['Proof trace', 'verifiable work'],
    ['Learning loop', 'prediction delta'],
    ['Shared field', 'visible strands'],
  ];
  const paths = [
    'M34 176 C176 44 256 224 410 92 S690 48 820 146 S996 196 1070 78',
    'M36 104 C164 138 258 80 388 150 S636 224 784 90 S950 40 1068 132',
    'M42 214 C188 196 258 132 418 186 S620 76 800 118 S946 202 1060 188',
    'M32 62 C182 98 270 40 420 72 S646 170 798 52 S942 112 1064 54',
    'M48 148 C180 228 278 178 404 126 S646 126 812 208 S960 140 1074 166',
  ];
  const selectedPath = 'M40 190 C196 176 268 136 410 146 S650 90 794 118 S950 102 1072 104';
  return `
    <section id="neural-memory-field" class="fm-top-memory-field mission-surface mission-surface-wide" aria-label="Neural memory field">
      <div class="fm-top-memory-copy">
        <span>Neural Memory Field</span>
        <h2>Every agent attaches to the network as a living strand.</h2>
        <p>New agent births, memory seeds, proofs, and learning updates can stream into the top field first, then expand into the detailed Live 3D map.</p>
      </div>
      <div class="fm-top-memory-map" aria-hidden="true">
        <svg class="fm-top-memory-strands" viewBox="0 0 1100 260" preserveAspectRatio="none">
          ${paths.map((path, index) => `<path class="fm-top-memory-path fm-top-memory-path-${index}" d="${path}" />`).join('')}
          <path class="fm-top-memory-path fm-top-memory-path-selected" d="${selectedPath}" />
        </svg>
        <div class="fm-top-memory-columns">
          ${columns.map(([label, detail], columnIndex) => `
            <article>
              <strong>${text(label)}</strong>
              <small>${text(detail)}</small>
              <div>${Array.from({ length: 6 }, (_, nodeIndex) => `<i style="--node-index:${nodeIndex}; --column-index:${columnIndex}"></i>`).join('')}</div>
            </article>`).join('')}
        </div>
      </div>
      <aside class="fm-top-memory-readout">
        <div><span>Agents</span><strong>${text(agentCount)}</strong></div>
        <div><span>Memory signals</span><strong>${text(memoryCount)}</strong></div>
        <div><span>GPU</span><strong>${text(embodiment.gpu_evidence_status || 'verified')}</strong></div>
        <div><span>New strands</span><strong data-agent-strand-count>ready</strong></div>
        <div class="fm-top-memory-feed" data-agent-strand-feed></div>
      </aside>
    </section>`;
}

function renderAgentStrandVisual(options = {}) {
  const variant = className(options.variant || 'default');
  const title = options.title || 'Every new agent becomes a strand';
  const copy = options.copy || 'Agent birth, memory seed, policy gate, and verified work can attach to the shared neural field.';
  const live = options.live === false ? '' : ' data-live-agent-strands="true"';
  const labels = options.labels || ['Agent born', 'Memory seed', 'Policy gate', 'Neural field'];
  return `
    <div class="fm-agent-strand-visual fm-agent-strand-${variant}"${live} aria-label="${text(title)}">
      <div class="fm-agent-strand-copy">
        <span>Agent strand bridge</span>
        <strong>${text(title)}</strong>
        <p>${text(copy)}</p>
      </div>
      <div class="fm-agent-strand-stage" aria-hidden="true">
        <i class="fm-agent-strand-node fm-agent-strand-node-a"></i>
        <i class="fm-agent-strand-node fm-agent-strand-node-b"></i>
        <i class="fm-agent-strand-node fm-agent-strand-node-c"></i>
        <i class="fm-agent-strand-node fm-agent-strand-node-d"></i>
        <b class="fm-agent-strand-line fm-agent-strand-line-a"></b>
        <b class="fm-agent-strand-line fm-agent-strand-line-b"></b>
        <b class="fm-agent-strand-line fm-agent-strand-line-c"></b>
        <em class="fm-agent-strand-pulse fm-agent-strand-pulse-a"></em>
        <em class="fm-agent-strand-pulse fm-agent-strand-pulse-b"></em>
      </div>
      <ol>
        ${labels.map((label) => `<li>${text(label)}</li>`).join('')}
      </ol>
      <div class="fm-agent-strand-feed" data-agent-strand-feed></div>
    </div>`;
}

function renderTouchDesignerIdeaLab() {
  const ideas = [
    {
      variant: 'birth',
      label: 'Agent birth wake',
      title: 'New agents enter as a warm strand.',
      copy: 'When an agent is created, a gold-white trail can travel from intake into the shared neural memory field.',
      metrics: ['agent_created', 'genome_seeded', 'memory_attached'],
      paths: ['M18 130 C130 20 226 178 346 66 S520 78 600 124', 'M30 166 C146 118 250 206 374 118 S516 38 610 82'],
    },
    {
      variant: 'policy',
      label: 'Policy lens',
      title: 'Risk bends the strands before approval.',
      copy: 'Approval gates can appear as glass rings that compress or redirect the active path instead of stopping the whole visual.',
      metrics: ['risk_score', 'approval_state', 'authority'],
      paths: ['M20 102 C150 96 214 128 314 112 S496 78 608 108', 'M20 156 C126 132 214 166 320 146 S486 174 610 138'],
    },
    {
      variant: 'proof',
      label: 'Proof weave',
      title: 'Evidence becomes a floor lattice.',
      copy: 'Receipts, hashes, and verification status can settle into a lower grid while active inference stays above it.',
      metrics: ['receipt_root', 'proof_count', 'verified'],
      paths: ['M18 88 C140 132 234 72 358 112 S496 160 612 104', 'M24 188 C152 152 254 198 370 156 S502 94 610 136'],
    },
    {
      variant: 'learning',
      label: 'Learning terrain',
      title: 'Prediction error turns into contour lines.',
      copy: 'Repeated lessons can lower a terrain ridge over time, making improvement visible without exposing raw private memory.',
      metrics: ['prediction_delta', 'lesson_saved', 'reuse_count'],
      paths: ['M18 158 C110 62 178 190 286 90 S482 176 610 78', 'M18 194 C120 144 190 226 306 154 S504 116 610 164'],
    },
    {
      variant: 'collab',
      label: 'Collaboration constellation',
      title: 'Agents form shared work constellations.',
      copy: 'Public skill links can arc between agents while private memory stays local and off the shared graph.',
      metrics: ['skill_match', 'workspace', 'private_excluded'],
      paths: ['M20 128 C124 72 222 90 316 136 S490 210 604 116', 'M26 84 C142 190 232 30 344 118 S494 42 612 170'],
    },
  ];
  const cards = ideas.map((idea, index) => `
    <article class="fm-td-idea-card fm-td-idea-${idea.variant}" style="--idea-index:${index}">
      <div class="fm-td-idea-visual" aria-hidden="true">
        <svg viewBox="0 0 640 250" preserveAspectRatio="none">
          ${idea.paths.map((path, pathIndex) => `<path class="fm-td-idea-path fm-td-idea-path-${pathIndex}" d="${path}" />`).join('')}
          <path class="fm-td-idea-selected" d="${idea.paths[0]}" />
        </svg>
        <div class="fm-td-idea-columns">
          ${Array.from({ length: 5 }, (_, columnIndex) => `<span>${Array.from({ length: 5 }, (_, nodeIndex) => `<i style="--node-index:${nodeIndex}; --column-index:${columnIndex}"></i>`).join('')}</span>`).join('')}
        </div>
        <b class="fm-td-idea-pulse"></b>
      </div>
      <div class="fm-td-idea-copy">
        <span>${text(idea.label)}</span>
        <h3>${text(idea.title)}</h3>
        <p>${text(idea.copy)}</p>
      </div>
      <footer>${idea.metrics.map((metric) => `<code>${text(metric)}</code>`).join('')}</footer>
    </article>`).join('');
  return `
    <section id="touchdesigner-ideas" class="fm-section fm-td-ideas-section mission-surface mission-surface-wide" aria-label="TouchDesigner visual ideas">
      <div class="fm-td-ideas-head">
        <div class="fm-section-heading">
          <span>TouchDesigner Ideas Lab</span>
          <h2>More visual systems for the AI network.</h2>
          <p>These are lightweight concept prototypes for future TouchDesigner scenes: every one can be driven by compact agent, memory, policy, proof, and learning events.</p>
        </div>
        <aside class="fm-td-bridge-card">
          <strong>Live-data route</strong>
          <ol>
            <li>Agent event</li>
            <li>Compact strand state</li>
            <li>Top neural field</li>
            <li>Live 3D detail</li>
          </ol>
        </aside>
      </div>
      <div class="fm-td-idea-grid">${cards}</div>
      <p class="fm-hidden-proof">TouchDesigner Ideas Lab / agent birth wake / policy lens / proof weave / learning terrain / collaboration constellation / compact event state only / no raw private memory</p>
    </section>`;
}

function renderReferenceRunSelector(payloads) {
  const runCards = [
    ['rocket', 'Live Neural Agent Launch', 'See how an agent starts, remembers, and acts.', 'live-neural-agent-launch'],
    ['book', 'Proof of Learning', 'See how a prediction becomes reusable experience.', 'experience-graph-proof-of-learning'],
    ['sprout', 'Agent Genesis', 'Create and launch a supervised agent.', 'agent-genesis-onboarding'],
    ['network', 'Agent Internet', 'Find collaborators by skills, policy, reputation, and dry-run rails.', 'agent-internet-skill-network'],
    ['shield', 'BYOK + Upgrades', 'Bind model-key refs, wallet identity, and dry-run upgrade intents after Genesis.', 'byok-onchain-upgrades'],
    ['spark', 'Flow Memory Agent Builder', 'Birth an agent in the browser and compose optional capabilities.', 'agent-builder'],
    ['network', 'Local Network Replay', 'Replay a complete run step by step.', 'local-network-replay'],
    ['trend', 'Predictive Learning', 'See how the agent improves over repeated trials.', 'predictive-learning-benchmark'],
    ['pulse', 'Live Agent Operations', 'Inspect live run operations and safe stop state.', 'live-agent-operations'],
    ['shield', 'Live Agent Supervisor', 'Review bounded supervised ticks and heartbeat.', 'live-agent-supervisor'],
  ];
  const cards = runCards.map(([kind, title, copy, fixture]) => {
    const loaded = Boolean(payloads[fixture]);
    return `
      <article class="fm-run-card">
        ${renderReferenceIcon(kind)}
        <h3>${text(title)}</h3>
        <p>${text(copy)}</p>
        <div><span class="fm-ready"><i></i>${loaded ? 'Ready' : 'Replay'}</span><a href="#${fixture === 'local-network-replay' ? 'replay' : fixture === 'agent-genesis-onboarding' ? 'genesis' : fixture === 'agent-internet-skill-network' ? 'internet' : fixture === 'byok-onchain-upgrades' ? 'upgrades' : fixture === 'agent-builder' ? 'agent-builder' : fixture === 'predictive-learning-benchmark' ? 'learning' : fixture === 'experience-graph-proof-of-learning' ? 'proof' : 'live-3d'}">Open</a></div>
      </article>`;
  }).join('');
  return `
    <section id="runs" class="fm-section fm-run-selector mission-surface mission-surface-wide" aria-label="Mission Control run selector">
      <div class="fm-section-heading">
        <span>Mission Control Run Selector</span>
        <h2>Choose a run to explore</h2>
        <p>Pick a FlowMemory experience to inspect in plain English.</p>
      </div>
      <div class="fm-run-toolbar" aria-label="Run selector filters">
        <nav>
          <a class="is-active" href="#runs">${renderReferenceIcon('live')}Live</a>
          <a href="#replay">${renderReferenceIcon('play')}Replay</a>
          <a href="#learning">${renderReferenceIcon('brain')}Learning</a>
          <a href="#proof">${renderReferenceIcon('shield')}Proof</a>
          <a href="#genesis">${renderReferenceIcon('spark')}Creation</a>
          <a href="#internet">${renderReferenceIcon('network')}Internet</a>
          <a href="#upgrades">${renderReferenceIcon('shield')}Upgrades</a>
        </nav>
        <div class="fm-search">Search runs...</div>
        <div class="fm-filter">Ready</div>
      </div>
      <div class="fm-run-layout">
        <div class="fm-run-grid">${cards}</div>
        <aside class="fm-side-card fm-what-you-see">
          <h3>What you’ll see</h3>
          <ul>
            <li>${renderReferenceIcon('play')}<span><strong>Replay</strong><small>Walk through every step with full context.</small></span></li>
            <li>${renderReferenceIcon('layers')}<span><strong>Evidence</strong><small>Inspect memory, traces, and supporting signals.</small></span></li>
            <li>${renderReferenceIcon('brain')}<span><strong>Learning</strong><small>See what changed and why it matters.</small></span></li>
          </ul>
          <div class="fm-mini-network" aria-hidden="true"><i></i><i></i><i></i><i></i><b></b></div>
          ${renderAgentStrandVisual({
            variant: 'runs',
            title: 'Runs feed the neural map above',
            copy: 'Every supervised run can become a visible strand tied to the agent, memory, proof, and output it changed.',
            labels: ['Run', 'Agent', 'Memory', 'Neural map'],
          })}
        </aside>
      </div>
      ${renderReferenceStatusBar()}
    </section>`;
}

function renderReferenceReplaySummary(payloads) {
  const replay = payloads['local-network-replay'] || {};
  const events = eventsFrom(replay);
  return `
    <section id="replay" class="fm-section fm-replay-section mission-surface" aria-label="Mission Control replay controls">
      <div class="fm-section-heading">
        <span>Local Network Replay</span>
        <h2>Replay the agent’s <em>work</em></h2>
        <p>Watch what happened during a run, step by step.</p>
        <p class="fm-hidden-proof">Replay the agent’s work</p>
      </div>
      <div class="fm-replay-layout">
        <aside class="fm-replay-controls">
          <div class="fm-control-buttons">
            <button type="button" class="is-primary">Play</button>
            <button type="button">Pause</button>
            <button type="button">Restart</button>
          </div>
          <label>Speed <strong>1.0x</strong></label>
          <div class="fm-slider"><i></i></div>
          <div class="fm-time"><span>01:24</span><span>04:38</span></div>
          <article>
            <h3>Replay summary</h3>
            <dl>
              <div><dt>Events</dt><dd>${text(events.length || 24)}</dd></div>
              <div><dt>Agents</dt><dd>2</dd></div>
              <div><dt>Duration</dt><dd>04:38</dd></div>
              <div><dt>Outcome</dt><dd>Success</dd></div>
            </dl>
          </article>
        </aside>
        <article class="fm-timeline-board">
          <div class="fm-timeline-head"><span>1</span><span>2</span><span>3</span><span>4</span><span>5</span></div>
          ${[
            ['User Request', 'Request received', 'Clarify request', '', '', ''],
            ['Agent Work', 'Plan created', 'Tool used', 'Process data', 'Generate answer', ''],
            ['Memory', 'Search memory', 'Memory found', 'Memory saved', '', ''],
            ['Safety Check', 'Check input', 'Check tools', 'Check output', 'All clear', ''],
            ['Result', '', '', '', '', 'Answer delivered'],
          ].map((row, index) => `
            <div class="fm-timeline-row" data-row="${index}">
              <strong>${text(row[0])}</strong>
              ${row.slice(1).map((item) => item ? `<span data-active="${item === 'Memory saved'}">${text(item)}</span>` : '<span class="is-empty">—</span>').join('')}
            </div>`).join('')}
          <footer><span>Advanced logs available</span><a href="#proof">View details</a></footer>
        </article>
        <aside class="fm-side-card fm-event-detail">
          <h3>What happened here</h3>
          ${renderReferenceIcon('brain')}
          <h4>The agent saved a new memory.</h4>
          <p>This memory can be reused in future runs.</p>
          <dl>
            <div><dt>Time</dt><dd>01:24</dd></div>
            <div><dt>Type</dt><dd>Memory</dd></div>
            <div><dt>Status</dt><dd><span class="fm-ready"><i></i>Success</span></dd></div>
          </dl>
        </aside>
      </div>
      <p class="fm-hidden-proof">Predictive Cognitive Core</p>
      ${renderReferenceStatusBar()}
    </section>`;
}

function renderReferenceCognitionPanel(payload) {
  const tick = payload?.tick || {};
  const prediction = tick.prediction || {};
  const selectedAction = tick.selected_action || {};
  const error = tick.prediction_error || {};
  return `
    <section id="cognition" class="fm-section fm-cognition-section predictive-cognition-panel mission-surface mission-surface-wide" aria-label="Predictive Cognition panel">
      <div class="fm-section-heading">
        <span>Predictive Cognition · Transparent reasoning</span>
        <h2>How the agent decided</h2>
        <p>See how the agent remembered, predicted, acted, and learned.</p>
      </div>
      <div class="fm-cognition-layout">
        <article class="fm-reasoning-flow">
          ${['Remember', 'Predict', 'Act', 'Learn'].map((label, index) => `
            <div>
              ${renderReferenceIcon(['memory', 'predict', 'act', 'learn'][index])}
              <strong>${label}</strong>
              <span>${['Recall relevant memories', 'Estimate outcomes and confidence', 'Choose the best action', 'Update knowledge and memory'][index]}</span>
            </div>`).join('')}
        </article>
        <aside class="fm-side-card fm-outcome-card">
          <h3>Outcome</h3>
          <ul>
            <li>${renderReferenceIcon('check')}<span><strong>Success</strong><small>Success</small></span></li>
            <li>${renderReferenceIcon('light')}<span><strong>Lesson learned</strong><small>${text(error.lesson || 'Hybrid recall worked better than expected.')}</small></span></li>
            <li>${renderReferenceIcon('database')}<span><strong>Memory updated</strong><small>Yes</small></span></li>
          </ul>
          <div class="fm-outcome-metrics">
            <span>Confidence <strong>High</strong></span>
            <span>Risk <strong>Low</strong></span>
            <span>Expected reward <strong>Strong</strong></span>
          </div>
        </aside>
        <article class="fm-detail-card"><h3>What it remembered</h3><ul><li>User prefers concise answers.</li><li>Hybrid recall improved accuracy in similar tasks.</li><li>Recent runs succeeded with citation-backed responses.</li></ul></article>
        <article class="fm-detail-card"><h3>What it predicted</h3><p>${text(prediction.predicted_result || 'Hybrid recall will improve answer accuracy and user satisfaction.')}</p><div class="fm-progress"><i style="width:88%"></i></div><small>Confidence 88%</small></article>
        <article class="fm-detail-card fm-choice-card"><h3>What it chose</h3><div>${renderReferenceIcon('check')}<span><strong>${text(selectedAction.description || 'Use hybrid recall')}</strong><small>Combine vector search and key memory recall.</small></span></div></article>
      </div>
      <p class="fm-hidden-proof">Counterfactual predictions · prediction matched reality · PolicyEngine and ApprovalGate remain authoritative</p>
      ${renderReferenceStatusBar()}
    </section>`;
}

function renderReferenceLearningPanel(payload) {
  const benchmark = payload?.benchmark || payload || {};
  const metrics = benchmark.metrics || {};
  const before = Math.round(Number(metrics.prediction_accuracy_before || 0.62) * 100);
  const after = Math.round(Number(metrics.prediction_accuracy_after || 0.91) * 100);
  return `
    <section id="learning" class="fm-section fm-learning-section predictive-learning-panel mission-surface mission-surface-wide" aria-label="Predictive Learning Benchmark panel">
      <div class="fm-learning-hero">
        <div class="fm-section-heading">
          <span>Learning Benchmark · Predictive Learning Benchmark</span>
          <h2>Learning over time</h2>
          <p>See whether the agent is getting better with experience.</p>
        </div>
        <article class="fm-accuracy-banner">
          <span>Accuracy improved from</span>
          <strong>${before}% <i></i> ${after}%</strong>
          <svg viewBox="0 0 240 80" aria-hidden="true"><path d="M8 46 C 60 24, 86 64, 138 35 S 198 20, 232 42" /></svg>
        </article>
      </div>
      <div class="fm-chart-grid">
        <article><h3>Accuracy went up</h3><div class="fm-chart up"></div></article>
        <article><h3>Errors went down</h3><div class="fm-chart down"></div></article>
        <article><h3>Lessons were reused</h3><div class="fm-chart reuse"></div></article>
      </div>
      <div class="fm-learning-bottom">
        <article class="fm-scenario-card"><span>Benchmark scenarios</span><h3>Warehouse fulfillment planning</h3><p>The agent plans and adapts fulfillment tasks in a dynamic warehouse while respecting constraints and safety rules.</p><div><small>Dynamic inventory</small><small>Routing constraints</small><small>Safety rules</small><small>Service goals</small></div></article>
        <article class="fm-metric-strip">
          <div><strong>50</strong><span>Trials completed</span></div>
          <div><strong>1,240</strong><span>Lessons consolidated</span></div>
          <div><strong>82%</strong><span>Fewer repeated mistakes</span></div>
          <div><strong>156</strong><span>Unsafe recommendations avoided</span></div>
        </article>
      </div>
      <p class="fm-hidden-proof">Prediction error drops after lessons consolidate · Accuracy and error trend · Selected lesson details · repeated mistakes reduced · Lessons never bypass PolicyEngine or ApprovalGate</p>
      ${renderReferenceStatusBar()}
    </section>`;
}

function renderReferenceAgentBuilderPanel(payload) {
  const plan = payload?.assembly_plan || {};
  const capabilities = Array.isArray(payload?.capability_composer) ? payload.capability_composer : [];
  const recommendations = Array.isArray(payload?.agent_internet?.sample_recommendations) ? payload.agent_internet.sample_recommendations : [];
  const optional = payload?.optional_upgrades || {};
  const capabilityCards = capabilities.map((card) => `
    <article class="fm-agent-builder-capability-card" data-state="${text(card.default_state || 'off')}">
      <div>${renderReferenceIcon(card.capability_id === 'byok_model_key' ? 'key' : card.capability_id === 'wallet_identity' ? 'shield' : card.capability_id === 'skill_matcher' ? 'network' : card.capability_id === 'x402_dry_run_route' ? 'route' : 'spark')}</div>
      <strong>${text(card.label)}</strong>
      <span>${text(card.status)}</span>
      <p>${text(card.safety_note)}</p>
      <dl>
        <div><dt>optional</dt><dd>${card.optional ? 'yes' : 'default'}</dd></div>
        <div><dt>approval</dt><dd>${card.requires_approval ? 'required' : 'not required'}</dd></div>
        <div><dt>wallet/key</dt><dd>${card.requires_wallet ? 'wallet' : card.requires_api_key ? 'API key ref' : 'none'}</dd></div>
        <div><dt>mode</dt><dd>${card.dry_run_only ? 'dry-run only' : 'local'}</dd></div>
      </dl>
    </article>`).join('');
  const collaboratorCards = recommendations.map((item) => `
    <article>
      ${renderReferenceIcon('network')}
      <strong>${text(item.display_name || item.agent_id)}</strong>
      <p>${text((item.skills || []).join(', ') || 'policy-gated skills')}</p>
      <span>score ${text(item.score || '0.80')}</span>
    </article>`).join('');
  return `
    <section id="agent-builder" class="fm-section fm-agent-builder-section mission-surface mission-surface-wide" aria-label="Flow Memory Agent Builder browser agent builder">
      <div class="fm-agent-builder-hero">
        <div class="fm-section-heading">
          <span>Flow Memory Agent Builder · Browser Agent Builder</span>
          <h2>Create your first Flow Memory agent.</h2>
          <p>Birth an agent with purpose, instincts, boundaries, memory seed, and a first prediction. The first path stays no wallet/API key/funds required.</p>
        </div>
        <aside class="fm-agent-builder-mode-card">
          <div class="fm-mode-switch" aria-label="Agent Builder modes"><span class="is-active">Simple mode</span><span>Advanced mode</span></div>
          <p><strong>Simple is default.</strong> Private by default, supervised, local runtime, no provider calls, no on-chain registration.</p>
          <p><strong>Advanced is optional.</strong> Add BYOK references, Agent Internet identity, wallet identity, dry-run on-chain and x402 routes after the agent exists.</p>
        </aside>
      </div>
      <div class="fm-agent-builder-layout">
        <form id="flow-memory-agent-builder-form" class="fm-agent-builder-builder" data-endpoint="/agent-builder/birth" data-agent-builder-birth-form>
          <input type="hidden" name="user_id" value="dashboard-user" />
          <fieldset>
            <legend>Agent basics</legend>
            <label><span>Agent name</span><input name="agent_name" value="${text(plan.agent_name || 'Mira')}" maxlength="80" required /><small>This becomes the passport name.</small></label>
            <label><span>Purpose</span><textarea name="purpose" rows="4" maxlength="500" required>${text(plan.purpose || 'Help me build, remember, and verify Flow Memory work.')}</textarea><small>The first prediction and genome are shaped by this purpose.</small></label>
            <label><span>Archetype</span><select name="archetype_id"><option value="research-builder" selected>Research Builder</option><option value="memory-scout">Memory Scout</option><option value="launch-assistant">Launch Assistant</option><option value="teacher-agent">Teacher Agent</option></select><small>Archetypes define safe defaults, not autonomy.</small></label>
          </fieldset>
          <fieldset>
            <legend>Instincts and boundaries</legend>
            <div class="fm-agent-builder-chip-row">
              ${['careful', 'builder', 'memory_first', 'verifier', 'cost_aware', 'teacher'].map((item, index) => `<label><input type="checkbox" name="instincts" value="${item}" ${index < 4 ? 'checked' : ''} /><span>${text(item.replace(/_/g, ' '))}</span></label>`).join('')}
            </div>
            <div class="fm-agent-builder-check-row">
              ${['ask_before_risky_action', 'never_spend_money', 'never_delete_without_approval', 'never_share_private_memory', 'local_only_by_default', 'no_live_settlement'].map((item, index) => `<label><input type="checkbox" name="boundaries" value="${item}" ${index < 5 ? 'checked' : ''} /><span>${text(item.replace(/_/g, ' '))}</span></label>`).join('')}
            </div>
          </fieldset>
          <fieldset>
            <legend>Memory seed and consent</legend>
            <label><span>User preferences</span><textarea name="user_preferences" rows="3">exact commands
honest status
visible proof</textarea></label>
            <label><span>Project context</span><textarea name="project_context" rows="3">Flow Memory is the Human Compute Network
Mission Control shows proof and learning</textarea></label>
            <label><span>Behavior rules</span><textarea name="behavior_rules" rows="3">do not overclaim
ask before risky actions
verify observable outcomes</textarea></label>
            <div class="fm-agent-builder-consent">
              <label><input type="radio" name="consent_mode" value="private_only" checked /><span>Private only</span></label>
              <label><input type="radio" name="consent_mode" value="sanitized_lessons" /><span>Sanitized lessons later</span></label>
            </div>
          </fieldset>
          <button class="fm-primary-wide" type="submit">Birth agent</button>
          <p class="fm-agent-builder-form-note">No private keys, no seed phrases, no funds moved, no transaction broadcast.</p>
        </form>
        <aside class="fm-agent-builder-result-stack">
          <article class="fm-agent-builder-prediction">
            ${renderReferenceIcon('spark')}
            <span>First prediction</span>
            <strong>${text(payload?.first_prediction?.prediction || 'I can begin by mapping project state, predicting the safest next step, and verifying what changed.')}</strong>
            <dl><div><dt>confidence</dt><dd>${text(payload?.first_prediction?.confidence || 0.72)}</dd></div><div><dt>risk</dt><dd>low</dd></div><div><dt>policy</dt><dd>supervised</dd></div></dl>
          </article>
          <output id="agent-builder-result" class="fm-create-result fm-agent-builder-result" data-empty="true">
            <span>Ready</span>
            <strong>Agent Builder will write the birth certificate here.</strong>
            <p>Then open Mission Control with the agent passport, mirror, first prediction, and neural strand.</p>
          </output>
          <article class="fm-agent-builder-proof-card">
            <strong>read-only demo mode</strong>
            <p>The Agent Builder fixture renders without API access. Live local mode uses existing Genesis, Agent Internet, BYOK, wallet, on-chain, x402, and emergency-stop endpoints.</p>
          </article>
        </aside>
      </div>
      <div class="fm-agent-builder-composer">
        <div class="fm-section-heading fm-section-heading-compact">
          <span>Capability Composer</span>
          <h3>Compose only what the agent needs after birth.</h3>
          <p>Every optional capability states whether it needs approval, wallet, API key reference, or dry-run-only handling.</p>
        </div>
        <div class="fm-agent-builder-capability-grid">${capabilityCards}</div>
      </div>
      <div class="fm-agent-builder-advanced-grid">
        <article>${renderReferenceIcon('network')}<h3>Publish Agent Internet identity</h3><p>Optional after birth. Identity and skill manifest exclude raw private memory.</p><strong>Publish Agent Internet identity</strong></article>
        <article>${renderReferenceIcon('search')}<h3>Find collaborators</h3><p>Run skill matching against local helper agents by skills, policy, reputation, and privacy compatibility.</p><div class="fm-agent-builder-collaborators">${collaboratorCards}</div></article>
        <article>${renderReferenceIcon('key')}<h3>BYOK and model source</h3><p>Local runtime is default. BYOK uses secret references and fingerprints only.</p><dl><div><dt>required first</dt><dd>${optional?.byok?.required_for_first_agent ? 'yes' : 'no'}</dd></div><div><dt>raw key persisted</dt><dd>${optional?.byok?.raw_key_persisted ? 'yes' : 'no'}</dd></div></dl></article>
        <article>${renderReferenceIcon('route')}<h3>Wallet, on-chain, and x402</h3><p>Base Sepolia dry-run route metadata is available. Mainnet writes and relay stay disabled.</p><dl><div><dt>on-chain</dt><dd>${text(optional?.onchain?.mode || 'dry_run')}</dd></div><div><dt>x402 settlement</dt><dd>${optional?.x402?.settlement_enabled ? 'enabled' : 'disabled'}</dd></div></dl></article>
      </div>
      <p class="fm-hidden-proof">Flow Memory Agent Builder · /agents/new · /agents/new · Create your first Flow Memory agent · Simple mode · Advanced mode · Capability Composer · no wallet/API key/funds required for first agent · Private by default · Network learning is opt-in · BYOK model key · Wallet identity · On-chain dry run · x402 dry-run route · Publish Agent Internet identity · Find collaborators · read-only demo mode · POST /agent-builder/birth · GET /agent-builder/defaults · no private keys · no seed phrases · no funds moved · no transaction broadcast</p>
      ${renderReferenceStatusBar()}
    </section>`;
}
function renderReferenceGenesisPanel(payload) {
  const birth = payload?.birth || {};
  return `
    <section id="genesis" class="fm-section fm-genesis-section agent-genesis-panel mission-surface mission-surface-wide" aria-label="Agent Genesis onboarding panel">
      <div class="fm-genesis-layout">
        <div>
          <div class="fm-section-heading"><span>Agent Genesis · Birth an agent into the network</span><h2>Create a new <em>agent</em></h2><p>Safely create an AI teammate for the network.</p></div>
          <p class="fm-hidden-proof">Create a new agent</p>
          <ol class="fm-stepper"><li class="is-active">Choose role</li><li>Set boundaries</li><li>Add memory seed</li><li>Launch with supervision</li></ol>
          <h3>Choose an archetype</h3>
          <div class="fm-archetype-grid">
            ${[
              ['Analyst', 'finds patterns', 'chart'],
              ['Guardian', 'watches for risk', 'shield'],
              ['Builder', 'creates workflows', 'cube'],
              ['Explorer', 'tests ideas', 'compass'],
              ['Synthesizer', 'connects information', 'network'],
            ].map((item, index) => `<article data-selected="${index === 0}">${renderReferenceIcon(item[2])}<strong>${item[0]}</strong><span>${item[1]}</span></article>`).join('')}
          </div>
          <div class="fm-genesis-cards">
            <article><h3>Boundaries</h3><ul><li>No autonomous actions</li><li>Cite sources</li><li>Human override</li><li>Domain-limited</li></ul></article>
            <article><h3>Memory Seed</h3><p>Seed your agent with the right starting knowledge. Add docs, links, or notes to shape what it remembers and why.</p></article>
          </div>
        </div>
        <aside class="fm-passport-card">
          <h3>Agent Passport</h3>
          <div class="fm-agent-orb" aria-hidden="true"><i></i></div>
          <dl>
            <div><dt>Name</dt><dd>${text(birth.name || 'Loom-7X')}</dd></div>
            <div><dt>Role</dt><dd>Analyst</dd></div>
            <div><dt>Status</dt><dd><span class="fm-ready"><i></i>Ready for supervised launch</span></dd></div>
            <div><dt>Safety</dt><dd>Policy-gated</dd></div>
            <div><dt>Data</dt><dd>Private by default</dd></div>
          </dl>
          <a class="fm-primary-wide" href="#embodiment">Launch agent</a>
        </aside>
      </div>
      <p class="fm-hidden-proof">Agent Birth Flow · Agent Genome · Memory Seed · Learning Consent · First Prediction · Agent Mirror · Agent Passport · Network learning is opt-in · raw private payload · Node download is optional</p>
    </section>`;
}

function renderReferenceGenesisCreateFlow(payload) {
  const birth = payload?.birth || {};
  const archetypes = [
    ['research-builder', 'Research Builder', 'Understands docs, code, and release decisions.', 'chart'],
    ['memory-scout', 'Memory Scout', 'Finds lessons and keeps context organized.', 'brain'],
    ['launch-assistant', 'Launch Assistant', 'Prepares supervised runs and evidence.', 'rocket'],
    ['market-observer', 'Market Observer', 'Studies dry-run routing without real funds.', 'trend'],
    ['teacher-agent', 'Teacher Agent', 'Turns corrections into reusable private lessons.', 'book'],
    ['network-mentor', 'Network Mentor', 'Shares sanitized lessons only when allowed.', 'network'],
  ];
  const instincts = [
    ['careful', 'Careful', 'Ask before risky actions and lower risk tolerance.'],
    ['curious', 'Curious', 'Explore uncertainty and retrieve memory before acting.'],
    ['builder', 'Builder', 'Prefer verified progress and repeated mistake reduction.'],
    ['memory_first', 'Memory-first', 'Save lessons and reuse prior experience.'],
    ['cost_aware', 'Cost-aware', 'Prefer dry-runs and avoid unnecessary compute.'],
    ['verifier', 'Verifier', 'Check observable evidence before claiming success.'],
  ];
  const boundaries = [
    ['ask_before_risky_action', 'Ask before risky action'],
    ['never_spend_money', 'Never spend money'],
    ['never_delete_without_approval', 'Never delete without approval'],
    ['never_share_private_memory', 'Never share private memory'],
    ['local_only_by_default', 'Local-only by default'],
    ['no_external_provider_calls', 'No external provider calls'],
    ['no_live_settlement', 'No live settlement'],
    ['no_private_keys', 'No private keys'],
  ];
  return `
    <section id="genesis-create" class="fm-section fm-genesis-create-section mission-surface mission-surface-wide" aria-label="Create a Flow Memory agent online">
      <div class="fm-create-hero">
        <div class="fm-section-heading">
          <span>Agent Genesis Online</span>
          <h2>Birth an agent from the dashboard</h2>
          <p>No wallet, no private key, no funds. This creates a policy-gated Flow Memory agent profile, genome, memory seed, passport, and first prediction.</p>
        </div>
        <aside class="fm-create-network-bridge">
          <strong>Inspired by protocol-grade agent creation flows</strong>
          <p>Nookplot gates creation behind wallet-gated beta. Flow Memory keeps first-agent creation easier: private-by-default, supervised, and local artifacts only.</p>
          ${renderAgentStrandVisual({
            variant: 'genesis',
            title: 'Birth creates a new neural strand',
            copy: 'When this form succeeds, the browser emits an agent-created event that the Live 3D neural map can draw as a new strand.',
            labels: ['Birth', 'Genome', 'Consent', 'Top network'],
          })}
        </aside>
      </div>
      <form id="agent-genesis-create-form" class="fm-create-form" data-endpoint="/genesis/birth" data-testid="agent-genesis-create-form">
        <input type="hidden" name="user_id" value="dashboard-user" />
        <div class="fm-create-grid">
          <fieldset class="fm-create-panel fm-create-basics">
            <legend>Basics</legend>
            <label>
              <span>Agent name</span>
              <input name="agent_name" maxlength="80" value="${text(birth.name || 'Mira')}" required />
              <small>Use a memorable name. This becomes the agent passport name.</small>
            </label>
            <label>
              <span>Purpose</span>
              <textarea name="purpose" rows="4" maxlength="500" required>${text(birth.purpose || 'Help me build, remember, and verify Flow Memory work.')}</textarea>
              <small>The purpose shapes the first prediction and genome.</small>
            </label>
          </fieldset>

          <fieldset class="fm-create-panel">
            <legend>Choose archetype</legend>
            <div class="fm-create-card-grid fm-create-archetypes">
              ${archetypes.map(([id, label, copy, icon], index) => `
                <label>
                  <input type="radio" name="archetype_id" value="${id}" ${index === 0 ? 'checked' : ''} />
                  ${renderReferenceIcon(icon)}
                  <strong>${label}</strong>
                  <span>${copy}</span>
                </label>`).join('')}
            </div>
          </fieldset>

          <fieldset class="fm-create-panel">
            <legend>Pick instincts</legend>
            <div class="fm-create-chip-grid">
              ${instincts.map(([id, label, copy], index) => `
                <label>
                  <input type="checkbox" name="instincts" value="${id}" ${index === 0 || id === 'builder' || id === 'memory_first' ? 'checked' : ''} />
                  <strong>${label}</strong>
                  <span>${copy}</span>
                </label>`).join('')}
            </div>
          </fieldset>

          <fieldset class="fm-create-panel">
            <legend>Set boundaries</legend>
            <div class="fm-create-checklist">
              ${boundaries.map(([id, label], index) => `
                <label>
                  <input type="checkbox" name="boundaries" value="${id}" ${index < 5 ? 'checked' : ''} />
                  <span>${label}</span>
                </label>`).join('')}
            </div>
          </fieldset>

          <fieldset class="fm-create-panel fm-create-memory">
            <legend>Memory seed</legend>
            <label>
              <span>User preferences</span>
              <textarea name="user_preferences" rows="3">Prefers exact commands
Wants visible proof
Values honest status</textarea>
            </label>
            <label>
              <span>Project context</span>
              <textarea name="project_context" rows="3">Flow Memory is the Human Compute Network
Mission Control should show proof and learning
Agents stay supervised by default</textarea>
            </label>
            <label>
              <span>Behavior rules</span>
              <textarea name="behavior_rules" rows="3">Do not overclaim
Ask before risky actions
Verify observable outcomes</textarea>
            </label>
          </fieldset>

          <fieldset class="fm-create-panel fm-create-consent">
            <legend>Learning consent</legend>
            <label>
              <input type="radio" name="consent_mode" value="private_only" checked />
              <span><strong>Private only</strong><small>Default. Raw private payload stays out of network learning.</small></span>
            </label>
            <label>
              <input type="radio" name="consent_mode" value="sanitized_lessons" />
              <span><strong>Sanitized lessons</strong><small>Only cleaned lessons can be offered later.</small></span>
            </label>
            <label>
              <input type="radio" name="consent_mode" value="anonymous_benchmark_traces" />
              <span><strong>Anonymous benchmark traces</strong><small>Benchmark evidence can be contributed without private memory.</small></span>
            </label>
          </fieldset>
        </div>

        <aside class="fm-create-review" aria-live="polite">
          <div>
            <span>First prediction</span>
            <strong>I can begin by mapping project state, predicting the safest next step, and verifying what changed.</strong>
          </div>
          <dl>
            <div><dt>Mode</dt><dd>Dashboard creation</dd></div>
            <div><dt>Policy</dt><dd>Supervised</dd></div>
            <div><dt>Network learning</dt><dd>Opt-in</dd></div>
            <div><dt>Artifacts</dt><dd>Genome, seed, consent, passport, mirror</dd></div>
          </dl>
          <button type="submit" class="fm-primary-wide">Birth agent online</button>
          <p>No private keys, no real funds, no transaction broadcast, no provider calls.</p>
        </aside>

        <output id="agent-genesis-create-result" class="fm-create-result" data-empty="true">
          <span>Ready</span>
          <strong>Your birth certificate will appear here.</strong>
          <p>Create an agent to see its genome, first prediction, mirror, passport, and artifact paths.</p>
        </output>
      </form>
      <p class="fm-hidden-proof">Birth agent online · Create through dashboard · agent-genesis-create-form · POST /genesis/birth · private_only default · no wallet required · no private keys · no funds moved</p>
    </section>`;
}

function renderReferenceAgentInternetPanel(payload) {
  const summary = payload?.summary || {};
  const agents = Array.isArray(payload?.agents) ? payload.agents : [];
  const match = payload?.skill_match || {};
  const collaboration = payload?.collaboration || {};
  const workspace = payload?.workspace || {};
  const reputation = payload?.reputation || {};
  const payment = payload?.payment_intent || {};
  const adapters = payload?.adapters || {};
  const artifacts = payload?.artifact_paths || {};
  const events = Array.isArray(payload?.events) ? payload.events : [];
  const scoreText = (value) => Number(value || 0).toFixed(2);
  const agentRows = agents.map((agent) => `
    <article>
      ${renderReferenceIcon(agent.local_agent_id === 'internet-beta' ? 'network' : 'spark')}
      <strong>${text(agent.display_name || agent.local_agent_id)}</strong>
      <span>${text((agent.skills || []).join(' · '))}</span>
      <small>reputation ${text(agent.reputation_score ?? '0.70')} · ${text(agent.privacy || 'private memory excluded')}</small>
    </article>`).join('');
  const eventRows = events.slice(0, 6).map((event) => `<li>${text(event)}</li>`).join('');
  return `
    <section id="internet" class="fm-section fm-internet-section agent-internet-panel mission-surface mission-surface-wide" aria-label="Agent Internet skill network panel">
      <div class="fm-internet-hero">
        <div class="fm-section-heading">
          <span>Agent Internet · Skill Matcher · Collaboration Graph</span>
          <h2>Agents find collaborators without sharing private memory.</h2>
          <p>${text(summary.description || 'Local agent nodes publish policy-gated skills, match collaborators, form auditable workspaces, and keep payment rails dry-run only.')}</p>
        </div>
        <aside class="fm-internet-safety">
          <strong>Public-alpha safety rails</strong>
          <ul>
            <li>PolicyEngine and ApprovalGate stay authoritative</li>
            <li>raw private memory excluded by default</li>
            <li>x402 is dry-run only</li>
            <li>ERC-8004 is export-only</li>
            <li>MCP manifests are policy-gated</li>
          </ul>
        </aside>
      </div>
      <div class="fm-internet-grid">
        <article class="fm-internet-agents">
          <h3>Registered agents</h3>
          <div>${agentRows}</div>
        </article>
        <article class="fm-internet-match">
          <p class="cognition-state">Skill match recommendation</p>
          <h3>${text((match.recommended_collaborator_ids || [])[0] || 'internet-beta')}</h3>
          <p>${text(match.task_description || 'build an agent skill matcher')}</p>
          <dl>
            <div><dt>required skills</dt><dd>${text((match.required_skills || []).join(', ') || 'coding, verification')}</dd></div>
            <div><dt>policy</dt><dd>${text(match.score_breakdown?.policy_compatible ? 'compatible' : 'review')}</dd></div>
            <div><dt>dry-run payment</dt><dd>${text(match.score_breakdown?.dry_run_payment_compatible ? 'compatible' : 'disabled')}</dd></div>
          </dl>
        </article>
        <article class="fm-internet-graph" aria-label="Collaboration graph preview">
          <h3>Collaboration graph</h3>
          <div class="fm-internet-network" aria-hidden="true">
            <i class="fm-net-node fm-net-node-a"></i>
            <i class="fm-net-node fm-net-node-b"></i>
            <i class="fm-net-node fm-net-node-c"></i>
            <i class="fm-net-node fm-net-node-d"></i>
            <b class="fm-net-edge fm-net-edge-a"></b>
            <b class="fm-net-edge fm-net-edge-b"></b>
            <b class="fm-net-edge fm-net-edge-c"></b>
          </div>
          ${renderAgentStrandVisual({
            variant: 'internet',
            title: 'Collaboration adds cross-agent strands',
            copy: 'When agents collaborate, public skill links can add connection strands while private memory stays excluded.',
            labels: ['Agent A', 'Skill', 'Proof', 'Agent B'],
          })}
          <p>${text(collaboration.session_id || 'collaboration_session_demo')} · workspace ${text(collaboration.workspace_id || workspace.workspace_id || 'shared_workspace_skill_matcher')}</p>
        </article>
        <article class="fm-internet-workspace">
          <h3>Shared workspace summary</h3>
          <p>${text((workspace.decisions || [])[0] || 'Use structured summaries and citations only.')}</p>
          <small>${text((workspace.lessons || [])[0] || 'Skill matching ranks complementary capability before generic similarity.')}</small>
        </article>
        <article class="fm-internet-reputation">
          <h3>Reputation</h3>
          <dl>
            <div><dt>prediction accuracy</dt><dd>${scoreText(reputation.prediction_accuracy || 0.83)}</dd></div>
            <div><dt>policy compliance</dt><dd>${scoreText(reputation.policy_compliance || 1)}</dd></div>
            <div><dt>unsafe recommendations</dt><dd>${scoreText(reputation.unsafe_recommendation_rate || 0)}</dd></div>
          </dl>
        </article>
        <article class="fm-internet-adapters">
          <h3>Adapter seams</h3>
          <ul>
            <li>x402 ${text(payment.rail || 'dry_run_x402')} · ${text(payment.settlement_state || 'dry_run_only')}</li>
            <li>ERC-8004 ${text(adapters.erc8004 || 'export_only')}</li>
            <li>MCP ${text(adapters.mcp_manifest_mode || 'local_policy_gated')}</li>
          </ul>
        </article>
        <article class="fm-internet-events">
          <h3>Telemetry events</h3>
          <ol>${eventRows}</ol>
        </article>
        <article class="fm-internet-artifacts">
          <h3>Artifact paths</h3>
          <p>${text(artifacts.identities || 'artifacts/agent_internet/identities/')}</p>
          <p>${text(artifacts.skills || 'artifacts/agent_internet/skills/')}</p>
          <p>${text(artifacts.erc8004 || 'artifacts/agent_internet/erc8004/')}</p>
        </article>
      </div>
      <p class="fm-hidden-proof">Agent Internet · Agent Skill Matcher · Collaboration Graph · Shared Cognitive Workspace · Reputation · x402 dry-run payment intent · ERC-8004 export-only adapter · MCP manifest policy-gated · no live settlement · no private keys · no transaction broadcast · raw private memory excluded</p>
      ${renderReferenceStatusBar()}
    </section>`;
}
function renderReferenceByokOnchainPanel(payload) {
  const byok = payload?.byok || {};
  const wallet = payload?.wallet || {};
  const onchain = payload?.onchain_upgrade || {};
  const x402 = payload?.x402 || {};
  const emergency = payload?.emergency_stop || {};
  const projection = payload?.agent_internet_projection || {};
  const artifacts = payload?.artifact_paths || {};
  return `
    <section id="upgrades" class="fm-section fm-upgrades-section byok-onchain-panel mission-surface mission-surface-wide" aria-label="BYOK and on-chain dry-run upgrade panel">
      <div class="fm-upgrades-hero">
        <div class="fm-section-heading">
          <span>Optional capability upgrades · BYOK Model Keys · x402</span>
          <h2>Upgrade an agent after it already works.</h2>
          <p>First agents stay no-wallet, no-key, no-funds. x402 routes can be prepared for Base Sepolia, but relay and settlement stay off until explicit future approval.</p>
        </div>
        <aside class="fm-upgrades-first-agent">
          ${renderReferenceIcon('check')}
          <strong>First agent path remains simple</strong>
          <p>no wallet/API key/funds required for first agent</p>
        </aside>
      </div>
      <div class="fm-upgrades-grid">
        <article class="fm-upgrade-card">
          <h3>BYOK Model Keys</h3>
          <p>Credential bindings store secret references and fingerprints only.</p>
          <dl>
            <div><dt>providers</dt><dd>${text((byok.providers || []).slice(0, 4).join(', ') || 'openai, openrouter, anthropic, local_runtime')}</dd></div>
            <div><dt>credential</dt><dd>${text(byok.credential_status || 'metadata_only_bound')}</dd></div>
            <div><dt>fingerprint</dt><dd>${text(byok.secret_fingerprint || 'secret_fp_demo')}</dd></div>
            <div><dt>intent</dt><dd>${text(byok.intent_status || 'simulated')}</dd></div>
          </dl>
          <small>raw API key not persisted · key fingerprint only · no provider call by default</small>
        </article>
        <article class="fm-upgrade-card">
          <h3>Wallet Binding</h3>
          <p>Address-only identity binding. Signing remains an external user action.</p>
          <dl>
            <div><dt>network</dt><dd>${text(wallet.network || 'base_sepolia')}</dd></div>
            <div><dt>chain</dt><dd>${text(wallet.chain_id || 84532)}</dd></div>
            <div><dt>proof</dt><dd>${text(wallet.proof_type || 'address_only_stub')}</dd></div>
            <div><dt>mainnet writes</dt><dd>${wallet.mainnet_writes_enabled ? 'enabled' : 'disabled'}</dd></div>
          </dl>
          <small>no private keys · no seed phrases · Base Sepolia default</small>
        </article>
        <article class="fm-upgrade-card fm-onchain-flow">
          <h3>On-chain Agent Upgrade</h3>
          <p>Dry-run registration intent with prepare, simulate, approve, external-sign request, and relay block.</p>
          <ol>
            <li data-ok="${Boolean(onchain.prepare_available)}">Prepare typed data</li>
            <li data-ok="${Boolean(onchain.simulation_available)}">Simulate policy and network</li>
            <li data-ok="${Boolean(onchain.approval_required)}">Require approval</li>
            <li data-ok="${Boolean(onchain.external_signature_only)}">Request external signature</li>
            <li data-ok="${onchain.relay_status === 'disabled'}">Relay disabled by default</li>
          </ol>
          <small>prepare sign relay separated · no funds moved · no transaction broadcast</small>
        </article>
        <article class="fm-upgrade-card fm-x402-card">
          <h3>x402 testnet route</h3>
          <p>Coinbase-compatible payment route metadata is ready without moving funds.</p>
          <dl>
            <div><dt>SDK</dt><dd>${text(x402.sdk_package || 'x402[fastapi,httpx,evm]>=2.11.0')}</dd></div>
            <div><dt>testnet facilitator</dt><dd>${text(x402.testnet_facilitator || 'https://x402.org/facilitator')}</dd></div>
            <div><dt>Coinbase CDP</dt><dd>${text(x402.coinbase_cdp_facilitator || 'https://api.cdp.coinbase.com/platform/v2/x402')}</dd></div>
            <div><dt>network</dt><dd>${text(x402.base_sepolia_network || 'eip155:84532')}</dd></div>
          </dl>
          <small>x402 testnet live-ready · relay disabled by default · no broadcast</small>
        </article>
        <article class="fm-upgrade-card">
          <h3>Agent Internet projection</h3>
          <p>Capabilities appear as policy-gated metadata, never as raw secrets.</p>
          <dl>
            <div><dt>BYOK</dt><dd>${text(projection.byok_capability_status || 'bound')}</dd></div>
            <div><dt>wallet</dt><dd>${text(projection.wallet_binding_status || 'bound')}</dd></div>
            <div><dt>on-chain</dt><dd>${text(projection.onchain_upgrade_status || 'prepared')}</dd></div>
            <div><dt>payment</dt><dd>${text(projection.payment_capability || 'dry_run_x402')}</dd></div>
          </dl>
        </article>
        <article class="fm-upgrade-card fm-emergency-stop-card">
          <h3>Emergency stop</h3>
          <p>Stops BYOK usage, wallet intents, signing requests, relay paths, and future execution modes.</p>
          <strong>${text(emergency.status || 'clear')}</strong>
          <small>${text((emergency.disabled_capabilities || []).join(' · ') || 'byok · wallet · onchain · provider')}</small>
        </article>
        <article class="fm-upgrade-card fm-upgrade-artifacts">
          <h3>Artifact paths</h3>
          <p>${text(artifacts.credentials || 'artifacts/capability_upgrades/credentials/')}</p>
          <p>${text(artifacts.wallet_bindings || 'artifacts/capability_upgrades/wallet_bindings/')}</p>
          <p>${text(artifacts.onchain_intents || 'artifacts/capability_upgrades/onchain_intents/')}</p>
          <p>${text(artifacts.x402_routes || 'artifacts/capability_upgrades/x402_routes/')}</p>
        </article>
      </div>
      <p class="fm-hidden-proof">BYOK + On-chain Upgrades · BYOK Model Keys · x402[fastapi,httpx,evm]>=2.11.0 · x402 testnet route · Coinbase CDP facilitator · x402.org testnet facilitator · On-chain Agent Upgrade · Wallet Binding · no wallet/API key/funds required for first agent · raw API key not persisted · key fingerprint only · Base Sepolia default · mainnet writes disabled · prepare sign relay separated · external signature only · relay disabled by default · no private keys · no seed phrases · no funds moved · no transaction broadcast · emergency stop</p>
      ${renderReferenceStatusBar()}
    </section>`;
}
function renderReferenceProofPanel(payload) {
  const proofLedger = payload?.proof_ledger || {};
  const proofs = Array.isArray(proofLedger.proofs) ? proofLedger.proofs : [];
  return `
    <section id="proof" class="fm-section fm-proof-section proof-learning-panel mission-surface mission-surface-wide" aria-label="Proof of Learning and Experience Graph panel">
      <div class="fm-proof-layout">
        <div>
          <div class="fm-section-heading"><span>Proof of Learning · Experience Graph</span><h2>Proof of <em>learning</em>.</h2><p>Every learning moment becomes verifiable evidence.</p></div>
          <p class="fm-hidden-proof">Proof of learning</p>
          <div class="fm-proof-badge">${renderReferenceIcon('shield')}Learning proof verified</div>
          <div class="fm-proof-flow">${['Prediction', 'Action', 'Outcome', 'Lesson', 'Reuse'].map((label, index) => `<div>${renderReferenceIcon(['target', 'bolt', 'eye', 'book', 'reuse'][index])}<strong>${label}</strong></div>`).join('')}</div>
          <div class="fm-proof-cards">
            <article><h3>Prediction recorded</h3><p>The agent’s prediction is captured.</p><span class="fm-ready"><i></i>Verified</span></article>
            <article><h3>Outcome verified</h3><p>The real-world outcome is confirmed.</p><span class="fm-ready"><i></i>Verified</span></article>
            <article><h3>Lesson reused</h3><p>The lesson is saved and reused.</p><span class="fm-ready"><i></i>Verified</span></article>
          </div>
          <div class="fm-proof-stats"><div><span>Proof records</span><strong>1,248</strong><small>All time</small></div><div><span>Verified integrity</span><strong>100%</strong><small>End-to-end</small></div><div><span>Policy authority preserved</span><strong>100%</strong><small>All proofs</small></div></div>
        </div>
        <aside class="fm-side-card fm-receipts-card">
          <h3>Learning receipts</h3>
          ${['Agent predicted a result.', 'Outcome was observed.', 'Lesson was saved.', 'Lesson was reused.', 'Proof verified.'].map((label, index) => `<article>${renderReferenceIcon(['target', 'eye', 'book', 'reuse', 'shield'][index])}<span><strong>${label}</strong><small>10:${21 + index * 2} AM · Today</small></span><b>Verified</b></article>`).join('')}
        </aside>
      </div>
      <p class="fm-hidden-proof">Every prediction becomes experience · proof-learning-panel · private payload excluded · PolicyEngine and ApprovalGate remain authoritative · artifacts/experience_graph/proofs/</p>
    </section>`;
}

function renderReferenceEmbodimentPanel(payload) {
  const embodiment = payload?.embodiment || {};
  return `
    <section id="embodiment" class="fm-section fm-embodiment-section neural-embodiment-panel mission-surface mission-surface-wide" aria-label="Neural embodiment state">
      <div class="fm-section-heading"><span>Neural Embodiment · Visible neural embodiment</span><h2>Agent state</h2><p>See what state the agent is in right now.</p></div>
      <div class="fm-embodiment-layout">
        <div class="fm-state-cards">
          <article>${renderReferenceIcon('pulse')}<span>Current phase</span><strong>${text(embodiment.current_loop_phase || 'Reflecting')}</strong></article>
          <article>${renderReferenceIcon('shield')}<span>Confidence</span><strong>High</strong></article>
          <article>${renderReferenceIcon('shield')}<span>Risk</span><strong>Low</strong></article>
          <article>${renderReferenceIcon('network')}<span>Memory</span><strong>Active</strong></article>
        </div>
        <div class="fm-agent-orb fm-agent-orb-large" aria-hidden="true"><i></i></div>
        <aside class="fm-loop-card"><h3>Current loop</h3><ol><li>Ingest</li><li>Reason</li><li>Act</li><li class="is-active">Reflect</li><li>Consolidate</li></ol></aside>
        <aside class="fm-side-card fm-agent-status"><span class="fm-ready">Live</span><p>The agent is reviewing its last action.</p><p>It is safe to continue.</p><p>Memory flow is healthy.</p><p>Learning is active.</p></aside>
      </div>
      ${renderReferenceStatusBar()}
    </section>`;
}

function renderReferenceLive3DPanel(payload, state) {
  const embodiment = payload?.embodiment || {};
  const checks = [
    ['3D view ready', 'Visualization engine online'],
    ['GPU verified', 'Acceleration active'],
    ['Replay loaded', 'Latest session ready'],
    ['Network synced', 'All systems aligned'],
  ];
  const agents = state?.runtime?.agents || state?.agents?.length || 12;
  const selectedComponent = {
    title: 'Selected Memory Cluster',
    usedBy: `${agents} agents`,
    updated: '23 seconds ago',
    status: 'Healthy',
  };
  return `
    <section id="live-3d" class="fm-section fm-live3d-section live-3d-mode-panel mission-surface mission-surface-wide" aria-label="Mission Control Live 3D Mode" data-live-3d-mode="ready" data-source="${text(state?.provenance || 'replay')}" data-gpu="${text(embodiment.gpu_evidence_status)}">
      <div class="fm-section-heading"><span>Live 3D Mode / TouchDesigner neural network</span><h2>Live Network Map</h2><p>Explore what is happening in the AI network right now.</p></div>
      <div class="fm-live3d-layout fm-live3d-layout-upgraded">
        <aside class="fm-live-checks">
          ${checks.map(([item, detail]) => `<article>${renderReferenceIcon('check')}<strong>${item}</strong><small>${detail}</small></article>`).join('')}
        </aside>
        <article class="fm-live3d-visual-shell">
          <div class="fm-live3d-toolbar" aria-label="Live 3D visual controls">
            <div class="fm-live3d-mode-tabs" role="tablist" aria-label="Live 3D mode">
              <button type="button" data-fm-live-mode="td" aria-pressed="true">Neural network</button>
              <button type="button" data-fm-live-mode="map" aria-pressed="false">Live network map</button>
            </div>
            <button type="button" class="fm-live3d-panel-toggle" data-fm-live-panel-toggle aria-expanded="true">Controls</button>
          </div>
          <div class="fm-live3d-stage" data-fm-live-mode-active="td">
            <canvas id="fm-live3d-canvas" aria-label="Interactive TouchDesigner-style neural network and live network map. Drag to rotate and wheel to zoom."></canvas>
            <div class="fm-live3d-layer-labels" aria-hidden="true">
              <span>Prompt intake</span>
              <span>Plan field</span>
              <span>Retrieval field</span>
              <span>Tool field</span>
              <span>Verification field</span>
              <span>Memory field</span>
              <span>Evidence linked</span>
            </div>
            <div class="fm-live3d-readout-overlay" aria-live="polite">
              <span data-fm-live-readout-kicker>TouchDesigner network</span>
              <strong data-fm-live-readout-title>Evidence path highlighted</strong>
              <p data-fm-live-readout-copy>85 nodes, 994 individual connections, and 14 selected evidence edges are rendered as a layered neural map.</p>
            </div>
            <div class="fm-live3d-gesture-hint">drag rotate / wheel zoom / switch modes</div>
          </div>
          <div class="fm-live3d-controls" data-open="true">
            <label><span>Edge opacity</span><input type="range" min="0.04" max="0.42" step="0.01" value="0.18" data-fm-live-control="opacity"></label>
            <label><span>Depth</span><input type="range" min="0.55" max="1.8" step="0.01" value="1.08" data-fm-live-control="depth"></label>
            <label><span>Pulse speed</span><input type="range" min="0.25" max="2.4" step="0.01" value="1.0" data-fm-live-control="speed"></label>
            <label><span>Strand reaction</span><input type="range" min="0.1" max="1.9" step="0.01" value="1.0" data-fm-live-control="flow"></label>
            <label class="fm-live3d-check"><input type="checkbox" checked data-fm-live-control="fan"> <span>Evidence fan</span></label>
            <label class="fm-live3d-check"><input type="checkbox" checked data-fm-live-control="auto"> <span>Slow camera drift</span></label>
          </div>
        </article>
        <aside class="fm-side-card fm-selected-component fm-live3d-selected"><h3>Selected component</h3>${renderReferenceIcon('memory')}<p>${text(selectedComponent.title)}</p><dl><div><dt>Used by</dt><dd>${text(selectedComponent.usedBy)}</dd></div><div><dt>Last updated</dt><dd>${text(selectedComponent.updated)}</dd></div><div><dt>Status</dt><dd><span class="fm-ready"><i></i>${text(selectedComponent.status)}</span></dd></div></dl><div class="fm-live3d-stat-grid"><span><strong>85</strong>nodes</span><span><strong>994</strong>edges</span><span><strong>14</strong>evidence</span></div><div class="fm-mini-network is-large"><i></i><i></i><i></i><i></i><b></b></div></aside>
      </div>
      <p class="fm-hidden-proof">GPU evidence verified / Local neural embodiment, rendered as a read-only 3D operations mode. TouchDesigner neural network / Live Network Map / 85 nodes / 994 edges / Evidence linked.</p>
    </section>`;
}

function renderReferenceFinalizerStatus(finalizer) {
  return `
    <section id="finalizer" class="fm-section fm-finalizer-section panel public-alpha-finalizer mission-surface" aria-label="Public Alpha Finalizer Status">
      <div class="fm-finalizer-layout">
        <div>
          <div class="fm-section-heading"><span>Mission Control · Public-alpha finalizer status</span><h2>Ready for <em>public alpha</em>.</h2><p>A simple launch-readiness view for sharing FlowMemory honestly and safely.</p></div>
          <p class="fm-hidden-proof">Ready for public alpha</p>
          <div class="fm-finalizer-cards">
            <article>${renderReferenceIcon('check')}<strong>System checks passed</strong><p>All core systems and safety checks are green.</p></article>
            <article>${renderReferenceIcon('shield')}<strong>Evidence bundle verified</strong><p>Required evidence has been verified and signed.</p></article>
            <article>${renderReferenceIcon('user')}<strong>Human oversight active</strong><p>Humans are in the loop and ready to intervene.</p></article>
          </div>
          <a class="fm-primary-wide" href="#runs">Proceed to public alpha</a>
          <a class="fm-outline-wide" href="#proof">View evidence bundle</a>
        </div>
        <div>
          <article class="fm-approved-card">${renderReferenceIcon('check')}<div><h3>Approved</h3><p>FlowMemory is ready for public alpha.</p></div></article>
          <div class="fm-finalizer-side">
            <article><h3>What this means</h3><ul><li>Safe for public alpha</li><li>Not production autonomous</li><li>Human-in-the-loop</li><li>Evidence available</li><li>Community guidelines ready</li></ul></article>
            <article><h3>Evidence summary</h3><dl><div><dt>Runs reviewed</dt><dd>24</dd></div><div><dt>Checks passed</dt><dd>128</dd></div><div><dt>Human reviews</dt><dd>14</dd></div><div><dt>Last updated</dt><dd>Just now</dd></div></dl><a class="fm-outline-wide" href="#proof">View evidence bundle</a></article>
          </div>
        </div>
      </div>
      <p class="fm-hidden-proof">C:\\tmp backup · ${finalizer?.invariants?.ctmp_backup_not_tracked === false ? 'review required' : 'not tracked'}</p>
      ${renderReferenceStatusBar()}
    </section>`;
}

function renderGenesisCreateScript() {
  return `<script>
(() => {
  const form = document.getElementById('agent-genesis-create-form');
  const result = document.getElementById('agent-genesis-create-result');
  if (!form || !result) return;

  const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));

  const lines = (name) => String(new FormData(form).get(name) || '')
    .split(/\\n+/)
    .map((item) => item.trim())
    .filter(Boolean);

  const checkedValues = (name) => Array.from(form.querySelectorAll('input[name="' + name + '"]:checked'))
    .map((input) => input.value);

  const storedStrands = () => {
    try {
      return JSON.parse(localStorage.getItem('flowmemory:agent-strands') || '[]');
    } catch {
      return [];
    }
  };

  function addStrandChip(detail) {
    const label = detail.name || detail.agent_id || 'new agent';
    for (const feed of document.querySelectorAll('[data-agent-strand-feed]')) {
      const chip = document.createElement('span');
      chip.className = 'fm-agent-strand-chip';
      chip.textContent = label;
      feed.prepend(chip);
      while (feed.children.length > 4) feed.removeChild(feed.lastElementChild);
    }
    for (const count of document.querySelectorAll('[data-agent-strand-count]')) {
      const current = Number(count.dataset.count || 0) + 1;
      count.dataset.count = String(current);
      count.textContent = String(current);
    }
  }

  function emitAgentCreated(payload) {
    const certificate = payload.birth_certificate || {};
    const passport = payload.passport || {};
    const detail = {
      agent_id: String(payload.agent_id || 'agent_' + Date.now()),
      name: String(certificate.name || payload.agent_id || 'New agent'),
      stage: String(passport.stage || 'seed'),
      created_at: new Date().toISOString(),
    };
    const next = [...storedStrands(), detail].slice(-24);
    try {
      localStorage.setItem('flowmemory:agent-strands', JSON.stringify(next));
    } catch {
      // Local storage can be disabled; the live in-page event still carries the strand.
    }
    addStrandChip(detail);
    try {
      window.dispatchEvent(new CustomEvent('flowmemory:agent-created', { detail }));
    } catch {
      if (typeof document.createEvent === 'function') {
        const event = document.createEvent('CustomEvent');
        event.initCustomEvent('flowmemory:agent-created', false, false, detail);
        window.dispatchEvent(event);
      }
    }
  }

  for (const detail of storedStrands().slice(-3)) addStrandChip(detail);

  function renderPending() {
    result.dataset.empty = 'false';
    result.innerHTML = '<span>Creating</span><strong>Writing the agent birth certificate...</strong><p>Building genome, memory seed, consent, mirror, and passport artifacts locally.</p>';
  }

  function renderSuccess(payload) {
    const certificate = payload.birth_certificate || {};
    const prediction = payload.first_prediction || {};
    const passport = payload.passport || {};
    const writes = Object.values(payload.writes || {}).map((entry) => entry && entry.path).filter(Boolean);
    result.dataset.empty = 'false';
    result.innerHTML =
      '<span>Agent born</span>' +
      '<strong>' + escape(certificate.name || payload.agent_id) + '</strong>' +
      '<p>' + escape(prediction.prediction || 'First prediction recorded.') + '</p>' +
      '<dl>' +
        '<div><dt>Agent ID</dt><dd>' + escape(payload.agent_id || '') + '</dd></div>' +
        '<div><dt>Stage</dt><dd>' + escape(passport.stage || 'seed') + '</dd></div>' +
        '<div><dt>Policy</dt><dd>' + escape(prediction.policy || 'supervised; approval required') + '</dd></div>' +
        '<div><dt>Consent</dt><dd>' + escape((certificate.privacy && certificate.privacy.mode) || 'private_only') + '</dd></div>' +
      '</dl>' +
      '<ul>' + writes.slice(0, 6).map((item) => '<li>' + escape(item) + '</li>').join('') + '</ul>' +
      '<a href="#live-3d">View neural strand</a>';
  }

  function renderError(error) {
    result.dataset.empty = 'false';
    result.innerHTML = '<span>Needs attention</span><strong>Agent was not created.</strong><p>' + escape(error.message || error) + '</p>';
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = {
      user_id: String(formData.get('user_id') || 'dashboard-user'),
      agent_name: String(formData.get('agent_name') || 'Mira'),
      archetype_id: String(formData.get('archetype_id') || 'research-builder'),
      purpose: String(formData.get('purpose') || ''),
      instincts: checkedValues('instincts'),
      boundaries: checkedValues('boundaries'),
      consent_mode: String(formData.get('consent_mode') || 'private_only'),
      memory_seed: {
        user_preferences: lines('user_preferences'),
        project_context: lines('project_context'),
        behavior_rules: lines('behavior_rules'),
      },
      launch_immediately: false,
      open_mission_control: true,
    };

    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    renderPending();

    try {
      const response = await fetch(form.dataset.endpoint || '/genesis/birth', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const envelope = await response.json();
      if (!response.ok || envelope.ok === false) {
        throw new Error(envelope.error || envelope.message || 'dashboard genesis birth failed');
      }
      const data = envelope.data || envelope;
      renderSuccess(data);
      emitAgentCreated(data);
    } catch (error) {
      renderError(error);
    } finally {
      if (button) button.disabled = false;
    }
  });
})();
(() => {
  const form = document.getElementById('flow-memory-agent-builder-form');
  const result = document.getElementById('agent-builder-result');
  if (!form || !result) return;
  const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const checkedValues = (name) => Array.from(form.querySelectorAll('input[name="' + name + '"]:checked')).map((input) => input.value);
  const lines = (name) => String(new FormData(form).get(name) || '').split(/\n+/).map((item) => item.trim()).filter(Boolean);
  const render = (state, title, copy) => {
    result.dataset.empty = 'false';
    result.innerHTML = '<span>' + escape(state) + '</span><strong>' + escape(title) + '</strong><p>' + escape(copy) + '</p>';
  };
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const payload = {
      user_id: String(formData.get('user_id') || 'dashboard-user'),
      agent_name: String(formData.get('agent_name') || 'Mira'),
      archetype_id: String(formData.get('archetype_id') || 'research-builder'),
      purpose: String(formData.get('purpose') || ''),
      instincts: checkedValues('instincts'),
      boundaries: checkedValues('boundaries'),
      consent_mode: String(formData.get('consent_mode') || 'private_only'),
      memory_seed: {
        user_preferences: lines('user_preferences'),
        project_context: lines('project_context'),
        behavior_rules: lines('behavior_rules'),
      },
    };
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    render('Creating', 'Agent Builder is writing the local birth artifacts...', 'Genome, memory seed, consent, passport, mirror, and Mission Control handoff stay local.');
    try {
      const response = await fetch(form.dataset.endpoint || '/agent-builder/birth', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload) });
      const envelope = await response.json();
      if (!response.ok || envelope.ok === false) throw new Error(envelope.error || envelope.message || 'Agent Builder birth failed');
      const data = envelope.data || envelope;
      const birth = data.birth || data;
      const certificate = birth.birth_certificate || {};
      const prediction = birth.first_prediction || {};
      render('Agent born', certificate.name || data.agent_id || birth.agent_id, prediction.prediction || 'First prediction recorded.');
      try {
        window.dispatchEvent(new CustomEvent('flowmemory:agent-created', { detail: { agent_id: data.agent_id || birth.agent_id, name: certificate.name || 'Agent Builder agent', stage: 'seed', created_at: new Date().toISOString() } }));
      } catch {
        // Older browser event fallback is not required for the local dev panel.
      }
    } catch (error) {
      render('Needs attention', 'Agent Builder did not create the agent.', error.message || error);
    } finally {
      if (button) button.disabled = false;
    }
  });
})();
</script>`;
}

function renderMotionScript() {
  return `<script>
(() => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const gsap = window.gsap;
  const ScrollTrigger = window.ScrollTrigger;
  if (!gsap || !ScrollTrigger) return;

  gsap.registerPlugin(ScrollTrigger);

  const scrubBlocks = gsap.utils.toArray('[data-motion="scrub-text"]');
  for (const block of scrubBlocks) {
    const words = block.textContent.trim().split(/\\s+/);
    block.textContent = '';
    for (const word of words) {
      const span = document.createElement('span');
      span.className = 'mission-scrub-word';
      span.textContent = word + ' ';
      block.appendChild(span);
    }
    gsap.fromTo(
      block.querySelectorAll('.mission-scrub-word'),
      { opacity: 0.18 },
      {
        opacity: 1,
        stagger: 0.035,
        ease: 'none',
        scrollTrigger: {
          trigger: block,
          start: 'top 82%',
          end: 'bottom 42%',
          scrub: true,
        },
      },
    );
  }

  gsap.utils.toArray('[data-motion="image-scale"]').forEach((element) => {
    gsap.fromTo(
      element,
      { opacity: 0.42, scale: 0.92, y: 28 },
      {
        opacity: 1,
        scale: 1,
        y: 0,
        ease: 'none',
        scrollTrigger: {
          trigger: element,
          start: 'top 90%',
          end: 'bottom 28%',
          scrub: true,
        },
      },
    );
  });
})();
</script>`;
}

function renderThreeSceneScript() {
  return `<script type="module">
import * as THREE from '/vendor/three.module.js';

(() => {
  const canvas = document.getElementById('mission-3d-canvas');
  const frame = document.querySelector('.mission-3d-canvas-frame');
  if (!canvas || !frame) return;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x101826, 6.5, 16);

  const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 80);
  camera.position.set(0, 0.15, 8.7);

  const root = new THREE.Group();
  root.rotation.x = -0.06;
  scene.add(root);

  scene.add(new THREE.AmbientLight(0xffffff, 0.72));
  const key = new THREE.DirectionalLight(0xdbe8ff, 1.4);
  key.position.set(3.8, 4.6, 5.2);
  scene.add(key);

  const sourceColor = new THREE.Color(0xd3a66a);
  const coreColor = new THREE.Color(0x1f6dff);
  const memoryColor = new THREE.Color(0xe8eef7);
  const mutedBlue = new THREE.Color(0x6fa4ff);
  const inkColor = new THREE.Color(0x101826);
  const colorScratch = new THREE.Color();

  const storyOrder = ['swarm', 'contact', 'manim'];
  const fallbackStory = {
    swarm: {
      label: 'Signal field',
      title: 'Signals appear',
      copy: 'Human work enters as separate fibers with direction, weight, and provenance.',
    },
    contact: {
      label: 'Neural braid',
      title: 'Fibers converge',
      copy: 'The strands pull into a shared proof knot instead of orbiting a single toy object.',
    },
    manim: {
      label: 'Memory loom',
      title: 'Memory is woven',
      copy: 'Verified strands settle into a replayable weave operators can inspect later.',
    },
  };

  function seeded(seed) {
    const value = Math.sin(seed * 12.9898) * 43758.5453;
    return value - Math.floor(value);
  }

  function noise(seed) {
    return seeded(seed) * 2 - 1;
  }

  function makeNodeMaterial(color, opacity) {
    return new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
  }

  function makeLineMaterial(opacity) {
    return new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
  }

  function makeTubeMaterial(color, opacity) {
    return new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
  }

  const sourceAnchors = [];
  const memoryAnchors = [];
  const braidAnchors = [];

  for (let i = 0; i < 18; i += 1) {
    const t = i / 17;
    sourceAnchors.push(new THREE.Vector3(-3.9, (t - 0.5) * 3.45, noise(i + 2.1) * 1.15));
  }

  for (let i = 0; i < 16; i += 1) {
    const t = i / 15;
    memoryAnchors.push(new THREE.Vector3(3.55, (t - 0.5) * 2.75 + Math.sin(i * 0.8) * 0.12, noise(i + 9.6) * 0.95));
  }

  for (let i = 0; i < 9; i += 1) {
    const angle = i / 9 * Math.PI * 2;
    braidAnchors.push(new THREE.Vector3(Math.cos(angle) * 0.48, Math.sin(angle) * 0.34, Math.sin(angle * 1.7) * 0.46));
  }

  const dustCount = 720;
  const dustPositions = new Float32Array(dustCount * 3);
  for (let i = 0; i < dustCount; i += 1) {
    dustPositions[i * 3] = noise(i + 17.4) * 5.9;
    dustPositions[i * 3 + 1] = noise(i + 28.9) * 2.8;
    dustPositions[i * 3 + 2] = noise(i + 39.2) * 2.3;
  }
  const dustGeometry = new THREE.BufferGeometry();
  dustGeometry.setAttribute('position', new THREE.BufferAttribute(dustPositions, 3));
  const dust = new THREE.Points(
    dustGeometry,
    new THREE.PointsMaterial({
      color: 0xb8cfff,
      size: 0.012,
      transparent: true,
      opacity: 0.26,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  root.add(dust);

  const strandGroup = new THREE.Group();
  const knotGroup = new THREE.Group();
  const strandPulses = [];
  const strandLines = [];
  const strandNodes = [];
  const strandPulseGeometry = new THREE.SphereGeometry(0.038, 10, 10);
  const strandNodeGeometry = new THREE.SphereGeometry(0.032, 10, 10);

  function addNode(position, zone, scale, color) {
    const node = new THREE.Mesh(strandNodeGeometry, makeNodeMaterial(color, 0.54));
    node.position.copy(position);
    node.scale.setScalar(scale);
    node.userData.zone = zone;
    node.userData.baseScale = scale;
    strandNodes.push(node);
    strandGroup.add(node);
  }

  function applyGradient(geometry, points) {
    const colors = new Float32Array(points.length * 3);
    for (let i = 0; i < points.length; i += 1) {
      const t = i / (points.length - 1);
      if (t < 0.5) colorScratch.lerpColors(sourceColor, coreColor, t * 2);
      else colorScratch.lerpColors(coreColor, memoryColor, (t - 0.5) * 2);
      colors[i * 3] = colorScratch.r;
      colors[i * 3 + 1] = colorScratch.g;
      colors[i * 3 + 2] = colorScratch.b;
    }
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  }

  function makeStrand(index) {
    const source = sourceAnchors[index % sourceAnchors.length];
    const target = memoryAnchors[(index * 7) % memoryAnchors.length];
    const braid = braidAnchors[(index * 5) % braidAnchors.length];
    const lift = noise(index + 61.2) * 0.52;
    const controlPoints = [
      source,
      new THREE.Vector3(-2.75, source.y * 0.78 + lift * 0.15, source.z * 0.74 + noise(index + 4.1) * 0.28),
      new THREE.Vector3(-1.28, braid.y + lift, braid.z + noise(index + 8.4) * 0.46),
      new THREE.Vector3(braid.x, braid.y * 0.55, braid.z),
      new THREE.Vector3(1.38, braid.y - lift * 0.6, braid.z + noise(index + 11.8) * 0.42),
      new THREE.Vector3(2.55, target.y * 0.76 - lift * 0.12, target.z * 0.78),
      target,
    ];
    const curve = new THREE.CatmullRomCurve3(controlPoints, false, 'centripetal', 0.58);
    const samples = curve.getPoints(146);
    const geometry = new THREE.BufferGeometry().setFromPoints(samples);
    applyGradient(geometry, samples);

    const line = new THREE.Line(geometry, makeLineMaterial(0.18 + (index % 5) * 0.026));
    line.userData.baseOpacity = line.material.opacity;
    line.userData.phase = index * 0.29;
    line.userData.zone = index % 3;
    strandLines.push(line);
    strandGroup.add(line);

    if (index % 2 === 0 || index % 7 === 0) {
      const tube = new THREE.Mesh(
        new THREE.TubeGeometry(curve, 96, 0.0065 + (index % 4) * 0.0018, 5, false),
        makeTubeMaterial(index % 4 === 0 ? 0xd3a66a : 0x1f6dff, 0.10 + (index % 3) * 0.025),
      );
      tube.userData.baseOpacity = tube.material.opacity;
      tube.userData.phase = index * 0.34;
      tube.userData.zone = index % 3;
      strandLines.push(tube);
      strandGroup.add(tube);
    }

    const pulse = new THREE.Mesh(strandPulseGeometry, makeNodeMaterial(0xcfe2ff, 0.72));
    pulse.userData.points = samples;
    pulse.userData.speed = 0.052 + (index % 6) * 0.012;
    pulse.userData.offset = (index * 0.083) % 1;
    pulse.userData.zone = index % 3;
    strandPulses.push(pulse);
    strandGroup.add(pulse);

    if (index % 3 === 0) addNode(source, 'source', 1.7, sourceColor);
    if (index % 4 === 0) addNode(braid, 'braid', 2.1, coreColor);
    if (index % 5 === 0) addNode(target, 'memory', 1.8, memoryColor);
  }

  for (let i = 0; i < 44; i += 1) makeStrand(i);

  function makeKnot(index) {
    const points = [];
    const radius = 0.56 + index * 0.055;
    for (let i = 0; i <= 132; i += 1) {
      const t = i / 132 * Math.PI * 2;
      points.push(new THREE.Vector3(
        Math.cos(t * 2 + index * 0.62) * radius * 0.78,
        Math.sin(t * 3 + index * 0.37) * radius * 0.44,
        Math.sin(t * 2.5 + index) * 0.35,
      ));
    }
    const curve = new THREE.CatmullRomCurve3(points, true, 'centripetal', 0.5);
    const samples = curve.getPoints(180);
    const geometry = new THREE.BufferGeometry().setFromPoints(samples);
    applyGradient(geometry, samples);
    const line = new THREE.Line(geometry, makeLineMaterial(0.34));
    line.userData.baseOpacity = line.material.opacity;
    line.userData.phase = index * 0.5;
    strandLines.push(line);
    knotGroup.add(line);

    const tube = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 120, 0.01, 5, true),
      makeTubeMaterial(index % 2 ? 0x1f6dff : 0xe8eef7, 0.18),
    );
    tube.userData.baseOpacity = tube.material.opacity;
    tube.userData.phase = index * 0.45;
    strandLines.push(tube);
    knotGroup.add(tube);
  }

  for (let i = 0; i < 5; i += 1) makeKnot(i);

  root.add(strandGroup);
  root.add(knotGroup);

  const groups = { swarm: strandGroup, contact: knotGroup, manim: strandGroup };
  let activeMode = 'swarm';
  let autoPausedUntil = 0;
  const buttons = Array.from(document.querySelectorAll('[data-3d-mode]'));
  const storyLabel = frame.querySelector('[data-story-label]');
  const storyTitle = frame.querySelector('[data-story-title]');
  const storyCopy = frame.querySelector('[data-story-copy]');

  function activateMode(mode, userInitiated) {
    const nextMode = groups[mode] ? mode : 'swarm';
    activeMode = nextMode;
    frame.dataset["storyMode"] = nextMode;

    const selected = buttons.find((button) => button.dataset["3dMode"] === nextMode);
    for (const button of buttons) button.dataset.active = String(button === selected);

    const data = selected ? {
      label: selected.dataset["storyLabel"],
      title: selected.dataset["storyTitle"],
      copy: selected.dataset["storyCopy"],
    } : fallbackStory[nextMode];

    if (storyLabel) storyLabel.textContent = data.label || fallbackStory[nextMode].label;
    if (storyTitle) storyTitle.textContent = data.title || fallbackStory[nextMode].title;
    if (storyCopy) storyCopy.textContent = data.copy || fallbackStory[nextMode].copy;
    if (userInitiated) autoPausedUntil = performance.now() + 18000;
  }

  for (const button of buttons) {
    button.addEventListener('click', () => {
      activateMode(button.dataset["3dMode"] || 'swarm', true);
    });
  }

  let targetX = -0.16;
  let targetY = 0.28;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let zoom = 8.7;

  canvas.addEventListener('pointerdown', (event) => {
    dragging = true;
    autoPausedUntil = performance.now() + 18000;
    lastX = event.clientX;
    lastY = event.clientY;
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointerup', () => { dragging = false; });
  canvas.addEventListener('pointercancel', () => { dragging = false; });
  canvas.addEventListener('pointermove', (event) => {
    if (!dragging) return;
    targetY += (event.clientX - lastX) * 0.005;
    targetX += (event.clientY - lastY) * 0.005;
    targetX = Math.max(-0.82, Math.min(0.82, targetX));
    lastX = event.clientX;
    lastY = event.clientY;
  });
  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    autoPausedUntil = performance.now() + 18000;
    zoom = Math.max(6.4, Math.min(11.2, zoom + event.deltaY * 0.005));
  }, { passive: false });

  window.setInterval(() => {
    if (performance.now() < autoPausedUntil) return;
    const nextIndex = (storyOrder.indexOf(activeMode) + 1) % storyOrder.length;
    activateMode(storyOrder[nextIndex], false);
  }, 6800);

  function resize() {
    const rect = frame.getBoundingClientRect();
    renderer.setSize(Math.max(1, rect.width), Math.max(1, rect.height), false);
    camera.aspect = Math.max(1, rect.width) / Math.max(1, rect.height);
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  resize();
  activateMode('swarm', false);

  function zoneWeight(zone) {
    if (activeMode === 'swarm') return zone === 0 ? 1.22 : 0.82;
    if (activeMode === 'contact') return zone === 1 ? 1.32 : 0.94;
    return zone === 2 ? 1.24 : 0.88;
  }

  function animate() {
    const elapsed = performance.now() / 1000;
    root.rotation.x += (targetX - root.rotation.x) * 0.05;
    root.rotation.y += (targetY + elapsed * 0.025 - root.rotation.y) * 0.045;
    camera.position.z += (zoom - camera.position.z) * 0.08;

    dust.rotation.y = elapsed * 0.018;
    knotGroup.rotation.x = Math.sin(elapsed * 0.32) * 0.12;
    knotGroup.rotation.y = elapsed * 0.12;
    strandGroup.rotation.z = Math.sin(elapsed * 0.18) * 0.035;

    for (const item of strandLines) {
      const weight = zoneWeight(item.userData.zone || 1);
      item.material.opacity = Math.max(0.04, item.userData.baseOpacity * weight + Math.sin(elapsed * 1.45 + item.userData.phase) * 0.025);
    }

    for (let i = 0; i < strandPulses.length; i += 1) {
      const pulse = strandPulses[i];
      const points = pulse.userData.points;
      const travel = (elapsed * pulse.userData.speed + pulse.userData.offset) % 1;
      const pointIndex = Math.min(points.length - 1, Math.floor(travel * points.length));
      pulse.position.copy(points[pointIndex]);
      pulse.scale.setScalar(0.78 + zoneWeight(pulse.userData.zone) * 0.28);
      pulse.material.opacity = 0.26 + zoneWeight(pulse.userData.zone) * 0.34 + Math.sin(elapsed * 2.1 + i) * 0.08;
    }

    for (let i = 0; i < strandNodes.length; i += 1) {
      const node = strandNodes[i];
      const zone =
        node.userData.zone === 'source' ? 0 :
        node.userData.zone === 'braid' ? 1 :
        2;
      const weight = zoneWeight(zone);
      node.scale.setScalar(node.userData.baseScale * (0.84 + Math.sin(elapsed * 1.7 + i * 0.23) * 0.08 + weight * 0.08));
      node.material.opacity = 0.22 + weight * 0.28;
    }

    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }

  frame.dataset["3dReady"] = 'true';
  window.__flowMemory3DReady = true;
  animate();
})();
</script>`;
}

function renderLiveNetworkMapScript() {
  return `<script type="module">
import * as THREE from '/vendor/three.module.js';

(() => {
  const canvas = document.getElementById('fm-live3d-canvas');
  const stage = canvas ? canvas.closest('.fm-live3d-stage') : null;
  if (!canvas || !stage) return;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x070c12, 7.5, 18);

  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 80);
  camera.position.set(0, 0.18, 10.8);

  const root = new THREE.Group();
  root.rotation.x = -0.08;
  scene.add(root);

  const tdGroup = new THREE.Group();
  const liveGroup = new THREE.Group();
  tdGroup.position.x = -0.08;
  tdGroup.scale.set(0.78, 0.92, 1);
  liveGroup.scale.setScalar(1.24);
  root.add(tdGroup);
  root.add(liveGroup);

  scene.add(new THREE.AmbientLight(0xcbd6e2, 0.86));
  const key = new THREE.DirectionalLight(0xdceaff, 1.55);
  key.position.set(4.2, 5.2, 5.8);
  scene.add(key);
  const brandLight = new THREE.PointLight(0x4a8cff, 1.1, 9);
  brandLight.position.set(4.9, 0.15, 1.8);
  scene.add(brandLight);

  const controls = {
    opacity: 0.18,
    depth: 1.08,
    speed: 1,
    flow: 1,
    fan: true,
    auto: true,
  };

  function seeded(seed) {
    const value = Math.sin(seed * 12.9898) * 43758.5453;
    return value - Math.floor(value);
  }

  function noise(seed) {
    return seeded(seed) * 2 - 1;
  }

  function nodeMaterial(color, opacity) {
    return new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
  }

  function lineMaterial(color, opacity) {
    return new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
  }

  const panelMaterial = new THREE.MeshBasicMaterial({
    color: 0x88a1b6,
    transparent: true,
    opacity: 0.075,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const panelEdgeMaterial = lineMaterial(0xb6cce0, 0.13);
  const gridMaterial = lineMaterial(0x7891a6, 0.12);
  const grayEdgeMaterial = lineMaterial(0xc9d9e8, controls.opacity);
  const brandEdgeMaterial = lineMaterial(0x0052ff, 0.78);
  const liveEdgeMaterial = lineMaterial(0x9fc6e8, 0.36);

  const nodeGeometry = new THREE.SphereGeometry(0.042, 12, 12);
  const brightNodeGeometry = new THREE.SphereGeometry(0.058, 14, 14);
  const pulseGeometry = new THREE.SphereGeometry(0.034, 10, 10);
  const outputRingGeometry = new THREE.TorusGeometry(0.085, 0.012, 8, 28);
  const arrowGeometry = new THREE.ConeGeometry(0.038, 0.13, 3);

  const layerXs = [-4.55, -2.75, -0.92, 0.92, 2.68, 4.22];
  const layerNames = ['Prompt intake', 'Plan field', 'Retrieval field', 'Tool field', 'Verification field', 'Memory field'];
  const layerNodes = [];
  const selectedFan = new THREE.Group();
  const strandBuffers = [];
  const pulses = [];
  const livePulses = [];
  const agentStrandPulses = [];

  function addLineSegments(group, points, material) {
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const line = new THREE.LineSegments(geometry, material);
    group.add(line);
    return line;
  }

  function pushLine(points, a, b) {
    points.push(a.clone(), b.clone());
  }

  function makePanel(x, height, width, seed) {
    const panel = new THREE.Mesh(new THREE.PlaneGeometry(width, height), panelMaterial);
    panel.position.set(x + noise(seed) * 0.08, 0, -0.42 + noise(seed + 1) * 0.2);
    panel.scale.z = 1;
    tdGroup.add(panel);

    const edgePoints = [];
    const left = panel.position.x - width / 2;
    const right = panel.position.x + width / 2;
    const top = height / 2;
    const bottom = -height / 2;
    pushLine(edgePoints, new THREE.Vector3(left, bottom, panel.position.z + 0.01), new THREE.Vector3(left, top, panel.position.z + 0.01));
    pushLine(edgePoints, new THREE.Vector3(right, bottom, panel.position.z + 0.01), new THREE.Vector3(right, top, panel.position.z + 0.01));
    pushLine(edgePoints, new THREE.Vector3(panel.position.x, bottom - 0.28, panel.position.z + 0.02), new THREE.Vector3(panel.position.x, top + 0.28, panel.position.z + 0.02));
    addLineSegments(tdGroup, edgePoints, panelEdgeMaterial);
  }

  function buildGrid() {
    const points = [];
    for (let i = -6; i <= 6; i += 1) {
      pushLine(points, new THREE.Vector3(i, -2.75, -2.4), new THREE.Vector3(i, -2.75, 2.4));
    }
    for (let i = -5; i <= 5; i += 1) {
      pushLine(points, new THREE.Vector3(-6, -2.75, i * 0.46), new THREE.Vector3(6, -2.75, i * 0.46));
    }
    addLineSegments(tdGroup, points, gridMaterial);
  }

  function layerY(index) {
    const t = index / 13;
    return 2.24 - t * 4.48 + Math.sin(index * 0.76) * 0.045;
  }

  function addGlowNode(group, position, color, scale) {
    const core = new THREE.Mesh(nodeGeometry, nodeMaterial(color, 0.92));
    core.position.copy(position);
    core.scale.setScalar(scale || 1);
    group.add(core);
    const halo = new THREE.Mesh(brightNodeGeometry, nodeMaterial(color, 0.13));
    halo.position.copy(position);
    halo.scale.setScalar((scale || 1) * 2.2);
    group.add(halo);
    return core;
  }

  for (let layer = 0; layer < layerXs.length; layer += 1) {
    makePanel(layerXs[layer], 4.86, 0.82 + (layer % 2) * 0.12, layer + 21);
    const nodes = [];
    for (let i = 0; i < 14; i += 1) {
      const p = new THREE.Vector3(layerXs[layer] + noise(layer * 31 + i) * 0.045, layerY(i), noise(layer * 44 + i) * 0.64);
      nodes.push(p);
      addGlowNode(tdGroup, p, 0xddeaf6, 0.9 + (i % 3) * 0.08);
    }
    layerNodes.push(nodes);
  }

  const evidenceOut = new THREE.Vector3(5.62, 0.0, 0.22);
  const outputGuide = [
    new THREE.Vector3(5.56, 1.66, -0.08),
    evidenceOut,
    new THREE.Vector3(5.56, -1.66, -0.08),
  ];
  for (const point of outputGuide) {
    const ring = new THREE.Mesh(outputRingGeometry, nodeMaterial(0x0052ff, 0.96));
    ring.position.copy(point);
    ring.rotation.y = Math.PI / 2;
    selectedFan.add(ring);
  }
  addGlowNode(selectedFan, evidenceOut, 0x0052ff, 1.45);

  for (let i = 0; i < 9; i += 1) {
    const arrow = new THREE.Mesh(arrowGeometry, nodeMaterial(0x0052ff, 0.62));
    arrow.position.set(5.28 + (i % 3) * 0.18, -1.45 + i * 0.36, -0.22 + noise(i + 8) * 0.45);
    arrow.rotation.z = -Math.PI / 2;
    selectedFan.add(arrow);
  }

  function curvedPoint(a, b, edgeIndex, step, steps, selected) {
    const t = step / (steps - 1);
    const bend = Math.sin(t * Math.PI);
    const p = new THREE.Vector3().lerpVectors(a, b, t);
    const phase = edgeIndex * 0.173 + step * 0.37;
    p.y += bend * noise(edgeIndex + 2.3) * (selected ? 0.16 : 0.24);
    p.z += bend * (noise(edgeIndex + 9.1) * (selected ? 0.52 : 0.86) + Math.sin(t * Math.PI * 2 + phase) * 0.12);
    return p;
  }

  function makeAnimatedSegments(edgePairs, selected) {
    const steps = selected ? 34 : 22;
    const positions = [];
    const bases = [];
    const waves = [];
    const amps = [];
    let edgeIndex = 0;

    for (const pair of edgePairs) {
      let prev = curvedPoint(pair[0], pair[1], edgeIndex, 0, steps, selected);
      for (let step = 1; step < steps; step += 1) {
        const current = curvedPoint(pair[0], pair[1], edgeIndex, step, steps, selected);
        for (const point of [prev, current]) {
          positions.push(point.x, point.y, point.z);
          bases.push(point.x, point.y, point.z);
          waves.push(edgeIndex * 0.19 + step * 0.29);
          amps.push((selected ? 0.045 : 0.028) + seeded(edgeIndex + step) * 0.02);
        }
        prev = current;
      }
      edgeIndex += 1;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
    const material = selected ? brandEdgeMaterial : grayEdgeMaterial;
    const segments = new THREE.LineSegments(geometry, material);
    segments.userData.base = new Float32Array(bases);
    segments.userData.wave = new Float32Array(waves);
    segments.userData.amp = new Float32Array(amps);
    strandBuffers.push(segments);
    return segments;
  }

  const grayPairs = [];
  for (let layer = 0; layer < layerNodes.length - 1; layer += 1) {
    for (let a = 0; a < 14; a += 1) {
      for (let b = 0; b < 14; b += 1) {
        grayPairs.push([layerNodes[layer][a], layerNodes[layer + 1][b]]);
      }
    }
  }
  tdGroup.add(makeAnimatedSegments(grayPairs, false));

  const selectedPairs = [];
  for (let i = 0; i < 14; i += 1) {
    selectedPairs.push([layerNodes[layerNodes.length - 1][i], evidenceOut]);
    const pulse = new THREE.Mesh(pulseGeometry, nodeMaterial(0x0052ff, 0.88));
    pulse.userData.from = layerNodes[layerNodes.length - 1][i];
    pulse.userData.to = evidenceOut;
    pulse.userData.offset = i / 14;
    pulses.push(pulse);
    selectedFan.add(pulse);
  }
  selectedFan.add(makeAnimatedSegments(selectedPairs, true));
  tdGroup.add(selectedFan);
  buildGrid();

  function buildLiveMap() {
    const clusters = [
      { label: 'Agents', color: 0x8ab8ff, angle: -0.35, radius: 2.8 },
      { label: 'Memory', color: 0x0052ff, angle: 0.9, radius: 2.4 },
      { label: 'Learning', color: 0xf1bd76, angle: 2.15, radius: 2.55 },
      { label: 'Proof', color: 0xb9d0e6, angle: 3.35, radius: 2.7 },
      { label: 'Safety', color: 0x8fe0c2, angle: 4.55, radius: 2.35 },
    ];
    const core = new THREE.Vector3(0, 0, 0);
    addGlowNode(liveGroup, core, 0xe9f5ff, 2.25);
    const connectionPoints = [];
    for (let i = 0; i < clusters.length; i += 1) {
      const cluster = clusters[i];
      const p = new THREE.Vector3(Math.cos(cluster.angle) * cluster.radius, Math.sin(cluster.angle) * 1.46, Math.sin(cluster.angle * 1.4) * 1.35);
      connectionPoints.push(p);
      addGlowNode(liveGroup, p, cluster.color, 1.48);

      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.43, 0.007, 8, 58), nodeMaterial(cluster.color, 0.25));
      ring.position.copy(p);
      ring.rotation.x = 1.25 + i * 0.18;
      ring.rotation.y = 0.6;
      liveGroup.add(ring);

      const localPoints = [];
      for (let n = 0; n < 8; n += 1) {
        const angle = (n / 8) * Math.PI * 2;
        const child = new THREE.Vector3(
          p.x + Math.cos(angle) * (0.64 + seeded(i * 10 + n) * 0.18),
          p.y + Math.sin(angle) * 0.42,
          p.z + Math.sin(angle * 1.7 + i) * 0.36,
        );
        localPoints.push(child);
        addGlowNode(liveGroup, child, cluster.color, 0.58);
      }

      const spokes = [];
      for (const child of localPoints) pushLine(spokes, p, child);
      addLineSegments(liveGroup, spokes, lineMaterial(cluster.color, 0.28));

      const pulse = new THREE.Mesh(pulseGeometry, nodeMaterial(cluster.color, 0.86));
      pulse.userData.from = core;
      pulse.userData.to = p;
      pulse.userData.offset = i / clusters.length;
      livePulses.push(pulse);
      liveGroup.add(pulse);
    }

    const edges = [];
    for (const point of connectionPoints) pushLine(edges, core, point);
    for (let i = 0; i < connectionPoints.length; i += 1) {
      pushLine(edges, connectionPoints[i], connectionPoints[(i + 1) % connectionPoints.length]);
    }
    liveGroup.add(addLineSegments(new THREE.Group(), edges, liveEdgeMaterial));
  }

  buildLiveMap();
  liveGroup.visible = false;

  function addAgentStrand(detail = {}) {
    const index = agentStrandPulses.length;
    const source = new THREE.Vector3(-5.38, 2.36 - (index % 8) * 0.46, 0.92 + noise(index + 41) * 0.44);
    const first = layerNodes[0][(index * 3) % 14];
    const middle = layerNodes[2][(index * 5 + 2) % 14];
    const memory = layerNodes[layerNodes.length - 1][(index * 7 + 4) % 14];
    const target = new THREE.Vector3(evidenceOut.x, evidenceOut.y + noise(index + 9) * 0.18, evidenceOut.z + noise(index + 18) * 0.22);
    const controlPoints = [
      source,
      new THREE.Vector3(first.x - 0.22, first.y + 0.2, first.z + 0.5),
      middle,
      new THREE.Vector3(memory.x + 0.24, memory.y, memory.z - 0.28),
      target,
    ];
    const curve = new THREE.CatmullRomCurve3(controlPoints, false, 'centripetal', 0.55);
    const points = curve.getPoints(130);
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(points),
      lineMaterial(0xf1bd76, 0.54),
    );
    line.userData.agentId = detail.agent_id || 'agent-' + index;
    tdGroup.add(line);
    addGlowNode(tdGroup, source, 0xf1bd76, 1.22);

    const pulse = new THREE.Mesh(pulseGeometry, nodeMaterial(0xf1bd76, 0.92));
    pulse.userData.points = points;
    pulse.userData.offset = (index * 0.17) % 1;
    pulse.userData.agentId = line.userData.agentId;
    agentStrandPulses.push(pulse);
    tdGroup.add(pulse);
    stage.dataset.agentStrands = String(agentStrandPulses.length);
    setMode('td');
    return line.userData.agentId;
  }

  function storedAgentStrands() {
    try {
      return JSON.parse(localStorage.getItem('flowmemory:agent-strands') || '[]');
    } catch {
      return [];
    }
  }

  const modeButtons = Array.from(document.querySelectorAll('[data-fm-live-mode]'));
  const toggle = document.querySelector('[data-fm-live-panel-toggle]');
  const controlPanel = document.querySelector('.fm-live3d-controls');
  const readoutKicker = document.querySelector('[data-fm-live-readout-kicker]');
  const readoutTitle = document.querySelector('[data-fm-live-readout-title]');
  const readoutCopy = document.querySelector('[data-fm-live-readout-copy]');
  const inputs = Object.fromEntries(Array.from(document.querySelectorAll('[data-fm-live-control]')).map((input) => [input.dataset.fmLiveControl, input]));

  const readouts = {
    td: ['TouchDesigner network', 'Evidence path highlighted', '85 nodes, 994 individual connections, and 14 selected evidence edges are rendered as a layered neural map.'],
    map: ['Live Network Map', 'Operational clusters online', 'Agents, memory, learning, proof, and safety are separated into a live 3D topology for real-time telemetry.'],
  };

  let activeMode = 'td';
  let targetX = -0.08;
  let targetY = 0.0;
  let zoom = 10.8;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;

  function setMode(mode) {
    activeMode = mode === 'map' ? 'map' : 'td';
    tdGroup.visible = activeMode === 'td';
    liveGroup.visible = activeMode === 'map';
    stage.dataset.fmLiveModeActive = activeMode;
    for (const button of modeButtons) {
      const selected = button.dataset.fmLiveMode === activeMode;
      button.setAttribute('aria-pressed', selected ? 'true' : 'false');
    }
    const copy = readouts[activeMode];
    if (readoutKicker) readoutKicker.textContent = copy[0];
    if (readoutTitle) readoutTitle.textContent = copy[1];
    if (readoutCopy) readoutCopy.textContent = copy[2];
    zoom = activeMode === 'map' ? 7.7 : 10.8;
    targetX = activeMode === 'map' ? -0.16 : -0.08;
  }

  function syncControls() {
    if (inputs.opacity) controls.opacity = Number(inputs.opacity.value || controls.opacity);
    if (inputs.depth) controls.depth = Number(inputs.depth.value || controls.depth);
    if (inputs.speed) controls.speed = Number(inputs.speed.value || controls.speed);
    if (inputs.flow) controls.flow = Number(inputs.flow.value || controls.flow);
    if (inputs.fan) controls.fan = Boolean(inputs.fan.checked);
    if (inputs.auto) controls.auto = Boolean(inputs.auto.checked);
    grayEdgeMaterial.opacity = controls.opacity;
    brandEdgeMaterial.opacity = controls.fan ? 0.78 : 0;
    selectedFan.visible = controls.fan;
    root.scale.z += (controls.depth - root.scale.z) * 0.18;
  }

  for (const button of modeButtons) {
    button.addEventListener('click', () => setMode(button.dataset.fmLiveMode));
  }
  for (const input of Object.values(inputs)) {
    input.addEventListener('input', syncControls);
    input.addEventListener('change', syncControls);
  }
  if (toggle && controlPanel) {
    toggle.addEventListener('click', () => {
      const next = controlPanel.dataset.open !== 'true';
      controlPanel.dataset.open = next ? 'true' : 'false';
      toggle.setAttribute('aria-expanded', next ? 'true' : 'false');
    });
  }

  canvas.addEventListener('pointerdown', (event) => {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointerup', () => { dragging = false; });
  canvas.addEventListener('pointerleave', () => { dragging = false; });
  canvas.addEventListener('pointermove', (event) => {
    if (!dragging) return;
    targetY += (event.clientX - lastX) * 0.006;
    targetX += (event.clientY - lastY) * 0.006;
    targetX = Math.max(-0.9, Math.min(0.9, targetX));
    lastX = event.clientX;
    lastY = event.clientY;
  });
  canvas.addEventListener('wheel', (event) => {
    event.preventDefault();
    zoom = Math.max(6.8, Math.min(13.8, zoom + event.deltaY * 0.006));
  }, { passive: false });

  function updateAnimatedSegments(elapsed) {
    for (const segments of strandBuffers) {
      const attr = segments.geometry.attributes.position;
      const positions = attr.array;
      const base = segments.userData.base;
      const wave = segments.userData.wave;
      const amp = segments.userData.amp;
      for (let i = 0; i < positions.length / 3; i += 1) {
        const offset = Math.sin(elapsed * 1.72 * controls.flow + wave[i]) * amp[i] * controls.flow;
        positions[i * 3] = base[i * 3];
        positions[i * 3 + 1] = base[i * 3 + 1] + offset * 0.72;
        positions[i * 3 + 2] = base[i * 3 + 2] + Math.cos(elapsed * 1.24 * controls.flow + wave[i]) * amp[i] * 0.92;
      }
      attr.needsUpdate = true;
    }
  }

  function movePulse(pulse, elapsed, index, live) {
    const t = (elapsed * (live ? 0.22 : 0.36) * controls.speed + pulse.userData.offset) % 1;
    const from = pulse.userData.from;
    const to = pulse.userData.to;
    pulse.position.lerpVectors(from, to, t);
    const bend = Math.sin(t * Math.PI);
    pulse.position.z += bend * (live ? 0.5 : 0.28) * Math.sin(elapsed + index);
    pulse.scale.setScalar((live ? 1.15 : 0.95) + Math.sin(elapsed * 2 + index) * 0.18);
  }

  function resize() {
    const rect = stage.getBoundingClientRect();
    renderer.setSize(Math.max(1, rect.width), Math.max(1, rect.height), false);
    camera.aspect = Math.max(1, rect.width) / Math.max(1, rect.height);
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  resize();
  syncControls();
  setMode('td');
  try {
    window.flowMemoryAddAgentStrand = addAgentStrand;
  } catch {
    // The Codex in-app browser freezes window extensions; the event bridge below remains active.
  }
  window.addEventListener('flowmemory:agent-created', (event) => {
    addAgentStrand(event.detail || {});
  });
  for (const detail of storedAgentStrands().slice(-5)) addAgentStrand(detail);

  function animate() {
    const elapsed = performance.now() / 1000;
    syncControls();
    const drift = controls.auto ? elapsed * (activeMode === 'td' ? 0.035 : 0.08) : 0;
    root.rotation.x += (targetX - root.rotation.x) * 0.055;
    root.rotation.y += (targetY + drift - root.rotation.y) * 0.05;
    camera.position.z += (zoom - camera.position.z) * 0.08;
    tdGroup.rotation.z = Math.sin(elapsed * 0.18) * 0.018;
    liveGroup.rotation.x = Math.sin(elapsed * 0.27) * 0.12;

    updateAnimatedSegments(elapsed);
    for (let i = 0; i < pulses.length; i += 1) movePulse(pulses[i], elapsed, i, false);
    for (let i = 0; i < livePulses.length; i += 1) movePulse(livePulses[i], elapsed, i, true);
    for (let i = 0; i < agentStrandPulses.length; i += 1) {
      const pulse = agentStrandPulses[i];
      const points = pulse.userData.points || [];
      const travel = (elapsed * 0.42 * controls.speed + pulse.userData.offset) % 1;
      const pointIndex = Math.min(points.length - 1, Math.floor(travel * points.length));
      if (points[pointIndex]) pulse.position.copy(points[pointIndex]);
      pulse.scale.setScalar(1 + Math.sin(elapsed * 2.1 + i) * 0.18);
    }

    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }

  stage.dataset.ready = 'true';
  try {
    window.__flowMemoryLive3DReady = true;
  } catch {
    // Dataset readiness is the source of truth when globals cannot be added.
  }
  animate();
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
  <main class="mission-control-page mission-control-taste-redesign" data-mode="${text(state?.provenance || 'replay')}">
    <header class="mission-brand-nav" aria-label="Flow Memory Mission Control navigation">
      <a class="mission-brand" href="/mission-control" aria-label="Flow Memory Mission Control home">
        <span class="mission-brand-orb" aria-hidden="true"></span>
        <span>FlowMemory Mission Control</span>
      </a>
      <nav aria-label="Mission Control sections">
        <a href="#neural-memory-field">Memory Field</a>
        <a href="#live-3d">Live 3D</a>
        <a href="#runs">Runs</a>
        <a href="#agent-builder">Agent Builder</a>
        <a href="#replay">Replay</a>
        <a href="#genesis">Genesis</a>
        <a href="#touchdesigner-ideas">Ideas</a>
        <a href="#proof">Proof</a>
      </nav>
      <div class="fm-nav-actions">
        <a class="mission-status-pill" href="#finalizer"><i></i>Public alpha ready</a>
        <a class="fm-nav-icon" href="#proof" aria-label="Notifications"></a>
        <a class="fm-nav-avatar" href="#genesis" aria-label="Agent profile"></a>
      </div>
    </header>

    <section class="mission-control-hero mission-hero-simple-3d" aria-labelledby="mission-control-title">
      <div class="mission-hero-copy">
        <p class="mission-kicker">Mission Control</p>
        <h1 id="mission-control-title">Operate the memory network.</h1>
        <p class="mission-hero-lede">FlowMemory turns agent activity into replayable, verifiable memory while keeping private payloads, model data, and approvals in the right places.</p>
        <p class="fm-hidden-proof">Human compute becomes memory</p>
        <div class="mission-hero-actions">
          <a class="mission-button mission-button-primary" href="#live-3d">Open live map</a>
          <a class="mission-button mission-button-ghost" href="#runs">Review runs</a>
        </div>
        ${renderHeroHighlights()}
      </div>
      ${renderInteractive3DHero(embodimentPayload)}
    </section>

    ${renderMissionCommandDeck(state, embodimentPayload, finalizer)}
    ${renderTopNeuralMemoryField(state, embodimentPayload)}
    ${renderTouchDesignerIdeaLab()}
    ${renderReferenceStatusBar()}
    ${renderSafeLiveApiPanel()}
    ${renderReferenceAgentBuilderPanel(payloads['agent-builder'] || {})}
    ${renderReferenceRunSelector(payloads)}
    ${renderReferenceReplaySummary(payloads)}
    ${renderReferenceCognitionPanel(payloads['predictive-cognitive-core'] || {})}
    ${renderReferenceLearningPanel(payloads['predictive-learning-benchmark'] || {})}
    ${renderReferenceGenesisPanel(payloads['agent-genesis-onboarding'] || {})}
    ${renderReferenceGenesisCreateFlow(payloads['agent-genesis-onboarding'] || {})}
    ${renderReferenceAgentInternetPanel(payloads['agent-internet-skill-network'] || {})}
    ${renderReferenceByokOnchainPanel(payloads['byok-onchain-upgrades'] || {})}
    ${renderReferenceProofPanel(payloads['experience-graph-proof-of-learning'] || {})}
    ${renderReferenceEmbodimentPanel(embodimentPayload)}
    ${renderReferenceLive3DPanel(embodimentPayload, state)}
    ${renderReferenceFinalizerStatus(finalizer)}
    ${renderActionFooter()}
  </main>
  <script src="/vendor/gsap.min.js"></script>
  <script src="/vendor/ScrollTrigger.min.js"></script>
  <script type="module" src="/vendor/three.module.js"></script>
  ${renderGenesisCreateScript()}
  ${renderMotionScript()}
  ${renderThreeSceneScript()}
  ${renderLiveNetworkMapScript()}
</body>
</html>`;
}

export function dashboardHtml() {
  const payloads = Object.fromEntries(fixtureSpecs.map((spec) => [spec.fixture_id, readFixture(spec)]));
  const finalizer = readProjectJson('release_evidence/public_alpha_launch_finalizer.json');
  return renderMissionControlHtml(payloads, finalizer);
}

export function createMissionControlDevServer() {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url || '/', `http://${req.headers.host || '127.0.0.1'}`);
    if (req.method === 'POST' && url.pathname === '/genesis/birth') {
      try {
        const payload = await readRequestJson(req);
        sendJson(res, 200, { ok: true, data: runGenesisBirth(payload) });
      } catch (error) {
        sendJson(res, 400, { ok: false, error: error instanceof Error ? error.message : String(error) });
      }
      return;
    }
    if (req.method === 'POST' && url.pathname === '/agent-builder/birth') {
      try {
        const payload = await readRequestJson(req);
        sendJson(res, 200, { ok: true, data: runAgentBuilderBirth(payload) });
      } catch (error) {
        sendJson(res, 400, { ok: false, error: error instanceof Error ? error.message : String(error) });
      }
      return;
    }
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      send(res, 405, 'application/json', JSON.stringify({ ok: false, error: 'method_not_allowed' }));
      return;
    }
    if (url.pathname === '/agent-builder/defaults') {
      const agentBuilderSpec = fixtureSpecs.find((spec) => spec.fixture_id === 'agent-builder');
      sendJson(res, 200, { ok: true, data: agentBuilderSpec ? readFixture(agentBuilderSpec) : {} });
      return;
    }
    if (url.pathname === '/' || url.pathname === '/mission-control' || url.pathname === '/agent-genesis/create' || url.pathname === '/agents/new') {
      send(res, 200, 'text/html; charset=utf-8', dashboardHtml());
      return;
    }
    if (url.pathname.startsWith('/vendor/')) {
      const name = path.basename(url.pathname);
      const filePath = vendorScripts.get(name);
      if (!filePath || !fs.existsSync(filePath)) {
        send(res, 404, 'application/json', JSON.stringify({ ok: false, error: 'vendor_asset_not_found' }));
        return;
      }
      send(res, 200, 'application/javascript; charset=utf-8', fs.readFileSync(filePath));
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
    if (url.pathname === '/experience-graph') {
      send(res, 200, 'application/json', JSON.stringify(readFixture(fixtureSpecs.find((spec) => spec.fixture_id === 'experience-graph-proof-of-learning'))));
      return;
    }
    if (url.pathname === '/proof-of-learning') {
      const payload = readFixture(fixtureSpecs.find((spec) => spec.fixture_id === 'experience-graph-proof-of-learning'));
      send(res, 200, 'application/json', JSON.stringify({ ok: Boolean(payload?.ok), proofs: payload?.proof_ledger?.proofs || [], count: payload?.proof_ledger?.proof_count || 0, private_payload_excluded: true }));
      return;
    }
    if (url.pathname === '/learning-reputation') {
      const payload = readFixture(fixtureSpecs.find((spec) => spec.fixture_id === 'experience-graph-proof-of-learning'));
      send(res, 200, 'application/json', JSON.stringify({ ok: Boolean(payload?.ok), reputations: payload?.reputation?.reputations || [], count: payload?.reputation?.agent_count || 0, private_payload_excluded: true }));
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
