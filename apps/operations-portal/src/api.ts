export type ServiceName = "policy" | "claims" | "orchestrator" | "legacy" | "payments";
export interface ApiConfig { baseUrls?: Partial<Record<ServiceName, string>>; token?: string; timeoutMs?: number; }
export interface Policy { id: string; policyholder_id: string; coverage_type: string; coverage_limits: Record<string, unknown>; effective_date: string; expiry_date: string; status: string; premium_amount?: string | number | null; created_at: string; updated_at: string; }
export interface Claim { id: string; claim_reference?: string; policy_id: string; policyholder_id: string; claim_amount: string | number; incident_date: string; description: string; adjuster_notes?: string | null; status: string; created_at: string; updated_at: string; }
export interface WorkflowStep { name: string; state: string; error_category?: string | null; started_at?: string | null; completed_at?: string | null; }
export interface Workflow { id: string; policy_id: string; policyholder_id: string; state: string; claim_id?: string | null; failure_category?: string | null; retry_count: number; created_at: string; updated_at: string; steps: WorkflowStep[]; }
export interface LegacyClaim { id: string; source_system: string; legacy_claim_id: string; policy_number?: string | null; policyholder_id?: string | null; claim_amount: string | number; incident_date: string; description: string; status: string; raw_payload: Record<string, unknown>; received_at: string; updated_at: string; }
export interface Payment { paymentId: string; operation: string; status: string; amount: number; currency: string; providerReference: string; requestId: string; }

const defaults: Record<ServiceName, string> = {
  policy: "http://localhost:8000", claims: "http://localhost:8001", orchestrator: "http://localhost:8002",
  legacy: "http://localhost:8003", payments: "http://localhost:8004"
};

export class ApiError extends Error {
  constructor(public readonly status: number, message: string, public readonly requestId?: string) { super(message); this.name = "ApiError"; }
}

export class ApiClient {
  private readonly urls: Record<ServiceName, string>;
  private readonly timeoutMs: number;
  constructor(private readonly config: ApiConfig = {}) {
    this.urls = { ...defaults, ...config.baseUrls };
    this.timeoutMs = config.timeoutMs ?? 12_000;
  }
  private async request<T>(service: ServiceName, path: string, init: RequestInit = {}, idempotent = false): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body) headers.set("Content-Type", "application/json");
    if (this.config.token) headers.set("Authorization", `Bearer ${this.config.token}`);
    if (idempotent && !headers.has("Idempotency-Key")) headers.set("Idempotency-Key", crypto.randomUUID());
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(`${this.urls[service].replace(/\/$/, "")}${path}`, { ...init, headers, signal: controller.signal });
      const requestId = response.headers.get("x-request-id") ?? undefined;
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new ApiError(response.status, body?.detail ?? body?.error ?? `Request failed (${response.status})`, requestId);
      return body as T;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw new ApiError(408, "Request timed out");
      throw error;
    } finally { clearTimeout(timer); }
  }
  getPolicy(id: string) { return this.request<Policy>("policy", `/policies/${encodeURIComponent(id)}`); }
  listPolicies(holderId: string) { return this.request<Policy[]>("policy", `/policyholders/${encodeURIComponent(holderId)}/policies`); }
  getClaim(id: string) { return this.request<Claim>("claims", `/claims/${encodeURIComponent(id)}`); }
  listClaims(holderId: string) { return this.request<Claim[]>("claims", `/policyholders/${encodeURIComponent(holderId)}/claims`); }
  submitWorkflow(input: Record<string, unknown>) { return this.request<Workflow>("orchestrator", "/workflows/claims", { method: "POST", body: JSON.stringify(input) }, true); }
  getWorkflow(id: string) { return this.request<Workflow>("orchestrator", `/workflows/${encodeURIComponent(id)}`); }
  retryWorkflow(id: string) { return this.request<Workflow>("orchestrator", `/workflows/${encodeURIComponent(id)}/retry`, { method: "POST" }); }
  ingestLegacy(input: Record<string, unknown>) { return this.request<LegacyClaim>("legacy", "/legacy/claims", { method: "POST", body: JSON.stringify(input) }, true); }
  authorizePayment(input: Record<string, unknown>) { return this.request<Payment>("payments", "/v1/payments/authorize", { method: "POST", body: JSON.stringify(input) }, true); }
  capturePayment(input: Record<string, unknown>) { return this.request<Payment>("payments", "/v1/payments/capture", { method: "POST", body: JSON.stringify(input) }, true); }
  refundPayment(input: Record<string, unknown>) { return this.request<Payment>("payments", "/v1/payments/refund", { method: "POST", body: JSON.stringify(input) }, true); }
}
