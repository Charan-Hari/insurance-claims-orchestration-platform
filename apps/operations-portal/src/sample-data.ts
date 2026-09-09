import type { Claim, Policy, Workflow } from "./api";

/**
 * Deterministic demonstration records.
 *
 * The console must always show meaningful history so an operator (or a reviewer
 * opening the project for the first time) can explore lookups, timelines, and
 * reconciliation handling without first having to create data. Sample records are
 * clearly flagged with `sample: true` so they are never mistaken for live records.
 */

export interface SampleFlag {
  /** True when the record is bundled demonstration data rather than a live API result. */
  sample?: boolean;
}

export type SamplePolicy = Policy & SampleFlag;
export type SampleClaim = Claim & SampleFlag;
export type SampleWorkflow = Workflow & SampleFlag;

export const DEMO_POLICYHOLDER_ID = "11111111-1111-1111-1111-111111111111";

/** Offsets a fixed reference point so sample data always looks recent. */
function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 3_600_000).toISOString();
}

function daysAgo(days: number): string {
  return new Date(Date.now() - days * 86_400_000).toISOString();
}

function dateOnly(daysBack: number): string {
  return new Date(Date.now() - daysBack * 86_400_000).toISOString().slice(0, 10);
}

export const samplePolicies: SamplePolicy[] = [
  {
    id: "e7318d9f-22eb-4cdb-9c79-a0cf8b963720",
    policyholder_id: DEMO_POLICYHOLDER_ID,
    coverage_type: "property",
    coverage_limits: { dwelling: 250000, contents: 75000 },
    effective_date: dateOnly(210),
    expiry_date: dateOnly(-155),
    status: "active",
    premium_amount: "1200.00",
    created_at: daysAgo(212),
    updated_at: daysAgo(3),
    sample: true,
  },
  {
    id: "b8241ac7-5f31-4d7a-9f0e-2c65f4a11d02",
    policyholder_id: DEMO_POLICYHOLDER_ID,
    coverage_type: "auto",
    coverage_limits: { collision: 50000, liability: 100000 },
    effective_date: dateOnly(120),
    expiry_date: dateOnly(-245),
    status: "active",
    premium_amount: "860.50",
    created_at: daysAgo(121),
    updated_at: daysAgo(11),
    sample: true,
  },
  {
    id: "c3910fe2-77b4-4f18-8a20-91d0c4be7714",
    policyholder_id: DEMO_POLICYHOLDER_ID,
    coverage_type: "liability",
    coverage_limits: { aggregate: 1000000 },
    effective_date: dateOnly(20),
    expiry_date: dateOnly(-345),
    status: "pending_underwriting",
    premium_amount: "2340.00",
    created_at: daysAgo(21),
    updated_at: daysAgo(1),
    sample: true,
  },
  {
    id: "d5062bb8-1c94-4e35-b7f6-08a3e91c5d47",
    policyholder_id: DEMO_POLICYHOLDER_ID,
    coverage_type: "renters",
    coverage_limits: { contents: 40000, liability: 25000 },
    effective_date: dateOnly(330),
    expiry_date: dateOnly(-35),
    status: "active",
    premium_amount: "410.25",
    created_at: daysAgo(331),
    updated_at: daysAgo(48),
    sample: true,
  },
  {
    id: "f1748cd3-6a20-4bb9-8e51-7c93d0f2a865",
    policyholder_id: DEMO_POLICYHOLDER_ID,
    coverage_type: "umbrella",
    coverage_limits: { aggregate: 2000000 },
    effective_date: dateOnly(400),
    expiry_date: dateOnly(35),
    status: "expired",
    premium_amount: "1580.00",
    created_at: daysAgo(402),
    updated_at: daysAgo(34),
    sample: true,
  },
  {
    id: "a92c50e7-4d18-4a76-9f23-6b81e4c07d59",
    policyholder_id: DEMO_POLICYHOLDER_ID,
    coverage_type: "flood",
    coverage_limits: { dwelling: 180000 },
    effective_date: dateOnly(5),
    expiry_date: dateOnly(-360),
    status: "draft",
    premium_amount: "965.75",
    created_at: daysAgo(5),
    updated_at: hoursAgo(9),
    sample: true,
  },
];

