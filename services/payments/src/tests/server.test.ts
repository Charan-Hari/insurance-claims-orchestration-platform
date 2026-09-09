import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { server, closeStore } from "../server.js";

let base: string;
before(async () => await new Promise<void>(resolve => server.listen(0, "127.0.0.1", () => { const address = server.address(); base = `http://127.0.0.1:${typeof address === "object" && address ? address.port : 0}`; resolve(); })));
after(async () => { closeStore(); await new Promise<void>(resolve => server.close(() => resolve())); });

test("authorizes and replays an idempotent request", async () => {
  const request = { amount: 1250, currency: "USD", paymentMethodToken: "tok_local" };
  const first = await fetch(`${base}/v1/payments/authorize`, { method: "POST", headers: { "content-type": "application/json", "idempotency-key": "test-authorize" }, body: JSON.stringify(request) });
  const second = await fetch(`${base}/v1/payments/authorize`, { method: "POST", headers: { "content-type": "application/json", "idempotency-key": "test-authorize" }, body: JSON.stringify(request) });
  assert.equal(first.status, 200); assert.deepEqual(await first.json(), await second.json());
});
test("rejects idempotency key reuse with another payload", async () => {
  const response = await fetch(`${base}/v1/payments/authorize`, { method: "POST", headers: { "content-type": "application/json", "idempotency-key": "test-authorize" }, body: JSON.stringify({ amount: 1, currency: "USD", paymentMethodToken: "tok_other" }) });
  assert.equal(response.status, 409);
});
test("declines deterministic mock token and exposes readiness", async () => {
  const response = await fetch(`${base}/v1/payments/authorize`, { method: "POST", headers: { "content-type": "application/json", "idempotency-key": "decline-test" }, body: JSON.stringify({ amount: 100, currency: "USD", paymentMethodToken: "tok_decline" }) });
  assert.equal(response.status, 402); assert.equal((await response.json()).status, "declined");
  assert.equal((await fetch(`${base}/ready`)).status, 200);
});
