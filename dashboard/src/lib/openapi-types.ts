export type FlowMemoryEndpoint = {
  method: "GET" | "POST";
  path: string;
  scope?: string;
};

export const flowMemoryEndpoints: FlowMemoryEndpoint[] = [
  { method: "GET", path: "/health" },
  { method: "POST", path: "/flowlang/run" },
  { method: "GET", path: "/visual/state", scope: "visual:read" },
  { method: "GET", path: "/visual/events", scope: "visual:read" },
  { method: "POST", path: "/network/run-scenario", scope: "network:run" },
  { method: "GET", path: "/dashboard/snapshot", scope: "dashboard:read" },
];
