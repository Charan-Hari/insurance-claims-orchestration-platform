import type { Workflow } from "./api";
import { type SampleWorkflow, sampleWorkflows } from "./sample-data";

/**
 * Workflow history persistence.
 *
 * Live workflows submitted from the console are retained in `localStorage` so an
 * operator keeps their recent working set across reloads. Bundled sample records
 * are always appended so the history view is never empty on a fresh environment.
 */

const STORAGE_KEY = "operations-portal.workflow-history.v1";
const MAX_LIVE_ENTRIES = 40;

/** Minimal storage surface so tests can supply an in-memory implementation. */
export interface HistoryStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function isWorkflow(value: unknown): value is Workflow {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<Workflow>;
  return typeof candidate.id === "string" && typeof candidate.state === "string" && Array.isArray(candidate.steps);
}

/** Resolves the browser storage, tolerating environments where access throws. */
function defaultStorage(): HistoryStorage | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

export class WorkflowHistory {
  private live: Workflow[] = [];

  constructor(private readonly storage: HistoryStorage | null = defaultStorage()) {
    this.live = this.read();
  }

  private read(): Workflow[] {
    if (!this.storage) return [];
    try {
      const parsed: unknown = JSON.parse(this.storage.getItem(STORAGE_KEY) ?? "[]");
      return Array.isArray(parsed) ? parsed.filter(isWorkflow) : [];
    } catch {
      // Corrupt or unreadable history must never block the console from loading.
      return [];
    }
  }

  private write(): void {
    if (!this.storage) return;
    try {
      this.storage.setItem(STORAGE_KEY, JSON.stringify(this.live));
    } catch {
      // Quota or privacy-mode failures degrade to in-memory history only.
    }
  }

  /** Inserts or updates a workflow, keeping the newest entries first. */
  record(workflow: Workflow): void {
    this.live = [workflow, ...this.live.filter((entry) => entry.id !== workflow.id)].slice(0, MAX_LIVE_ENTRIES);
    this.write();
  }

  /** Live workflows only, newest first. */
  liveEntries(): Workflow[] {
    return [...this.live];
  }

  /** Live workflows followed by bundled samples, so history always has content. */
  all(): Array<Workflow | SampleWorkflow> {
    const liveIds = new Set(this.live.map((entry) => entry.id));
    return [...this.live, ...sampleWorkflows.filter((entry) => !liveIds.has(entry.id))];
  }

  /** Looks up a workflow across both live and sample records. */
  find(id: string): Workflow | SampleWorkflow | undefined {
    return this.all().find((entry) => entry.id === id);
  }

  /** Aggregated counters backing the dashboard summary cards. */
  metrics() {
    const entries = this.all();
    return {
      total: entries.length,
      completed: entries.filter((entry) => entry.state === "completed").length,
      inFlight: entries.filter((entry) => entry.state === "running" || entry.state === "pending").length,
      reconciliation: entries.filter((entry) => entry.state === "reconciliation_required" || entry.state === "failed").length,
      retries: entries.reduce((total, entry) => total + (entry.retry_count ?? 0), 0),
    };
  }

  /** Clears live history; bundled sample records remain available. */
  clear(): void {
    this.live = [];
    this.write();
  }
}
