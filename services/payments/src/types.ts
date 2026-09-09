export type Operation = "authorize" | "capture" | "refund";

export interface PaymentRequest {
  amount: number;
  currency: string;
  paymentMethodToken?: string;
  paymentId?: string;
}

export interface PaymentResponse {
  paymentId: string;
  operation: Operation;
  status: "approved" | "declined" | "captured" | "refunded";
  amount: number;
  currency: string;
  providerReference: string;
  requestId: string;
}

export interface PaymentProvider {
  authorize(input: PaymentRequest): Promise<Omit<PaymentResponse, "requestId">>;
  capture(input: PaymentRequest): Promise<Omit<PaymentResponse, "requestId">>;
  refund(input: PaymentRequest): Promise<Omit<PaymentResponse, "requestId">>;
}
