import { createHash, randomUUID } from "node:crypto";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { IdempotencyStore } from "./store.js";
import { log } from "./logger.js";
import { MockPaymentProvider } from "./provider.js";
import type { Operation, PaymentRequest, PaymentResponse } from "./types.js";

const provider = new MockPaymentProvider();
const store = new IdempotencyStore();
const validOperations = new Set<Operation>(["authorize", "capture", "refund"]);

function send(res: ServerResponse, status: number, body: unknown, requestId: string) {
  res.writeHead(status, { "content-type": "application/json", "x-request-id": requestId });
  res.end(JSON.stringify(body));
}
async function body(req: IncomingMessage): Promise<unknown> {
  let text = "";
  for await (const chunk of req) text += chunk;
  return JSON.parse(text || "{}");
}
function hash(value: unknown): string { return createHash("sha256").update(JSON.stringify(value)).digest("hex"); }

export const server = createServer(async (req, res) => {
  const requestId = typeof req.headers["x-request-id"] === "string" ? req.headers["x-request-id"] : randomUUID();
  const path = req.url?.split("?")[0] ?? "/";
  try {
    if (req.method === "GET" && path === "/health") return send(res, 200, { status: "ok" }, requestId);
    if (req.method === "GET" && path === "/ready") return send(res, 200, { status: "ready" }, requestId);
    const match = path.match(/^\/v1\/payments\/(authorize|capture|refund)$/);
    if (req.method !== "POST" || !match) return send(res, 404, { error: "not_found", requestId }, requestId);
    const operation = match[1] as Operation;
    const key = req.headers["idempotency-key"];
    if (typeof key !== "string" || key.length < 1 || key.length > 255) return send(res, 400, { error: "idempotency_key_required", requestId }, requestId);
    const input = await body(req) as Partial<PaymentRequest>;
    if (typeof input.amount !== "number" || !Number.isInteger(input.amount) || input.amount <= 0 || typeof input.currency !== "string" || !/^[A-Z]{3}$/.test(input.currency) ||
        (operation === "authorize" && typeof input.paymentMethodToken !== "string") ||
        (operation !== "authorize" && typeof input.paymentId !== "string")) {
      return send(res, 400, { error: "invalid_request", requestId }, requestId);
    }
    const paymentInput = input as PaymentRequest;
    const requestHash = hash(paymentInput);
    const existing = store.get(operation, key, requestHash);
    if (existing === "conflict") return send(res, 409, { error: "idempotency_key_reused", requestId }, requestId);
    if (existing) return send(res, 200, existing, requestId);
    const result = await provider[operation](paymentInput);
    const response: PaymentResponse = { ...result, requestId };
    store.save(operation, key, requestHash, response);
    log("info", "payment_operation", { requestId, operation, paymentId: response.paymentId, status: response.status });
    return send(res, response.status === "declined" ? 402 : 200, response, requestId);
  } catch (error) {
    log("error", "request_failed", { requestId, error: error instanceof Error ? error.message : "unknown" });
    return send(res, 500, { error: "internal_error", requestId }, requestId);
  }
});

export function closeStore(): void { store.close(); }
