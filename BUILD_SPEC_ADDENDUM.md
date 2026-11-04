# 28. Version 2 mandate: Vercel-inspired, functional by design

**Status:** Approved design direction for implementation planning, not evidence of a running product. **Supersedes any earlier ambiguous UI or integration requirement.** Use the original Sections 1-27 as the baseline; this addendum makes the specification actionable for Codex.

## 28.1 Product principle

The application must *feel as deliberate, fast, legible, and dependable as a top-tier developer cloud console*. The visual reference is Vercel's Geist design language (structure, typography, monochrome surfaces, grid, code-first clarity, and refined interactions), **not** an instruction to copy Vercel branding, source code, trademarks, illustrations, or trade dress pixel for pixel. Our product must have its own name, visual identity, and independently implemented design system.

**Non-negotiable:** Nothing presented as functional may be fake. A button must navigate, call an implemented API, open a meaningful dialog, change persisted state, or be visibly disabled with an explanation. No random data masquerading as live usage. No frontend-only success messages when backend actions failed. Unsupported connectors must say `Coming later / Requires configuration`, not `Connected`. Every page needs honest empty, loading, error, permission-denied, and degraded-service states.

## 28.2 Vertical slices, not mockups

Use **one feature end to end at a time**: persisted database model -> authenticated API endpoint -> background worker -> stored artifact/observability -> web experience -> SDK -> tests -> docs. Screenshots and visual QA are required, but a beautiful screenshot is not proof that a feature works. A feature is complete only when the user journey runs using real services in a reproducible local environment.

## 28.3 Scope protection

The full product includes the twelve engines already described. V1 must demonstrate the platform contract on CPU and optionally through one authorized, configured API provider. Advanced video, Isaac Sim/Isaac Lab, multi-cloud HPC, custom accelerator drivers, browser 3D editing, and full enterprise integrations are **phased integrations**. Do not simulate paid GPU jobs or label placeholders as production. All connectors expose capability, configuration, dependency, availability, permission, and health state.

# 29. Product information architecture and screen-by-screen design

## 29.1 Left navigation

Persistent workspace-aware navigation, collapsed sidebar on narrow screens, proper keyboard focus and semantics. Proposed IA:

| Group | Destination | Must be functional |
|---|---|---|
| HOME | Overview | Organization summary, recent runs, failures, usage, setup checklist |
| DATA | Datasets | Browse/search/filter/create/import; access-controlled listing |
| DATA | Dataset detail | Versions, sample preview, manifests, quality, lineage, exports, permissions |
| BUILD | Generation Studio | Text, image, audio, video requests through available generators |
| BUILD | Teacher Studio | Authorized model endpoints, structured output, independent verification |
| BUILD | Simulation Studio | Scene recipes, engine compatibility, job setup, asset previews, episode results |
| BUILD | Annotation Studio | Projects, queues, labeling, adjudication, quality and export |
| BUILD | Workflows | DAG recipe editor, schedules, revisions, run history |
| BUILD | Data Intelligence | Cleaning, quality profiles, dedupe, search, distribution reports |
| COMPUTE | Compute pools | Agents, accelerators, capacity, capabilities, prices, quotas, job placement |
| COMPUTE | Jobs & Runs | Queue/status/retries/cancel, logs, checkpoints, cost, trace and outputs |
| MEASURE | Evaluation Lab | Dataset metrics, compare versions, benchmark results, feedback loop |
| MEASURE | Usage & Billing | Spending, budgets, meters, invoices if configured; clear unbilled state |
| DEVELOPERS | API keys | Scoped credentials, one-time secret reveal, rotation, audit |
| DEVELOPERS | Webhooks | Endpoints, signing secrets, delivery history, replay |
| DEVELOPERS | API Explorer | OpenAPI-generated explorer, snippets, code examples, SDK links |
| SETTINGS | Connections | AI providers, buckets, Git repositories, storage, compute, test connection |
| SETTINGS | Members & roles | Invite, revoke, role assignment, service accounts |
| SETTINGS | Policies | Retention, PII, source rights, approvals, region and export policy |
| SETTINGS | Audit log | Query actor, action, target, IP/time, correlation IDs, export |

Add a global command menu (Ctrl/Cmd+K), omnibox search, organization/project switcher, breadcrumbs, keyboard shortcuts, a notifications center, persistent help/docs, and mobile-friendly navigation. Every global affordance needs an actual behavior and tests.

## 29.2 Five critical routes first

1. `/overview` — real organization summary and onboarding states; zero values display as zero, not fabricated KPIs.
2. `/datasets` and `/datasets/[id]` — create, import, inspect, compare, publish, export; real upload status and quotas.
3. `/workflows/new` and `/workflows/[id]` — declarative recipe form with source/transform/validate/export steps; form builder first, visual DAG second.
4. `/runs` and `/runs/[id]` — honest run state, attempts, progress, error, retry/abort actions, downloadable log and trace IDs.
5. `/settings/api-keys` — scoped key creation/revoke and authenticated quick-start example.

Implement these before filling out the rest of the navigation. Sidebar destinations without functionality must either be hidden by flags or clearly disabled.

## 29.3 Primary interaction patterns

