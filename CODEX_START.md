# START HERE — CODEX BUILD EXECUTION

**This is an implementation handoff, not evidence of completed software.** The goal is a working production-oriented web console and API for multimodal training data. First build a perfect Vercel-inspired UI foundation, but do not prioritize visuals over actual functionality.

## Exact opening prompt for Codex

> Read `AGENTS.md`, `AI_Data_Foundry_Master_Plan_v2.md`, `design/VERCEL_INSPIRED_DESIGN_SYSTEM.md`, `codex/PHASES.md`, `verification/ACCEPTANCE_TESTS.md`, and the machine-readable contracts. Inspect the live repo and available services. Start P00 then P01, creating a genuine local Next.js/FastAPI/PostgreSQL/S3-compatible object storage setup and a cohesive Geist-inspired app shell. No fake data, nonfunctional UI controls or simulated API success. Preserve the product's unique identity rather than copying Vercel branding. Build the first real vertical slice: authentication -> dataset -> recipe -> durable job -> validation -> immutable version -> signed export -> signed webhook. Implement and test each stage before proceeding to specialized generators/simulators. Use tests, screenshots and run traces as proof. Make no paid model requests, provision no billable cloud services and do not deploy production without my explicit approval. At the end, report what passes, what is blocked and the next phase.

## Recommended execution order

1. **Repository inspection** — infer current framework and git status; don't overwrite prior work. Record dependencies, secrets availability (not values), deployment status, and baseline tests.
2. **P00 foundation** — wire Next.js app, FastAPI, Postgres, MinIO, CPU worker and CI in Docker Compose. Health checks and database migrations.
3. **P01 first visual pass** — implement design tokens and app shell, five priority routes, responsive states and real API health. Review both light/dark screenshots and keyboard behavior.
4. **P02-P04 core features** — real auth, data creation, upload, recipe/run orchestration, worker processing, validation, manifests, immutable versions and download.
5. **P05 developer parity** — OpenAPI, SDKs, CLI, signed webhooks, docs, complete E2E tests. At this point the first product must work.
6. **P06-P12 expand** — labels, quality/curation, authorized model adapters, compute, simulations on compatible hardware, evaluation, enterprise, ops and release security.

## How to launch Codex

Create/open a new Git repository or use the existing project repository. Put the contents of this packet in the root of the working repo (retain `AGENTS.md`), run Codex in that repository, and paste the opening prompt. Do not run arbitrary remote installation scripts. For cloud Codex, connect the intended repository in Codex and make this packet accessible as repo files. Work one `codex/phases/Pxx.md` at a time, opening reviewable pull requests, merging only after phase acceptance.

## Required evidence after every session

- Changed files and why; exact test commands and results.
- Direct API request/response and persisted DB/object artifacts where applicable.
- Responsive screenshots at desktop and mobile sizes with light/dark states.
- E2E video/trace or Playwright output for each claimed working workflow.
- Verified security negatives, missing dependencies and true operational limitations.
- Updates to `BUILD_LOG.md`, `docs/decisions`, and the feature status matrix.

## First demo (non-negotiable)

Using only local components, sign into two test organizations. In organization A create a text dataset, upload or generate 100 deterministic samples, validate, publish version v1, export JSONL, observe a signed webhook. Organization B must be unable to access any of A's objects, runs, keys or signed downloads. Repeat idempotent launch and worker restart without double publication/billing. All UI elements involved must work; all relevant actions also work through API and SDK.

## Approval boundaries

Approval needed before paying for compute/API usage; importing private production data; live external model calls; configuring secret production integrations; production deployment; public sharing; modifying external repositories other than the selected working repo.
