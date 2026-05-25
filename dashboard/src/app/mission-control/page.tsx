import "../../styles/mission-control.css";
import replay from "../../mock-data/local-network-replay.json";
import liveLaunchReplay from "../../mock-data/live-neural-agent-launch.json";
import liveOperationsReplay from "../../mock-data/live-agent-operations.json";
import liveSupervisorReplay from "../../mock-data/live-agent-supervisor.json";
import liveEmbodimentReplay from "../../mock-data/live-neural-embodiment.json";
import type { NeuralEmbodimentPayload, VisualNetworkState } from "../../lib/visual-state";
import { summarizeVisualState } from "../../lib/visual-state";
import { modeLabel, missionControlModes, missionControlEndpoints } from "../../lib/mission-control-config";
import { modeStatus, modeSwitchOptions } from "../../lib/event-stream";
import { MissionControlCanvas } from "../../components/mission-control/MissionControlCanvas";
import { AgentDetailDrawer } from "../../components/mission-control/AgentDetailDrawer";
import { NetworkLegend } from "../../components/mission-control/NetworkLegend";
import { ReplayControls } from "../../components/mission-control/ReplayControls";
import { RunSelector } from "../../components/mission-control/RunSelector";
import { NeuralEmbodimentPanel } from "../../components/mission-control/NeuralEmbodimentPanel";
import { AgentPanel } from "../../components/panels/AgentPanel";
import { NeuralPanel } from "../../components/panels/NeuralPanel";
import { EconomyPanel } from "../../components/panels/EconomyPanel";
import { RLPanel } from "../../components/panels/RLPanel";
import { AuditPanel } from "../../components/panels/AuditPanel";
import { RuntimePanel } from "../../components/panels/RuntimePanel";

export default function MissionControlPage() {
  const state = replay.state as VisualNetworkState;
  const status = modeStatus({ mode: state.provenance === "live" ? "live" : "replay", baseUrl: "http://127.0.0.1:8765", replayPath: "local-network-replay.json" }, state.provenance === "live");
  return (
    <main className="mission-control-page" data-mode={state.provenance}>
      <header className="mission-control-hero">
        <div>
          <p>The Human Compute Network</p>
          <h1>Flow Memory Mission Control</h1>
          <span>{summarizeVisualState(state)}</span>
        </div>
        <aside className="mode-switcher" aria-label="Mission Control mode switcher">
          <strong>{status.label}</strong>
          <small>{status.description}</small>
          <div>{modeSwitchOptions().map((option) => <button key={option.mode} type="button" data-active={option.mode === status.mode}>{option.label}</button>)}</div>
        </aside>
      </header>
      <section className="mission-control-endpoints">
        <strong>{modeLabel(state.provenance === "live" ? "live" : "replay")}</strong>
        <span>Modes: {missionControlModes.map(modeLabel).join(" / ")}</span>
        <span>Live endpoints: {missionControlEndpoints.filter((endpoint) => endpoint.mode === "live").map((endpoint) => endpoint.path).join(", ")}</span>
      </section>
      <RunSelector payloads={{
        "live-neural-agent-launch": liveLaunchReplay,
        "live-agent-operations": liveOperationsReplay,
        "live-agent-supervisor": liveSupervisorReplay,
        "local-network-replay": replay,
        "live-neural-embodiment": liveEmbodimentReplay,
      }} />
      <MissionControlCanvas state={state} />
      <ReplayControls state={state} events={replay.events} />
      <AgentDetailDrawer agent={state.agents[0]} state={state} />
      <NetworkLegend />
      <NeuralEmbodimentPanel payload={liveEmbodimentReplay as NeuralEmbodimentPayload} />
      <section className="mission-control-panels">
        <RuntimePanel state={state} />
        <AgentPanel state={state} />
        <NeuralPanel state={state} />
        <EconomyPanel state={state} />
        <RLPanel state={state} />
        <AuditPanel state={state} />
      </section>
    </main>
  );
}