- Multi-step **Create dataset** flow: choose modality -> name/schema -> ingest/generate -> preview requirements -> quote cost -> review source-use policy -> create -> monitor -> inspect version.
- **Build pipeline**: choose an ingestion/generation node, validation and output; validate DAG at edit time; display generated DSL; confirm credits/budget; launch; show logs and cost.
- **Teacher synthesis**: choose permitted provider/teacher; present license warning and model-use permissions; prompt/schema; sample generation; independent verification; approval; run.
- **Simulation**: pick Blender/Isaac engine; display capability requirements, asset licenses and worker availability; edit recipe parameters; preview locally/remotely if available; run; inspect synchronized frames/labels.
- **Dataset review**: paginate and lazily load samples, annotate, comment, resolve disagreements, export accepted artifacts.
- **Failure recovery**: show root cause with retry classification, link to logs, budget consequences, checkpoints and retry eligibility.

## 29.4 Functional UI contract

Each route is defined with `route ID`, `query API`, `mutations`, `required scopes`, `empty state`, `loading state`, `error state`, `disabled state`, `telemetry`, `a11y tests`, and `E2E flow`. A page cannot merge without filling this contract. Interactive graph nodes, filters, sorts, pagination, file-drop zones, dataset cards, and keyboard commands must have tests; all metadata must come from real API responses or explicitly marked fixtures in development mode.

# 30. Visual system: Geist-inspired, original identity

## 30.1 Art direction

- Use a refined neutral palette, high contrast and restrained accents; bright colors are for meaning (success, failure, warning, active selection), not decoration.
- Clean desktop console, sophisticated narrow-width layouts, generous whitespace but dense enough for data engineers. Prefer a 12-column layout, consistent container widths, and an 8px spacing scale.
- Headings in Geist Sans or legally available equivalent; code/logs/IDs in Geist Mono or equivalent. Pin font packages and license compliance. Do not bundle font files in handoff documents.
- Minimal black/white landing, subtle borders/dividers, 1px hairlines, soft shadows only on overlays. Square-ish cards with small tasteful radius. Avoid gradients, glassmorphism, exaggerated animations, or arbitrary colors.
- Light and dark themes with persisted preference; system default, accessible contrast, reduced-motion behavior.
- Icons from a coherent set (Lucide or an appropriately licensed set); real tables, charts, terminal logs, graph edges, image previews and dataset samples take priority over decoration.
- Render server-owned data in server components where practical; client components only for interactivity. Provide skeletons that match the final layout and prevent hydration flicker.

## 30.2 Initial tokens (proposal, adjust with visual QA)

| Token | Light | Dark | Purpose |
|---|---|---|---|
| Canvas | `#FFFFFF` | `#0A0A0A` | App background |
| Surface | `#FAFAFA` | `#111111` | Subtle secondary surface |
| Elevated | `#FFFFFF` | `#171717` | Popovers and modals |
| Text primary | `#171717` | `#EDEDED` | Main copy |
| Text muted | `#666666` | `#A1A1A1` | Supporting copy |
| Border | `#EAEAEA` | `#333333` | Delimiters |
| Focus ring | `#0070F3` | `#3291FF` | Accessible focus state |
| Positive | `#16803C` | `#46A758` | Success |
| Warning | `#B76E00` | `#F5A524` | Attention |
| Destructive | `#DC2626` | `#F87171` | Irreversible/failure |

These are *our proposed tokens*, not a claim of identical Vercel tokens. Define CSS variables and consume them through semantic Tailwind aliases; never hard-code colors in individual page components.

## 30.3 Component inventory

`AppShell`, `WorkspaceSwitcher`, `Sidebar`, `Topbar`, `CommandMenu`, `Breadcrumbs`, `PageHeader`, `DataTable`, `Metric`, `StatusPill`, `EmptyState`, `ErrorState`, `ConfirmDialog`, `ActivityTimeline`, `ResourceSelector`, `QuotaBar`, `CostEstimate`, `KeyValueList`, `JSONViewer`, `CodeEditor`, `LogViewer`, `ArtifactPreview`, `SampleGallery`, `SchemaEditor`, `DAGCanvas`, `JobTimeline`, `FilterBuilder`, `UploadManager`, `DataCard`, `PermissionGate`, `InlineNotice`, `FormField`, `CopyableValue`, `Toast`.

Primitive UI: Next.js App Router + React + TypeScript + Tailwind CSS + accessible Radix/shadcn-style primitives (copy to project code, customize with tokens), TanStack Query for client synchronization, TanStack Table for complex grids, React Flow for DAG canvas, Monaco or CodeMirror for DSL editing if bundle and licensing are acceptable, and Lucide. Avoid mixing four UI libraries. Storybook is optional initially; component stories/tests required at least for critical primitives.

## 30.4 Responsive and accessibility acceptance

- Test 360px, 390px, 768px, 1024px and 1440px widths; no horizontal overflow outside intentionally scrollable data grids.
- All controls usable without a mouse; visible focus and meaningful labels; escape closes dialogs; focus returns to trigger; status updates announced where needed.
- WCAG 2.2 AA as acceptance target; automated axe checks and manual keyboard/screen reader smoke test.
- Virtualize long tables/lists; pagination server side; image/audio/video previews load progressively; support reduced motion.
- Error and success toasts include a correlation ID when actionable; never replace an error with a silent reset.

