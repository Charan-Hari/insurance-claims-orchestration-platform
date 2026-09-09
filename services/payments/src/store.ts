import Database from "better-sqlite3";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import type { Operation, PaymentResponse } from "./types.js";

export class IdempotencyStore {
  private readonly db: Database.Database;
  constructor(filename = process.env.PAYMENTS_DB_PATH ?? "./data/payments.db") {
    mkdirSync(dirname(filename), { recursive: true });
    this.db = new Database(filename);
    this.db.pragma("journal_mode = WAL");
    this.db.exec(`CREATE TABLE IF NOT EXISTS idempotency (
      operation TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
      response_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (operation, idempotency_key)
    )`);
  }
  get(operation: Operation, key: string, requestHash: string): PaymentResponse | "conflict" | undefined {
    const row = this.db.prepare("SELECT request_hash, response_json FROM idempotency WHERE operation = ? AND idempotency_key = ?").get(operation, key) as { request_hash: string; response_json: string } | undefined;
    if (!row) return undefined;
    return row.request_hash === requestHash ? JSON.parse(row.response_json) as PaymentResponse : "conflict";
  }
  save(operation: Operation, key: string, requestHash: string, response: PaymentResponse): void {
    this.db.prepare("INSERT INTO idempotency(operation, idempotency_key, request_hash, response_json) VALUES (?, ?, ?, ?)").run(operation, key, requestHash, JSON.stringify(response));
  }
  close(): void { this.db.close(); }
}
