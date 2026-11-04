# Curate and review a local dataset

Start the stack with the root README. Sign in as an Owner/Admin or Engineer and
create a text or image dataset with source-use permission. Upload UTF-8 JSONL
for text, or real PNG/JPEG files for images. Completed uploads show their actual
verification status; image thumbnails use the decoded, normalized pixels.

1. Choose **Review & curate** on the dataset, or **Curation → New review session**.
2. Select an immutable quality profile, or create one with duplicate handling and
   publication thresholds. Set the label vocabulary and review policy.
3. Select completed uploads or a published source version. Creating the session
   snapshots the source and records deterministic duplicate exclusions.
4. Provision individual **Labeler** accounts in Members. Assign tasks, or let
   labelers claim unassigned tasks. Each reviewer inspects the source, edits a
   category or image boxes, and records a reason. Image boxes can be drawn with
   a pointer or entered through keyboard-accessible pixel coordinate fields.
5. Matching independent reviews resolve the task. Conflicts require an independent
   Owner/Admin to adjudicate. An administrator can reopen an unfrozen task for a
   new round. History remains visible. A stale edit returns `STALE_REVIEW`;
   refresh, inspect the newer decision, and submit intentionally.
6. Complete the data card. Inspect coverage, acceptance, duplicate counts,
   agreement denominator and the blocking reasons. Rejected rows are removed;
   a bad accepted source must be rejected or replaced through a new source/session.
7. Choose **Approve review snapshot** when the gate passes. Approval freezes the
   labels, card and evidence. Corrections after approval require another session.
8. Choose **Publish reviewed version**, inspect the actual estimate and budget,
   and confirm. Follow the durable run through quality and publication.
9. On the dataset's **Versions** tab, download JSONL or, for reviewed image boxes,
   COCO/YOLO ZIPs. The **Data card** and **Lineage** tabs expose the sealed evidence.

Default sessions require two independent users. An explicitly chosen one-reviewer
session has no independent-consensus claim. Reviewer agreement and perceptual or
lexical similarity do not establish accuracy or semantic equivalence.

## API and SDK

All behavior is in the generated `/v1/openapi.json` and `/v1/docs`. Main routes:

| Operation | Route |
| --- | --- |
| Create/list/get immutable profile | `/v1/quality-profiles` and `/{id}` |
| Create/list/get session | `/v1/curations` and `/{id}` |
| Save authored card | `PATCH /v1/curations/{id}/data-card` |
| Approve and freeze | `POST /v1/curations/{id}/freeze` |
| List/filter tasks | `GET /v1/annotation-tasks?curation_id=…&status=…&assigned_to=…` |
| Read sample and history | `GET /v1/annotation-tasks/{id}` |
| Assign/submit/adjudicate/reopen | `POST /v1/annotation-tasks/{id}/{assign,decision,adjudicate,reopen}` |
| List eligible local reviewers | `GET /v1/annotations/reviewers` |
| Private normalized image | `GET /v1/annotation-tasks/{id}/media` |
| Create/download export | `/v1/exports`, format `jsonl`, `coco` or `yolo` |

Creation and task POSTs require `Idempotency-Key`. Review requests must use the
current `expected_revision`, decision, reason and typed annotation. Actual labels:

```json
{"kind":"category","label":"object"}
```

```json
{"kind":"boxes","boxes":[{"label":"object","x":8,"y":6,"width":32,"height":24}]}
```

The Python SDK exposes `quality_profiles`, `curations`, and `annotations` with
typed results. The TypeScript SDK exposes `qualityProfiles`, `curations`, and
`annotations`. Both support real image upload and checksum-verified export.
Use current IDs/revisions from API results. Credentials stay in environment
variables or your credential manager; never put them in examples or browser bundles.

```python
# api is an authenticated DataFoundry client; task comes from annotations.get().
reviewed = api.annotations.review(
    task.id,
    expected_revision=task.revision,
    decision="accept",
    annotation={"kind": "category", "label": "object"},
    note="Inspected this source and corrected its category.",
)
current = api.curations.get(reviewed.curation_id)
# Only approve after inspecting all labels, the completed card, and quality.
frozen = api.curations.freeze(
    current.id,
    expected_revision=current.revision,
    approved_for_publication=True,
)
```

Publish through the same budgeted API/SDK run flow using this source node:

```json
{"id":"source","type":"curate","config":{"curation_id":"ACTUAL_FROZEN_CURATION_ID"}}
```

Follow it with `validate → publish`. The console creates that real recipe for
you. The CLI provides `curations profiles/create-profile/create/get/list/data-card/freeze`
and `annotations list/get/assign/decision/adjudicate/reopen`; use `--help` for the
file arguments. `datafoundry datasets export VERSION_ID output.zip --format coco`
downloads and verifies an image bundle. CLI freeze requires the explicit
`--approve-publication` flag.

## Limits and failures

Local sessions: 500 samples, 20 MiB source/normalized media, 100 uploads, 100 label
categories, 100 boxes per image. Text near matching: at most 10,000 text characters
per sample. Invalid MIME, image dimensions, coordinates, categories, tenant IDs,
stale revisions, assignments, insufficient scopes or incomplete review are rejected
by the API. No external model, paid service or remote image URL is used.

Keep `.local` logs and Playwright traces private. Redacted API evidence and public
synthetic screenshots are in `verification/evidence/p06`. Frozen artifacts and
database rows must not be edited to repair a review: create a new session/version.
