# P06: bounded local curation and human review

Decision: extend the existing API, database, object store and durable CPU worker.
This phase supports text category labels and image bounding boxes. It introduces
no model provider, distributed curation engine, paid integration or deployment.

## Sources and image integrity

A curation session snapshots either a published version or completed uploads
from the same dataset and organization. Source rows live in a content-addressed
JSONL artifact, rather than a relational sample table. Each task references its
source row. Local sessions are limited to 500 samples and 20 MiB; text matching
also limits each sample to 10,000 text characters.

Image uploads accept single PNG/JPEG files, checksum them, decode them with the
locked Pillow version, apply EXIF orientation and produce metadata-free RGB PNG
bytes and a thumbnail. Limits are 6 million pixels and 4096 pixels per edge.
Original source hashes remain in provenance. Previews require current tenant
authentication; user-supplied object keys or remote URLs are never accepted.
This is format isolation and bounded decoding, not a general malware scanner.

## Immutable profiles and reproducible cleaning

Quality profiles are immutable database records. They configure exact/near
removal, minimum accepted samples, acceptance ratio, remaining duplicate ratios,
and the near-match threshold. A new profile is required to change these rules.

Text exact matches use canonical JSON SHA-256. Near matches use Jaccard similarity
of word trigrams after Unicode NFKC normalization and case folding. Image exact
matches use the normalized PNG checksum; near matches use 64-bit grayscale dHash
Hamming distance. The first source-order representative wins. The report records
excluded source indexes, representatives, algorithm and parameters. These are
lexical/perceptual checks; semantic equivalence and label accuracy are not claimed.

## Review identity, concurrency and disagreement

Owner/Admin can manage, review and adjudicate. Engineer can manage and review.
Labeler can read datasets, claim unassigned tasks, and review. Viewer can read.
API keys retain their explicit scopes and current owning-user membership.

Every task mutation checks its expected revision. All mutations lock the parent
curation before the task, so approval cannot race a label edit. Assignments are
validated against current organization memberships. Reviews record the actual
user, optional API-key ID, annotation, decision, reason, timestamp, revision and
review round. Corrections append history; a user's latest vote in a round counts
once, including when that user has multiple keys.

The default requires two independent users. Matching decisions/annotations yield
ACCEPTED or REJECTED; disagreements yield NEEDS_ADJUDICATION. An Owner/Admin who
did not vote in that round may adjudicate. Reopening starts a new round while
retaining history. An explicitly selected single-review policy is supported and
does not claim independent consensus. Agreement reports show their paired-task
denominator; agreement is not ground-truth accuracy.

## Approval and publication

The gate checks review coverage, accepted payload schema, annotation vocabulary
and image bounds, minimum count/acceptance, exact/near duplication, data-card
completeness, active dataset and declared source-use permission. Rejected and
duplicate-excluded rows are removed. Invalid accepted data blocks approval and
publication. A failed gate persists its report and an audit event.

Data cards contain authored purpose, intended use, limitations, content risks and
restrictions, alongside observed sources and declared policy. Approval records
the approving user and timestamp and writes a sealed snapshot containing the
accepted records, labels, complete review history, profile, card and quality.
PostgreSQL triggers protect profile/review history and all frozen curation/task
evidence from mutation.

A typed `curate` source node feeds the existing Temporal pipeline. The worker
rechecks the frozen snapshot, schema, annotations, checksums and rights; uses the
existing budget reservations/checkpoints; and publishes a new immutable version.
The manifest seals card, quality profile, approval and review-history artifact.
Annotation review units count decisions, including corrections and adjudication,
but exclude administrative reopen events. They have zero external cost and no
additional internal charge in this local rate card.

## COCO and YOLO

Image publication builds both ZIP bundles in the worker. Each includes the actual
normalized images and data card. COCO uses pixel `[x,y,width,height]` and 1-based
category IDs. YOLO uses 0-based categories and normalized center/width/height;
its `data.yaml` uses valid YAML 1.2 JSON syntax. Image names use opaque sample IDs.
ZIP entry order/timestamps are deterministic. Signed, authenticated exports reuse
the existing five-minute tenant/user-bound grants and SHA-256 verification.

JSONL contains the same accepted annotation and provenance. COCO/YOLO are offered
only for published image versions with approved box annotations. No text-to-box
conversion, segmentation, polygons, keypoints, video or robotics labels are implied.

## Scope and review boundary

Machine suggestions await the authorized model-provider work in P07. Semantic
dedupe, PII/contamination models, gold-standard accuracy, reviewer analytics and
larger-scale/distributed processing remain unimplemented. Rights are declared
and enforced as metadata; this phase does not establish legal ownership.

The review branch is local. No Git remote is configured, so opening a hosted PR
is blocked until a repository is connected. The proposed PR body is in
`docs/reviews/P06_PR.md`; no remote publication or merge is claimed.