# 31. Runtime boundary: Vercel UI, external compute

## 31.1 The deployable topology

```text
                Browser / SDK / CLI
                        |
                  TLS / WAF / CDN
                        |
           +------------+-----------+
           |                        |
       Next.js UI                  FastAPI API
       on Vercel                 on container host
           |                        |
       Server-side              IAM / policy / budgets
       auth/BFF                      |
           |                  Postgres + object storage
           |                        |
           +----- signed API calls -+
                                    |
                             Durable workflows
                                    |
                      Worker runtime / GPU scheduler
                           |           |        |
                         CPU/Ray    RTX/Isaac  Slurm/HPC
```

**Important:** Vercel is the UI hosting and edge delivery layer, **not** the default execution venue for hours-long GPU simulation or training-data generation. Even where platform functions permit relatively long durations, they have bounded execution time and lack arbitrary access to dedicated NVIDIA GPUs/Isaac runtime. Keep jobs in long-lived, isolated container/cluster workers. Frontend calls use short requests to submit and poll jobs, or subscribe to an event gateway.

## 31.2 Environments

| Environment | Purpose | Data and billing |
|---|---|---|
| local | Docker Compose: API, Postgres, MinIO, workflow worker, web | Seeded synthetic fixtures, no paid integrations by default |
| preview | Per-PR Vercel UI; optional shared limited API/test DB | Synthetic fixtures, isolated test tenants; no production secrets |
| staging | Full integrated rehearsal of production topology | Dedicated DB/bucket/keys; capped resources |
| production | Customer-facing service with monitoring, backup, rotation and change control | Live customers; gated promotion and rollback |

Vercel project connects to Git branches; preview and production use separate environment variables. API must validate trusted origins, JWT issuer/audience/scopes, and CORS according to the deployment topology. Never expose provider secrets or private agent credentials in `NEXT_PUBLIC_` variables. Direct browser-to-object-store transfers must use short-lived signed URLs and bucket CORS rules.

## 31.3 Deployment pipelines

PR -> lint/types/unit -> API contract check -> backend integration -> Playwright E2E -> security checks -> build -> preview -> design/functional QA -> merge -> staging migration rehearsal -> load/recovery checks -> approved production release -> synthetic production checks. Database schema migrations must be backward-compatible with the prior deployed API, and destructive migrations require a multi-release process.

# 32. Monorepo blueprint

```text
ai-data-foundry/
  AGENTS.md                    # Codex's standing instructions
  README.md                    # setup, development and verified capabilities
  CODEX_START.md               # phase-by-phase launch directions
  docker-compose.yml           # local Postgres, MinIO, Temporal/worker
  Makefile                     # setup/dev/test/lint/smoke commands
  .env.example                 # placeholders only: no secrets
  pnpm-workspace.yaml
  turbo.json
  apps/
    web/                       # Next.js App Router, design system + screens
    api/                       # FastAPI, models, routers, migrations
    docs/                      # API guides + developer docs (later)
  packages/
    ui/                        # reusable design system + tokens
    api-types/                 # generated TS types from OpenAPI
    sdk-ts/                    # TypeScript API SDK
    sdk-python/                # Python SDK with real HTTP transport
    contracts/                 # JSON Schema, OpenAPI and events
    config/                    # shared lint/types/tooling
  workers/
    core/                      # deterministic CPU jobs, quality, export
    generation/                # permitted teacher & media adapters
    blender/                   # packaged headless Blender runtime
    isaac-sim/                 # RTX Linux GPU runtime, independent image
    isaac-lab/                 # compatible robot-learning runtime
    compute-agent/             # outbound-only signed private agent
  services/
    scheduler/                 # compute eligibility, placement, leases
    event-delivery/            # outbox, signed webhooks and retries
  infra/
    terraform/                 # versioned production infrastructure
    k8s/                       # GPU workers and Kueue profiles
    slurm/                     # adapter submission/test fixtures
    vercel/                    # frontend config/reference
  tests/
    e2e/                       # Playwright full user journeys
    integration/               # API + DB + S3 + workers
    security/                  # cross-tenant and auth negatives
    load/                      # k6 or Locust benchmarks
    fixtures/                  # versioned synthetic data only
  docs/
    architecture/              # ADRs, threat model, diagrams
    product/                   # feature matrix, acceptance criteria
    runbooks/                  # incident, rollback, backup/restore
    api/                       # API versioning and webhook behavior
    designs/                   # tokens, screens, interaction contract
  .github/workflows/           # CI, PR validation, SAST/dependency checks
```

Do not create dozens of empty packages just to match this tree. Create each directory when its first working executable, contract, or test lands. Tests and docs may be created early to define intent; runtime modules without implementation are explicitly marked `not implemented` and are excluded from default UI navigation.

# 33. API and SDK contract: production-grade behavior

## 33.1 Rules

