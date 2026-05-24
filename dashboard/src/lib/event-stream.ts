import type { MissionControlMode } from "./mission-control-config";

export type StreamDescriptor = {
  mode: MissionControlMode;
  baseUrl: string;
  replayPath?: string;
  lastRefresh?: string;
  error?: string;
};

export type ModeStatus = {
  mode: MissionControlMode;
  label: string;
  description: string;
  connected: boolean;
};

export function describeStream(stream: StreamDescriptor): string {
  if (stream.mode === "live") {
    return stream.error
      ? `Local API disconnected: ${stream.error}`
      : `Live Local API polling ${stream.baseUrl}/visual/state and ${stream.baseUrl}/visual/events`;
  }
  if (stream.mode === "replay") {
    return `Replay mode: ${stream.replayPath ?? "local-network-replay.json"} with deterministic event playback. Local API disconnected by design.`;
  }
  return "Mock mode: synthetic fallback data is clearly labeled. Local API disconnected by design.";
}

export function modeStatus(stream: StreamDescriptor, liveReachable: boolean): ModeStatus {
  if (stream.mode === "live") {
    return {
      mode: "live",
      label: liveReachable ? "Live Local API" : "Local API disconnected",
      description: liveReachable ? describeStream(stream) : "Local API disconnected. Start scripts/run_local_api_server.py to enable live mode.",
      connected: liveReachable,
    };
  }
  if (stream.mode === "replay") {
    return { mode: "replay", label: "Replay artifact", description: describeStream(stream), connected: true };
  }
  return { mode: "mock", label: "Mock fallback", description: describeStream(stream), connected: true };
}

export function modeSwitchOptions(): { mode: MissionControlMode; label: string; description: string }[] {
  return [
    { mode: "mock", label: "Mock", description: "clearly labeled synthetic fallback" },
    { mode: "replay", label: "Replay", description: "deterministic local-network replay" },
    { mode: "live", label: "Live Local API", description: "poll /visual/state and /visual/events" },
  ];
}

export function localApiDisconnectedState(baseUrl = "http://127.0.0.1:8765"): ModeStatus {
  return modeStatus({ mode: "live", baseUrl, error: "offline" }, false);
}
