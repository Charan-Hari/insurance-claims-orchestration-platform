/**
 * Operations Portal demo capture.
 *
 * Drives the console through the full five-step workflow and writes numbered
 * screenshots plus GIF frames to `docs/demo/`. Downstream service responses are
 * stubbed at the network layer so the recording is deterministic and can be
 * reproduced without running the whole Compose stack.
 *
 * Usage (from the repository root, with the portal served on PORTAL_URL):
 *   node scripts/capture-demo.mjs
 */

import { mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT_DIR = path.join(ROOT, "docs", "demo");
const FRAME_DIR = path.join(OUT_DIR, "frames");
const PORTAL_URL = process.env.PORTAL_URL ?? "http://localhost:5199/";
const VIEWPORT = { width: 1440, height: 900 };

const POLICY_ID = "e7318d9f-22eb-4cdb-9c79-a0cf8b963720";
const HOLDER_ID = "11111111-1111-1111-1111-111111111111";
const CLAIM_ID = "caad1319-94c8-4a8a-b689-70e49171f9d4";
const WORKFLOW_ID = "4d4feb20-ad73-47a1-afcc-41bf4f177c1f";

const now = new Date().toISOString();

const WORKFLOW_RESPONSE = {
  id: WORKFLOW_ID,
  policy_id: POLICY_ID,
  policyholder_id: HOLDER_ID,
  state: "completed",
  claim_id: CLAIM_ID,
  failure_category: null,
  retry_count: 0,
  created_at: now,
  updated_at: now,
  steps: [
    { name: "policy_verification", state: "succeeded", error_category: null, started_at: now, completed_at: now },
    { name: "claim_submission", state: "succeeded", error_category: null, started_at: now, completed_at: now },
  ],
};

const POLICIES = [
  { id: POLICY_ID, policyholder_id: HOLDER_ID, coverage_type: "property", coverage_limits: { dwelling: 250000 }, effective_date: "2026-02-11", expiry_date: "2027-02-11", status: "active", premium_amount: "1200.00", created_at: now, updated_at: now },
  { id: "b8241ac7-5f31-4d7a-9f0e-2c65f4a11d02", policyholder_id: HOLDER_ID, coverage_type: "auto", coverage_limits: { collision: 50000 }, effective_date: "2026-05-12", expiry_date: "2027-05-12", status: "active", premium_amount: "860.50", created_at: now, updated_at: now },
  { id: "c3910fe2-77b4-4f18-8a20-91d0c4be7714", policyholder_id: HOLDER_ID, coverage_type: "liability", coverage_limits: { aggregate: 1000000 }, effective_date: "2026-08-20", expiry_date: "2027-08-20", status: "pending_underwriting", premium_amount: "2340.00", created_at: now, updated_at: now },
  { id: "d5062bb8-1c94-4e35-b7f6-08a3e91c5d47", policyholder_id: HOLDER_ID, coverage_type: "renters", coverage_limits: { contents: 40000 }, effective_date: "2025-10-14", expiry_date: "2026-10-14", status: "active", premium_amount: "410.25", created_at: now, updated_at: now },
  { id: "f1748cd3-6a20-4bb9-8e51-7c93d0f2a865", policyholder_id: HOLDER_ID, coverage_type: "umbrella", coverage_limits: { aggregate: 2000000 }, effective_date: "2025-08-05", expiry_date: "2026-08-05", status: "expired", premium_amount: "1580.00", created_at: now, updated_at: now },
  { id: "a92c50e7-4d18-4a76-9f23-6b81e4c07d59", policyholder_id: HOLDER_ID, coverage_type: "flood", coverage_limits: { dwelling: 180000 }, effective_date: "2026-09-04", expiry_date: "2027-09-04", status: "draft", premium_amount: "965.75", created_at: now, updated_at: now },
];

const CLAIMS = [
  { id: CLAIM_ID, policy_id: POLICY_ID, policyholder_id: HOLDER_ID, claim_amount: "1250.00", incident_date: "2026-09-01", description: "Water damage in the basement after a burst supply line.", adjuster_notes: "Plumber invoice verified.", status: "under_review", created_at: now, updated_at: now },
  { id: "4b0c19aa-7e58-4d43-9cb7-6f8b0e2a4d31", policy_id: "b8241ac7-5f31-4d7a-9f0e-2c65f4a11d02", policyholder_id: HOLDER_ID, claim_amount: "3480.75", incident_date: "2026-08-14", description: "Rear-end collision at a signalled intersection.", adjuster_notes: "Repair estimate approved.", status: "approved", created_at: now, updated_at: now },
  { id: "9d7f42c1-3a6e-4f90-8bd5-1e4c7a9b2f68", policy_id: POLICY_ID, policyholder_id: HOLDER_ID, claim_amount: "620.00", incident_date: "2026-07-07", description: "Storm damage to exterior fencing and gutters.", adjuster_notes: "Settled and paid via the payments service.", status: "settled", created_at: now, updated_at: now },
  { id: "6e3b84f0-2c17-4d59-a801-9f5c7b2e40d3", policy_id: "d5062bb8-1c94-4e35-b7f6-08a3e91c5d47", policyholder_id: HOLDER_ID, claim_amount: "1890.40", incident_date: "2026-08-25", description: "Theft of personal electronics during a building break-in.", adjuster_notes: "Police report attached and validated.", status: "under_review", created_at: now, updated_at: now },
  { id: "8c19d7e5-5b02-4a13-9e64-2d70f8a3c916", policy_id: "b8241ac7-5f31-4d7a-9f0e-2c65f4a11d02", policyholder_id: HOLDER_ID, claim_amount: "245.00", incident_date: "2026-06-05", description: "Windshield chip repair after highway debris impact.", adjuster_notes: "Below deductible threshold.", status: "denied", created_at: now, updated_at: now },
  { id: "3a5f60b9-8d43-4c27-b0f1-4e92a7c1d508", policy_id: "f1748cd3-6a20-4bb9-8e51-7c93d0f2a865", policyholder_id: HOLDER_ID, claim_amount: "12400.00", incident_date: "2026-04-22", description: "Third-party liability claim following a guest injury.", adjuster_notes: "Legal review completed.", status: "settled", created_at: now, updated_at: now },
  { id: "7f2e91c4-0a68-4b35-8d17-5c93b6e2f740", policy_id: "c3910fe2-77b4-4f18-8a20-91d0c4be7714", policyholder_id: HOLDER_ID, claim_amount: "4750.25", incident_date: "2026-09-06", description: "Smoke damage to inventory following an adjacent unit fire.", adjuster_notes: "Awaiting fire marshal report.", status: "submitted", created_at: now, updated_at: now },
];

/** Serves deterministic responses for every platform endpoint the console calls. */
async function stubServices(page) {
  await page.route("**://localhost:800*/**", async (route) => {
    const url = new URL(route.request().url());
    const json = (body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (url.pathname === "/health") return json({ status: "ok" });
    if (url.pathname === "/workflows/claims") return json(WORKFLOW_RESPONSE, 201);
    if (url.pathname.startsWith("/workflows/")) return json(WORKFLOW_RESPONSE);
    if (url.pathname.endsWith("/policies")) return json(POLICIES);
    if (url.pathname.endsWith("/claims")) return json(CLAIMS);
    return json({ detail: "Not found" }, 404);
  });
}

let frameIndex = 0;
const shots = [];

/** Captures a GIF frame; `label` additionally saves a named screenshot. */
async function capture(page, label = null, repeat = 1) {
  for (let index = 0; index < repeat; index += 1) {
    await page.screenshot({ path: path.join(FRAME_DIR, `frame-${String(frameIndex).padStart(3, "0")}.png`) });
    frameIndex += 1;
  }
  if (label) {
    const file = path.join(OUT_DIR, `${label}.png`);
    await page.screenshot({ path: file });
    shots.push(label);
  }
}

async function main() {
  await rm(FRAME_DIR, { recursive: true, force: true });
  await mkdir(FRAME_DIR, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  await stubServices(page);

  await page.goto(PORTAL_URL, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await capture(page, "01-dashboard", 12);

  // Step 1 — policy identification, prefilled from the bundled sample claim.
  await page.getByRole("button", { name: "Start new workflow" }).click();
  await page.waitForTimeout(400);
  await capture(page, null, 4);
  await page.getByRole("button", { name: "Use sample claim" }).click();
  await page.waitForTimeout(500);
  await capture(page, "02-step1-policy", 10);

  // Step 2 — incident details.
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForTimeout(500);
  await capture(page, "03-step2-incident", 10);

  // Step 3 — assessment.
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForTimeout(500);
  await capture(page, "04-step3-assessment", 10);

  // Step 4 — review before submission.
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForTimeout(500);
  await capture(page, "05-step4-review", 12);

  // Step 5 — orchestration result with the saga timeline.
  await page.getByRole("button", { name: "Submit workflow" }).click();
  await page.waitForTimeout(1200);
  await capture(page, "06-step5-result", 16);

  // History, records, and reconciliation views.
  await page.getByRole("button", { name: /^History/ }).click();
  await page.waitForTimeout(600);
  await capture(page, "07-history", 12);

  await page.getByRole("button", { name: /^Records/ }).click();
  await page.waitForTimeout(400);
  await page.getByRole("button", { name: "Use sample ID" }).click();
  await page.waitForTimeout(900);
  await capture(page, "08-records", 12);

  await page.getByRole("button", { name: /^Reconciliation/ }).click();
  await page.waitForTimeout(600);
  await capture(page, "09-reconciliation", 14);

  await browser.close();

  console.log(`Captured ${frameIndex} frames and ${shots.length} screenshots into ${OUT_DIR}`);
  console.log("Next: python scripts/build-demo-gif.py");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