- Public base path `/v1`; OpenAPI 3.1 source of truth, generated TS types and Python client contracts; additive changes are compatible, breaking changes require a new version.
- Authentication: OIDC session for browser, short-lived scoped service tokens/API keys for service integration, tenant verified from authenticated principal rather than from arbitrary request body.
- Request correlation ID, RFC 7807 Problem Details errors, trace ID, consistent UTC RFC 3339 timestamps and opaque ULIDs/UUIDs.
- Cursor pagination (`limit`, `cursor`), stable ordering, filter syntax and sort whitelist; limits enforced server-side.
- Create/launch endpoints accept `Idempotency-Key` and canonical request hash; replay identical request yields same resource, mismatched body yields conflict.
- API returns `202 Accepted` for compute-bound launches with `Location` run URL. Never hold a request open until a GPU job completes.
- Exact-once externally observable effects are achieved by idempotency and outbox dedupe, not by claiming distributed workers execute exactly once.
- Mutations enforce scopes and per-resource policy; archived dataset versions remain immutable and only metadata explicitly designated mutable can be edited.
- Provide OpenAPI-examples for both successful and negative responses; generated SDKs handle retries only on safe/idempotent operations.

## 33.2 Key API resources

| Resource | Primary actions | Notes |
|---|---|---|
| `/organizations`, `/projects` | list/create/update | Tenant-scoped administrative permissions |
| `/datasets` | list/create/search | Schema, modality, lifecycle |
| `/datasets/{id}/versions` | list/get/publish | Immutable manifest and digest |
| `/uploads` | initiate/complete/abort | Multipart direct-to-object-store, checksum verification |
| `/imports` | create/inspect | URL allowlist/SSRF protection, sources/licenses |
| `/recipes`, `/recipes/{id}/revisions` | validate/create/revise | Versioned DAG and engine locks |
| `/runs` | launch/list/get/cancel/retry | Durably queued, budget approved |
| `/runs/{id}/events` | list/stream | Server-Sent Events/polling fallback, resume token |
| `/generations`, `/distillations`, `/simulations` | create and get | Convenience endpoints compile recipes to runs |
| `/annotations/tasks`, `/reviews` | list/assign/submit/adjudicate | Optimistic locking, reviewer audit |
| `/quality-profiles`, `/evaluations` | manage/run/compare | Quality gate evidence |
| `/exports` | create/get/download | Signed, short-lived, policy checked |
| `/compute/pools`, `/compute/agents` | register/status/revoke | mTLS or equivalent workload identity |
| `/provider-connections` | configure/test/rotate | No secret values in GET response |
| `/usage`, `/budgets` | view/change | Append-only ledger, budget lock |
| `/webhooks`, `/webhook-deliveries` | subscribe/rotate/replay | Signed at-least-once delivery |
| `/audit-logs` | immutable query | Privileged, filtered, retention |
| `/health/live`, `/health/ready` | status | No sensitive runtime details in public response |

## 33.3 Representative sample contracts

`POST /v1/datasets`: name, modality, validated schema, project ID, optional retention, policy; returns `201` plus opaque ID. `POST /v1/recipes`: versioned DAG with source -> processor -> validator -> publisher, engine/connector versions and resource budgets; graph validated before persistence. `POST /v1/runs`: `{recipe_revision_id, dataset_id, request_id, max_budget_usd, compute_constraints}` -> `202` and run state. `POST /v1/exports`: `{version_id, format, destination}` -> asynchronous export; download via signed URL after READY.

Events use `event_id`, `event_type`, `schema_version`, `occurred_at`, `organization_id`, `resource_id`, and `data`. Signed webhooks include timestamp, delivery ID and HMAC SHA-256 signature; verify on raw request bytes and bounded time window. Failed deliveries are retried with backoff and dead-letter handling; users can replay authorized deliveries.

## 33.4 SDK must work from a blank environment

Python: `from datafoundry import DataFoundry`; `client.datasets.create(...)`, `client.runs.create(...)`, `client.runs.wait(...)`, `client.datasets.download(...)`; async and sync clients where reasonable. TypeScript: `import {DataFoundry} from '@datafoundry/sdk'` with typed error shapes, timeout/cancellation and retry policy. CLI: `datafoundry auth`, `datasets`, `runs`, `compute`, `webhooks`, `doctor`. Do not publish package names until owned and registered; initially test workspace-local SDKs against the actual API and record supported compatibility versions.

## 33.5 External API usage of generation providers

A provider adapter must declare: supported modalities, input/output schemas, max batch/throughput, token/image pricing metadata, content/data retention settings, API region, terms/license flags, rate limits, timeout/retry rules, credentials, and permitted downstream training uses. No teacher-derived training output is scheduled until the provider connection records explicit authorization. Keep provider response hashes, provenance and generated output in permission-scoped storage. Reserve budget before dispatch; reconcile real provider cost afterward.

# 34. Persistence, consistency, and data correctness

## 34.1 Database essentials

Use PostgreSQL for tenants, projects, datasets, versions, recipe revisions, run state/attempts, external job references, budgets/reservations, usage, audit, webhooks, outbox and approvals. Use `organization_id` on every tenant-bound table; defense in depth via scoped repository queries and optional PostgreSQL RLS. Unique indexes enforce slugs, idempotency requests, version numbering and sample digest uniqueness within a chosen dedupe scope. Use SQL migrations (Alembic for FastAPI). Retention/deletion flows must include legal holds, delayed object deletion, and derivative index cleanup.

