# P14 — Local reliability and recovery

Verified 6 November 2026 on `phase/p14-local-reliability`, based on `5f22375`.
The user cancelled deployment and requested codebase improvements. Everything
in this phase runs locally; no deployment or infrastructure was provisioned.

## Changes

- Session checks distinguish HTTP 401 from service failures. API outages show
  an accessible recovery screen with a real retry action. Expired sessions
  cancel and remove workspace queries, including when a cached session expires
  during a background check. Switching test users does not show the old workspace.
- Network failures, non-JSON errors, null documents, unexpected detail types
  and unreadable success responses produce useful errors with request IDs.
- The web proxy enforces the existing 1 MiB control-request limit for declared
  and chunked bodies before forwarding. Exactly 1 MiB reaches the API. Proxy
  failures use Problem Details, request IDs and no-store. Dataset uploads keep
  using their separate bounded object-storage sessions.
- PostgreSQL, S3 and Temporal probes run independently under four-second
  deadlines. Synchronous calls use threads and native timeouts. A failed
  dependency does not hide healthy ones or block liveness. Tests include real
  services and a connection failure to an isolated unused storage port.
- Importing an evaluation puts its confirmed server record into the tenant's
  query cache immediately. Feedback creation works before list refresh finishes.
  A delayed-refresh test verifies feedback references the persisted evaluation.

## Verification

**107 distinct cases verified:** 35 unit/contract, 30 integration, 16 security
and 26 browser cases. Repeated runs and smoke are not counted again.

| Check | Result |
| --- | --- |
| `make lint` | Ruff lint/format and TypeScript passed |
| `make test` | 35 passed |
| `make test-integration` | 30 passed; [log](integration.log) |
| `make test-security` | 16 passed; [log](security.log) |
| Browser suite | 25 passed in the final full run; one test cleanup failure corrected and its case passed separately |
| Evaluation regression | 1 passed with delayed refresh; [log](evaluation-final.log) |
| `make smoke` | SDK, durable job, immutable export, signed webhook and CLI passed; [log](smoke.log) |
| `pnpm build` | Optimized Next.js build passed |
| `uv run alembic check` | No schema drift |
| Contract drift check | 123 API paths and 90 Python models current |

The full browser command did **not** exit cleanly: its single failure was
`route.continue: Route is already handled!` in delayed-response test cleanup.
The test now waits for active handlers and passed its focused recheck.
Application code did not change between that full run and the successful
recheck. See the [full browser log](e2e.log) and [command results](commands.json).
No all-green single-run claim is made.

Earlier verification exposed the actual evaluation-selector race described
above. The initial integration attempt found a stopped local supervisor. Its
verified orphan processes were stopped and the supervisor restarted independently
of the tool session. Full integration/security checks then passed, including
worker replacement. An S3 probe cleanup mistake and initial browser selector/event
assertions were also corrected during development.

The [live observation](runtime-health.json) records HTTP 200 for API and web login
with all three dependencies available. The [mobile capture](session-recovery-mobile.png)
uses an explicitly injected API failure; real sign-in is checked after removing it.
New regression screenshots and test records are in `regression/`; historical
P00–P13 artifacts were restored. [Source hashes](source-files.json) identify the
changed executable/test files. Credentials and private browser traces are excluded.

Existing production identity, external infrastructure, independent review and
optional dependency limitations remain outside this local phase.
