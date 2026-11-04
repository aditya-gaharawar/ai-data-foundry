# Deployment and operational playbook (planned)

## Topology
- **Vercel**: Next.js frontend and static/docs pages; bounded BFF and server rendering functions. No physics simulation, distributed GPU training or long-lived CPU batch jobs in Vercel Functions.
- **Container host**: FastAPI with autoscaling, auth middleware, Postgres connection pooling and controlled egress.
- **Database/object storage**: Managed Postgres + S3-compatible versioned buckets, independent per environment, encryption and backup.
- **Durable workflows**: Temporal or verified equivalent, workers with retriable checkpoints and outbox-based webhook delivery.
- **Compute plane**: CPU workers, Ray later, Kubernetes GPU pools, RTX Isaac Sim/Blender containers, authorized Slurm/private agents.

## Deployment strategy
Preview app on PR with no production secrets. Staging has isolated resources and budget caps. Deploy backend before introducing web code that depends on it, but use backwards-compatible migrations. Run integration/E2E smoke, rollback and restore rehearsals. Production promotion only after approval and security review. Use lockfile pinning, signed images, dependency scanning and provenance evidence.

## Health and observability
Liveness only for process; readiness checks DB/workflow dependencies; explicit dependency health dashboard for external providers/agents. Structured logs with trace ID, tenant ID (non-secret), run ID, phase and engine. OTel traces across API, workflow and worker; metrics for queue depth, failure/reties, cost, object uploads, quality and active nodes. Alerts: stuck queue, runaway spend, unauthorized attempts, run/worker failure, webhook dead letters, failed backups.

## Recovery
Document retention/RPO/RTO as measured targets, not guesses. Nightly encrypted backups plus PITR; restore drills. Object versioning and immutable manifest hashes; cross-check DB pointers and object checksums. Per-worker leases/timeouts for crash recovery; support safe retry with idempotent artifact writes. Manual incident role handoff and customer notice templates.