## 34.2 Data in object storage, not SQL rows

Raw and output shards live in S3-compatible storage: JSONL/Parquet for text and structured samples, references to images/audio/video, manifest `sha256`, data cards, metrics, lineage and sample indexes. Use temp staging prefixes and a two-phase publish step: validate/checksum all artifacts -> transactionally publish a manifest and immutable dataset version -> make read-only. A failed publish must leave a recoverable staging run, never a half-published version.

## 34.3 Version semantics

`dataset_id` is mutable logical identity. `dataset_version_id` is an immutable snapshot. `recipe_revision_id` is immutable run input; `run_id` is unique per attempt group; `attempt_id` identifies retries. Canonical manifest contains artifact digests, model versions, provider rights, data splits, sample counts, quality results, config, seeds, environment digests and `created_at`. Reproducing a *deterministic* pipeline should compare identical digests; inherently stochastic external providers must be annotated `best-effort reproducible` with captured request and actual response digests, not falsely guaranteed deterministic.

# 35. Production execution engine and failure design

## 35.1 Workflow compilation

User forms and DAG canvas both compile to the same typed recipe JSON Schema. Compiler validates graph acyclicity, declared input/output modality compatibility, permissions, provider rights, environment constraints, budget and required resources. Execution plan is frozen and hashed. Workers process idempotent steps and emit structured events. Outbox publish and webhook dispatch are transactional/compensating so subscribers never receive success before a committed version.

## 35.2 Worker lifecycle

`SUBMITTED -> POLICY_CHECK -> ESTIMATED -> APPROVED -> ADMITTED -> ASSIGNED -> RUNNING -> VERIFYING -> PUBLISHED` plus `BLOCKED`, `CANCELLED`, `FAILED`, `EXPIRED`, and `RETRYING`. Retry only safe stages based on recorded checkpoints; user-visible error includes code, cause, owner and suggested action. Cancellation releases reservations and attempts best-effort cleanup of engine resources; accounting still records spent resources.

## 35.3 Long-running jobs

Use Temporal or an equivalent verified durable orchestration engine. API enqueues jobs and responds immediately; durable worker owns state. Streaming status can use SSE from a dedicated API endpoint with polling fallback; no browser client directly watches a GPU node. Limit concurrency per tenant and provider, reserve budgets, enforce queue fairness, and reject or defer jobs requiring unavailable hardware.

## 35.4 Operational tests that matter

Kill worker mid-job, restart API, turn off object storage, inject provider 429/500, use stale API key, upload invalid MIME, submit duplicate idempotency keys, cross-tenant access, exceed budget, force quality gate failure, disconnect HPC agent, invalidate webhook secret, cancel after partial generation, retry after scheduler timeout. Each scenario has a deterministic integration/E2E test or a documented controlled fault injection test.

# 36. Exact engine integration contracts

| Engine | Output contract | Constraint | Proof of real integration |
|---|---|---|---|
| Text provider | `SampleEnvelope[]`, token usage, license/provenance, validation scores | Terms permit target training use; quota/latency | Real provider call in integration environment with redacted trace |
| Open-weight teacher | Checkpoint digest, tokenizer, input/output records, GPU use | License and deployment environment | Reproducible inference run with captured model hash |
| Image generation | Image artifact + prompt/seed/settings, labels where independently checked | Provider/asset rights, content policies | Verifiable media checksum and preview |
| Audio generation | Audio artifact, transcript/alignment, speaker/locale metadata | Consent/licensing; voice safeguards | Playable file and alignment quality check |
| Video generation | Timestamped clip + frames + captions | High cost; rights and storage | Verified timeline, duration and artifact |
| Blender | Scene recipe, engine version, camera transforms, renders, masks/depth where configured | Blender runtime/image, asset licenses | Headless render and labeled sample E2E on designated node |
| Isaac Sim / Replicator | USD scene, synchronized RGB/depth/segmentation, sensor calibration, poses | RTX GPU with RT cores, Linux/runtime matrix | Actual rendered episode and metadata on compatible RTX worker |
| Isaac Lab | Parallel rollouts, observations, actions, rewards, done flags | Simulator version, GPU, config compatibility | Complete trajectory shard with episode boundaries |
| User uploads | Hash/metadata, parse result, safe preview | Virus/format screening; ZIP bomb safeguards | Test files uploaded to object store, parsed and versioned |
| Annotation model | Label, confidence, model hash, review provenance | Model capabilities, privacy | Prediction + editable reviewer correction persisted |
| HPC/Slurm | Job ID, state, logs, resource accounting, outputs | Slurm version, outbound agent, workload-compatible nodes | Submit, query, cancel, retrieve artifacts on configured cluster |
| Kubernetes GPU | Pod/job IDs, logs, metrics, output artifact | Node labels/drivers, quotas, image signatures | End-to-end workload on configured cluster |

**Hardware placement rule:** An H100/H200 can be appropriate for inference, curation or model training but **cannot satisfy Isaac Sim's RTX real-time ray-tracing requirement** because A100/H100-class hardware lacks suitable RT cores. An engine-aware scheduler must reject unsuitable assignments with an actionable compatibility explanation. Validate the current Isaac Sim/Isaac Lab release matrix before pinning containers.

