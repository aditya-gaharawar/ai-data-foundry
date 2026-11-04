# ADR 001: local milestone runtime

The handoff is authoritative for behavior. Use the newer JSON recipe and event
contracts when earlier prose examples disagree. FastAPI/Pydantic generate the
checked OpenAPI document; SDK generation and contract tests detect drift.

Use PostgreSQL for application metadata, S3-compatible storage for bytes, and a
Temporal development server with a persistent volume for local orchestration.
The Temporal development server and database-backed local authentication are
explicitly local-only; startup refuses production mode. No provider API, remote
cluster, paid infrastructure, or deployment is enabled.

On 4 November 2026, official MinIO Docker Hub and Quay image retrieval failed
with registry access errors, including the latest Docker Hub tag. Use the
official RustFS image pinned by digest as the local S3-compatible implementation.
The Compose service retains the `minio` DNS name to preserve S3 endpoint settings.
Compatibility must be demonstrated with real multipart, checksum, versioning,
conditional writes, signed URLs, and restart tests. MinIO-specific verification
remains blocked by image availability; do not claim MinIO was executed.

Exports use signed five-minute grants checked against the authenticated user
and organization before streaming pinned object versions through the API. Raw
S3 presigned downloads are bearer credentials and cannot meet the packet's
stronger requirement that another authenticated tenant cannot reuse a link.

The supplied broad recipe schema is narrowed by server-side engine validation
to one connected source → validator → publisher → optional JSONL export pipeline.
Unsupported graph/engine/configuration requests fail explicitly. No user code runs.

Internal local estimates use a configured rate card in integer micro-USD and are
clearly separated from actual external cost, which is zero. No invoices or paid
billing are simulated. Work is metered at durable processing checkpoints.

There is no intended Git remote configured. Reviewable changes and phase evidence
are local; remote PR creation and merging are not represented as completed.
