# AI DATA FOUNDRY — REPOSITORY INSTRUCTIONS FOR CODEX

## Mission
Build a real, API-first, multimodal AI training-data platform, with a distinct Vercel Geist-inspired developer-console design. Read `CODEX_START.md`, `AI_Data_Foundry_Master_Plan_v2.md`, and the active phase file before coding. This is a planning handoff; inspect the actual repository and existing code before deciding where files belong.

## Ground rules
1. **No dead controls or fake successes.** Every advertised button, link, graph node, dropdown and mutation must be backed by actual persisted behavior. Hide or accurately disable unimplemented features. Use fixture data only if clearly labeled `DEMO DATA` in a local/dev-only mode.
2. **Build complete vertical slices.** API + persistence + worker + UI + SDK/doc + integration/E2E proof. Never claim a module works because a screen renders.
3. **API-first.** Public routes under `/v1`, OpenAPI contracts, deterministic errors, idempotency, auth, pagination, signed webhooks, tenant isolation, audit and costs.
4. **Vercel is the UI host.** Long-running Python/GPU/HPC/Isaac jobs execute on separate isolated infrastructure, never inside a frontend function.
5. **Own dataset recipe/version/run semantics.** Every published version is immutable, content-addressed, auditable and supported by quality and rights evidence.
6. **Engine compatibility is explicit.** Isaac Sim requires RTX-capable NVIDIA hardware with RT cores; an H100 alone is not a valid renderer. A missing provider/cluster = clear `BLOCKED_EXTERNAL` status.
7. **Security first.** No secrets committed, no client-side privileged credentials, no cross-tenant reads, no arbitrary unsandboxed code, no unapproved model-output distillation.
8. **Cost control.** Require budget admission, accurate estimates, reservations and real usage reconciliation for any billable task. Do not make paid calls or create chargeable infrastructure without approval.
9. **No production deployment without approval.** Develop locally and use preview/staging only within explicitly authorized environments.
10. **Evidence required.** At end of each phase, write `BUILD_LOG.md` with commands, exit codes, screenshots/traces, verified routes, blockers and next actions. Report unfinished features honestly.

## Preferred implementation stack
Next.js App Router + TypeScript + Tailwind + Radix/shadcn-style primitives + React Flow; FastAPI + Pydantic + PostgreSQL + Alembic; S3-compatible object storage; Temporal or another verified durable orchestrator; Python workers; OpenAPI-generated SDK types. Docker Compose for local; container cluster/Kubernetes/Slurm agents for external heavy execution. Avoid adding technologies without a concrete workload need.

## Quality checks (implement in repo Makefile)
- `make bootstrap`: fresh reproducible setup
- `make dev`: start web, API, database, object storage, worker
- `make lint`: code style, types and static analysis
- `make test`: unit + API contract tests
- `make test-integration`: real DB/object store/worker integration tests
- `make test-e2e`: Playwright browser journeys with real API
- `make test-security`: auth, tenant, key, upload, budget negatives
- `make smoke`: create -> run -> quality -> publish -> export -> webhook

These are target commands; if they do not exist in the current repo, implement them before claiming success. Do not pretend they have run.

## Source priorities
1. Active phase instructions in `codex/phases/`
2. Design and API/contracts files in this packet
3. Full `AI_Data_Foundry_Master_Plan_v2.md`
4. Current repository ADRs and working implementation

If two instructions conflict, document the conflict in an ADR, prioritize security/data correctness, and keep the scope explicit.
