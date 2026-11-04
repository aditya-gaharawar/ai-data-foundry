# Local operations

Use `make bootstrap` once, then `make dev`; stop with Ctrl+C or `make stop`.
Named volumes preserve metadata, object versions and Temporal history. Do not
run `docker compose down -v` unless you intentionally want to destroy local data.

Readiness is `/v1/health/ready`; liveness is `/v1/health/live`. The overview checks
CPU worker heartbeats. API logs use request IDs and paths without query strings.
Worker logs and run events use organization/run IDs. No raw dataset content,
passwords, API keys, signing secrets or signed grant URLs belong in public logs.

Inspect `.local/api.log`, `.local/worker.log`, `.local/web.log`, and
`docker compose logs temporal` for failures. Database migrations use Alembic;
`uv run alembic check` verifies model/schema consistency. Do not edit a published
version or recipe revision: create a new one. PostgreSQL rejects changes to
versions, revisions, usage and audit evidence.

Worker restarts recover through Temporal and durable object checkpoints. Run
effects are idempotent; execution itself is at-least-once. Cancelling records
already processed work and releases unused reservation. Retrying creates a new
run while preserving the failed/cancelled evidence. The UI exposes actual states.

Webhook failures retry five times, then dead-letter. Fix the receiver, inspect
its delivery error, and use authorized replay. Rotate a secret only when the
receiver is ready to use the new value. A recreated API key replaces a revoked
key; its original secret cannot be retrieved.

Keep `.env` private. Its app secret protects sessions, signing, encryption and
idempotency fingerprints; changing it invalidates existing local credentials and
webhook encryption. Do not rotate it casually or copy it into public artifacts.
Private Playwright traces may contain session material; publish screenshots and
redacted evidence only. There are no production backups or incident SLA claims.

P06 curation/review is implemented locally; follow `curation.md`. Quality profiles
and review history are append-only; frozen sessions/tasks cannot be modified.
P07 adds authorized model adapters; P08–P09 add verified
compute/simulation; P10 adds evaluation; P11–P12 add enterprise, operations,
backup/restore, load, security and release gates. Production remains disabled.
