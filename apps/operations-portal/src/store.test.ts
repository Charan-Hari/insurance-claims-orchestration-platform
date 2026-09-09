import { describe, expect, it } from "vitest";
import { WorkflowHistory, type HistoryStorage } from "./store";
import { sampleWorkflows } from "./sample-data";
import type { Workflow } from "./api";

/** In-memory storage double so tests never depend on a real browser. */
class MemoryStorage implements HistoryStorage {
  private readonly values = new Map<string, string>();
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
}

function workflow(id: string, overrides: Partial<Workflow> = {}): Workflow {
  return {
    id,
    policy_id: "e7318d9f-22eb-4cdb-9c79-a0cf8b963720",
    policyholder_id: "11111111-1111-1111-1111-111111111111",
    state: "completed",
    claim_id: "caad1319-94c8-4a8a-b689-70e49171f9d4",
    failure_category: null,
    retry_count: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    steps: [{ name: "policy_verification", state: "succeeded" }],
    ...overrides,
  };
}

describe("WorkflowHistory", () => {
  it("always exposes sample records so history is never empty", () => {
    expect(new WorkflowHistory(new MemoryStorage()).all().length).toBe(sampleWorkflows.length);
  });

  it("persists live workflows newest first and deduplicates by id", () => {
    const storage = new MemoryStorage();
    const history = new WorkflowHistory(storage);
    history.record(workflow("a"));
    history.record(workflow("b"));
    history.record(workflow("a", { state: "reconciliation_required" }));

    expect(history.liveEntries().map((entry) => entry.id)).toEqual(["a", "b"]);
    expect(history.find("a")?.state).toBe("reconciliation_required");
    expect(new WorkflowHistory(storage).liveEntries()).toHaveLength(2);
  });

  it("ignores corrupt persisted history instead of failing to load", () => {
    const storage = new MemoryStorage();
    storage.setItem("operations-portal.workflow-history.v1", "{not json");
    expect(new WorkflowHistory(storage).liveEntries()).toEqual([]);
  });

  it("aggregates dashboard metrics across live and sample records", () => {
    const history = new WorkflowHistory(new MemoryStorage());
    history.record(workflow("live-1", { state: "reconciliation_required", retry_count: 3 }));
    const metrics = history.metrics();

    expect(metrics.total).toBe(sampleWorkflows.length + 1);
    expect(metrics.reconciliation).toBeGreaterThanOrEqual(2);
    expect(metrics.retries).toBeGreaterThanOrEqual(3);
  });

  it("clears live entries while keeping sample records available", () => {
    const history = new WorkflowHistory(new MemoryStorage());
    history.record(workflow("live-1"));
    history.clear();

    expect(history.liveEntries()).toEqual([]);
    expect(history.all()).toHaveLength(sampleWorkflows.length);
  });
});
