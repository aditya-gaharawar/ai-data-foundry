# P13 — Bounded schedules and private notifications

Executed checkpoint: **6 November 2026, 10:44 IST**. This is a local expansion
candidate on `phase/p13-automation-notifications`, based on `585743e`.

Executable source SHA-256:
`f05db523e5f2021bf8885f24d27ae76134873ee6727e9f4f5333426034069a30`.
The signed [readiness report](readiness-report.json) and redacted
[operator reports](operator-reports.json) use this exact fingerprint. All eight
local gates passed. **Production release remains BLOCKED_EXTERNAL.**

## Delivered behavior

- `/v1/schedules`: persisted definitions pin a dataset and immutable recipe
  revision. Interval/daily cadence, IANA timezone preview, aware future windows
  of at most 30 days, up to 100 launches, and per-run/total internal caps require
  explicit execution approval. There is a 100-open-schedule tenant limit and a
  1,000-occurrence safety limit. Definitions stay fixed; controls use revision
  checks and idempotency. Resume explicitly captures the caller's current
  delegation and starts at a future occurrence.
- The existing Python worker polls PostgreSQL, locks due rows with
  `FOR UPDATE SKIP LOCKED`, and admits real Temporal runs using the same
  `plan_run` / `admit_run` functions as manual launches. It rechecks current user,
  membership, role, originating key, source rights/state, governance and budgets.
  Rejected admission rolls back run, reservation and outbox rows while recording
  the blocked occurrence. Admitted estimates are never refunded into the
  schedule's total cap. The local configured rate is nonbillable.
- Immutable occurrences, atomic counters/outbox commits and unique
  `(schedule_id, scheduled_at)` values prevent duplicate admission. An active
  preceding run skips an overlapping occurrence. Ticks more than 120 seconds
  late skip backlog instead of launching a burst. Daily DST gaps are skipped;
  repeated local times use their first fold. A completed schedule stops future
  dispatch; an admitted run still has its own outcome.
- Active schedules must be paused/cancelled before holdout protection or artifact
  erasure. Recovery takes an exclusive advisory lock against scheduler admission
  and refuses active schedules or jobs. A legal hold controls erasure and does
  not independently prohibit processing.
- `/v1/notifications`: actual terminal run events and schedule failures/skips
  produce a personal tenant/user inbox, unread bell, signed cursors and read
  acknowledgements. Outbox materialization deduplicates events. Legacy runs
  without a reliable submitting user do not acquire fabricated recipients.
  Mark-all uses a server cutoff; the console obtains a fresh summary when it is
  clicked. Later notices remain unread. Generic notices expose navigation only
  while current access permits the resource, including replayed read requests.
- Console routes `/schedules` and `/notifications`, generated OpenAPI/Python/TS
  types, Python/TypeScript SDK namespaces and dedicated CLI commands use actual
  HTTP persistence. The API-key screen includes the new scopes; existing keys
  do not gain them automatically. No external messaging was added.

The [automation guide](../../../docs/P13_AUTOMATION.md) documents usage and
[ADRs 010–011](../../../docs/decisions/005-p13-bounded-automation.md) describe
semantics, locking and tradeoffs. This is a PostgreSQL polling scheduler, not
Temporal's native Schedule API. Arbitrary cron, paid scheduler services and
external notification channels are outside this phase.

## Executed checks

**92 unique tests passed:** 30 unit/contract + 28 integration + 16 security +
18 browser. Smoke repeats, operator probes and repeated browser attempts do not
increase that count. Every final command below exited **0**; see
[commands.json](commands.json).

| Command | Result / evidence |
| --- | --- |
| `make lint` | Ruff checks/format and both TS packages passed; [log](lint-final.log) |
| `make test` | 30 passed; [log](unit-contract-final.log) |
| `make test-integration` | 28 passed against real services; [log](integration.log) |
| `make test-security` | 16 passed; [log](security.log) |
| `make test-e2e` | All 18 passed on optimized local Next.js; [log](e2e.log) |
| `make smoke` | Existing actual export/webhook lifecycle repeated; [log](smoke.log) |
| `pnpm build` | Next.js optimized build passed; [log](build.log) |
| `uv run alembic check` | No schema drift; [log](alembic.log) |
| `uv run python scripts/contracts.py --check` | OpenAPI 3.1, 123 paths and 90 generated Python models current; [log](contracts.log) |
| `uv run python scripts/verify_fresh_database.py` | Fresh migrations, seed, auth, API restart persistence and tenant isolation; [log](fresh-database.log) |
| `uv run pytest tests/test_expansion.py::test_ledger_and_signed_readiness_are_persisted -q` | Readiness/ledger regression repeat passed; [log](operations-regression.log) |
| `FOUNDRY_EVIDENCE_DIR=.local/evidence/p13 uv run python scripts/security_review.py` | Real npm/OSV queries and private-value scan; [log](dependency-security.log) |
| `FOUNDRY_EVIDENCE_DIR=.local/evidence/p13 uv run python scripts/operational_checks.py load` | 60 requests / 4 readers, zero errors; [log](load.log) |
| `FOUNDRY_EVIDENCE_DIR=.local/evidence/p13 uv run python scripts/operational_checks.py restore` | Isolated database/object restore, restored API and cleanup passed; [log](restore.log) |