export const sampleClaims: SampleClaim[] = [
  {
    id: "caad1319-94c8-4a8a-b689-70e49171f9d4",
    claim_reference: "CLM-2026-004105",
    policy_id: samplePolicies[0].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    claim_amount: "1250.00",
    incident_date: dateOnly(8),
    description: "Water damage in the basement after a burst supply line.",
    adjuster_notes: "Plumber invoice received and verified.",
    status: "under_review",
    created_at: daysAgo(7),
    updated_at: hoursAgo(6),
    sample: true,
  },
  {
    id: "4b0c19aa-7e58-4d43-9cb7-6f8b0e2a4d31",
    claim_reference: "CLM-2026-004103",
    policy_id: samplePolicies[1].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    claim_amount: "3480.75",
    incident_date: dateOnly(26),
    description: "Rear-end collision at a signalled intersection.",
    adjuster_notes: "Repair estimate approved by the preferred body shop.",
    status: "approved",
    created_at: daysAgo(25),
    updated_at: daysAgo(9),
    sample: true,
  },
  {
    id: "9d7f42c1-3a6e-4f90-8bd5-1e4c7a9b2f68",
    claim_reference: "CLM-2026-004102",
    policy_id: samplePolicies[0].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    claim_amount: "620.00",
    incident_date: dateOnly(64),
    description: "Storm damage to exterior fencing and gutters.",
    adjuster_notes: "Settled and paid via the payments service.",
    status: "settled",
    created_at: daysAgo(63),
    updated_at: daysAgo(41),
    sample: true,
  },
  {
    id: "6e3b84f0-2c17-4d59-a801-9f5c7b2e40d3",
    claim_reference: "CLM-2026-004104",
    policy_id: samplePolicies[3].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    claim_amount: "1890.40",
    incident_date: dateOnly(15),
    description: "Theft of personal electronics during a building break-in.",
    adjuster_notes: "Police report attached and validated against the incident date.",
    status: "under_review",
    created_at: daysAgo(14),
    updated_at: hoursAgo(30),
    sample: true,
  },
  {
    id: "8c19d7e5-5b02-4a13-9e64-2d70f8a3c916",
    claim_reference: "CLM-2026-004101",
    policy_id: samplePolicies[1].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    claim_amount: "245.00",
    incident_date: dateOnly(96),
    description: "Windshield chip repair after highway debris impact.",
    adjuster_notes: "Below deductible threshold; closed without payment.",
    status: "denied",
    created_at: daysAgo(95),
    updated_at: daysAgo(88),
    sample: true,
  },
  {
    id: "3a5f60b9-8d43-4c27-b0f1-4e92a7c1d508",
    claim_reference: "CLM-2026-004100",
    policy_id: samplePolicies[4].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    claim_amount: "12400.00",
    incident_date: dateOnly(140),
    description: "Third-party liability claim following a guest injury.",
    adjuster_notes: "Escalated to senior adjuster; legal review completed.",
    status: "settled",
    created_at: daysAgo(139),
    updated_at: daysAgo(102),
    sample: true,
  },
  {
    id: "7f2e91c4-0a68-4b35-8d17-5c93b6e2f740",
    claim_reference: "CLM-2026-004106",
    policy_id: samplePolicies[2].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    claim_amount: "4750.25",
    incident_date: dateOnly(3),
    description: "Smoke damage to inventory following an adjacent unit fire.",
    adjuster_notes: "Awaiting fire marshal report before assessment.",
    status: "submitted",
    created_at: daysAgo(2),
    updated_at: hoursAgo(4),
    sample: true,
  },
];

