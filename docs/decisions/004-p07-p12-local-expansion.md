# ADR 004: Deliver the remaining phase slices as one local batch

The user explicitly requested the next phases and everything together. Continue
P07–P12 in one branch, preserving the P00–P06 implementation and evidence. This
supersedes the handoff's incremental execution cadence, not its acceptance or
authorization boundaries. Six local review drafts describe each phase; hosted
PRs, merges, and remote CI are unavailable because no Git remote is configured.

Use the existing PostgreSQL/S3/Temporal architecture. Add real CPU model and
Blender operators, scoped outbound agents, fixed-benchmark evaluation, native
privacy policies, independent approvals, artifact retention, and operational
evidence. Each locally available flow must work through API, console, SDK, and
tests. Unavailable external integrations stay BLOCKED_EXTERNAL.

No paid inference, cloud resource provisioning, private production input,
external repository change, staging deployment, or production cutover is
authorized by this batch. Local synthetic fixtures and reversible recovery
resources are in scope. This is a local expansion candidate, not completed V2.

# ADR 005: Trusted CPU inference and procedural Blender first

The text adapter uses llama-cpp-python 0.3.19 built with GCC and a pinned
Apache-2.0 SmolLM2-135M-Instruct GGUF. Model SHA-256, source/quantization
revisions, explicit permission evidence, accepted token counts, and runtime
provenance are retained. JSON Schema validity does not imply factual accuracy.
Native subprocesses run only trusted built-in scripts with a minimal
environment. They are not a sandbox for arbitrary user code.

The optional dependency initially failed with unavailable clang and a musl
wheel on this glibc host. Rebuilding the PyPI source with GCC, two build workers,
and OpenMP/BLAS disabled produced a working native runtime. No substitute model
responses are used. Weights stay private and outside the source archive.

Blender 4.3.2 renders original primitives using CPU Cycles, RGB, real object-index
masks, mask-derived boxes, calibration/poses/timestamps, and GLB scenes. Seeded
camera, material, and light variation is reproducible configuration. Scripted
motion is not robot physics or sim-to-real validation. Isaac remains blocked
without a validated release/driver/container matrix and RTX GPU with RT cores;
H100, H200, and A100 do not satisfy rendering requirements.

External structured-text/base64-image codecs, Kueue job templates, and Slurm
submission/accounting codecs have contract tests. No live remote execution or
approved remote price/account exists. Do not enable these as connected adapters
on the strength of codec tests.

# ADR 006: Tenant-bound leases and protected outcomes

Agent tokens are one-time, hashed, revocable, and scoped to one organization and
pool. Current capability heartbeats precede claims. Pool capacity, one live lease
per agent, attempt limits, expiry, secret fencing, cancellation, and API-side
artifact checks constrain fixed verification jobs. Agent durations are reported
and nonbillable, not trusted external invoices. No arbitrary programs execute.

Holdout access is a distinct scope. Dataset, version, export, sample, review,
compute, evaluation, search, and listing paths use common visibility rules.
Holdout conversion rejects active runs/compute jobs and exact overlap, including
bounded checks of legacy versions without search indexes. Generation publication
checks protected content hashes under an organization lock. This is not semantic
contamination detection or independent attestation of benchmark provenance.

Evaluations store imported counts, denominators, Wilson intervals, source run
references and immutable evidence on a fixed protected benchmark. Comparisons are
descriptive; synthetic fixtures cannot prove model gains. Feedback saves a bounded
manual recommendation and never dispatches training or generation automatically.

# ADR 007: Local governance and artifact erasure

Organization policy revisions are immutable. They enforce declared license lists,
native email/US-SSN/formatted-phone handling, and optional frozen human review.
Policy drift prevents stale source approvals/publication; native PII rules are
explicitly incomplete and do not provide a safety classifier.

Legal hold release and erasure approval require a different administrator.
Erasure uses a policy delay, exact dataset-name confirmation, a sealed S3 object
version plan, and a committed access tombstone before durable physical deletion.
Organization artifact-reference locks prevent new attachments racing erasure;
the worker preserves blobs referenced by other live datasets and verifies deleted
versions are unavailable. Failed deletion retains the tombstone and resumes the
same plan on an authorized retry. Audit, manifests, reviews and control metadata
remain. Unreferenced orphan GC and full personal-data/compliance erasure are not
claimed.

SCIM is a local core-Users subset: domain-restricted provisioning tokens,
Engineer/Labeler/Viewer roles, membership-local deactivation, ETags, filter and
bounded pagination. It cannot provision Owner/Admin or change a global account's
password/profile. SSO, Groups, Bulk, Password and licensed IdP interoperability
are unconfigured. Deleted bindings remain tombstoned; reprovisioning a previously
bound user needs an explicit future recovery design.

# ADR 008: Local evidence is not a production release

Reconciliation records disagreements between append-only usage, run balances,
and organization balances without editing money. Incident signals come from real
failed runs or stale enrolled agents. Local load reports measure bounded HTTP
read traffic and cannot establish availability, production capacity, or an SLA.

Recovery archives are mode 0600 and excluded from Git/source bundles. pg_dump is
restored into a new disposable database; all S3 object versions are restored to a
new disposable bucket. Original object-version identifiers are remapped only by
a private operator file so immutable manifests do not change. A separate restored
API proves authentication, tenant negatives, and sample reads before termination.
This is a recovery/configuration rollback rehearsal, not a staging traffic
rollback. Temporal development-server history and external KMS/SSO need separate
production recovery procedures. The app secret is not included in backups.

HMAC evidence is an attestation by this local operator. Readiness expires evidence
after a day or any source fingerprint change. It separately blocks staging,
production identity, independent security review, external infrastructure, remote
CI/review, and production SLA gates. No release status or compliance certification
is inferred from passing local tests.

# ADR 009: Dependency findings and remaining security boundary

Actual npm and OSV package-version queries found advisories. Cryptography was
updated to 50.0.2 and Pillow to 13.0.0, then regression was rerun. The optional
llama.cpp wrapper still depends on diskcache 5.6.3, whose unsafe pickle advisory
has no upstream fixed release. The app never creates a disk cache, accepts cache
paths, or deserializes cache data; its inference child refuses a configured cache.
The exact residual advisory is recorded, not suppressed from scan output. Remove
or replace that dependency before production. A scoped local security PASS means
the documented local gate and mitigations passed, not zero advisories or an
independent penetration test.