## 36.1 Additional future modalities

Structured tabular, event/time-series, spatial point clouds, 3D CAD/mesh, molecular/biological, simulation scientific fields, geospatial, multimodal documents, motion capture, and sensor fusion are first-class *schema extension points*. Do not claim scientific domain correctness without specialized validators, expert review and data policies.

# 37. Security and governance as product behavior

## 37.1 Authorizations

Authentication and tenant ownership must be enforced server-side for every dataset, run, key, webhook, export, sample and compute resource. RBAC baseline: Owner, Admin, Engineer, Labeler, Viewer, Service Account; scopes define exact operations (`datasets:read`, `datasets:write`, `runs:execute`, `compute:admin`, etc.). Resource-based policies may further restrict PII or licensed datasets. UI visibility is never a substitute for API authorization.

## 37.2 Dangerous boundaries

- Uploaded scripts and plugins: sandbox per job, outbound egress restrictions, no privileged host mounts, signed/pinned images, quota and time limits.
- Imports: SSRF and DNS-rebinding defense, deny metadata IPs/private ranges, content length and decompression bounds, MIME/sniff checks, malware screening policy.
- Provider credentials: stored in secret manager, encrypted, rotation supported; logs and UI must redact them; no secret values returned after creation.
- Compute agents: outbound connections, per-agent identity, revocation, lease expiry, signed job definitions, narrowly scoped temporary object-store credentials.
- AI-generated data: capture consent/rights/license and provider usage policy, prohibit unlicensed teacher-output training; avoid storing private teacher reasoning traces or sensitive contents unnecessarily.
- PII: classify/redact/approve as needed, data residency and deletion propagation, retention policies, immutable audit with minimized sensitive payloads.
- Abuse prevention: organization rate limits, model provider quota, spend caps, bot protection on key creation, adversarial prompt/poisoned data checks.

## 37.3 Governance UI

Present actionable source-use policies and approval requests before job dispatch. Show `why blocked`, `who can approve`, `what would change`, and actual provider/hardware restrictions. Every decision is auditable. Data card for each version includes purpose, sources, rights, quality measurements, known limitations, content risks, target training uses, and restrictions. Include human-signed review when required.

# 38. Quality, feedback, and evaluation

## 38.1 Quality profiles

Text: schema, grammar where applicable, executable verification, duplicated content, PII/rights and contamination checks, factuality estimates not guarantees. Vision: corrupt images, resolution, perceptual duplicates, object count, bounding box/mask validity, caption alignment, class distributions. Audio/video: codec integrity, silence/clipping, transcription alignment, temporal coherence, consent. Robotics: observation/action synchronization, sensor calibration, collision traces, reward semantics, units and episode completeness.

## 38.2 Quality gates

Every job can set minimum sample acceptance, maximum duplication, license coverage and validation thresholds. A failed gate publishes *nothing*, but stores an error report and allows an authorized correction/retry. Human review has inter-annotator disagreement and adjudication histories. Quality reports show denominators and coverage; confidence is not ground-truth accuracy.

## 38.3 Model impact

Accept evaluation feedback produced by external training systems. Keep holdout datasets access-controlled and prohibit generation workers from reading heldout solutions; measure changes on fixed real-world benchmarks; record baselines, confidence and cost; do not auto-approve synthetic-data iterations solely because they improve on self-generated tests. Use closed-loop generation with budgets, stop conditions and manual approval.

# 39. Pricing, product telemetry, and cost predictability

Meter with append-only usage events: dataset storage bytes and duration, data ingress/egress bytes, sample generation count, tokens/images/audio/video seconds, GPU-seconds per accelerator pool, simulation node-hours, annotation review units, API requests (if billable), custom provider passthrough charges, and export bytes. Distinguish actual external cost from estimated/internal charge. Show reserved, spent, pending and refunded amounts separately. Enforce hard caps before scheduling; later add warning thresholds and monthly organizational budgets. Provide pricing estimator with assumptions instead of pretending estimates are exact.

Admin telemetry: activation funnel (first dataset -> first run -> first published version -> first export), success rate per engine, time-to-dataset, quality acceptance rate, cost/sample, time in queue, run recovery success, frequent failure classes and churn indicators. Respect privacy and avoid recording raw prompts or dataset content into product analytics by default.

# 40. Feature parity and evidence policy

**Release test for EVERY feature:**

1. **Behavior:** Does the control perform the advertised mutation or query against a real authenticated backend?
2. **Persistence:** Does it survive refresh, reconnect, and backend restart?
3. **Authorization:** Does a different tenant/insufficient scope get denied?
4. **Failures:** Does a dependency failure display accurate status, retryability, and request ID?
5. **Accessibility:** Keyboard focus, labels, responsive layouts and reduced motion pass checks.
6. **API parity:** Can equivalent supported behavior be performed through a documented API/SDK call?
7. **Observability:** Can engineers trace the operation by ID and observe measured cost?
8. **Proof:** Is there a passing test, response/log reference, screenshot/video and known-limitations entry?