export const sampleWorkflows: SampleWorkflow[] = [
  {
    id: "4d4feb20-ad73-47a1-afcc-41bf4f177c1f",
    policy_id: samplePolicies[0].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    state: "completed",
    claim_id: sampleClaims[0].id,
    failure_category: null,
    retry_count: 0,
    created_at: hoursAgo(7),
    updated_at: hoursAgo(7),
    sample: true,
    steps: [
      { name: "policy_verification", state: "succeeded", error_category: null, started_at: hoursAgo(7), completed_at: hoursAgo(7) },
      { name: "claim_submission", state: "succeeded", error_category: null, started_at: hoursAgo(7), completed_at: hoursAgo(7) },
    ],
  },
  {
    id: "17c6b3d8-90fa-4c22-b0e7-5a1d8e3c9047",
    policy_id: samplePolicies[1].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    state: "reconciliation_required",
    claim_id: null,
    failure_category: "downstream_unavailable",
    retry_count: 2,
    created_at: daysAgo(2),
    updated_at: daysAgo(2),
    sample: true,
    steps: [
      { name: "policy_verification", state: "succeeded", error_category: null, started_at: daysAgo(2), completed_at: daysAgo(2) },
      { name: "claim_submission", state: "failed", error_category: "downstream_unavailable", started_at: daysAgo(2), completed_at: daysAgo(2) },
    ],
  },
  {
    id: "2f8a5e14-6bd3-4a71-9c08-3d5f1b7e6a92",
    policy_id: samplePolicies[1].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    state: "completed",
    claim_id: sampleClaims[1].id,
    failure_category: null,
    retry_count: 1,
    created_at: daysAgo(25),
    updated_at: daysAgo(25),
    sample: true,
    steps: [
      { name: "policy_verification", state: "succeeded", error_category: null, started_at: daysAgo(25), completed_at: daysAgo(25) },
      { name: "claim_submission", state: "succeeded", error_category: null, started_at: daysAgo(25), completed_at: daysAgo(25) },
    ],
  },
  {
    id: "5b93e0a7-41cd-4f68-9a25-8e17c6b4d032",
    policy_id: samplePolicies[3].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    state: "completed",
    claim_id: sampleClaims[3].id,
    failure_category: null,
    retry_count: 0,
    created_at: daysAgo(14),
    updated_at: daysAgo(14),
    sample: true,
    steps: [
      { name: "policy_verification", state: "succeeded", error_category: null, started_at: daysAgo(14), completed_at: daysAgo(14) },
      { name: "claim_submission", state: "succeeded", error_category: null, started_at: daysAgo(14), completed_at: daysAgo(14) },
    ],
  },
  {
    id: "c8071f52-9b6e-4a30-8d94-1f25e7c3b6a8",
    policy_id: samplePolicies[4].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    state: "failed",
    claim_id: null,
    failure_category: "policy_not_active",
    retry_count: 1,
    created_at: daysAgo(34),
    updated_at: daysAgo(34),
    sample: true,
    steps: [
      { name: "policy_verification", state: "failed", error_category: "policy_not_active", started_at: daysAgo(34), completed_at: daysAgo(34) },
      { name: "claim_submission", state: "skipped", error_category: null, started_at: null, completed_at: null },
    ],
  },
  {
    id: "9e40c7b1-2f85-4d69-b013-7a56d9e2f184",
    policy_id: samplePolicies[2].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    state: "completed",
    claim_id: sampleClaims[6].id,
    failure_category: null,
    retry_count: 0,
    created_at: daysAgo(2),
    updated_at: hoursAgo(46),
    sample: true,
    steps: [
      { name: "policy_verification", state: "succeeded", error_category: null, started_at: daysAgo(2), completed_at: daysAgo(2) },
      { name: "claim_submission", state: "succeeded", error_category: null, started_at: daysAgo(2), completed_at: hoursAgo(46) },
    ],
  },
  {
    id: "b16d359e-7c04-4218-a5f7-3e80b9c14d26",
    policy_id: samplePolicies[0].id,
    policyholder_id: DEMO_POLICYHOLDER_ID,
    state: "completed",
    claim_id: sampleClaims[2].id,
    failure_category: null,
    retry_count: 2,
    created_at: daysAgo(63),
    updated_at: daysAgo(63),
    sample: true,
    steps: [
      { name: "policy_verification", state: "succeeded", error_category: null, started_at: daysAgo(63), completed_at: daysAgo(63) },
      { name: "claim_submission", state: "succeeded", error_category: null, started_at: daysAgo(63), completed_at: daysAgo(63) },
    ],
  },
];

/** Prefill values used by the guided workflow wizard's "Use sample claim" action. */
export const sampleWorkflowDraft = {
  policy_id: samplePolicies[0].id,
  policyholder_id: DEMO_POLICYHOLDER_ID,
  claim_amount: "1250.00",
  incident_date: dateOnly(8),
  description: "Water damage in the basement after a burst supply line.",
  adjuster_notes: "Plumber invoice received and verified.",
};
