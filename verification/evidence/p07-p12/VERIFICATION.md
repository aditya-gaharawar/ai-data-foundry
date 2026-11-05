# P07–P12 local expansion verification

Verified checkpoint: **2026-11-06 01:29 IST**. Branch: `phases/p07-p12-completion`, based on
P06 `0f1d469`. The user requested one combined build effort. This report covers
actual local slices of every remaining phase, not a completed production V2.
No hosted PR, merge, remote CI or deployment is claimed; no Git remote exists.

Current executable-source fingerprint: `86e88c83df591f33a6cae4dbf1ace3445d215a9228161453b6bfbc524e1aeb18`.
It covers application/SDK code, contracts, tests, operator scripts, dependency
locks, runtime configuration, infrastructure and CI definitions. Documentation,
private files, generated build directories and evidence are excluded from this
fingerprint; the delivery manifest separately seals packaged source/evidence.

## Result

**77 unique tests passed:** 25 unit/contract, 23 integration, 13 security,
and 16 browser. Smoke repeats one integration story. Two final native tests and
two optimized-browser native journeys repeat covered cases and are not counted
again. Bootstrap, lint/types, frozen contracts, clean migrations, fresh database
and restart/tenancy, optimized build, recovery, load and scoped security review
also exited 0. The optimized local app is serving at `http://localhost:3000`;
API docs are at `http://localhost:8000/v1/docs`.

The persisted, HMAC-signed [readiness report](readiness-report.json) has all seven
local gates PASS and production release **BLOCKED_EXTERNAL**. Its HMAC was
verified with the private local operator secret. This is a local operator
attestation, not an independent signature, audit, penetration test or deployment
approval. Raw operational import signatures and credential-bearing backups remain
private. [Redacted operator reports](operator-reports.json) retain actual measures.

## End-to-end phase slices

| Phase | Actual implemented flow | Evidence / limits |
| --- | --- | --- |
| P07 | Permitted local provider registry → immutable consent/terms → CPU model → schema validation → measured accepted tokens → durable source checkpoint → immutable version | Genuine llama.cpp 0.3.19 inference using pinned Apache-2.0 SmolLM2 GGUF; schema validity is not factual quality. External text/image accounts remain blocked. |
| P08 | Pool → hashed outbound identity → capability heartbeat → capacity admission → queued fixed artifact operator → expiring fenced lease → real worker result independently checked by API | Disconnection/expiry/stale result/retry/revocation and active-lease holdout rejection verified. Kueue/Slurm templates/codecs lack a connected cluster or live execution. |
| P09 | Typed scene recipe → trusted Blender 4.3.2 CPU Cycles process → RGB/object mask → derived boxes/calibration/poses/timestamps → GLB → protected 3D/frame viewer → actual COCO/YOLO | Real inspectable artifacts. Scripted primitive motion is not robot physics. RTX Isaac Sim/Replicator and Isaac Lab remain blocked; H100/H200/A100 are rejected. |
| P10 | Immutable versions → PostgreSQL lexical index/distributions/diffs → protected fixed benchmark → imported counts and Wilson intervals → traceable bounded proposal → manual decision | Synthetic fixture counts are labeled; they cannot prove model gains. Exact holdout hashes are enforced across publication/search/export/compute, including legacy sources; semantic contamination/search and automatic training are absent. |
| P11 | Immutable policy → native PII block/redact/license/review gate → independent legal-hold/erasure approval → delay/sealed plan/name confirmation → access tombstone → real durable S3 version deletion | Shared blobs survive. Audit/review/manifests remain. SCIM core Users CRUD/filter/paging/ETags is tenant/domain scoped and preserves other tenants; SSO/licensed IdP/Groups/Bulk/Password and full compliance erasure are not claimed. |
| P12 | Immutable usage reconciliation → actual incident signals/ack → real isolated metadata/object/API restore → configuration rollback rehearsal → bounded load → advisory/source review → source-bound readiness | Local checks passed; production identity, staging demonstration/traffic rollback, independent pentest, remote review/CI, external infrastructure and SLA are blocked. |