Each feature gets one of: `NOT_STARTED`, `IMPLEMENTING`, `INTEGRATED`, `TESTED`, `RELEASED`, `BLOCKED_EXTERNAL`. An engineer may NOT use `RELEASED` without evidence; `BLOCKED_EXTERNAL` cannot be marketed as live. `DESIGN_ONLY` is a separate truthful tag for screens/prototypes. CI should fail if unimplemented feature flags are enabled in production.

# 41. Codex operating model and governance

Codex is an implementation agent, not a substitute for real verification. The handoff ZIP contains `AGENTS.md`, `CODEX_START.md`, phased `codex/phases/*.md`, an acceptance matrix, and example contracts. Apply the source plan to an actual repository. Codex must inspect the repo before touching it, document baseline, implement the smallest runnable slice, run commands and tests, and record verified evidence in `BUILD_LOG.md`. Avoid one giant task to build everything in a single response. Finish phase gates before moving to optional systems; parallelize independent components only after stable contracts are accepted.

## 41.1 Mandatory review checkpoints

- Design tokens and first 5 screens: responsive screenshots, contrast, keyboard, empty/loading/error states.
- Core vertical slice: recorded end-to-end dataset flow using real Postgres/object store/workers.
- Security: negative cross-tenant tests, tokens, secret redaction, provider-license checks, budget enforcement.
- Generation/provider integration: authorized account and a redacted sample trace.
- Simulation: proof on compatible NVIDIA RTX or explicit `BLOCKED_EXTERNAL`.
- Release: passing CI, rollback, metadata restore exercise, runbooks and approved environment changes.

## 41.2 Explicit approvals

Always obtain user permission before: spending money, provisioning paid cloud/HPC, sending data to an external model provider, adding production secrets, changing live databases, publishing a public deployment, registering paid domains, or altering an existing production system. Local synthetic test data and no-cost tooling may be used as configured, but never claim access to unconnected resources.

## 41.3 Required Codex output per phase

`Summary`, `Files changed`, `Commands executed`, `Passing tests`, `Screenshots or traces`, `API examples`, `Verified features`, `Known blockers`, `Security assessment`, `Next phase` and `Approval requested (if any)`. Include failures and incomplete steps; never replace genuine errors with fabricated sample results.

# 42. Build milestones with executable acceptance gates

| Phase | Implementation | Demo gate (must pass before phase marked done) |
|---|---|---|
| P00 | Baseline, architecture decisions, repo, CI, env examples | Fresh clone setup, app shell/API boot, health checks and tests |
| P01 | Geist-inspired tokenized UI shell + responsive routing | Desktop/mobile screenshots; working navigation, auth placeholders correctly disabled |
| P02 | Multi-tenancy, auth, PostgreSQL models, object store | Real sign-in; no cross-tenant reads; migrations/seed idempotent |
| P03 | Dataset + version + multipart upload APIs and screens | Upload fixture; hash verified; browse after refresh; preview/download |
| P04 | Recipe schema, run queue, orchestration and CPU worker | Submit -> process -> validate -> immutable publish -> export |
| P05 | OpenAPI, SDKs, CLI, signed webhooks, audit | API/SDK/CLI same end-to-end job, signed webhook verified |
| P06 | Quality/curation and annotation with reviews | Dedupe/label/edit/approve; failed gate refuses publish |
| P07 | Authorized teacher provider + multi-modal adapters | Real licensed provider sample; permissions/budget/usage and retry validated |
| P08 | Compute pools/agents, scheduler, RTX/Slurm adapter | Node capability checks; real eligible job or honest blocked status |
| P09 | Blender, Isaac Sim, Isaac Lab runtime integration | Real designated worker produces inspectable episode/sample artifacts |
| P10 | Evaluation, feedback, search and dataset diffs | Fixed benchmark comparison and reproducible version diff |
| P11 | Enterprise, billing, tenancy hardening, ops | SSO/test policies, audits, billing reconciliation, restore drill |
| P12 | Load, disaster recovery, security review, release | Full regression and approved staging cutover; no critical defects |

Phases represent dependency-ordered scope, not credible calendar promises. First P00-P05 is the first genuinely working platform. Remaining phases extend real production capability; all are planned unless verified as implemented in a live repository.

# 43. First five Codex sessions: precise work orders

**Session 1: Repository baseline and foundation.** Read `AGENTS.md`, plan and docs. Set up pnpm/Next.js/FastAPI/PostgreSQL/MinIO/worker/Docker Compose, `.env.example`, Makefile and CI. Create health endpoints and first DB migration, seed fixture and two basic smoke tests. Show actual boot logs, test result and file tree. Do not claim other modules implemented.

**Session 2: Design system and app shell.** Build original Vercel-inspired UI tokens, typography, nav, project switching, command palette, theme mode, responsive layouts, data table, form state and skeleton/empty/error patterns. Connect dashboard to health and tenant-aware API; hide absent modules. Validate at 360/390/768/1440 and keyboard/axe. Provide screenshots.

**Session 3: Dataset CRUD and storage.** Organization/project models, scoped user auth, create/list/get dataset, presigned multipart upload, completion checksum, sample/object metadata, search/filter/pagination, dataset detail. Tests: file upload, refresh persists, revoked access, cross-tenant denial, invalid content, duplicate request.

