# AI Data Foundry — V2 Codex Implementation Package

**Current status:** Complete implementation specification. **This is not an already-running application.**

## Contents

- `AI_Data_Foundry_Master_Plan_v2.md` — complete baseline (27 sections) plus 19 new chapters specifying Vercel-inspired visual UX and full implementation.
- `AI_Data_Foundry_Master_Plan_v2.docx` and `.pdf` — readable editions of the same full document (in the enclosing release package).
- `AGENTS.md` — persistent Codex repository rules.
- `CODEX_START.md` — copy/paste start prompt and first five sessions.
- `codex/PHASES.md` and `codex/phases/P00.md`–`P12.md` — dependency-ordered build instructions and evidence gates.
- `design/VERCEL_INSPIRED_DESIGN_SYSTEM.md` — design tokens, page architecture, components, accessibility requirements.
- `contracts/openapi-planning.yaml` — initial OpenAPI contract, **not** a deployed service.
- `contracts/recipe.schema.json` and `contracts/job-event.schema.json` — draft machine-readable contract schemas.
- `verification/ACCEPTANCE_TESTS.md` and `verification/FEATURE_MATRIX.csv` — test cases and statuses (initially NOT_STARTED).
- `ops/DEPLOYMENT_PLAYBOOK.md` — boundaries: Vercel UI, remote API/workers, HPC/RTX.
- `BUILD_LOG.md` — ledger Codex must fill with actual evidence.

## Important workflow

Copy this folder into the **intended Git repository**, keep `AGENTS.md` at its root, and give Codex the task from `CODEX_START.md`. Start with P00 then P01, then complete P02-P05 for a real working vertical slice. Create reviewable pull requests. Do not pretend paid providers, external GPUs or model rights exist. Do not deploy production or spend paid resources without approval.

## Product bar

Everything users can click must work or be explicitly unavailable. All published dataset versions must be reproducible/traceable within the limits of the generator. All features must have authenticated APIs, persisted backend behavior, observability and tests. A design prototype is not a completed feature.
