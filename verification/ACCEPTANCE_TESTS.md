# End-to-end acceptance tests and release proof

All tests are proposals until implemented and executed in an actual repository. For each, maintain a test file, preconditions, commands, real output/artifact reference, security negatives, and evidence in BUILD_LOG.md.

## Core E2E: first usable product
1. Fresh clone; `make bootstrap`; `make dev`. Health/readiness endpoints pass; login available; no hard-coded production credentials.
2. Two seeded independent organizations; organization A user authenticates, creates text dataset; organization B cannot see A's dataset via query or direct ID.
3. Organization A uploads valid text JSONL fixture with multipart signed URLs; resulting file sha256 matches; invalid MIME/oversized/unsupported file blocked.
4. User creates typed recipe with deterministic generator -> validator -> publisher; malformed graph or unsupported modality rejected.
5. User launches job from dashboard, same job from API and Python SDK; worker is actually scheduled and writes data; UI polls or subscribes to real state; no invented metrics.
6. Quality checks pass; immutable version published with complete manifest and provenance; version digest stable; signed export downloads parseable JSONL.
7. Signed webhook is delivered and verified using raw-body HMAC and timestamp; second delivery is idempotently consumed; endpoint 500 triggers retry and bounded dead-letter state.
8. Reusing idempotency key with same payload returns original resource; different payload conflicts; worker crash/retry does not double-publish or double-charge.
9. Budget below estimated cost blocks job before compute; hard spend cap stops additional work; full usage ledger matches measured local work.
10. UI and API render accurate errors on 401/403/409/422/429/500; client sees retry help and request ID where appropriate.

## Labeling + quality
Review assign/accept/edit/reject/adjudicate; persist reviewer identity and timestamp; COCO/YOLO export label matches UI; corrupt label blocks publication; dedupe counts recompute reproducibly.

## Model and provider adapters
Configured, approved teacher-model call succeeds with real trace and usage; unavailable/missing rights returns `POLICY_BLOCKED` or `PROVIDER_NOT_CONFIGURED`; rate-limit retry and budget checked. Never generate unauthorized training data.

## Simulation
Blender headless render produces actual frame, metadata and checksum. Isaac Sim/Isaac Lab run only on pinned RTX-capable compatible node; H100-only node returns capability unavailable. Episode files have monotonic timestamps and valid observation/action alignment. Empty configured pools produce correct no-worker state.

## Operational
Restore DB to clean staging; verify manifest index and S3 consistency. Cancel/retry job and reconcile spend. Simulate disk/storage/provider errors. Security checks for SSRF imports, ZIP bombs, XSS in sample previews, token logging, expired signed URLs and plugin sandbox escapes. Load test planned target sustained usage and record p95/queue/worker utilization before any SLA.

## UI
Axe baseline, keyboard-only create-to-export flow, responsive widths 360/390/768/1024/1440, light/dark/reduced motion, authenticated logout, app shell no overflow; all visible buttons and navigation work or are explicitly disabled.

## Release decision
Never mark `RELEASED` without execution evidence. Track `NOT_STARTED / IMPLEMENTING / INTEGRATED / TESTED / RELEASED / BLOCKED_EXTERNAL / DESIGN_ONLY`. Required signoff: engineering, security, data provenance/rights and infrastructure owner.
