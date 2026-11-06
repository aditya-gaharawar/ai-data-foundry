# Bounded workflow schedules and a personal notification inbox

Researchers can now explicitly authorize a finite sequence of real workflow
launches pinned to a recipe revision. A database due queue in the existing worker
admits each run through the same current permission, source, policy and budget
checks as manual submission. Pause/resume/cancel, duplicate dispatch prevention,
overlap/backlog skips and conservative total caps keep automation bounded.

The console also shows a user-private notification inbox and unread bell from
actual terminal run events and scheduling failures. Outbox deduplication,
identity-bound cursors, read cutoffs and current-access navigation preserve
privacy and idempotency. API, migrations, generated contracts, Python/TypeScript
SDKs and CLI cover the complete slice.

Validation and actual command results are recorded in
`verification/evidence/p13/VERIFICATION.md`. This is a local review draft on
`phase/p13-automation-notifications`; there is no Git remote or hosted PR. The
existing production, infrastructure and dependency blockers remain in force.
No deployment or external messaging is part of this change.
