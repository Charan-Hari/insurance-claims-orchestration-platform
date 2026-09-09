import { describe, expect, it, vi } from "vitest";
import { escapeHtml, formatCurrency, humanize, relativeTime, shortId, toneFor } from "./format";
import { probeService, summarize, type ServiceHealth } from "./health";
import { filterWorkflows, recordsView } from "./views";
import type { Workflow } from "./api";

describe("formatting helpers", () => {
  it("escapes HTML so rendered values cannot inject markup", () => {
    expect(escapeHtml(`<img src=x onerror="alert(1)">`)).toBe("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
  });

  it("humanizes snake-case domain states", () => {
    expect(humanize("reconciliation_required")).toBe("Reconciliation required");
  });

  it("formats currency and falls back for unusable values", () => {
    expect(formatCurrency("1250.5")).toBe("$1,250.50");
    expect(formatCurrency(null)).toBe("—");
  });

  it("renders compact relative times", () => {
    const now = Date.now();
    expect(relativeTime(new Date(now - 5_000).toISOString(), now)).toBe("just now");
    expect(relativeTime(new Date(now - 7_200_000).toISOString(), now)).toBe("2h ago");
  });

  it("shortens long identifiers only", () => {
    expect(shortId("e7318d9f-22eb-4cdb-9c79-a0cf8b963720")).toBe("e7318d9f…3720");
    expect(shortId("short")).toBe("short");
  });

  it("maps domain states onto badge tones", () => {
    expect(toneFor("completed")).toBe("positive");
    expect(toneFor("reconciliation_required")).toBe("negative");
    expect(toneFor("pending")).toBe("warning");
  });
});

describe("service health", () => {
  const descriptor = { key: "policy", label: "Policy", baseUrl: "http://policy.test" };

  it("marks a service online when /health responds successfully", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
    await expect(probeService(descriptor)).resolves.toMatchObject({ state: "online" });
    expect(fetchMock.mock.calls[0][0]).toBe("http://policy.test/health");
    fetchMock.mockRestore();
  });

  it("treats transport failures as offline rather than throwing", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("connection refused"));
    await expect(probeService(descriptor)).resolves.toMatchObject({ state: "offline" });
    fetchMock.mockRestore();
  });

  it("summarizes partial availability for the header indicator", () => {
    const results: ServiceHealth[] = [
      { ...descriptor, state: "online", checkedAt: null },
      { ...descriptor, key: "claims", state: "offline", checkedAt: null },
    ];
    expect(summarize(results)).toMatchObject({ state: "offline", label: "1 of 2 services online" });
    expect(summarize([results[0]])).toMatchObject({ state: "online", label: "All 1 services online" });
  });
});

describe("history filtering", () => {
  const entries = [
    { id: "aaa", state: "completed", policy_id: "p1", claim_id: "c1", failure_category: null },
    { id: "bbb", state: "reconciliation_required", policy_id: "p2", claim_id: null, failure_category: "downstream_unavailable" },
  ] as Workflow[];

  it("returns everything for an empty query", () => {
    expect(filterWorkflows(entries, "  ")).toHaveLength(2);
  });

  it("matches identifiers, state, and failure category case-insensitively", () => {
    expect(filterWorkflows(entries, "RECONCILIATION")).toHaveLength(1);
    expect(filterWorkflows(entries, "c1")).toHaveLength(1);
    expect(filterWorkflows(entries, "nothing")).toHaveLength(0);
  });
});

describe("recordsView claim identifiers", () => {
  const base = {
    holder: "11111111-1111-4111-8111-111111111111",
    loading: false,
    policies: [],
    usingSamples: false,
  };
  const claim = {
    id: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
    policy_id: "11111111-1111-4111-8111-111111111111",
    claim_reference: "CLM-2026-004100",
    description: "Water damage",
    incident_date: "2026-01-04",
    claim_amount: 4200,
    status: "approved",
    created_at: "2026-01-05T10:00:00Z",
    updated_at: "2026-01-05T10:00:00Z",
  };

  it("renders the human-facing reference rather than the raw UUID", () => {
    const html = recordsView({ ...base, claims: [claim] } as never);
    expect(html).toContain("CLM-2026-004100");
    expect(html).not.toContain(">aaaaaaaa<");
  });

  it("keeps the UUID available as a tooltip for support lookups", () => {
    const html = recordsView({ ...base, claims: [claim] } as never);
    expect(html).toContain(`title="${claim.id}"`);
  });

  it("falls back to a shortened UUID when no reference exists", () => {
    const { claim_reference: _omitted, ...legacy } = claim;
    const html = recordsView({ ...base, claims: [legacy] } as never);
    expect(html).toContain("aaaaaaaa");
  });
});

