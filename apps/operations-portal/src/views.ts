import type { Claim, Policy, Workflow, WorkflowStep } from "./api";
import { escapeHtml, formatCurrency, formatDate, formatDateTime, humanize, relativeTime, shortId, toneFor } from "./format";
import type { ServiceHealth } from "./health";
import { summarize } from "./health";
import type { SampleClaim, SamplePolicy, SampleWorkflow } from "./sample-data";
import { DEMO_POLICYHOLDER_ID } from "./sample-data";
import type { FieldErrors, WizardDraft, WizardStep } from "./wizard";
import { WIZARD_STEPS, errorsForStep, validateDraft } from "./wizard";

/** Presentation-only rendering helpers. Every function returns an HTML string. */

export type NavKey = "dashboard" | "workflow" | "history" | "records" | "reconciliation";

export interface Banner {
  tone: "success" | "error" | "info";
  text: string;
  requestId?: string;
}

export interface ShellState {
  active: NavKey;
  banner: Banner | null;
  health: ServiceHealth[];
  healthOpen: boolean;
  navOpen: boolean;
}

const NAV_ITEMS: Array<{ key: NavKey; label: string; icon: string; hint: string }> = [
  { key: "dashboard", label: "Dashboard", icon: "▦", hint: "Operational summary" },
  { key: "workflow", label: "New workflow", icon: "✦", hint: "Guided 5-step submission" },
  { key: "history", label: "History", icon: "🕘", hint: "Previous workflow runs" },
  { key: "records", label: "Records", icon: "▤", hint: "Policies and claims" },
  { key: "reconciliation", label: "Reconciliation", icon: "◈", hint: "Exceptions and retries" },
];

export function badge(value: string): string {
  return `<span class="badge badge--${toneFor(value)}">${escapeHtml(humanize(value))}</span>`;
}

function sampleTag(isSample: boolean | undefined): string {
  return isSample ? `<span class="tag tag--sample" title="Reference record, not a live API result">Example</span>` : "";
}

/** Application chrome: header with live health, sidebar navigation, and banner slot. */
export function shell(state: ShellState, content: string): string {
  const health = summarize(state.health);
  const nav = NAV_ITEMS.map(
    (item) => `
      <button type="button" class="nav__item ${state.active === item.key ? "is-active" : ""}" data-nav="${item.key}"
        aria-current="${state.active === item.key ? "page" : "false"}">
        <span class="nav__icon" aria-hidden="true">${item.icon}</span>
        <span class="nav__text"><span class="nav__label">${escapeHtml(item.label)}</span><span class="nav__hint">${escapeHtml(item.hint)}</span></span>
      </button>`,
  ).join("");

  const healthRows = state.health.length
    ? state.health
        .map(
          (service) => `
            <li class="health__row">
              <span class="dot dot--${service.state}" aria-hidden="true"></span>
              <span class="health__name">${escapeHtml(service.label)}</span>
              <span class="health__state">${escapeHtml(humanize(service.state))}</span>
            </li>`,
        )
        .join("")
    : `<li class="health__row health__row--empty">Probing services…</li>`;

  return `
    <a class="skip-link" href="#main-content">Skip to main content</a>
    <header class="topbar">
      <div class="topbar__brand">
        <span class="brand__mark" aria-hidden="true">
          <svg viewBox="0 0 32 32" role="img" focusable="false">
            <path d="M16 3 4.8 7.6v8.1c0 6.9 4.6 12.1 11.2 14.3 6.6-2.2 11.2-7.4 11.2-14.3V7.6L16 3Z" fill="url(#shieldFill)"/>
            <path d="m10.9 16.4 3.4 3.5 6.8-7" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
            <defs>
              <linearGradient id="shieldFill" x1="4" y1="3" x2="28" y2="30" gradientUnits="userSpaceOnUse">
                <stop stop-color="#60a5fa"/><stop offset="1" stop-color="#2563eb"/>
              </linearGradient>
            </defs>
          </svg>
        </span>
        <span class="brand__text">
          <span class="brand__title">Claims<span class="brand__accent">Ops</span></span>
          <span class="brand__sub">Insurance Orchestration Platform</span>
        </span>
      </div>
      <div class="topbar__right">
        <div class="health">
          <button type="button" class="health__toggle" id="health-toggle" aria-expanded="${state.healthOpen}">
            <span class="dot dot--${health.state}" aria-hidden="true"></span>
            <span class="health__summary">${escapeHtml(health.label)}</span>
            <span class="health__chevron" aria-hidden="true">▾</span>
          </button>
          <ul class="health__panel ${state.healthOpen ? "is-open" : ""}" role="list">${healthRows}</ul>
        </div>
        <button type="button" class="icon-button" id="nav-toggle" aria-label="Toggle navigation" aria-expanded="${state.navOpen}">☰</button>
      </div>
    </header>
    <div class="layout">
      <nav class="nav ${state.navOpen ? "is-open" : ""}" aria-label="Main navigation">${nav}</nav>
      <main id="main-content" class="main" tabindex="-1">
        ${state.banner ? banner(state.banner) : ""}
        ${content}
      </main>
    </div>`;
}

