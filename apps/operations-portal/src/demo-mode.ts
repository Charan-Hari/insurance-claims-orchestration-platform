/**
 * Public demo mode.
 *
 * The Operations Console normally drives eight live services over HTTP. For the
 * published GitHub Pages build there is no backend, so this module simulates the
 * orchestrator's saga semantics locally: services report healthy, and submitted
 * workflows resolve through the same state machine the real orchestrator uses
 * (policy verification -> claim submission, with failure classification).
 *
 * Enabled at build time with VITE_DEMO_MODE=true. It is never active in the
 * Compose or Codespace runtime, so the real integration path is unaffected.
 */

import type { Workflow } from "./api";
import { DEMO_POLICYHOLDER_ID } from "./sample-data";

export const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

/** Latency band used to make the simulated saga feel like a real network call. */
const SIMULATED_LATENCY_MS = 900;

function uuid(): string {
  return crypto.randomUUID();
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Mirrors the orchestrator's failure taxonomy so the demo exercises the same
 * reconciliation and retry affordances an operator sees against live services.
 */
function classify(policyId: string): { state: Workflow["state"]; category: string | null } {
  const normalised = policyId.trim().toLowerCase();
  if (normalised.endsWith("0000")) {
    return { state: "reconciliation_required", category: "downstream_unavailable" };
  }
  if (normalised.endsWith("ffff")) {
    return { state: "failed", category: "policy_not_active" };
  }
  return { state: "completed", category: null };
}

/** Produces a workflow that matches the orchestrator's response contract. */
export async function simulateWorkflow(
  input: Record<string, unknown>,
  latencyMs = SIMULATED_LATENCY_MS,
): Promise<Workflow> {
  await delay(latencyMs);

  const policyId = String(input.policy_id ?? "");
  const { state, category } = classify(policyId);
  const now = new Date().toISOString();
  const succeeded = state === "completed";

  return {
    id: uuid(),
    policy_id: policyId,
    policyholder_id: String(input.policyholder_id ?? DEMO_POLICYHOLDER_ID),
    state,
    claim_id: succeeded ? uuid() : null,
    failure_category: category,
    retry_count: 0,
    created_at: now,
    updated_at: now,
    steps: [
      {
        name: "policy_verification",
        state: state === "failed" ? "failed" : "succeeded",
        error_category: state === "failed" ? category : null,
        started_at: now,
        completed_at: now,
      },
      {
        name: "claim_submission",
        state: succeeded ? "succeeded" : state === "failed" ? "skipped" : "failed",
        error_category: state === "reconciliation_required" ? category : null,
        started_at: state === "failed" ? null : now,
        completed_at: state === "failed" ? null : now,
      },
    ],
  };
}

/** Retrying a reconciliation-required workflow resolves it, as the real saga does. */
export async function simulateRetry(workflow: Workflow, latencyMs = SIMULATED_LATENCY_MS): Promise<Workflow> {
  await delay(latencyMs);
  const now = new Date().toISOString();

  return {
    ...workflow,
    state: "completed",
    claim_id: workflow.claim_id ?? uuid(),
    failure_category: null,
    retry_count: workflow.retry_count + 1,
    updated_at: now,
    steps: workflow.steps.map((step) => ({
      ...step,
      state: "succeeded",
      error_category: null,
      completed_at: now,
    })),
  };
}
