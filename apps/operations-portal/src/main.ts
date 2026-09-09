import { ApiClient, ApiError, type Claim, type Policy, type Workflow } from "./api";
import { DEMO_MODE, simulateRetry, simulateWorkflow } from "./demo-mode";
import { probeAll, SERVICES, type ServiceHealth } from "./health";
import { DEMO_POLICYHOLDER_ID, sampleClaims, samplePolicies, sampleWorkflowDraft } from "./sample-data";
import { WorkflowHistory } from "./store";
import {
  dashboardView,
  historyView,
  reconciliationView,
  recordsView,
  shell,
  wizardView,
  type Banner,
  type NavKey,
  type RecordsState,
  type WizardViewState,
} from "./views";
import {
  EMPTY_DRAFT,
  WIZARD_STEPS,
  canAdvance,
  furthestReachableStep,
  toWorkflowRequest,
  validateDraft,
  type WizardDraft,
} from "./wizard";
import "./styles.css";

const client = new ApiClient({ token: import.meta.env.VITE_API_TOKEN });
const history = new WorkflowHistory();
const app = document.querySelector<HTMLDivElement>("#app")!;

const HEALTH_POLL_MS = 20_000;

interface AppState {
  active: NavKey;
  banner: Banner | null;
  navOpen: boolean;
  healthOpen: boolean;
  health: ServiceHealth[];
  wizard: WizardViewState;
  records: RecordsState;
  selectedWorkflowId: string | null;
  historyQuery: string;
}

const state: AppState = {
  active: "dashboard",
  banner: null,
  navOpen: false,
  healthOpen: false,
  health: SERVICES.map((service) => ({ ...service, state: "checking", checkedAt: null })),
  wizard: { step: 1, draft: { ...EMPTY_DRAFT }, showErrors: false, submitting: false, result: null },
  records: { holder: "", loading: false, loaded: false, policies: samplePolicies, claims: sampleClaims, usingSamples: true },
  selectedWorkflowId: null,
  historyQuery: "",
};

/** Rebuilds the DOM for the current state and restores transient focus. */
function render(): void {
  const activeId = document.activeElement instanceof HTMLElement ? document.activeElement.id : null;
  const caret = document.activeElement instanceof HTMLInputElement ? document.activeElement.selectionStart : null;

  const selected = state.selectedWorkflowId ? history.find(state.selectedWorkflowId) ?? null : null;
  let content: string;

  switch (state.active) {
    case "workflow":
      content = wizardView(state.wizard, furthestReachableStep(state.wizard.draft));
      break;
    case "history":
      content = historyView(history.all(), selected, state.historyQuery);
      break;
    case "records":
      content = recordsView(state.records);
      break;
    case "reconciliation":
      content = reconciliationView(history.all(), selected);
      break;
    default:
      content = dashboardView(history.metrics(), history.all(), state.health);
  }

  app.innerHTML = shell(
    { active: state.active, banner: state.banner, health: state.health, healthOpen: state.healthOpen, navOpen: state.navOpen },
    content,
  );

  if (activeId) {
    const restored = document.getElementById(activeId);
    if (restored instanceof HTMLInputElement || restored instanceof HTMLTextAreaElement) {
      restored.focus();
      if (caret !== null && restored instanceof HTMLInputElement && restored.type !== "date" && restored.type !== "number") {
        restored.setSelectionRange(caret, caret);
      }
    }
  }
}

function navigate(target: NavKey): void {
  state.active = target;
  state.navOpen = false;
  state.banner = null;
  render();
}

function notify(tone: Banner["tone"], text: string, requestId?: string): void {
  state.banner = { tone, text, requestId };
}

/** Executes an API call, translating failures into a consistent banner message. */
async function run<T>(action: () => Promise<T>, onSuccess: (value: T) => void): Promise<void> {
  try {
    onSuccess(await action());
  } catch (error) {
    if (error instanceof ApiError) notify("error", error.message, error.requestId);
    else notify("error", "Unable to reach the service. Check that the Compose stack is running.");
    render();
  }
}

/* --------------------------------------------------------------- wizard flow */

/** Copies live form values into the draft so navigation never loses input. */
function captureDraft(): void {
  const form = document.querySelector<HTMLFormElement>("#wizard-form");
  if (!form) return;
  const data = new FormData(form);
  for (const key of Object.keys(state.wizard.draft) as Array<keyof WizardDraft>) {
    const value = data.get(key);
    if (typeof value === "string") state.wizard.draft[key] = value;
  }
}

function goToStep(step: number): void {
  captureDraft();
  state.wizard.step = Math.min(Math.max(step, 1), WIZARD_STEPS.length);
  state.wizard.showErrors = false;
  render();
}

