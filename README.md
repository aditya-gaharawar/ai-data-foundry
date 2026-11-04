# AI Data Foundry

A working local console and API for multi-user text and image datasets: create or upload,
run a durable pipeline, validate, publish an immutable version, export JSONL and
verify a signed webhook through real local services.

P06 adds quality profiles, exact/near duplicate cleaning, category/box annotation,
independent reviews and adjudication, authored data cards, approved publication,
and real COCO/YOLO image bundles. Follow [the curation guide](docs/runbooks/curation.md).

The original V2 handoff remains in this repository. Its original README is in
`docs/handoff/README.md`. Read `BUILD_LOG.md` for executed evidence and
`verification/FEATURE_MATRIX.csv` for precise feature status. P07–P12 remain
later phases; this is not a production release.

## Start

Requirements: Linux AMD64, Node 24, pnpm 11.25, Python 3.12, uv 0.13.4,
Docker Compose v2 and Make. Initial setup needs dependency registry access.

```sh
make bootstrap
make dev
```

Open **http://localhost:3000**. API documentation is at
http://localhost:8000/v1/docs; the Temporal development UI is at
http://localhost:8233.

Two independent organizations are seeded idempotently:

| Account | Organization |
| --- | --- |
| `alex@foundry.local` | Atlas Research |
| `blair@foundry.local` | Meridian Lab |

Use the generated **`DEV_PASSWORD` in your private `.env`**. Credentials are
machine-local, ignored by Git, and never printed by bootstrap. Administrators
can provision individual accounts and roles in Members. Local authentication is
disabled in production. The console labels its development data.

The default runner uses Compose for persistent PostgreSQL, S3 and Temporal, with
supervised host application processes to fit the workspace. Ctrl+C stops those
processes; `make stop` also stops infrastructure while preserving named volumes.
Logs/PIDs are in ignored `.local/`. `make dev-containers` defines the full
container topology but requires more disk and is unverified in this workspace.

## First dataset

1. Sign in; create a text or image dataset and declare permitted source use.
2. Upload JSONL or PNG/JPEG, or configure the deterministic text source in a workflow.
3. Save the workflow, review its estimate/budget and launch.
4. Inspect real progress, logs, quality, samples and provenance.
5. Export the published immutable version as verified JSONL.

The CPU generator creates reproducible arithmetic tasks, without model calls.
Internal estimates use a configurable **nonbillable** local rate card, defaulting
to 0.001 USD per durably processed sample. Actual external cost remains zero.
Budgets are reserved before scheduling and reconciled at checkpoints.

## Developer access

Create a scoped API key in Settings. Secrets are revealed once; revocation is
immediate. APIs use `/v1`, Problem Details, request IDs, pagination and idempotent
creation. The checked contract is `packages/contracts/openapi.json`; TypeScript
and Python model contracts are generated from it.

Standalone Python SDK: `uv pip install packages/sdk-python`. The root install
also provides the SDK and CLI. Use a key from your credential manager:

```python
import os
from datafoundry import DataFoundry

with DataFoundry(api_key=os.environ["FOUNDRY_API_KEY"]) as client:
    for dataset in client.datasets.list():
        print(dataset.id, dataset.name)
```

The workspace-local TypeScript client is `@datafoundry/sdk`. Do not embed
privileged keys in a public browser bundle. The CLI reads `FOUNDRY_API_KEY` and
optional `FOUNDRY_API_URL`:

```sh
datafoundry doctor
datafoundry auth
datafoundry datasets list
datafoundry recipes validate examples/text-recipe.json
datafoundry runs watch RUN_ID
```

Exported JSONL is a sample envelope: training fields are under `payload`, with
sample/content IDs, source references and policy metadata alongside them. SDK
downloads verify SHA-256.

## Verify

Keep `make dev` running in another terminal:

```sh
make lint
make test
make test-integration
make test-security
make test-e2e
make smoke
uv run python scripts/verify_fresh_database.py
```

Integration checks use real services and retain synthetic evidence. They inject
worker/API restarts and verify no duplicate publication/accounting. Browser tests
cover create-to-export, multiple users, permissions, keyboard use, failures,
themes, responsive screenshots and axe. Screenshots are in
`verification/evidence/screenshots`; private traces/reports are in `.local/`.
Traces can contain session material and must not be published raw.

`make smoke` verifies the signed local webhook, SDK lifecycle, CLI and export.
The verifier runs on port 9100; its control endpoints require the local app
secret. The Webhooks UI supports creation, rotation, inspection and replay.
Arbitrary external destinations are disabled.

`make contracts` regenerates OpenAPI/models. `uv run python scripts/contracts.py
--check` detects contract drift; `uv run alembic check` checks migrations. GitHub
Actions is configured, with no remote execution claimed until a repo is connected.

## Boundaries

- UTF-8 text JSONL, at most 20 MiB and 10,000 records; inline JSON Schema.
- PNG/JPEG uploads, at most 6 MP and 4096 pixels per edge; normalized private previews.
- Local curation: 500 samples / 20 MiB; text categories and image boxes.
- Linear typed recipes; no arbitrary code or general branching execution.
- Blocking schema, integrity, review, annotation, duplicate and declared-rights checks.
- Authenticated, tenant-bound signed export grants.
- Local users and user-owned scoped API keys; production identity deferred.
- RustFS provides tested S3 storage because MinIO registries were unavailable.
- No paid calls, GPU jobs, simulations, enterprise billing or deployments.

See `docs/decisions/`, `docs/runbooks/local-operations.md` and the handoff phase
files for implementation decisions and remaining release gates.