Both SDKs and CLI execute the new domains over real HTTP, including separate-token
SCIM lifecycle/If-Match. OpenAPI has **113 paths and 75 generated Python models**,
plus generated TypeScript contracts and distinct user/agent/SCIM security schemes.
Three tenant-scoped migrations follow P06: `71ef4bff5ffd`, `766782ecb1f7`,
`4186cec3afc4`. PostgreSQL enforces tenant references and immutable evidence.

## Native artifacts and data flow

The optimized browser journeys verified login → BFF → API → PostgreSQL/S3 →
Temporal/native worker → publication → returned samples and protected GLB, with
actual rendering rather than substituted responses. The [API proof](api-proof.json)
and [artifact directory](artifacts) contain source/manifest/engine/license/usage
metadata, JSONL, normalized frame, aligned mask, GLB and verified export ZIPs.

| Engine | Actual run | Samples | Data SHA-256 |
| --- | --- | --- | --- |
| local.llama.cpp@0.3.19 | `run_a78ab26a113642c7b653f15c488505eb` | 1 | `703d72013899c9c95c6339468bf635a848fbeca86ca141dd16fa5bb7043d45d9` |
| blender.procedural@1 | `run_f2ae9d0e57ed4bbc948980f470024b44` | 2 | `5ef9d9360e85f7d20ddcc1804ecd09e57ccb84cd8f9878e07fe3d276bb38c74d` |

All engine/export bytes and immutable manifest seals were checked. Export grants,
credentials, cookies, private weights and backups are not included. Local model
weights SHA-256 is `2e8040ceae7815abe0dcb3540b9995eaa1fa0d2ca9e797d0a635ae4433c68c2d`.
The setup script retains pinned source/quantization revisions and Apache-2.0
metadata. Native model/runtime setup is optional and must be installed separately
from the source bundle. Missing engines report a dependency blocker.

[Final guard checks](final-guards.json) show second-tenant provider/version/sample
reads return 404, malformed recipe values are not echoed, and disposable recovery
DBs/buckets were cleaned up. The full suites also cover holdout access denial,
exact contamination rejection, PII block/redaction, role/scope negatives, SCIM
revocation and ETags, independent approvals, erasure and shared-image survival.

## Recovery, load and security

The final recovery verified **1556 object
versions / 186,342,895 bytes**, **38
metadata tables**, **161 immutable manifests**,
and **2 tenants**. Restored API login, tenant negatives and
actual immutable sample reads passed. Original S3 version IDs were remapped by a
private operator file without modifying manifests. Only generated temporary DB/
bucket resources were removed. Backup ZIPs/maps are mode 0600 in ignored `.local/`
and are never shipped. The app secret is a separate recovery prerequisite.
Temporal service history, external KMS/SSO and unfinished multipart sessions are
outside this drill; unfinished uploads require re-upload. This is not a staging
traffic rollback or a production RPO/RTO promise.

The bounded load issued **60 requests at concurrency 4**,
with **0 errors**, p50 **63.79 ms**, p95 **103.83 ms**
and **59.75 requests/s**. These are local observations,
not a production SLA or fleet-capacity claim. The [load report](operator-reports.json)
records its threshold and limits.

Actual npm audit reported zero advisories. OSV checked **68 installed Python
packages**. Cryptography was updated to **50.0.2** and Pillow to **13.0.0**.
The optional llama.cpp wrapper retains **diskcache 5.6.3**, with
`GHSA-w8v5-vhqr-4h9v` / `PYSEC-2026-2447` and no fixed upstream release. The
application never configures/reads a disk cache, accepts cache paths or unpickles
cache data; its native child refuses an enabled cache. This is a reviewed local
mitigation, not advisory removal. Replace/remove it before production.
Source review found no known private secret/password values in delivered files;
the documented development S3 access-key ID is a public username, not signing
material. No independent pentest, native binary audit or container OS scan is
claimed. Exact advisory responses are retained in `python-osv-audit.json` and
`npm-audit.json`.

Internal fixture budgets were explicitly widened to USD 1,000 for repeated local
regression. This is a nonbillable local rate card, not money charged; actual
external usage cost is zero. No paid API call, cloud resource, public publication,
remote repository change or production deployment occurred.

## Browser and visual proof

There are **29 new phase screenshots**, plus **34 preserved current
core/P06 regression screenshots** under `regression/`. Historical P00–P06 evidence
was restored unchanged after saving current captures separately. New flows cover
provider permission/loading, real generation, actual rendering/GLB/mask, a real
outbound worker, A/B reports/import/feedback, legal hold/SCIM revocation, independently
approved sealed erasure, ledger/incidents and signed readiness.

