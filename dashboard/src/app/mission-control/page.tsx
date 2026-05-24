import replay from "../../mock-data/local-network-replay.json";
import type { VisualNetworkState } from "../../lib/visual-state";
import { summarizeVisualState } from "../../lib/visual-state";
import { MissionControlCanvas } from "../../components/mission-control/MissionControlCanvas";
import { AgentDetailDrawer } from "../../components/mission-control/AgentDetailDrawer";
import { NetworkLegend } from "../../components/mission-control/NetworkLegend";
import { AgentPanel } from "../../components/panels/AgentPanel";
import { NeuralPanel } from "../../components/panels/NeuralPanel";
import { EconomyPanel } from "../../components/panels/EconomyPanel";
import { RLPanel } from "../../components/panels/RLPanel";
import { AuditPanel } from "../../components/panels/AuditPanel";
import { RuntimePanel } from "../../components/panels/RuntimePanel";

export default function MissionControlPage() {
  const state = replay.state as VisualNetworkState;
  return (
    <main className="mission-control-page" data-mode={state.provenance}>
      <header>
        <p>The Human Compute Network</p>
        <h1>Flow Memory Mission Control</h1>
        <span>{summarizeVisualState(state)}</span>
      </header>
      <MissionControlCanvas state={state} />
      <AgentDetailDrawer agent={state.agents[0]} />
      <NetworkLegend />
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
