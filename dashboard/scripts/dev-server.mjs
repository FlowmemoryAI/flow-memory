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
    ['play', 'Replay what happened', 'Step through any run and see exactly how it unfolded.'],
    ['shield', 'Prove what changed', 'Cryptographic proof and GPU evidence you can trust.'],
    ['brain', 'Learn from every run', 'Memory gets smarter so every run makes the next better.'],
  ];
  return `<div class="fm-hero-highlights">${cards.map(([kind, title, copy]) => `
    <article>
      ${renderReferenceIcon(kind)}
      <strong>${text(title)}</strong>
      <p>${text(copy)}</p>
    </article>`).join('')}</div>`;
}

function renderReferenceRunSelector(payloads) {
  const runCards = [
    ['rocket', 'Live Neural Agent Launch', 'See how an agent starts, remembers, and acts.', 'live-neural-agent-launch'],
    ['book', 'Proof of Learning', 'See how a prediction becomes reusable experience.', 'experience-graph-proof-of-learning'],
    ['sprout', 'Agent Genesis', 'Create and launch a supervised agent.', 'agent-genesis-onboarding'],
    ['network', 'Agent Internet', 'Find collaborators by skills, policy, reputation, and dry-run rails.', 'agent-internet-skill-network'],
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
        <div><span class="fm-ready"><i></i>${loaded ? 'Ready' : 'Replay'}</span><a href="#${fixture === 'local-network-replay' ? 'replay' : fixture === 'agent-genesis-onboarding' ? 'genesis' : fixture === 'agent-internet-skill-network' ? 'internet' : fixture === 'predictive-learning-benchmark' ? 'learning' : fixture === 'experience-graph-proof-of-learning' ? 'proof' : 'live-3d'}">Open</a></div>
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
        <aside>
          <strong>Inspired by protocol-grade Forge flows</strong>
          <p>Nookplot gates creation behind wallet/Forge beta. Flow Memory keeps first-agent creation easier: private-by-default, supervised, and local artifacts only.</p>
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
  return `
    <section id="live-3d" class="fm-section fm-live3d-section live-3d-mode-panel mission-surface mission-surface-wide" aria-label="Mission Control Live 3D Mode" data-live-3d-mode="ready" data-source="${text(state?.provenance || 'replay')}" data-gpu="${text(embodiment.gpu_evidence_status)}">
      <div class="fm-section-heading"><span>Live 3D Mode · Mission Control Live 3D Mode</span><h2>Live network map</h2><p>Explore what is happening in the AI network right now.</p></div>
      <div class="fm-live3d-layout">
        <aside class="fm-live-checks">
          ${['3D view ready', 'GPU verified', 'Replay loaded', 'Network synced'].map((item) => `<article>${renderReferenceIcon('check')}<strong>${item}</strong><small>${item === 'GPU verified' ? 'Acceleration active' : item === 'Replay loaded' ? 'Latest session ready' : item === 'Network synced' ? 'All systems aligned' : 'Visualization engine online'}</small></article>`).join('')}
        </aside>
        <article class="fm-network-map">
          ${['Agents', 'Memory', 'Learning', 'Proof', 'Safety'].map((label, index) => `<div class="fm-cluster fm-cluster-${index}"><span>${label}</span><i></i><b></b><b></b><b></b><b></b></div>`).join('')}
          <div class="fm-map-legend"><span>Agents</span><span>Memory</span><span>Learning</span><span>Proof</span><span>Safety</span></div>
          <a class="fm-primary-wide" href="#live-3d">Start live view</a>
        </article>
        <aside class="fm-side-card fm-selected-component"><h3>Selected component</h3>${renderReferenceIcon('memory')}<p>Selected <strong>Memory Cluster</strong></p><dl><div><dt>Used by</dt><dd>12 agents</dd></div><div><dt>Last updated</dt><dd>23 seconds ago</dd></div><div><dt>Status</dt><dd><span class="fm-ready"><i></i>Healthy</span></dd></div></dl><div class="fm-mini-network is-large"><i></i><i></i><i></i><i></i><b></b></div></aside>
      </div>
      <p class="fm-hidden-proof">GPU evidence verified · Local neural embodiment, rendered as a read-only 3D operations mode.</p>
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
      '<a href="#genesis-' + escape(payload.agent_id || '') + '">Open in Mission Control</a>';
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
      renderSuccess(envelope.data || envelope);
    } catch (error) {
      renderError(error);
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
        <a href="#cognition">Cognition</a>
        <a href="#learning">Learning</a>
        <a href="#genesis">Genesis</a>
        <a href="#internet">Internet</a>
        <a href="#proof">Proof</a>
        <a href="#embodiment">Embodiment</a>
        <a href="#live-3d">Live 3D</a>
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
        <h1 id="mission-control-title">Human compute becomes <em>memory</em>.</h1>
        <p class="mission-hero-lede">FlowMemory turns agent activity into replayable, verifiable memory.</p>
        <p class="fm-hidden-proof">Human compute becomes memory</p>
        <div class="mission-hero-actions">
          <a class="mission-button mission-button-primary" href="#runs">Explore a run</a>
          <a class="mission-button mission-button-ghost" href="#proof">See proof</a>
        </div>
        ${renderHeroHighlights()}
      </div>
      ${renderInteractive3DHero(embodimentPayload)}
    </section>

    ${renderReferenceStatusBar()}
    ${renderSafeLiveApiPanel()}
    ${renderReferenceRunSelector(payloads)}
    ${renderReferenceReplaySummary(payloads)}
    ${renderReferenceCognitionPanel(payloads['predictive-cognitive-core'] || {})}
    ${renderReferenceLearningPanel(payloads['predictive-learning-benchmark'] || {})}
    ${renderReferenceGenesisPanel(payloads['agent-genesis-onboarding'] || {})}
    ${renderReferenceGenesisCreateFlow(payloads['agent-genesis-onboarding'] || {})}
    ${renderReferenceAgentInternetPanel(payloads['agent-internet-skill-network'] || {})}
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
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      send(res, 405, 'application/json', JSON.stringify({ ok: false, error: 'method_not_allowed' }));
      return;
    }
    if (url.pathname === '/' || url.pathname === '/mission-control' || url.pathname === '/agent-genesis/create') {
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