All six new pages passed axe WCAG A/AA checks in light and dark themes. Layouts
fit 360/390/768/1024/1440 widths and 200% zoom. The complete suite retains the
keyboard-only lifecycle and mobile navigation. Automated checks are not a human
screen-reader or full accessibility certification. Raw traces remain private
because they may contain sessions or one-time credentials.

## Exact executed checks

| Command | Exit |
| --- | --- |
| `make bootstrap` | 0 |
| `make lint` | 0 |
| `make test` | 0 |
| `make test-integration` | 0 |
| `make test-security` | 0 |
| `make test-e2e` | 0 |
| `make smoke` | 0 |
| `uv run python scripts/verify_fresh_database.py` | 0 |
| `uv run alembic check` | 0 |
| `uv run python scripts/contracts.py --check` | 0 |
| `pnpm build` | 0 |
| `uv run pytest -q tests/test_expansion.py -k "genuine_licensed or blender_frames"` | 0 |
| `pnpm exec playwright test tests/e2e/expansion.spec.ts --grep "Teacher Studio records|Simulation Studio renders" --max-failures=1 --reporter=list` | 0 |
| `make scan-security` | 0 |
| `make test-recovery` | 0 |
| `make test-load` | 0 |
| `uv run python scripts/collect_expansion_evidence.py` | 0 |

`commands.json` and adjacent logs are the executed summaries. Bootstrap and the
full suites were run before the optimized start; the two native browser stories
were repeated successfully against the optimized server. Example teacher/Blender
recipe definitions were also validated against the actual compiler.

## Corrections and honest blockers

- Native model setup initially hit unavailable clang and an incompatible musl
  wheel. Building the pinned PyPI source with GCC and the recorded CPU flags
  yielded genuine working inference; no model output was substituted.
- A recovery maintenance lock interrupted an initial concurrent browser run.
  The corrected runs execute recovery and browser mutations serially.
- Model metadata could arrive after the provider form submitted. Saving now
  waits for verified metadata and refreshes the actual connection record. The
  browser test delays the real catalog response and passes.
- Form helper text/native select options affected exact accessible names; controls
  now have stable labels. Reused approval notes made a repeated test ambiguous;
  fixtures now use unique identifiers.
- Pagination originally ordered random IDs; it now uses creation time plus ID.
  Lease/holdout conversion, approval decisions, revocation and publication use
  current state/locks to prevent stale decisions and protected-source access.
- PostgreSQL aggregate decimals were normalized for persisted ledger JSON.
  Request-size/secret-echo guards and proper SCIM errors/security/ETags were checked.
- The isolated restore API initially resolved a virtualenv symlink into the base
  interpreter; it now preserves the venv path and uses a disposable loopback port.
  The first report upload reused an already-open HTTP client; the operator helper
  now has an explicit context lifecycle, and the complete drill/import passed.
- The first source scan treated a public development S3 username as a secret.
  It now distinguishes identifiers from real secret/password material and records
  that classification explicitly; actual private values are still scanned.

Feature matrix totals: **{'TESTED': 70, 'INTEGRATED': 22, 'NOT_STARTED': 8, 'BLOCKED_EXTERNAL': 8}**, with no RELEASED feature. The remaining
unimplemented broader V2 features are: **Notifications center; Import licensed external source; Audio data pipeline; Video data pipeline; Sim-to-real distribution comparison; Machine label suggestions; Scheduled workflow run; Data residency policy**. Partial rows
also disclose richer charts, semantic methods, general DAG/SSE/service-account
extensions and other advanced scope. The external/blocker rows are not completed
integrations simply because contracts or disabled controls exist.

See [the expansion runbook](../../../docs/runbooks/expansion.md),
[ADRs 004–009](../../../docs/decisions/004-p07-p12-local-expansion.md), and the six
local [phase review drafts](../../../docs/reviews/). Hosted PRs/staging release
remain unavailable without a configured remote/target and applicable approval.

Final source sealing normalized TOML EOF formatting without changing its parsed
configuration. Operational evidence was regenerated for the final fingerprint;
the application/test behavior and optimized build are unchanged.