function banner(value: Banner): string {
  const icon = value.tone === "success" ? "✓" : value.tone === "error" ? "!" : "i";
  return `
    <div class="banner banner--${value.tone}" role="${value.tone === "error" ? "alert" : "status"}">
      <span class="banner__icon" aria-hidden="true">${icon}</span>
      <span class="banner__text">${escapeHtml(value.text)}${value.requestId ? ` <span class="banner__meta">Request ${escapeHtml(value.requestId)}</span>` : ""}</span>
      <button type="button" class="banner__close" id="banner-dismiss" aria-label="Dismiss message">×</button>
    </div>`;
}

function pageHead(eyebrow: string, title: string, description: string, action = ""): string {
  return `
    <div class="page-head">
      <div>
        <p class="eyebrow">${escapeHtml(eyebrow)}</p>
        <h1>${escapeHtml(title)}</h1>
        <p class="muted">${escapeHtml(description)}</p>
      </div>
      ${action}
    </div>`;
}

/* ------------------------------------------------------------------ dashboard */

export interface DashboardMetrics {
  total: number;
  completed: number;
  inFlight: number;
  reconciliation: number;
  retries: number;
}

export function dashboardView(
  metrics: DashboardMetrics,
  recent: Array<Workflow | SampleWorkflow>,
  health: ServiceHealth[],
): string {
  const cards = [
    { label: "Workflows tracked", value: metrics.total, hint: "All recorded runs", tone: "" },
    { label: "Completed", value: metrics.completed, hint: "Both saga steps succeeded", tone: "positive" },
    { label: "Needs reconciliation", value: metrics.reconciliation, hint: "Operator review required", tone: metrics.reconciliation ? "negative" : "" },
    { label: "Retry attempts", value: metrics.retries, hint: "Bounded automatic retries", tone: "" },
  ]
    .map(
      (card) => `
        <article class="stat ${card.tone ? `stat--${card.tone}` : ""}">
          <p class="stat__label">${escapeHtml(card.label)}</p>
          <p class="stat__value">${escapeHtml(card.value)}</p>
          <p class="stat__hint">${escapeHtml(card.hint)}</p>
        </article>`,
    )
    .join("");

  const online = summarize(health);

  return `
    ${pageHead(
      "Overview",
      "Operations dashboard",
      "Live orchestration health, recent workflow activity, and outstanding exceptions.",
      `<button type="button" class="button button--primary" data-nav="workflow">Start new workflow</button>`,
    )}
    <section class="stats" aria-label="Key metrics">${cards}</section>
    <section class="grid grid--split">
      <div class="card">
        <div class="card__head">
          <h2>Recent activity</h2>
          <button type="button" class="button button--ghost" data-nav="history">View all</button>
        </div>
        ${activityList(recent.slice(0, 5))}
      </div>
      <div class="card">
        <div class="card__head"><h2>Platform services</h2><span class="pill">${escapeHtml(`${online.online}/${online.total}`)}</span></div>
        <ul class="service-list" role="list">
          ${health
            .map(
              (service) => `
                <li class="service-list__row">
                  <span class="dot dot--${service.state}" aria-hidden="true"></span>
                  <span class="service-list__name">${escapeHtml(service.label)}</span>
                  <code class="service-list__url">${escapeHtml(service.baseUrl.replace("http://", ""))}</code>
                  <span class="service-list__state service-list__state--${service.state}">${escapeHtml(humanize(service.state))}</span>
                </li>`,
            )
            .join("") || `<li class="service-list__row">Probing services…</li>`}
        </ul>
      </div>
    </section>`;
}