async function advanceWizard(): Promise<void> {
  captureDraft();
  const step = WIZARD_STEPS[state.wizard.step - 1];

  if (!canAdvance(state.wizard.draft, step)) {
    state.wizard.showErrors = true;
    notify("error", "Fix the highlighted fields before continuing.");
    render();
    return;
  }

  if (step.key !== "review") {
    state.wizard.step += 1;
    state.wizard.showErrors = false;
    state.banner = null;
    render();
    return;
  }

  if (Object.keys(validateDraft(state.wizard.draft)).length > 0) {
    state.wizard.showErrors = true;
    render();
    return;
  }

  state.wizard.submitting = true;
  state.banner = null;
  render();

  await run(
    () => (DEMO_MODE ? simulateWorkflow(toWorkflowRequest(state.wizard.draft)) : client.submitWorkflow(toWorkflowRequest(state.wizard.draft))),
    (workflow: Workflow) => {
      history.record(workflow);
      state.wizard.result = workflow;
      state.wizard.step = WIZARD_STEPS.length;
      state.selectedWorkflowId = workflow.id;
      notify(
        workflow.state === "completed" ? "success" : "info",
        `Workflow ${workflow.id} is ${workflow.state.replace(/_/g, " ")}.`,
      );
    },
  );

  state.wizard.submitting = false;
  render();
}

function resetWizard(): void {
  state.wizard = { step: 1, draft: { ...EMPTY_DRAFT }, showErrors: false, submitting: false, result: null };
  state.banner = null;
  render();
}

/* -------------------------------------------------------------- records flow */

async function loadRecords(holder: string): Promise<void> {
  state.records.holder = holder;
  state.records.loading = true;
  state.banner = null;
  render();

  await run(
    async () =>
      DEMO_MODE
        ? { policies: samplePolicies, claims: sampleClaims }
        : { policies: await client.listPolicies(holder), claims: await client.listClaims(holder) },
    (value: { policies: Policy[]; claims: Claim[] }) => {
      state.records = {
        holder,
        loading: false,
        loaded: true,
        policies: value.policies,
        claims: value.claims,
        usingSamples: false,
      };
      notify("success", `Loaded ${value.policies.length} policies and ${value.claims.length} claims.`);
    },
  );

  state.records.loading = false;
  render();
}

/* ------------------------------------------------------------------- events */

document.addEventListener("submit", (event) => {
  const form = event.target as HTMLFormElement;
  event.preventDefault();

  if (form.id === "wizard-form") void advanceWizard();
  if (form.id === "records-form") {
    const holder = String(new FormData(form).get("holder") ?? "").trim();
    if (holder) void loadRecords(holder);
  }
});

document.addEventListener("click", (event) => {
  const target = (event.target as HTMLElement).closest<HTMLElement>("button");
  if (!target) return;

  if (target.dataset.nav) return navigate(target.dataset.nav as NavKey);
  if (target.dataset.step) return goToStep(Number(target.dataset.step));
  if (target.hasAttribute("data-step-back")) return goToStep(state.wizard.step - 1);

  if (target.dataset.workflow) {
    state.selectedWorkflowId = target.dataset.workflow;
    if (state.active !== "reconciliation") state.active = "history";
    return render();
  }

  if (target.dataset.retry) {
    const id = target.dataset.retry;
    const existing = history.find(id);
    void run(
      () => (DEMO_MODE && existing ? simulateRetry(existing) : client.retryWorkflow(id)),
      (workflow: Workflow) => {
        history.record(workflow);
        state.selectedWorkflowId = workflow.id;
        notify("success", `Retry requested. Workflow is now ${workflow.state.replace(/_/g, " ")}.`);
        render();
      },
    );
    return;
  }

  switch (target.id) {
    case "nav-toggle":
      state.navOpen = !state.navOpen;
      return render();
    case "health-toggle":
      state.healthOpen = !state.healthOpen;
      return render();
    case "banner-dismiss":
      state.banner = null;
      return render();
    case "wizard-reset":
      return resetWizard();
    case "use-sample":
      state.wizard.draft = { ...sampleWorkflowDraft };
      state.wizard.showErrors = false;
      notify("info", "Example claim details loaded. Review each step before submitting.");
      return render();
    case "use-sample-holder":
      return void loadRecords(DEMO_POLICYHOLDER_ID);
    default:
      break;
  }
});

document.addEventListener("input", (event) => {
  const target = event.target as HTMLElement;
  if (target.id === "history-search") {
    state.historyQuery = (target as HTMLInputElement).value;
    render();
  }
});

/* -------------------------------------------------------------- health poll */

async function refreshHealth(): Promise<void> {
  state.health = await probeAll();
  render();
}

void refreshHealth();
setInterval(() => void refreshHealth(), HEALTH_POLL_MS);

render();
