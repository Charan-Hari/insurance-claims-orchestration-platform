import { describe, expect, it } from "vitest";
import { simulateRetry, simulateWorkflow } from "./demo-mode";

const BASE = {
  policyholder_id: "11111111-1111-1111-1111-111111111111",
  claim_amount: "1250.00",
  incident_date: "2026-09-01",
  description: "Water damage",
};

describe("simulateWorkflow", () => {
  it("completes and issues a claim id for an ordinary policy", async () => {
    const workflow = await simulateWorkflow({ ...BASE, policy_id: "e7318d9f-22eb-4cdb-9c79-a0cf8b963720" }, 0);

    expect(workflow.state).toBe("completed");
    expect(workflow.claim_id).toBeTruthy();
    expect(workflow.failure_category).toBeNull();
    expect(workflow.steps.every((step) => step.state === "succeeded")).toBe(true);
  });

  it("routes the reconciliation trigger to reconciliation_required", async () => {
    const workflow = await simulateWorkflow({ ...BASE, policy_id: "e7318d9f-22eb-4cdb-9c79-a0cf8b960000" }, 0);

    expect(workflow.state).toBe("reconciliation_required");
    expect(workflow.failure_category).toBe("downstream_unavailable");
    expect(workflow.claim_id).toBeNull();
    expect(workflow.steps[0].state).toBe("succeeded");
    expect(workflow.steps[1].state).toBe("failed");
  });

  it("fails before claim submission when the policy is not active", async () => {
    const workflow = await simulateWorkflow({ ...BASE, policy_id: "e7318d9f-22eb-4cdb-9c79-a0cf8b96ffff" }, 0);

    expect(workflow.state).toBe("failed");
    expect(workflow.failure_category).toBe("policy_not_active");
    expect(workflow.steps[0].state).toBe("failed");
    expect(workflow.steps[1].state).toBe("skipped");
  });

  it("produces a distinct id per submission", async () => {
    const first = await simulateWorkflow({ ...BASE, policy_id: "a1" }, 0);
    const second = await simulateWorkflow({ ...BASE, policy_id: "a1" }, 0);

    expect(first.id).not.toBe(second.id);
  });
});

describe("simulateRetry", () => {
  it("resolves a reconciliation-required workflow and increments the retry count", async () => {
    const failed = await simulateWorkflow({ ...BASE, policy_id: "e7318d9f-22eb-4cdb-9c79-a0cf8b960000" }, 0);
    const retried = await simulateRetry(failed, 0);

    expect(retried.id).toBe(failed.id);
    expect(retried.state).toBe("completed");
    expect(retried.retry_count).toBe(failed.retry_count + 1);
    expect(retried.failure_category).toBeNull();
    expect(retried.claim_id).toBeTruthy();
    expect(retried.steps.every((step) => step.state === "succeeded")).toBe(true);
  });
});
