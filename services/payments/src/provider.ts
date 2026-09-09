import { randomUUID } from "node:crypto";
import type { PaymentProvider, PaymentRequest, PaymentResponse } from "./types.js";

/** Deterministic provider: tokens containing "decline" are declined. */
export class MockPaymentProvider implements PaymentProvider {
  private result(operation: PaymentResponse["operation"], input: PaymentRequest, status: PaymentResponse["status"]) {
    const paymentId = input.paymentId ?? randomUUID();
    return {
      paymentId,
      operation,
      status,
      amount: input.amount,
      currency: input.currency,
      providerReference: `mock_${operation}_${paymentId.replaceAll("-", "").slice(0, 16)}`
    };
  }

  async authorize(input: PaymentRequest) {
    return this.result("authorize", input, input.paymentMethodToken?.toLowerCase().includes("decline") ? "declined" : "approved");
  }
  async capture(input: PaymentRequest) { return this.result("capture", input, "captured"); }
  async refund(input: PaymentRequest) { return this.result("refund", input, "refunded"); }
}
