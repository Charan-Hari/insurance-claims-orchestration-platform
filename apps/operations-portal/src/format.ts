/**
 * Presentation helpers shared by every view.
 *
 * All values rendered by the console pass through `escapeHtml` because the UI is
 * intentionally framework-free and builds markup from strings.
 */

const HTML_ENTITIES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#039;",
};

/** Escapes a value so it can be safely interpolated into an HTML template. */
export function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => HTML_ENTITIES[character]!);
}

/** Converts `reconciliation_required` style tokens into `Reconciliation required`. */
export function humanize(value: string): string {
  const spaced = value.replace(/[_-]+/g, " ").trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : "";
}

/** Formats a monetary amount using US currency conventions. */
export function formatCurrency(value: string | number | null | undefined): string {
  const amount = typeof value === "string" ? Number.parseFloat(value) : value;
  if (amount === null || amount === undefined || Number.isNaN(amount)) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);
}

/** Formats an ISO timestamp as a short, locale-aware date and time. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Formats an ISO date without the time component. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/**
 * Renders a compact relative age such as `4m ago`, used in activity feeds where
 * absolute timestamps add noise.
 */
export function relativeTime(value: string | null | undefined, now: number = Date.now()): string {
  if (!value) return "—";
  const parsed = new Date(value).getTime();
  if (Number.isNaN(parsed)) return "—";

  const seconds = Math.round((now - parsed) / 1000);
  if (seconds < 45) return "just now";

  const thresholds: Array<[number, string]> = [
    [60, "m"],
    [3600, "h"],
    [86_400, "d"],
  ];
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}${thresholds[0][1]} ago`;
  const hours = Math.round(seconds / 3600);
  if (hours < 24) return `${hours}${thresholds[1][1]} ago`;
  return `${Math.round(seconds / 86_400)}${thresholds[2][1]} ago`;
}

/** Shortens a UUID for dense table cells while keeping it recognisable. */
export function shortId(value: string | null | undefined): string {
  const text = String(value ?? "");
  return text.length > 13 ? `${text.slice(0, 8)}…${text.slice(-4)}` : text || "—";
}

/** Maps a domain state onto the badge tone used by the design system. */
export function toneFor(state: string): "positive" | "negative" | "warning" | "neutral" {
  const normalized = state.toLowerCase();
  if (["completed", "succeeded", "active", "approved", "captured", "settled"].includes(normalized)) {
    return "positive";
  }
  if (["failed", "declined", "reconciliation_required", "cancelled", "denied"].includes(normalized)) {
    return "negative";
  }
  if (["running", "pending", "pending_underwriting", "submitted", "under_review", "draft"].includes(normalized)) {
    return "warning";
  }
  return "neutral";
}
