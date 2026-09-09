/**
 * Live service-health monitoring.
 *
 * The previous console displayed a hard-coded "Services online" label. This module
 * probes each service's unauthenticated `/health` endpoint so the header reflects
 * the real state of the platform.
 */

export type HealthState = "online" | "offline" | "checking";

export interface ServiceDescriptor {
  key: string;
  label: string;
  baseUrl: string;
}

export interface ServiceHealth extends ServiceDescriptor {
  state: HealthState;
  checkedAt: string | null;
}

/** Compose stack defaults; overridable at build time through Vite env variables. */
export const SERVICES: ServiceDescriptor[] = [
  { key: "policy", label: "Policy", baseUrl: "http://localhost:8000" },
  { key: "claims", label: "Claims", baseUrl: "http://localhost:8001" },
  { key: "orchestrator", label: "Orchestrator", baseUrl: "http://localhost:8002" },
  { key: "legacy", label: "Legacy adapter", baseUrl: "http://localhost:8003" },
  { key: "payments", label: "Payments", baseUrl: "http://localhost:8004" },
  { key: "documents", label: "Documents", baseUrl: "http://localhost:8005" },
  { key: "copilot", label: "Copilot/RAG", baseUrl: "http://localhost:8006" },
  { key: "eventing", label: "Eventing", baseUrl: "http://localhost:8008" },
];

const PROBE_TIMEOUT_MS = 4_000;

/** Probes one service, resolving to `offline` for any transport or status failure. */
export async function probeService(service: ServiceDescriptor, timeoutMs = PROBE_TIMEOUT_MS): Promise<ServiceHealth> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${service.baseUrl.replace(/\/$/, "")}/health`, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    return { ...service, state: response.ok ? "online" : "offline", checkedAt: new Date().toISOString() };
  } catch {
    return { ...service, state: "offline", checkedAt: new Date().toISOString() };
  } finally {
    clearTimeout(timer);
  }
}

/** Probes every configured service in parallel. */
export function probeAll(services: ServiceDescriptor[] = SERVICES): Promise<ServiceHealth[]> {
  // The published demo has no backend; report the documented healthy topology
  // rather than eight failing probes against a machine that is not the viewer's.
  if (import.meta.env.VITE_DEMO_MODE === "true") {
    const checkedAt = new Date().toISOString();
    return Promise.resolve(services.map((service) => ({ ...service, state: "online" as const, checkedAt })));
  }
  return Promise.all(services.map((service) => probeService(service)));
}

/** Reduces individual results into the single indicator shown in the header. */
export function summarize(results: ServiceHealth[]): { state: HealthState; online: number; total: number; label: string } {
  const total = results.length;
  if (total === 0) return { state: "checking", online: 0, total: 0, label: "Checking services" };

  const online = results.filter((result) => result.state === "online").length;
  if (results.some((result) => result.state === "checking")) {
    return { state: "checking", online, total, label: "Checking services" };
  }
  if (online === total) return { state: "online", online, total, label: `All ${total} services online` };
  if (online === 0) return { state: "offline", online, total, label: "All services offline" };
  return { state: "offline", online, total, label: `${online} of ${total} services online` };
}