**Session 4: Full job vertical slice.** Compile JSON recipe, create idempotent run, durable queue, CPU generator/validator, artifact manifest with hashes, quality gate, immutable publish, export, structured logs and retry. Demonstrate a real 100-sample job; test worker crash, duplicate idempotency, budget denial and invalid data.

**Session 5: Developer parity.** Generate OpenAPI from API, typed client and Python/TypeScript SDK, CLI, webhook signing and delivery/replay, accurate docs, integration and Playwright E2E. Run same workflow by SDK and UI and verify the manifest hashes/cost ledger. End with a production readiness gap report.

# 44. Product-wide acceptance scenarios

**A: Text dataset end-to-end.** Sign in -> create text dataset -> configure a deterministic approved local CPU generator -> launch -> witness trace events -> quality report -> publish immutable version -> download JSONL/Parquet -> compare hashes -> API/SDK repeat -> webhook proof. Expected: persisted results and no fake UI.

**B: Image upload + labeling.** Upload signed real image bytes -> thumbnails generated -> annotation task created -> auto label or manual label -> reviewer edits -> export COCO/YOLO -> audit shows edits and user -> quality gate blocks corrupt annotations. Expected: preview and exported labels agree.

**C: Teacher synthesis.** Connect a *permitted* provider -> record rights and quota -> prompt+schema validation -> generate -> verify against heldout/task-specific tests -> reject invalid samples -> store response lineage -> export. If no authorization/credentials, show clearly blocked test, not a fake success.

**D: Blender / Isaac.** Compatible remote worker detected -> validate scene and assets -> budget approval -> job queued -> execute -> synchronized frame/label bundle -> inspect episode -> export. If an RTX node is missing for Isaac Sim, server returns a structured `CAPABILITY_UNAVAILABLE` with requirements; UI shows blocking message and never launches.

**E: Multi-tenant attack.** Two organizations: neither can read or mutate the other's datasets, logs, keys, upload URLs, artifacts, webhooks, compute jobs or billing. Include ID substitution and cursor/pagination tests. 403/404 policy consistent and no sensitive leakage.

**F: Failure, recovery, and billing.** Kill worker, duplicate requests, provider 429, storage offline, webhook 500, quality failure, budget cap. System responds accurately; lease expires; retries are idempotent; published versions are not corrupt; cost ledger reconciles and no double-billing occurs.

**G: Responsive developer UI.** 360px mobile to wide desktop, light/dark, keyboard-only actions, screen reader checks, real data/empty/slow/error cases, keyboard command palette, API docs; no dead controls, overflow or hidden critical action.

# 45. Detailed delivery checklist and stop conditions

A phase is blocked if: migrations do not apply cleanly; test fixture cannot run from a new checkout; any advertised page has dead controls; authentication is bypassed; credentials appear in client assets or logs; tenant-isolation tests fail; data can be published without a passing quality/license gate; user cannot cancel a paid run; a GPU integration is simulated as real; API docs do not match running API; monitoring cannot diagnose a failed run; or CI has failing critical tests.

A general availability candidate also needs: threat model review; penetration test remediation; disaster recovery drill; backup restore evidence; documented key/secret rotation; alert escalation; on-call runbooks; audit retention and deletion; explicit supported-engine version matrix; license/legal check; accessibility testing; production load tests; cost model and spend caps; product terms/privacy; signed artifact provenance; rate/abuse limits; incident communications; safe feature flag rollback; and zero known critical vulnerabilities.

# 46. Decision summary for Codex

1. **Start with visual architecture:** Original Geist-inspired theme, UI kit and app shell before product screens, but connect to real backend services immediately.
2. **Vercel is for the web product:** Keep the web on Vercel; run FastAPI, durable workflows, storage, and CPU/GPU/HPC workers on appropriate container/cluster infrastructure.
3. **Every interface uses one API contract:** Web, CLI, SDK, automation and AI agent call the same policy-enforced backend.
4. **Make the core dataset flow work before specializing:** Create/import -> recipe -> run -> verify -> version -> export -> webhook.
5. **Add multimodal engines as audited adapters:** Provider permissions, asset rights, capability checks, and independent verification are always explicit.
6. **Show the truth:** Production features show real data, mock/demo fixtures are clearly marked, unavailable modules are disabled or marked blocked.
7. **Do not spend or deploy without approval:** PR/preview development is preferred; external paid calls and production promotions require explicit review.
8. **Record proof:** A Codex phase is complete only after run IDs, screenshots, test logs, contracts, and known limitations are saved.

## Updated reference links (verify versions before implementation)

- Vercel Geist: https://vercel.com/geist/introduction ; typography: https://vercel.com/geist/typography
- Vercel Functions: https://vercel.com/docs/functions/configuring-functions/duration ; feature availability and limits may differ by plan and date.
- Codex AGENTS.md guidance: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Codex iterative engineering harness: https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex
- NVIDIA Isaac Sim technical requirements: https://docs.isaacsim.omniverse.nvidia.com/6.0.0/installation/requirements.html
- OpenAPI: https://spec.openapis.org/oas/latest.html ; CloudEvents: https://cloudevents.io/
- OWASP API Security Top 10: https://owasp.org/API-Security/ ; WCAG 2.2: https://www.w3.org/TR/WCAG22/

