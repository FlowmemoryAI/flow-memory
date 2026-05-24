import replay from "../../mock-data/local-network-replay.json";

export default function RLArenaPage() {
  return <main><h1>RL Arena</h1><pre>{JSON.stringify(replay.state.rl, null, 2)}</pre></main>;
}
