export function log(level: "info" | "error", event: string, fields: Record<string, unknown> = {}): void {
  // Never log request bodies, tokens, card data, or provider payloads.
  process.stdout.write(JSON.stringify({ timestamp: new Date().toISOString(), level, event, ...fields }) + "\n");
}
