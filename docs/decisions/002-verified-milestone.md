# ADR 002: local capability boundaries

P00–P05 deliver a local multi-user text dataset lifecycle. P06–P12 remain later
phases. The default `make dev` uses Compose for persistent PostgreSQL, RustFS and
Temporal, with supervised host API, worker, web and webhook receiver processes.
This fits the managed workspace's 7.9 GiB writable filesystem. The full container
topology is configured in `make dev-containers` but has not been executed here.
Application base image digests target Linux AMD64; dependency downloads retain
TLS verification with mounted CA trust. Temporal CLI 1.4.1 uses persistent local
storage and explicit local NO_PROXY entries for its internal gRPC connections.

Executable recipes are one linear source → validator → publisher → optional
JSONL export pipeline. Forms, JSON and graph inspection share one definition.
General branching, schedules, arbitrary code, AI inference, GPU/HPC dispatch and
simulation are unavailable. The generator makes independently checkable
arithmetic examples. It is not an AI or teacher-model adapter.

Uploads are UTF-8 JSONL, at most 20 MiB and 10,000 records. Sample schemas are
inline JSON Schema without `$ref`/`$dynamicRef` resolution, preventing remote
fetches. Quality covers schema, SHA-256 integrity, exact duplicates and declared
source rights. Semantic, PII, contamination and factuality models are deferred.

Published manifests identify the exact local worker source/lockfile SHA-256 and
Python version. Host processes have no container image attestation. Production
image signing, OTel spans, backup/PITR and release hardening remain later gates.

Browser sessions last 12 hours with HttpOnly/SameSite cookies, an allowed origin
and a CSRF token on mutations. Startup refuses production mode. API keys are
user-owned, scoped, hashed and revocable; independent service identities are
deferred. Idempotency fingerprints use HMAC, preventing a fast offline password
oracle for member creation. Cached secret-creation responses omit the secrets.

Webhooks are HMAC signed over timestamp and exact bytes. Five attempts use
bounded exponential backoff, then dead-letter; replay preserves event identity.
Consumers deduplicate at-least-once delivery. Only explicit local destinations
are allowed and revalidated before sending. Redirects and arbitrary external
delivery/imports are disabled. The local verifier's control/read endpoints
require the local app secret and are for testing only.

No Git remote is configured. There are no pushed commits, remote PRs, cloud
deployments or paid calls. This milestone must not be represented as a
production release or as completion of the entire feature matrix.
