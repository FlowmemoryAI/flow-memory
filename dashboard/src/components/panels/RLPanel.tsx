import type { VisualNetworkState } from "../../lib/visual-state";

export function RLPanel({ state }: { state: VisualNetworkState }) {
  const episode = state.rl[0];
  return (
    <section className="panel panel-rl">
      <header><span>RL Arena</span><strong>{state.rl.length}</strong></header>
      {episode ? (
        <dl>
          <div><dt>Environment</dt><dd>{episode.env_id}</dd></div>
          <div><dt>Episode</dt><dd>{episode.episode_id}</dd></div>
          <div><dt>Policy</dt><dd>{episode.policy}</dd></div>
          <div><dt>Reward</dt><dd>{episode.mean_reward.toFixed(2)}</dd></div>
          <div><dt>Success</dt><dd>{(episode.success_rate * 100).toFixed(0)}%</dd></div>
          <div><dt>Safety violations</dt><dd>{(episode.safety_violation_rate * 100).toFixed(0)}%</dd></div>
        </dl>
      ) : <p>No RL episode in this visual state.</p>}
    </section>
  );
}
