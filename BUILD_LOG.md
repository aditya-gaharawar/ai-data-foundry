# Build evidence log

Latest checkpoint: **2026-11-06 01:29 IST**, P07–P12 local expansion. [Detailed evidence](verification/evidence/p07-p12/VERIFICATION.md). Historical checkpoints follow.

Delivery checkpoint: **2026-11-05 02:30 IST**. The imported archive was a planning package;
there was no AI Data Foundry implementation, repository, configured provider or
remote at baseline. Its SHA-256 manifest was verified before import. Original
planning evidence/manifest are retained under `docs/handoff/`.

## Implemented local milestone

| Phase | Verified behavior | Proof and limits |
| --- | --- | --- |
| P00 | New Git project; locked Next.js/FastAPI/Postgres/S3/Temporal runtime; migrations, private secrets, Make targets and CI configuration | Real local health and fresh DB proof. Compose infrastructure plus host application runner. Full application-container execution and remote CI unverified. |
| P01 | Tokenized Geist console, navigation, project selector, command menu, themes, priority routes, real states | 24 screenshots, axe in both themes, responsive widths, keyboard-only lifecycle. Human screen-reader signoff remains. |
| P02 | Separate accounts, memberships/roles, two organizations, sessions/CSRF, hashed scoped keys, audit and revocation | Security tests, actual administrator-created Viewer, cross-tenant denial and revoked-membership logout/re-authentication checks. Local auth only. |
| P03 | Dataset registry, metadata search/cursors, signed multipart upload, server checksum and safe preview | SDK multipart >5 MiB and real browser S3 upload/CORS. Text JSONL only. |
| P04 | Typed linear recipes, immutable revisions, durable outbox/Temporal, checkpoints, budgets/usage, quality, immutable versions and signed export | Real 100-record lifecycle, killed-worker 10,000-record recovery, idempotent effects, cancel/retry, quality and budget negatives. General DAGs/external engines deferred. |
| P05 | OpenAPI 3.1, generated TS/Python contracts, SDKs, CLI, HMAC webhooks with retry/dead-letter/replay | Both SDK flows, standalone SDK environment, CLI, raw-body signature verification and complete browser flows. Wider provider/compute commands deferred. |
| P06 | Immutable quality profiles; exact/near cleaning; real PNG/JPEG decoding/preview; category/box labels; assignments, independent consensus/adjudication, correction history; authored data cards, blocking review gate and immutable approval; durable reviewed JSONL/COCO/YOLO publication; both SDKs and CLI | 51 unique automated tests across the current core, production build, clean migration and API-restart proof, 18 new screenshots. Text/image local limits; no model suggestions or accuracy guarantee. Full report: `verification/evidence/p06/VERIFICATION.md`. |

## P00–P05 baseline commands and results

All executed check summaries and command outputs are under
`verification/evidence/VERIFICATION.md` and its adjacent logs: bootstrap (exit 0),
lint (0), unit/contract **13 passed** (0), integration **9 passed** (0), security
**7 passed** (0), browser **6 passed** (0), smoke **1 passed** (0), production web
build (0), fresh-database exercise (0), Alembic drift (0) and contract drift (0).
The smoke test repeats an integration scenario; do not count it as an extra test.

Real persisted run: `run_bcc47efd4638471b8064823780348eba`; version `ver_bcc47efd4638471b8064823780348eba`;
100 exported JSONL records. Artifact/manifest/source hashes, actual API fields,
second-tenant denials and verified webhook metadata are saved in
`verification/evidence/api-proof.json` and `webhook-proof.json`. No credentials,
cookies, signing secrets or signed grants are included in those evidence files.

## Corrections discovered during execution

- Official MinIO registry retrieval failed. An official digest-pinned RustFS
  container provides S3; real compatibility tests passed. MinIO itself was not run.
- Initial migration ordering put composite FKs before referenced unique indexes;
  ordering was corrected and verified against a completely fresh database.
- Temporal required correct volume ownership and local NO_PROXY settings for
  internal gRPC; the pinned persistent development server now passes readiness.
- The editable root install initially preceded creation of the SDK directory;
  reinstalling the package fixed discovery, and a standalone SDK package/install
  test proves clean-environment usage.
- Accessibility checks exposed a search accessible-name mismatch, loading role
  markup and third-party attribution contrast. All were corrected and rechecked.
- The API restart test initially accepted the old server's final response;
  it now waits for a different PID and a real responding replacement process.
- Generated-model import spacing caused a drift check; the generator now emits
  the same canonical formatting as the checked models.
- Browser upload proof exposed a workflow target lost on navigation. Saving now
  preserves its dataset; existing ingestion workflows resolve their source's
  tenant-scoped dataset. Browser tests assert the original dataset identity.
- Removed members could otherwise authenticate without a workspace. Login now
  rejects that state; logout can safely clear a revoked member's session.
- Access logging was hardened to exclude signed query strings. Legacy local log
  grant values were redacted; checked evidence contains no reusable credentials.

## Changed subsystems

Web console and BFF; API/domain models and three explicit migrations; CPU/Temporal
worker and transactional event delivery; SDKs and CLI; Compose/Docker/CI tooling;
security/integration/browser tests; reproducible examples; architecture decisions,
runbooks, route contracts and feature matrix. No unrelated workspace repository
was modified.