function activityList(entries: Array<Workflow | SampleWorkflow>): string {
  if (!entries.length) return emptyState("No workflow activity yet", "Submit a workflow to populate this feed.", "workflow", "Start a workflow");
  return `
    <ul class="activity" role="list">
      ${entries
        .map(
          (entry) => `
            <li class="activity__row">
              <span class="activity__icon activity__icon--${toneFor(entry.state)}" aria-hidden="true">${entry.state === "completed" ? "✓" : entry.state === "reconciliation_required" || entry.state === "failed" ? "!" : "·"}</span>
              <span class="activity__body">
                <button type="button" class="link" data-workflow="${escapeHtml(entry.id)}">${escapeHtml(shortId(entry.id))}</button>
                ${sampleTag((entry as SampleWorkflow).sample)}
                <span class="activity__meta">${escapeHtml(humanize(entry.state))} · ${escapeHtml(relativeTime(entry.updated_at))}</span>
              </span>
              ${badge(entry.state)}
            </li>`,
        )
        .join("")}
    </ul>`;
}

/* -------------------------------------------------------------------- wizard */

export interface WizardViewState {
  step: number;
  draft: WizardDraft;
  showErrors: boolean;
  submitting: boolean;
  result: Workflow | null;
}

/** Numbered progress indicator rendered above every wizard step. */
export function stepper(current: number, furthest: number): string {
  return `
    <ol class="stepper" role="list" aria-label="Workflow progress">
      ${WIZARD_STEPS.map((step) => {
        const status = step.index < current ? "done" : step.index === current ? "current" : "upcoming";
        const reachable = step.index <= furthest;
        return `
          <li class="stepper__item stepper__item--${status}">
            <button type="button" class="stepper__button" data-step="${step.index}" ${reachable ? "" : "disabled"}
              aria-current="${status === "current" ? "step" : "false"}">
              <span class="stepper__index" aria-hidden="true">${status === "done" ? "✓" : step.index}</span>
              <span class="stepper__text">
                <span class="stepper__title">${escapeHtml(step.title)}</span>
                <span class="stepper__summary">${escapeHtml(step.summary)}</span>
              </span>
            </button>
          </li>`;
      }).join("")}
    </ol>`;
}

function field(
  name: keyof WizardDraft,
  label: string,
  input: string,
  errors: FieldErrors,
  hint = "",
): string {
  const error = errors[name];
  return `
    <div class="field ${error ? "field--invalid" : ""}">
      <label class="field__label" for="field-${name}">${escapeHtml(label)}</label>
      ${input}
      ${error ? `<p class="field__error" id="error-${name}">${escapeHtml(error)}</p>` : hint ? `<p class="field__hint">${escapeHtml(hint)}</p>` : ""}
    </div>`;
}

function textInput(name: keyof WizardDraft, draft: WizardDraft, attrs = ""): string {
  return `<input class="input" id="field-${name}" name="${name}" value="${escapeHtml(draft[name])}" ${attrs}>`;
}

export function wizardView(state: WizardViewState, furthest: number): string {
  const step = WIZARD_STEPS[state.step - 1];
  const errors = state.showErrors ? (step.key === "review" ? validateDraft(state.draft) : errorsForStep(state.draft, step)) : {};

  return `
    ${pageHead(
      "Guided submission",
      "New claim workflow",
      "Five steps take a claim from policy verification through orchestrated submission.",
      `<button type="button" class="button button--ghost" id="use-sample">Prefill example</button>`,
    )}
    ${stepper(state.step, Math.max(furthest, state.step))}
    <section class="card wizard">
      <form id="wizard-form" novalidate>
        ${stepBody(step, state, errors)}
        ${step.key === "result" ? "" : wizardActions(state, step)}
      </form>
    </section>`;
}

