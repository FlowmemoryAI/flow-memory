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
          <strong>Neural loom</strong>
          <span>Strings of work converge into memory</span>
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
        <a href="#proof">Proof</a>
        <a href="#embodiment">Embodiment</a>
        <a href="#live-3d">Live 3D</a>
      </nav>
      <a class="mission-status-pill" href="#finalizer">Public alpha ready</a>
    </header>

    <section class="mission-control-hero mission-hero-simple-3d" aria-labelledby="mission-control-title">
      <div class="mission-hero-copy">
        <p class="mission-kicker">FlowMemory / Human Compute Network</p>
        <h1 id="mission-control-title">Human compute becomes memory.</h1>
        <p class="mission-hero-lede">Run swarms, proof meshes, and geometric traces locally in the browser.</p>
        <div class="mission-hero-actions">
          <a class="mission-button mission-button-primary" href="#runs">Inspect runs <span aria-hidden="true">→</span></a>
          <a class="mission-button mission-button-ghost" href="#live-3d">View evidence</a>
        </div>
      </div>
      ${renderInteractive3DHero(embodimentPayload)}
    </section>

    ${renderSafeLiveApiPanel()}
    ${renderRunSelector(payloads)}
    <div class="mission-stack-grid">
      ${renderReplaySummary(payloads)}
      ${renderFinalizerStatus(finalizer)}
    </div>
    ${renderPredictiveCognitionPanel(payloads['predictive-cognitive-core'] || {})}
    ${renderPredictiveLearningPanel(payloads['predictive-learning-benchmark'] || {})}
    ${renderAgentGenesisPanel(payloads['agent-genesis-onboarding'] || {})}
    ${renderProofOfLearningPanel(payloads['experience-graph-proof-of-learning'] || {})}
    ${renderEmbodimentPanel(embodimentPayload)}
    ${renderLive3DPanel(embodimentPayload, state)}
    ${renderActionFooter()}
  </main>
  <script src="/vendor/gsap.min.js"></script>
  <script src="/vendor/ScrollTrigger.min.js"></script>
  <script type="module" src="/vendor/three.module.js"></script>
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