## True remaining limits and next phase

The full 108-feature product is not complete: **51 TESTED, 13 INTEGRATED with
explicit limits, 44 NOT_STARTED**. No feature is marked released. The local core and P06
curation/annotation work; P07 authorized model generation is next. Model adapters, GPU/HPC,
simulations, enterprise identity/billing, advanced quality and production ops
remain later phases. No authorized provider credentials/rights or compatible
RTX/cluster are configured; no fake provider/GPU results were produced.

The default runner fits this workspace's constrained disk by running application
processes on the host and persistent services in Docker. Full app-container
execution, remote PR/CI execution, production security/load/restore and human
screen-reader review are not claimed. No Git remote is configured, so no PR was
opened or merged. All work is locally reviewable. No paid calls/infrastructure,
external model transmission, public publishing or production deployment occurred.


## P06 executed checkpoint

Current verification: **51 unique automated tests passed** (20 unit/contract,
15 integration including one targeted rejection case, 8 security, 8 browser).
Bootstrap, lint/type checks, optimized production build, clean-database migration
and persistence, OpenAPI/Alembic drift checks and smoke all exited 0. Smoke repeats
a core scenario and is not counted again. Exact commands, outputs, failures and
corrections are in `verification/evidence/p06/VERIFICATION.md` and adjacent logs.

The phase adds four tenant-scoped tables and migration `0730f891010f`, bounded
image decoding, a typed reviewed-source worker path, review/data-card console
routes, generated contracts and SDK/CLI parity. Server-side checks enforce
assignment, current role/scope, expected revision, independent users/adjudicator,
annotation validity, coverage, schema, source rights and immutable approval.
PostgreSQL rejects mutable history and frozen evidence. Signed exports contain
the same accepted labels as the UI; actual synthetic COCO/YOLO bundles and JSONL
are retained alongside source/manifest/checksum and second-tenant denial proof.

Reviewer corrections, review history, data card and manifest survived an actual
API restart with a different PID. Browser flows cover two independent labelers,
administrator adjudication, image upload/box publication/download, safe source
rendering, keyboard review, all original core journeys, responsive widths and
light/dark axe checks. Eighteen new P06 screenshots are retained.

The first live-service test attempt hit an exited supervisor; it was restored
before retesting. Native-select test selectors and duplicate unlabeled landmarks
were corrected. The extra Axe capture harness was adjusted to use an explicit
BrowserContext. Passing results reflect executed corrected code, not substituted
responses. See the detailed evidence report for scope and exact outputs.

P06 is a verified local text-category/image-box slice. Machine suggestions,
semantic dedupe, advanced annotations and measured label accuracy remain pending.
No remote, paid provider or production system was changed. A reviewable local
branch and `docs/reviews/P06_PR.md` are prepared; opening the required hosted PR
is blocked because this checkout has no Git remote. Nothing was pushed or merged.


## P07–P12 executed local expansion

Checkpoint: **2026-11-06 01:29 IST**. The requested combined phase build now has real CPU
teacher generation, Blender perception artifacts/3D preview, scoped outbound
compute leases, version search/diffs/evaluation/feedback, privacy/license/review
policy, independent hold/erasure approvals, local SCIM Users, durable shared-safe
artifact deletion, ledger/incidents and signed local recovery/readiness.

**77 unique tests passed**: 25 unit/contract, 23 integration, 13 security and
16 browser. Bootstrap, lint/types, OpenAPI/Alembic drift, fresh DB/restart/tenancy,
smoke and optimized build passed. Two genuine generation/render browser journeys
were repeated against the optimized local server. Native smoke repeats and the
core smoke are not extra unique tests.

Actual recovery verified 1556 object versions,
186,342,895 bytes, 161
manifest seals, 38 metadata tables and two
tenants through an isolated restored API. Temporary DB/bucket cleanup passed.
The bounded 60-request/4-concurrency local load
had zero errors and p95 103.83 ms. It is not a production SLA.

All seven source-bound local readiness gates passed; the persisted report is
HMAC signed and verified. Production release remains BLOCKED_EXTERNAL. The
optional diskcache advisory, unconfigured SSO/provider/cluster/RTX/staging,
independent pentest and remote CI/review remain explicit release blockers.
Cryptography/Pillow were updated and rescanned; no zero-advisory Python claim
is made. Native PII/exact holdout and artifact-erasure limits remain documented.

All exact commands, native artifacts, screenshots, early failures/corrections
(including metadata-loading and recovery-helper fixes), source hashes and
limitations are in `verification/evidence/p07-p12/VERIFICATION.md`. Historical
P00–P06 evidence is retained; current regression captures are saved separately.
Feature counts are {'TESTED': 70, 'INTEGRATED': 22, 'NOT_STARTED': 8, 'BLOCKED_EXTERNAL': 8}. No feature is marked RELEASED.

Local branch `phases/p07-p12-completion` and six phase review drafts are prepared.
No Git remote exists, so no hosted PR or merge is claimed. No paid service,
private production import, external model inference, cloud resource, public
publication, remote repository or production system was changed. The source
bundle excludes private secrets, weights, native binaries and recovery backups.
