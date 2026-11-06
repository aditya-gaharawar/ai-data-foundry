# ADR 010: A bounded database due queue for workflow schedules

P13 closes the remaining local schedule and notification gaps after P00–P12.
Use the existing PostgreSQL and Python worker, with Temporal continuing to own
run execution and retries. This is a polling scheduler, not Temporal's native
Schedule API. A second independent scheduling database or service would add
cross-system activation and cancellation races without a current workload need.

Each immutable schedule definition pins its dataset, recipe revision, cadence,
window and caps. Interval schedules have a 10-second local minimum. Daily
schedules use IANA timezones: nonexistent local times are skipped and repeated
times use the first fold. Windows are at most 30 days; launch limits are at most
100; the worker stops after 1,000 processed occurrences. There is no arbitrary
cron, calendar exception editor, or external paid scheduler integration.

Creation and resumption require explicit execution approval. Resumption captures
the current caller's delegation, so administrator takeover is explicit. Before
each launch the worker intersects the saved scopes with the authorizing user's
current role and originating API key. Inactive users, missing memberships,
revoked keys or insufficient scopes stop future admission. Existing API keys
never acquire the new scopes automatically. Engineers control their own
schedules; administrators may control workspace schedules.

Manual and scheduled runs share `plan_run` and `admit_run`. They recheck source
rights, archive/erasure/holdout state, current governance and engine capability,
recipe and organization budgets. A savepoint rolls back rejected admission,
including reservations and run/outbox rows, while preserving a blocked occurrence
and generic notice. The aggregate cap conservatively counts admitted estimates;
cancelled or failed launches never replenish it. Local internal rates are
nonbillable estimates, not external provider prices or a customer invoice.

The scheduler locks due rows with `FOR UPDATE SKIP LOCKED`. A unique
`(schedule_id, scheduled_at)` occurrence and atomic run/reservation/outbox commit
prevent duplicate admission. Runs execute using their existing unique Temporal
workflow IDs. An overlapping run skips the new occurrence. At most one launch
can catch up within 120 seconds; older backlog is recorded once and skipped.
Pause/resume never replays paused slots. `COMPLETED` closes future dispatch when
the launch cap or final available occurrence is reached; it does not assert that
an already admitted run succeeded. Run outcomes remain separate.

The lock order is schedule, authority rows, dataset, organization. Governance
holds the dataset lock and checks active schedules without reversing that lock
order. Protecting a dataset as a holdout or erasing its artifacts requires
pausing/cancelling its schedules. A legal hold controls erasure, not run admission.
Recovery takes an exclusive advisory lock against shared scheduler admission,
refuses active schedules/runs/compute jobs, and then snapshots metadata/objects.
Worker heartbeat and persisted state survive a worker process replacement.

# ADR 011: Personal notices from durable facts

Only actual new run terminal events and schedule failures/skips generate in-app
notifications. Legacy runs without a recorded submitting user have no fabricated
recipient. Outcome materialization runs in the outbox transaction, with a unique
tenant/user/event key. No email, Slack, browser push or other external recipient
is contacted. Existing local webhook behavior remains a separately configured
developer feature, now also accepting `run.cancelled`.

Every inbox read and acknowledgement is constrained to the current organization
and user, including administrators. Cursors are signed and bind organization,
user and unread filter. Acknowledgements preserve their first read timestamp;
mark-all uses a server-returned time cutoff so later notices remain unread.
Payloads contain generic summaries, not prompts or dataset contents. Navigation
is recomputed against current scopes and dataset protection, including replayed
acknowledgements. A notification never grants resource access.

Schedule definitions, occurrence history, run attribution and notification
recipient/content are protected by database triggers. Control state, counters,
authorization and `read_at` remain mutable through authorized endpoints. Control
metadata is retained as audit evidence; this phase does not claim personal-data
erasure or introduce an external notification-retention policy.

This remains a local expansion candidate. External IdP/provider/cluster/RTX,
staging, independent security review, remote CI/review and production SLA gates,
including the documented optional diskcache advisory, remain blockers. No remote
repository, paid resource or production deployment is authorized or performed.
