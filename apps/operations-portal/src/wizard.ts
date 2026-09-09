/**
 * Guided claim-workflow wizard model.
 *
 * The submission flow is split into five explicit steps so operators always know
 * where they are, what is required next, and what will be sent downstream. This
 * module owns the data and validation rules; rendering lives in `views.ts`.
 */

export interface WizardDraft {
  policy_id: string;
  policyholder_id: string;
  claim_amount: string;
  incident_date: string;
  description: string;
  adjuster_notes: string;
}

export interface WizardStep {
  /** One-based number rendered in the progress indicator. */
  index: number;
  key: StepKey;
  title: string;
  summary: string;
  /** Draft fields that must be valid before the operator may advance. */
  fields: Array<keyof WizardDraft>;
}

export type StepKey = "policy" | "incident" | "assessment" | "review" | "result";

export const WIZARD_STEPS: WizardStep[] = [
  { index: 1, key: "policy", title: "Policy", summary: "Identify the policy and policyholder", fields: ["policy_id", "policyholder_id"] },
  { index: 2, key: "incident", title: "Incident", summary: "Describe what happened and when", fields: ["incident_date", "description"] },
  { index: 3, key: "assessment", title: "Assessment", summary: "Capture the amount and adjuster notes", fields: ["claim_amount"] },
  { index: 4, key: "review", title: "Review", summary: "Confirm the payload before submission", fields: [] },
  { index: 5, key: "result", title: "Result", summary: "Track each orchestrated saga step", fields: [] },
];

export const EMPTY_DRAFT: WizardDraft = {
  policy_id: "",
  policyholder_id: "",
  claim_amount: "",
  incident_date: "",
  description: "",
  adjuster_notes: "",
};

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type FieldErrors = Partial<Record<keyof WizardDraft, string>>;

/** Validates every field of the draft, independent of the current step. */
export function validateDraft(draft: WizardDraft): FieldErrors {
  const errors: FieldErrors = {};

  if (!draft.policy_id.trim()) errors.policy_id = "Policy ID is required.";
  else if (!UUID_PATTERN.test(draft.policy_id.trim())) errors.policy_id = "Policy ID must be a UUID.";

  if (!draft.policyholder_id.trim()) errors.policyholder_id = "Policyholder ID is required.";
  else if (!UUID_PATTERN.test(draft.policyholder_id.trim())) errors.policyholder_id = "Policyholder ID must be a UUID.";

  if (!draft.incident_date.trim()) errors.incident_date = "Incident date is required.";
  else if (Number.isNaN(new Date(draft.incident_date).getTime())) errors.incident_date = "Incident date is invalid.";
  else if (new Date(draft.incident_date).getTime() > Date.now()) errors.incident_date = "Incident date cannot be in the future.";

  const description = draft.description.trim();
  if (!description) errors.description = "Description is required.";
  else if (description.length < 10) errors.description = "Add at least 10 characters of detail.";

  const amount = Number.parseFloat(draft.claim_amount);
  if (!draft.claim_amount.trim()) errors.claim_amount = "Claim amount is required.";
  else if (Number.isNaN(amount) || amount <= 0) errors.claim_amount = "Claim amount must be greater than zero.";

  return errors;
}

/** Restricts validation output to the fields owned by a given step. */
export function errorsForStep(draft: WizardDraft, step: WizardStep): FieldErrors {
  const all = validateDraft(draft);
  const scoped: FieldErrors = {};
  for (const field of step.fields) {
    if (all[field]) scoped[field] = all[field];
  }
  return scoped;
}

/** True when the operator may advance past the supplied step. */
export function canAdvance(draft: WizardDraft, step: WizardStep): boolean {
  if (step.key === "review") return Object.keys(validateDraft(draft)).length === 0;
  return Object.keys(errorsForStep(draft, step)).length === 0;
}

/** Highest step number the operator has satisfied, used to gate stepper navigation. */
export function furthestReachableStep(draft: WizardDraft): number {
  let reachable = 1;
  for (const step of WIZARD_STEPS) {
    if (step.key === "result") break;
    if (!canAdvance(draft, step)) return reachable;
    reachable = Math.min(step.index + 1, WIZARD_STEPS.length);
  }
  return reachable;
}

/** Builds the request body sent to the orchestrator's claim-workflow endpoint. */
export function toWorkflowRequest(draft: WizardDraft): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    policy_id: draft.policy_id.trim(),
    policyholder_id: draft.policyholder_id.trim(),
    claim_amount: Number.parseFloat(draft.claim_amount).toFixed(2),
    incident_date: draft.incident_date,
    description: draft.description.trim(),
  };
  const notes = draft.adjuster_notes.trim();
  if (notes) payload.adjuster_notes = notes;
  return payload;
}
