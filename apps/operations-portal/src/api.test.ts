import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "./api";

describe("ApiClient", () => {
  it("adds bearer auth and idempotency keys to workflow submissions", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ id: "w1" }), { status: 201 }));
    await new ApiClient({ token: "secret", baseUrls: { orchestrator: "https://orch.test" } }).submitWorkflow({ policy_id: "p" });
    const [, init] = fetchMock.mock.calls[0]; const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer secret");
    expect(headers.get("Idempotency-Key")).toBeTruthy();
    fetchMock.mockRestore();
  });
  it("turns API failures into safe typed errors", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Not found" }), { status: 404, headers: { "x-request-id": "r1" } }));
    await expect(new ApiClient().getWorkflow("missing")).rejects.toMatchObject({ status: 404, message: "Not found", requestId: "r1" });
    fetchMock.mockRestore();
  });
});
