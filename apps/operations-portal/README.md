# Operations Portal

Framework-free TypeScript operations console for the claims orchestration platform. It is the human control surface for submitting workflows, inspecting saga execution, looking up records, and handling reconciliation exceptions.

![Operations Portal walkthrough](../../docs/demo/operations-portal-demo.gif)

## Capabilities

- **Guided five-step workflow.** Policy → Incident → Assessment → Review → Result. Each step validates only its own fields, the numbered stepper shows progress, and completed steps stay navigable so operators can go back without losing input.
- **Live service health.** Every platform service `/health` endpoint is polled on an interval; the header indicator and dashboard reflect the true state instead of a static label.
- **Persistent history.** Workflows submitted from the console are stored in `localStorage` and survive reloads. Bundled sample runs are always appended so history, records, and reconciliation views are never empty on a fresh environment. Sample records are visibly tagged.
- **Records lookup.** Policies and claims for a policyholder, with a one-click sample identifier.
- **Reconciliation queue.** Failed and reconciliation-required workflows with failure category, retry count, and an operator retry action.

## Security and resilience

Credentials stay in memory (`VITE_API_TOKEN` is injected at build time and never persisted). Requests use abortable timeouts, generated `Idempotency-Key` headers on state-changing calls, URL-encoded identifiers, and typed API errors that surface the service `x-request-id`. All rendered values pass through HTML escaping because the UI builds markup from strings.

## Architecture

| Module | Responsibility |
| --- | --- |
| `api.ts` | Typed HTTP client for every platform service |
| `wizard.ts` | Step model, validation rules, and request mapping |
| `views.ts` | Pure rendering functions returning HTML strings |
| `store.ts` | Workflow history persistence and dashboard metrics |
| `health.ts` | Service probing and availability summarisation |
| `format.ts` | Escaping, currency, date, and badge-tone helpers |
| `sample-data.ts` | Deterministic demonstration records |
| `main.ts` | State, event wiring, and render orchestration |

## Local development

```sh
npm install
npm run dev
npm test        # 28 tests across api, wizard, store, and UI helpers
npm run build   # type-check then production bundle
```

Service URLs default to ports `8000`–`8008` from the repository Compose stack. Set `VITE_API_TOKEN` for authenticated API calls.

## Container

From the repository root, `docker compose up --build operations-portal` serves the compiled app at http://localhost:3000. Browser API calls still target the host service ports by default; configure the service URLs at build time for another environment.

## Accessibility

The console ships a skip link, landmark regions, `aria-current` navigation state, labelled form fields with inline error text, live-region banners, visible focus rings, and a `prefers-reduced-motion` fallback. The layout is responsive down to mobile widths with an off-canvas navigation drawer.
