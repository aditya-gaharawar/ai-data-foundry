# Verification evidence

Observed 2026-11-05 00:22 IST. This is the local P00–P05 text lifecycle, not a production release.

| Check | Exit | Actual result |
| --- | --- | --- |
| `make bootstrap` | 0 | Frozen Python/JS install, browser install, infrastructure health, migrations, idempotent seed |
| `make lint` | 0 | Ruff, formatting and TypeScript checks |
| `make test` | 0 | 13 unit/contract tests |
| `make test-integration` | 0 | 9 real-service integration tests |
| `make test-security` | 0 | 7 auth, tenant, scope, CSRF, upload, policy and budget tests |
| `make test-e2e` | 0 | 6 browser journeys |
| `make smoke` | 0 | SDK → 100 records → quality → immutable version → signed export → verified webhook + CLI |
| `pnpm build` | 0 | Optimized production web build |
| `uv run python scripts/verify_fresh_database.py` | 0 | Fresh migrations/seed, readiness, restart persistence and tenant isolation |
| `uv run alembic check` | 0 | No migration drift |
| `uv run python scripts/contracts.py --check` | 0 | 44 OpenAPI paths and 31 Python generated models match |

Logs beside this file are real command outputs. Private Playwright traces/reports
remain in `.local/` and are excluded from source archives because they can contain
session material. Screenshots are safe synthetic-data views.

Browser evidence covers generation and actual direct-to-S3 browser upload,
publication into the selected dataset, HTML-escaped sample previews, member
provisioning, Viewer denial, responsive overflow, light/dark, axe, keyboard menu,
mobile navigation, dependency errors, logout, and a fully keyboard-only
sign-in-to-export journey. Screenshots cover 360/390/768/1024/1440 widths and
five priority routes in both themes, plus isolated second-tenant empty states.
There are 24 PNG screenshots.

Integration proof includes a real >5 MiB multipart upload; four concurrent
idempotent launches producing one version/usage total; failed quality preventing
publication; five failed webhook attempts followed by dead-letter and successful
replay; SIGKILL of a worker after a real checkpoint followed by a single
10,000-record publication; cancellation/retry; API process replacement and
persisted state; both SDKs; a standalone Python SDK install; and CLI execution.
Additional live API evidence exercises metadata search, distinct cursor pages,
and HTTP 429 login throttling.

The captured run `run_bcc47efd4638471b8064823780348eba` succeeded with 100 rows.
Its immutable version is `ver_bcc47efd4638471b8064823780348eba`.
Manifest SHA-256: `bf609af10351f64b790fd96dcff2f6afe3ab0236b0e32cd00232e06a449a96d8`.
The downloaded bytes and current worker source/lockfile digest were independently
checked. The second organization receives 404 for its dataset, run, and copied
signed download. See `api-proof.json`, `webhook-proof.json`, `fresh-database.json`,
`additional-api.json`, and `tenant-b-ui.json`.

Feature matrix: {'TESTED': 42, 'INTEGRATED': 16, 'NOT_STARTED': 50}. Status applies only to the scope explained in each row.
There is no `RELEASED` claim. Human screen-reader signoff, production security/load,
backup/restore, full container application runtime, remote CI and remote PRs are
not verified. P06–P12 remain later phases.