function wizardActions(state: WizardViewState, step: WizardStep): string {
  const isReview = step.key === "review";
  return `
    <div class="wizard__actions">
      <button type="button" class="button button--ghost" data-step-back ${state.step === 1 ? "disabled" : ""}>Back</button>
      <span class="wizard__progress">Step ${state.step} of ${WIZARD_STEPS.length}</span>
      <button type="submit" class="button button--primary" ${state.submitting ? "disabled" : ""}>
        ${state.submitting ? `<span class="spinner" aria-hidden="true"></span> Submitting…` : isReview ? "Submit workflow" : "Continue"}
      </button>
    </div>`;
}

function stepBody(step: WizardStep, state: WizardViewState, errors: FieldErrors): string {
  const draft = state.draft;

  if (step.key === "policy") {
    return `
      <div class="wizard__head"><h2>Step 1 · Identify the policy</h2><p class="muted">The orchestrator verifies this policy before any claim is created.</p></div>
      <div class="field-grid">
        ${field("policy_id", "Policy ID", textInput("policy_id", draft, `placeholder="00000000-0000-0000-0000-000000000000" autocomplete="off"`), errors, "UUID of an active policy.")}
        ${field("policyholder_id", "Policyholder ID", textInput("policyholder_id", draft, `placeholder="${DEMO_POLICYHOLDER_ID}" autocomplete="off"`), errors, "Must match the policy owner.")}
      </div>`;
  }

  if (step.key === "incident") {
    return `
      <div class="wizard__head"><h2>Step 2 · Describe the incident</h2><p class="muted">Recorded on the claim and written to the audit trail.</p></div>
      <div class="field-grid">
        ${field("incident_date", "Incident date", textInput("incident_date", draft, `type="date" max="${new Date().toISOString().slice(0, 10)}"`), errors, "Cannot be a future date.")}
      </div>
      ${field("description", "Description", `<textarea class="input" id="field-description" name="description" rows="4" placeholder="What happened?">${escapeHtml(draft.description)}</textarea>`, errors, "Minimum 10 characters.")}`;
  }

  if (step.key === "assessment") {
    return `
      <div class="wizard__head"><h2>Step 3 · Assessment</h2><p class="muted">Amounts are validated against policy coverage downstream.</p></div>
      <div class="field-grid">
        ${field("claim_amount", "Claim amount (USD)", textInput("claim_amount", draft, `type="number" min="0.01" step="0.01" placeholder="0.00"`), errors, "Must be greater than zero.")}
      </div>
      ${field("adjuster_notes", "Adjuster notes (optional)", `<textarea class="input" id="field-adjuster_notes" name="adjuster_notes" rows="3" placeholder="Supporting context for reviewers">${escapeHtml(draft.adjuster_notes)}</textarea>`, errors, "Stored with the claim for reviewers.")}`;
  }

  if (step.key === "review") {
    const rows: Array<[string, string]> = [
      ["Policy ID", draft.policy_id || "—"],
      ["Policyholder ID", draft.policyholder_id || "—"],
      ["Incident date", formatDate(draft.incident_date)],
      ["Claim amount", formatCurrency(draft.claim_amount)],
      ["Description", draft.description || "—"],
      ["Adjuster notes", draft.adjuster_notes || "—"],
    ];
    const outstanding = Object.values(errors).filter(Boolean);
    return `
      <div class="wizard__head"><h2>Step 4 · Review and confirm</h2><p class="muted">Submission is idempotent — an Idempotency-Key is generated for this request.</p></div>
      ${outstanding.length ? `<div class="banner banner--error" role="alert"><span class="banner__icon" aria-hidden="true">!</span><span class="banner__text">Resolve ${outstanding.length} validation issue(s) before submitting.</span></div>` : ""}
      <dl class="review">
        ${rows.map(([label, value]) => `<div class="review__row"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}
      </dl>`;
  }

  return resultStep(state.result);
}

function resultStep(workflow: Workflow | null): string {
  if (!workflow) {
    return `
      <div class="wizard__head"><h2>Step 5 · Result</h2></div>
      ${emptyState("No submission yet", "Complete the previous steps to run the orchestration.", "workflow", "Back to step 1")}`;
  }
  return `
    <div class="wizard__head"><h2>Step 5 · Orchestration result</h2><p class="muted">Each saga step reported by the orchestrator.</p></div>
    ${workflowDetail(workflow)}
    <div class="wizard__actions wizard__actions--end">
      <button type="button" class="button button--ghost" id="wizard-reset">Start another workflow</button>
      <button type="button" class="button button--primary" data-nav="history">View history</button>
    </div>`;
}

/* --------------------------------------------------------- workflow detail */

export function workflowDetail(workflow: Workflow | SampleWorkflow): string {
  const canRetry = workflow.state === "failed" || workflow.state === "reconciliation_required";
  return `
    <section class="workflow">
      <header class="workflow__head">
        <div>
          <p class="eyebrow">Workflow</p>
          <code class="workflow__id">${escapeHtml(workflow.id)}</code>
        </div>
        <div class="workflow__badges">
          ${sampleTag((workflow as SampleWorkflow).sample)}
          ${badge(workflow.state)}
          ${workflow.retry_count ? `<span class="pill pill--muted">↻ ${escapeHtml(workflow.retry_count)} retries</span>` : ""}
        </div>
      </header>
      <dl class="meta-grid">
        <div><dt>Policy</dt><dd><code>${escapeHtml(shortId(workflow.policy_id))}</code></dd></div>
        <div><dt>Claim</dt><dd><code>${escapeHtml(workflow.claim_id ? shortId(workflow.claim_id) : "Not created")}</code></dd></div>
        <div><dt>Started</dt><dd>${escapeHtml(formatDateTime(workflow.created_at))}</dd></div>
        <div><dt>Updated</dt><dd>${escapeHtml(formatDateTime(workflow.updated_at))}</dd></div>
      </dl>
      ${timeline(workflow.steps)}
      ${workflow.failure_category ? `<div class="banner banner--error" role="alert"><span class="banner__icon" aria-hidden="true">!</span><span class="banner__text">Failure category: ${escapeHtml(humanize(workflow.failure_category))} — review the failed step before retrying.</span></div>` : ""}
      ${canRetry ? `<button type="button" class="button button--warning" data-retry="${escapeHtml(workflow.id)}">↻ Retry workflow</button>` : ""}
    </section>`;
}

function timeline(steps: WorkflowStep[]): string {
  if (!steps.length) return `<p class="muted">No steps recorded.</p>`;
  return `
    <ol class="timeline" role="list">
      ${steps
        .map((step, position) => {
          const tone = toneFor(step.state);
          const icon = step.state === "succeeded" ? "✓" : step.state === "failed" ? "!" : String(position + 1);
          return `
            <li class="timeline__item timeline__item--${tone}">
              <span class="timeline__marker" aria-hidden="true">${icon}</span>
              <div class="timeline__body">
                <p class="timeline__title">${escapeHtml(humanize(step.name))}</p>
                <p class="timeline__meta">${escapeHtml(humanize(step.state))}${step.error_category ? ` · ${escapeHtml(humanize(step.error_category))}` : ""}${step.completed_at ? ` · ${escapeHtml(formatDateTime(step.completed_at))}` : ""}</p>
              </div>
              ${badge(step.state)}
            </li>`;
        })
        .join("")}
    </ol>`;
}

/* ------------------------------------------------------------------ history */

export function historyView(entries: Array<Workflow | SampleWorkflow>, selected: Workflow | SampleWorkflow | null, query: string): string {
  const filtered = filterWorkflows(entries, query);
  return `
    ${pageHead(
      "Audit",
      "Workflow history",
      "Every workflow submitted from this console.",
      `<button type="button" class="button button--primary" data-nav="workflow">Start new workflow</button>`,
    )}
    <section class="card">
      <div class="card__head">
        <h2>Runs</h2>
        <input class="input input--search" id="history-search" type="search" placeholder="Filter by ID, state, or policy" value="${escapeHtml(query)}" aria-label="Filter workflow history">
      </div>
      ${
        filtered.length
          ? `<div class="table-wrap"><table class="table">
              <thead><tr><th scope="col">Workflow</th><th scope="col">State</th><th scope="col">Claim</th><th scope="col">Retries</th><th scope="col">Updated</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
              <tbody>
                ${filtered
                  .map(
                    (entry) => `
                      <tr class="${selected?.id === entry.id ? "is-selected" : ""}">
                        <td><code>${escapeHtml(shortId(entry.id))}</code> ${sampleTag((entry as SampleWorkflow).sample)}</td>
                        <td>${badge(entry.state)}</td>
                        <td><code>${escapeHtml(entry.claim_id ? shortId(entry.claim_id) : "—")}</code></td>
                        <td>${escapeHtml(entry.retry_count ?? 0)}</td>
                        <td>${escapeHtml(relativeTime(entry.updated_at))}</td>
                        <td class="table__actions"><button type="button" class="button button--ghost button--sm" data-workflow="${escapeHtml(entry.id)}">Inspect</button></td>
                      </tr>`,
                  )
                  .join("")}
              </tbody>
            </table></div>`
          : emptyState("No matching workflows", "Adjust the filter to see more runs.", "workflow", "Start a workflow")
      }
    </section>
    ${selected ? `<section class="card">${workflowDetail(selected)}</section>` : ""}`;
}

/** Case-insensitive filter across identifiers and state. */
export function filterWorkflows<T extends Workflow>(entries: T[], query: string): T[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return entries;
  return entries.filter((entry) =>
    [entry.id, entry.state, entry.policy_id, entry.claim_id ?? "", entry.failure_category ?? ""]
      .join(" ")
      .toLowerCase()
      .includes(needle),
  );
}

/* ------------------------------------------------------------------ records */

export interface RecordsState {
  holder: string;
  loading: boolean;
  loaded: boolean;
  policies: Array<Policy | SamplePolicy>;
  claims: Array<Claim | SampleClaim>;
  usingSamples: boolean;
}

export function recordsView(state: RecordsState): string {
  return `
    ${pageHead(
      "Lookup",
      "Policies and claims",
      "Read-only records scoped to a single policyholder, backed by the Policy and Claims services.",
    )}
    <section class="card">
      <form id="records-form" class="inline-form">
        <div class="field">
          <label class="field__label" for="holder">Policyholder ID</label>
          <input class="input" id="holder" name="holder" value="${escapeHtml(state.holder)}" placeholder="${DEMO_POLICYHOLDER_ID}" required>
        </div>
        <button type="submit" class="button button--primary" ${state.loading ? "disabled" : ""}>${state.loading ? `<span class="spinner" aria-hidden="true"></span> Loading…` : "Load records"}</button>
        <button type="button" class="button button--ghost" id="use-sample-holder">Prefill ID</button>
      </form>
    </section>
    ${state.usingSamples ? `<p class="note">Showing reference records. Load a policyholder ID to query live services.</p>` : ""}
    ${state.loading ? skeletonGrid() : recordsGrid(state)}`;
}

function recordsGrid(state: RecordsState): string {
  return `
    <section class="grid grid--split">
      <div class="card">
        <div class="card__head"><h2>Policies</h2><span class="pill">${escapeHtml(state.policies.length)}</span></div>
        ${
          state.policies.length
            ? `<ul class="record-list" role="list">${state.policies
                .map(
                  (policy) => `
                    <li class="record">
                      <div class="record__main">
                        <span class="record__title">${escapeHtml(humanize(policy.coverage_type))} ${sampleTag((policy as SamplePolicy).sample)}</span>
                        <code class="record__id">${escapeHtml(shortId(policy.id))}</code>
                        <span class="record__meta">${escapeHtml(formatDate(policy.effective_date))} → ${escapeHtml(formatDate(policy.expiry_date))}</span>
                      </div>
                      <div class="record__side">${badge(policy.status)}<span class="record__amount">${escapeHtml(formatCurrency(policy.premium_amount))}</span></div>
                    </li>`,
                )
                .join("")}</ul>`
            : emptyState("No policies found", "This policyholder has no policies on record.", "workflow", "Start a workflow")
        }
      </div>
      <div class="card">
        <div class="card__head"><h2>Claims</h2><span class="pill">${escapeHtml(state.claims.length)}</span></div>
        ${
          state.claims.length
            ? `<ul class="record-list" role="list">${state.claims
                .map(
                  (claim) => `
                    <li class="record">
                      <div class="record__main">
                        <span class="record__title">${escapeHtml(claim.description)} ${sampleTag((claim as SampleClaim).sample)}</span>
                        <code class="record__id" title="${escapeHtml(claim.id)}">${escapeHtml(claim.claim_reference ?? shortId(claim.id))}</code>
                        <span class="record__meta">Incident ${escapeHtml(formatDate(claim.incident_date))}</span>
                      </div>
                      <div class="record__side">${badge(claim.status)}<span class="record__amount">${escapeHtml(formatCurrency(claim.claim_amount))}</span></div>
                    </li>`,
                )
                .join("")}</ul>`
            : emptyState("No claims found", "This policyholder has no claims on record.", "workflow", "Start a workflow")
        }
      </div>
    </section>`;
}

function skeletonGrid(): string {
  const rows = Array.from({ length: 3 }, () => `<li class="skeleton-row"><span class="skeleton"></span><span class="skeleton skeleton--short"></span></li>`).join("");
  return `<section class="grid grid--split">
    <div class="card"><div class="card__head"><h2>Policies</h2></div><ul class="record-list" role="list">${rows}</ul></div>
    <div class="card"><div class="card__head"><h2>Claims</h2></div><ul class="record-list" role="list">${rows}</ul></div>
  </section>`;
}

/* ----------------------------------------------------------- reconciliation */

export function reconciliationView(entries: Array<Workflow | SampleWorkflow>, selected: Workflow | SampleWorkflow | null): string {
  const exceptions = entries.filter((entry) => entry.state === "reconciliation_required" || entry.state === "failed");
  return `
    ${pageHead(
      "Controls",
      "Reconciliation queue",
      "Workflows whose downstream steps failed and require an operator decision before retrying.",
    )}
    <section class="card">
      <div class="card__head"><h2>Exceptions</h2><span class="pill ${exceptions.length ? "pill--danger" : ""}">${escapeHtml(exceptions.length)}</span></div>
      ${
        exceptions.length
          ? `<ul class="record-list" role="list">${exceptions
              .map(
                (entry) => `
                  <li class="record">
                    <div class="record__main">
                      <span class="record__title">${escapeHtml(humanize(entry.failure_category ?? entry.state))} ${sampleTag((entry as SampleWorkflow).sample)}</span>
                      <code class="record__id">${escapeHtml(shortId(entry.id))}</code>
                      <span class="record__meta">${escapeHtml(entry.retry_count)} retries · ${escapeHtml(relativeTime(entry.updated_at))}</span>
                    </div>
                    <div class="record__side">${badge(entry.state)}<button type="button" class="button button--ghost button--sm" data-workflow="${escapeHtml(entry.id)}">Inspect</button></div>
                  </li>`,
              )
              .join("")}</ul>`
          : `<div class="empty empty--positive"><span class="empty__icon" aria-hidden="true">✓</span><h3>Queue is clear</h3><p class="muted">No workflows currently require reconciliation.</p></div>`
      }
    </section>
    ${selected ? `<section class="card">${workflowDetail(selected)}</section>` : ""}`;
}

/* ------------------------------------------------------------------- shared */

export function emptyState(title: string, description: string, navTarget: NavKey, actionLabel: string): string {
  return `
    <div class="empty">
      <span class="empty__icon" aria-hidden="true">◍</span>
      <h3>${escapeHtml(title)}</h3>
      <p class="muted">${escapeHtml(description)}</p>
      <button type="button" class="button button--ghost" data-nav="${navTarget}">${escapeHtml(actionLabel)}</button>
    </div>`;
}