The P13 tests exercise two real scheduled publications, exact launch totals,
single notification materialization after duplicated events, read timestamps,
mark-all cutoff preservation, pause/resume/cancel, stale revisions, actual worker
PID replacement, concurrent dispatchers, blocked revoked keys/roles, aggregate
budget rollback, archived sources, holdout admission and per-user/tenant privacy.
Python, compiled TypeScript and the CLI make real HTTP calls.

The recovery test pauses the real worker and races four dispatchers against a
persisted due schedule. Only one run is admitted. Its test process advances the
scheduler clock to exercise overlap/backlog boundaries; the live worker's clock
is never altered. The real queued run subsequently executes and publishes.
[scheduler-recovery.json](scheduler-recovery.json) records this distinction.

Additional rollback-only database probes rejected notification-content changes,
run-attribution changes and a cross-tenant occurrence foreign key. See
[database-guards.json](database-guards.json). No probe committed a forbidden write.
API tests also rejected schedule-definition and occurrence-history mutation.

## Durable artifacts and operator evidence

- [Scheduled lifecycle](scheduled-lifecycle.json): actual schedule/occurrence IDs,
  two run IDs, two immutable version hashes, exact cost totals and inbox cutoff.
- [Revoked delegation](revoked-authority.json),
  [budget/source checks](bounded-budget-policy.json),
  [private inbox](private-inbox.json), and
  [failed/cancelled outcomes](terminal-outcomes.json).
- Recovery verified **41 metadata tables, two tenants, 242 manifest seals,
  2,002 object versions and 224,278,437 bytes**. Every restored object checksum
  and manifest seal was checked. An isolated restored API proved local auth,
  tenant-negative access and a real sample read. Temporary resources were
  removed. Credential-bearing raw archives and object-version maps remain
  private at mode 0600 and are excluded from source bundles.
- Load: 60 reads / four concurrent readers, **zero errors**, p50 **60.02 ms**,
  p95 **83.69 ms**. This bounded single-host measurement is not a production SLA.
- [Reconciliation](reconciliation.json) passed without altering money.
  The signed readiness report passed all **eight** source-bound local gates,
  including the new scheduler heartbeat, and its HMAC was independently
  recomputed using the local operator key.

## Screenshots and corrections

Actual screenshots include [launch preview](screenshots/schedule-preview-light.png),
[light schedules](screenshots/schedules-light-desktop.png),
[dark schedules](screenshots/schedules-dark-desktop.png),
[mobile schedules](screenshots/schedules-dark-mobile.png),
[light inbox](screenshots/notifications-light-desktop.png),
[dark inbox](screenshots/notifications-dark-desktop.png),
[mobile empty inbox](screenshots/notifications-dark-mobile.png), and
[final readiness](screenshots/readiness-light-desktop.png).

The final browser run verifies both new pages, mobile document width, light/dark
axe checks, explicit consent, real publication, read/read-all controls, keyboard
flows, and all existing core/curation/model/Blender/compute/evaluation/governance
journeys. Current regression captures and P06 browser JSON are under `regression/`;
historical P00–P12 files were restored byte-for-byte after capture.

Initial added tests used an incorrect governance route/status and were corrected.
The first browser attempt caught an empty-state heading jump. Visual inspection
also found a positioned hidden table label widening the mobile document; a
visible header and explicit width assertion corrected it. Repeated inbox runs
removed cross-test unread-state assumptions and improved mark-all's fresh
cutoff. Earlier failing attempts remain in `e2e-initial.log`,
`e2e-first-full.log`, and `e2e-second-full.log`; the final complete clean result
is `e2e.log`. Private traces are not packaged. No checks were disabled or replaced
with fabricated responses.

## Remaining boundaries

Actual npm scanning returned zero advisories. OSV checked 68 installed Python
packages; the existing optional **diskcache 5.6.3** pickle advisory
`GHSA-w8v5-vhqr-4h9v` / `PYSEC-2026-2447` remains explicitly reported. No disk
cache is configured or accepted by the inference child. This local reviewed
mitigation is not a zero-advisory claim or an independent security audit.

The environment remains `APP_ENV=local` despite the optimized web build.
SSO/IdP, paid providers, Kubernetes/Kueue, Slurm, certified RTX Isaac runtimes,
staging deployment/rollback, independent pentest, remote CI/review and production
SLA gates remain blocked. Recovery excludes Temporal development-server workflow
history and external KMS/SSO; the operator secret remains a separate prerequisite.
No paid inference, private production import, external message, public
publication, remote repository change or production deployment was performed.

AT-006 and AT-073 are now TESTED. Feature totals are **72 TESTED / 22 INTEGRATED /
6 NOT_STARTED / 8 BLOCKED_EXTERNAL**, with no RELEASED rows. The remaining six
unstarted features are licensed imports, audio/video pipelines, sim-to-real
comparison, machine label suggestions and data residency. The phase's local
[PR draft](../../../docs/reviews/P13_PR.md) is prepared; no Git remote exists.
