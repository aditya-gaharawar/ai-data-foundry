# Build evidence log

Delivery checkpoint: **2026-11-05 00:22 IST**. The imported archive was a planning package;
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

## Commands and results

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

The full 108-feature product is not complete: **42 TESTED, 16 INTEGRATED with
explicit limits, 50 NOT_STARTED**. No feature is marked released. The first local
vertical slice works; P06 curation/annotation is next. Model adapters, GPU/HPC,
simulations, enterprise identity/billing, advanced quality and production ops
remain later phases. No authorized provider credentials/rights or compatible
RTX/cluster are configured; no fake provider/GPU results were produced.

The default runner fits this workspace's constrained disk by running application
processes on the host and persistent services in Docker. Full app-container
execution, remote PR/CI execution, production security/load/restore and human
screen-reader review are not claimed. No Git remote is configured, so no PR was
opened or merged. All work is locally reviewable. No paid calls/infrastructure,
external model transmission, public publishing or production deployment occurred.
