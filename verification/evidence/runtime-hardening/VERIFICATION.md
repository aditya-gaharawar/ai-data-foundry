# Local runtime hardening

Changes: exclusive checkout lock before startup, occupied-port preflight, atomic
PID files, bounded process shutdown with escalation, closed restart log handles,
and five bounded retries with backoff for API/worker/receiver crashes. Unexpected
web exit and persistent crash loops now terminate with a failure exit code.

The host readiness command verifies supervisor and worker identities and rejects
stopped/zombie processes. It also checks HTTP readiness with a bounded wait.
Use `--services-only` for HTTP-only container checks; this does not verify workers.

Executed successfully:
- `make lint`: Python lint/format and both TypeScript packages.
- Four runtime tests: cross-process locking, forced shutdown/reaping,
  corrupt/unrelated PID rejection, and occupied-port rejection.
- Real scheduler worker-replacement/concurrent-dispatch recovery test.
- `make smoke`: real job, export, signed webhook and SDK/CLI lifecycle.
- Duplicate launch rejected with exit 1; existing worker PID unchanged.
- Paused worker blocked readiness; after resuming, full host readiness passed.

No browser or deployment changes. The broader application suite was not repeated
for this runtime-only follow-up. Existing phase evidence remains historical.
