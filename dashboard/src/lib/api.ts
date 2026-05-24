import type { VisualNetworkState } from "./visual-state";

export const localApiBaseUrl = "http://127.0.0.1:8765";

export const visualApiEndpoints = {
  visualState: "/visual/state",
  visualEvents: "/visual/events",
  visualSchema: "/visual/schema",
  networkState: "/network/state",
  networkRunScenario: "/network/run-scenario",
  visualReplayStart: "/visual/replay/start",
} as const;

export type VisualApiResult<T> = {
  ok: boolean;
  data?: T;
  error?: string;
  disconnected?: boolean;
};

export function buildLocalApiUrl(path: string, baseUrl = localApiBaseUrl): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${baseUrl.replace(/\/$/, "")}${normalized}`;
}

export async function fetchVisualState(baseUrl = localApiBaseUrl): Promise<VisualApiResult<{ state: VisualNetworkState }>> {
  return fetchJson(buildLocalApiUrl(visualApiEndpoints.visualState, baseUrl));
}

export async function fetchVisualEvents(baseUrl = localApiBaseUrl): Promise<VisualApiResult<{ events: unknown[] }>> {
  return fetchJson(buildLocalApiUrl(visualApiEndpoints.visualEvents, baseUrl));
}

export async function runNetworkScenario(scenario = "all", baseUrl = localApiBaseUrl): Promise<VisualApiResult<unknown>> {
  return fetchJson(buildLocalApiUrl(visualApiEndpoints.networkRunScenario, baseUrl), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ scenario, emit_visual_events: true }),
  });
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<VisualApiResult<T>> {
  try {
    const response = await fetch(url, init);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) return { ok: false, error: body?.error?.message ?? `HTTP ${response.status}` };
    return { ok: true, data: body?.data ?? body };
  } catch (error) {
    return { ok: false, disconnected: true, error: error instanceof Error ? error.message : "Local API disconnected" };
  }
}
