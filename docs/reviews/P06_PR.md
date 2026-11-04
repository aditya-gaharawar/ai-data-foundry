# P06: curate text and images with audited human review

The local core could publish text but could not clean a review source, persist
label corrections, resolve reviewer disagreements or export approved image boxes.
This change adds a complete local curation path through API, PostgreSQL/S3,
Temporal worker, console, Python/TypeScript SDKs and CLI.

- Immutable quality profiles; reproducible exact/lexical/perceptual dedupe.
- Bounded PNG/JPEG upload, normalized pixels and authenticated thumbnails.
- Scoped Labeler role, assignments, revision checks, append-only review history,
  independent consensus/adjudication and reopen rounds.
- Authored data cards, blocking review/schema/annotation gates and immutable approval.
- Durable reviewed publication with sealed provenance and real JSONL/COCO/YOLO exports.

Migration `0730f891010f` adds profile/session/task/review tables with composite
tenant foreign keys, immutability guards and a backfilled upload-media field.
Generated OpenAPI and both client contracts cover the new endpoints.

Executed validation and artifact references are in
`verification/evidence/p06/VERIFICATION.md`. That report distinguishes full-suite
and targeted executions and records genuine failures/corrections. Advanced label
types, machine suggestions, semantic dedupe and production release remain outside
the verified local scope.

Local review branch: `phase/p06-curation-annotation`. No Git remote is configured;
this is a prepared PR description, not evidence of an opened or merged hosted PR.
