import { describe, expect, it } from "vitest";
import {
  EMPTY_DRAFT,
  WIZARD_STEPS,
  canAdvance,
  errorsForStep,
  furthestReachableStep,
  toWorkflowRequest,
  validateDraft,
  type WizardDraft,
} from "./wizard";

const yesterday = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);

function validDraft(overrides: Partial<WizardDraft> = {}): WizardDraft {
  return {
    policy_id: "e7318d9f-22eb-4cdb-9c79-a0cf8b963720",
    policyholder_id: "11111111-1111-1111-1111-111111111111",
    claim_amount: "1250.5",
    incident_date: yesterday,
    description: "Water damage in the basement after a burst pipe.",
    adjuster_notes: "  Verified invoice  ",
    ...overrides,
  };
}

describe("wizard validation", () => {
  it("reports no errors for a complete draft", () => {
    expect(validateDraft(validDraft())).toEqual({});
  });

  it("rejects non-UUID identifiers", () => {
    const errors = validateDraft(validDraft({ policy_id: "not-a-uuid", policyholder_id: "" }));
    expect(errors.policy_id).toMatch(/UUID/);
    expect(errors.policyholder_id).toMatch(/required/);
  });

  it("rejects future incident dates and non-positive amounts", () => {
    const future = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10);
    const errors = validateDraft(validDraft({ incident_date: future, claim_amount: "0" }));
    expect(errors.incident_date).toMatch(/future/);
    expect(errors.claim_amount).toMatch(/greater than zero/);
  });

  it("requires a meaningful description", () => {
    expect(validateDraft(validDraft({ description: "short" })).description).toMatch(/10 characters/);
  });

  it("scopes errors to the fields owned by a step", () => {
    const draft = validDraft({ policy_id: "bad", claim_amount: "-1" });
    expect(Object.keys(errorsForStep(draft, WIZARD_STEPS[0]))).toEqual(["policy_id"]);
    expect(Object.keys(errorsForStep(draft, WIZARD_STEPS[2]))).toEqual(["claim_amount"]);
  });
});

describe("wizard navigation", () => {
  it("blocks advancing past an incomplete step", () => {
    expect(canAdvance(EMPTY_DRAFT, WIZARD_STEPS[0])).toBe(false);
    expect(canAdvance(validDraft(), WIZARD_STEPS[0])).toBe(true);
  });

  it("allows review submission only when the whole draft is valid", () => {
    const review = WIZARD_STEPS[3];
    expect(canAdvance(validDraft({ claim_amount: "" }), review)).toBe(false);
    expect(canAdvance(validDraft(), review)).toBe(true);
  });

  it("computes the furthest reachable step from draft completeness", () => {
    expect(furthestReachableStep(EMPTY_DRAFT)).toBe(1);
    expect(furthestReachableStep(validDraft({ claim_amount: "" }))).toBe(3);
    expect(furthestReachableStep(validDraft())).toBe(WIZARD_STEPS.length);
  });
});

describe("workflow request mapping", () => {
  it("normalises amounts and trims text before submission", () => {
    expect(toWorkflowRequest(validDraft())).toMatchObject({
      claim_amount: "1250.50",
      description: "Water damage in the basement after a burst pipe.",
      adjuster_notes: "Verified invoice",
    });
  });

  it("omits empty adjuster notes", () => {
    expect(toWorkflowRequest(validDraft({ adjuster_notes: "   " }))).not.toHaveProperty("adjuster_notes");
  });
});
