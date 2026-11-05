# Console route contracts

All routes require a real session; APIs also accept scoped user-owned keys.
Tenant context is verified server-side. Unimplemented destinations are hidden.
Common states: role="status" skeletons, real empty results, Problem Details
errors with request IDs, and scope-denied views. No fixture KPIs are substituted.

P07–P12 add these verified local routes. Their limits and full browser evidence
are in `verification/evidence/p07-p12/VERIFICATION.md`.

| Route | Query source | Mutations | Required scope / verification |
| --- | --- | --- | --- |
| `/teacher` | providers/catalog, providers, datasets | rights-aware connection/revoke, saved recipe/estimate, durable generation | providers:manage to connect; datasets:write + runs:execute to generate |
| `/simulations` | capabilities, image datasets | parameterized Blender recipe/estimate/run | datasets:write + runs:execute; incompatible Isaac blocked |
| `/datasets/[id]` simulation inspector | authenticated RGB, mask and GLB artifacts, metadata | lazy verified 3D viewer; exports | datasets:read; holdout and erasure checked server-side |
| `/compute` | pools, agents, jobs, versions | pool/enrollment/revoke, placement, fixed verification/cancel | compute:manage for identities; runs:execute for jobs |
| `/evaluations` | lexical index, version distributions/diffs, benchmarks, outcomes, feedback | benchmark registration, outcome import, bounded proposal/decision | evaluations:write; holdouts:read for benchmarks/solutions |
| `/settings/governance` | immutable policy, dataset protection, approvals, erasures, tokens | policy revisions, holdout/legal hold, independent approval, sealed erasure, SCIM token/revoke | governance:manage; members:manage for provisioning tokens |
| `/operations` | source fingerprint, current gates, ledger, incidents, operator proofs | reconciliation, incident scan/ack, signed readiness | operations:manage; proof import additionally needs operator HMAC |

| Route | Query source | Mutations | Required scope / verification |
| --- | --- | --- | --- |
| `/overview` | `/v1/overview`, projects and session | Open create dialog, project/theme/menu preferences | datasets:read; browser/a11y/empty-tenant proof |
| `/datasets` | Paginated `/v1/datasets` with q/project/cursor | POST dataset | datasets:read/write; persisted create/search/cursor proof |
| `/datasets/[id]` | Dataset, versions, sample pages and uploads | PATCH details, multipart create/complete, export | datasets:read/write; generation and real browser upload to version |
| `/curation`, `/curation/new`, `/curation/[id]` | Sessions, source uploads/versions, quality, tasks | Create session, save data card, approve/freeze, prepare recipe/estimate and launch publication | annotations:manage and runs:execute for writes; real review-to-export browser proof |
| `/curation/profiles` | Paginated immutable quality profiles | Create scoped profile | annotations:manage; actual persisted thresholds and dedupe evidence |
| `/curation/tasks/[id]` | Source payload/private image, review history and eligible reviewers | Claim/assign, category/box edits, review/reject/adjudicate/reopen | annotations:review/manage/adjudicate; independent users, revision conflicts, keyboard and axe proof |
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
