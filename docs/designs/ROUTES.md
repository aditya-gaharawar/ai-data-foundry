# Console route contracts

All routes require a real session; APIs also accept scoped user-owned keys.
Tenant context is verified server-side. Unimplemented destinations are hidden.
Common states: role="status" skeletons, real empty results, Problem Details
errors with request IDs, and scope-denied views. No fixture KPIs are substituted.

| Route | Query source | Mutations | Required scope / verification |
| --- | --- | --- | --- |
| `/overview` | `/v1/overview`, projects and session | Open create dialog, project/theme/menu preferences | datasets:read; browser/a11y/empty-tenant proof |
| `/datasets` | Paginated `/v1/datasets` with q/project/cursor | POST dataset | datasets:read/write; persisted create/search/cursor proof |
| `/datasets/[id]` | Dataset, versions, sample pages and uploads | PATCH details, multipart create/complete, export | datasets:read/write; generation and real browser upload to version |
| `/workflows`, `/workflows/new`, `/workflows/[id]` | Recipes/revisions, datasets, upload metadata and estimate | Validate, save immutable revision, launch | datasets:write and runs:execute; JSON/form/graph share a DSL and preserve target |
| `/runs`, `/runs/[id]` | Runs, real polling, structured events | Cancel, retry, export; local log download/filter | datasets:read and runs:execute; durable recovery and keyboard-only proof |
| `/settings/api-keys` | Scoped key metadata | Create/reveal once, revoke, copy | keys:manage; one-time/hash/scope/revocation proof |
| `/settings/members` | Organization memberships | Provision local user, change role, remove membership | members:manage; Viewer and revocation proof |
| `/settings/webhooks` | Endpoints and delivery attempts | Create, rotate secret, disable and authorized replay | webhooks:manage; HMAC/500/retry/dead-letter/replay proof |
| `/settings/usage` | Actual meters, reservations and caps | PATCH internal budget | budgets:manage for edits; no invoice or paid-cost simulation |
| `/settings/audit` | Cursor-paginated immutable audit | Copy correlation ID | audit:read; scoped append-only evidence |
| `/developers` | Actual generated `/v1/openapi.json` | Copy examples, download contract | authenticated console; no fictional operations or credentials |

Desktop sidebar collapses; below 768px navigation is a keyboard-accessible drawer.
Grids become one/two columns and long tables scroll inside labeled regions.
Dialogs trap and return focus; Escape closes them. Ctrl/Cmd+K searches navigation
and actual datasets. Light/dark preference persists and reduced motion is honored.
Actual DOM and Playwright behavior, not static render-only mocks, provide proof.

Telemetry is structured API request IDs, tenant-scoped audit and worker/run event
IDs, plus actual usage. Production OTel traces and a notification center remain
unimplemented. Every partial capability is identified in the feature matrix.
