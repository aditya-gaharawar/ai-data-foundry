from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, Record


class User(Record, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Organization(Record, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(160))
    budget_micro: Mapped[int] = mapped_column(BigInteger, default=100_000_000)
    reserved_micro: Mapped[int] = mapped_column(BigInteger, default=0)
    spent_micro: Mapped[int] = mapped_column(BigInteger, default=0)


class Membership(Base):
    __tablename__ = "memberships"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(30))


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TenantRecord(Record):
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)


class Project(TenantRecord, Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)
    name: Mapped[str] = mapped_column(String(160))


class ApiKey(TenantRecord, Base):
    __tablename__ = "api_keys"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(160))
    prefix: Mapped[str] = mapped_column(String(24))
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(JSONB)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Dataset(TenantRecord, Base):
    __tablename__ = "datasets"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    modality: Mapped[str] = mapped_column(String(30), default="text")
    sample_schema: Mapped[dict[str, Any]] = mapped_column(JSONB)
    policy: Mapped[dict[str, Any]] = mapped_column(JSONB)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    protection: Mapped[str] = mapped_column(String(30), default="standard", server_default="standard")
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    erased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    governance_revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class Upload(TenantRecord, Base):
    __tablename__ = "uploads"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    filename: Mapped[str] = mapped_column(String(240))
    content_type: Mapped[str] = mapped_column(String(120))
    expected_bytes: Mapped[int] = mapped_column(BigInteger)
    expected_sha256: Mapped[str] = mapped_column(String(64))
    object_key: Mapped[str] = mapped_column(Text)
    multipart_id: Mapped[str] = mapped_column(Text)
    object_version: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="UPLOADING")
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    media: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Recipe(TenantRecord, Base):
    __tablename__ = "recipes"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(160))


class RecipeRevision(TenantRecord, Base):
    __tablename__ = "recipe_revisions"
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"))
    digest: Mapped[str] = mapped_column(String(64))
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Run(TenantRecord, Base):
    __tablename__ = "runs"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    recipe_revision_id: Mapped[str] = mapped_column(ForeignKey("recipe_revisions.id"))
    submitted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    schedule_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_schedules.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    max_budget_micro: Mapped[int] = mapped_column(BigInteger)
    reserved_micro: Mapped[int] = mapped_column(BigInteger)
    spent_micro: Mapped[int] = mapped_column(BigInteger, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    quality: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunEvent(TenantRecord, Base):
    __tablename__ = "run_events"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Version(TenantRecord, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "number"),)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), unique=True)
    number: Mapped[int] = mapped_column(Integer)
    sample_count: Mapped[int] = mapped_column(Integer)
    manifest_hash: Mapped[str] = mapped_column(String(64))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Export(TenantRecord, Base):
    __tablename__ = "exports"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    format: Mapped[str] = mapped_column(String(30), default="jsonl")
    status: Mapped[str] = mapped_column(String(30), default="READY")


class Usage(TenantRecord, Base):
    __tablename__ = "usage_events"
    __table_args__ = (UniqueConstraint("run_id", "metric", "dedupe_key"),)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    metric: Mapped[str] = mapped_column(String(80))
    quantity: Mapped[int] = mapped_column(BigInteger)
    dedupe_key: Mapped[str] = mapped_column(String(160))
    internal_cost_micro: Mapped[int] = mapped_column(BigInteger, default=0)
    external_cost_micro: Mapped[int] = mapped_column(BigInteger, default=0)


class Webhook(TenantRecord, Base):
    __tablename__ = "webhooks"
    url: Mapped[str] = mapped_column(Text)
    events: Mapped[list[str]] = mapped_column(JSONB)
    secret_encrypted: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Outbox(TenantRecord, Base):
    __tablename__ = "outbox"
    kind: Mapped[str] = mapped_column(String(30))
    resource_id: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class Delivery(TenantRecord, Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (UniqueConstraint("webhook_id", "event_id"),)
    webhook_id: Mapped[str] = mapped_column(ForeignKey("webhooks.id"))
    event_id: Mapped[str] = mapped_column(ForeignKey("outbox.id"))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)


class Audit(TenantRecord, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(64))


class Idempotency(Base):
    __tablename__ = "idempotency"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation: Mapped[str] = mapped_column(String(120), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status_code: Mapped[int] = mapped_column(Integer)


class Heartbeat(Base):
    __tablename__ = "heartbeats"
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RateLimit(Base):
    __tablename__ = "rate_limits"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class QualityProfile(TenantRecord, Base):
    __tablename__ = "quality_profiles"
    name: Mapped[str] = mapped_column(String(160))
    modality: Mapped[str] = mapped_column(String(30))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Curation(TenantRecord, Base):
    __tablename__ = "curations"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("quality_profiles.id"))
    source_version_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_versions.id"))
    name: Mapped[str] = mapped_column(String(160))
    categories: Mapped[list[str]] = mapped_column(JSONB)
    required_reviews: Mapped[int] = mapped_column(Integer, default=2)
    source_artifact: Mapped[dict[str, Any]] = mapped_column(JSONB)
    dedupe_report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    data_card: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    state: Mapped[str] = mapped_column(String(30), default="OPEN")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    quality: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    frozen_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnnotationTask(TenantRecord, Base):
    __tablename__ = "annotation_tasks"
    __table_args__ = (UniqueConstraint("curation_id", "sample_index"),)
    curation_id: Mapped[str] = mapped_column(ForeignKey("curations.id"), index=True)
    sample_index: Mapped[int] = mapped_column(Integer)
    source_sample_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="NEW", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    round: Mapped[int] = mapped_column(Integer, default=1)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    annotation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    accepted: Mapped[bool | None] = mapped_column(Boolean)
    excluded_reason: Mapped[str | None] = mapped_column(Text)


class AnnotationReview(TenantRecord, Base):
    __tablename__ = "annotation_reviews"
    __table_args__ = (UniqueConstraint("task_id", "task_revision"),)
    task_id: Mapped[str] = mapped_column(ForeignKey("annotation_tasks.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    api_key_id: Mapped[str | None] = mapped_column(ForeignKey("api_keys.id"))
    round: Mapped[int] = mapped_column(Integer)
    task_revision: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(30))
    annotation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    note: Mapped[str] = mapped_column(Text)


class ProviderConnection(TenantRecord, Base):
    __tablename__ = "provider_connections"
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(40))
    model_ref: Mapped[str] = mapped_column(String(200))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rights: Mapped[dict[str, Any]] = mapped_column(JSONB)
    secret_encrypted: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class ComputePool(TenantRecord, Base):
    __tablename__ = "compute_pools"
    name: Mapped[str] = mapped_column(String(160))
    scheduler: Mapped[str] = mapped_column(String(30))
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ComputeAgent(TenantRecord, Base):
    __tablename__ = "compute_agents"
    pool_id: Mapped[str] = mapped_column(ForeignKey("compute_pools.id"))
    name: Mapped[str] = mapped_column(String(160))
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ComputeJob(TenantRecord, Base):
    __tablename__ = "compute_jobs"
    pool_id: Mapped[str] = mapped_column(ForeignKey("compute_pools.id"))
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    kind: Mapped[str] = mapped_column(String(40))
    requirements: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    lease_agent_id: Mapped[str | None] = mapped_column(ForeignKey("compute_agents.id"))
    lease_secret_hash: Mapped[str | None] = mapped_column(String(64))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Benchmark(TenantRecord, Base):
    __tablename__ = "benchmarks"
    name: Mapped[str] = mapped_column(String(160))
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    external_ref: Mapped[str] = mapped_column(String(400))
    content_sha256: Mapped[str] = mapped_column(String(64))
    source_kind: Mapped[str] = mapped_column(String(40))
    policy: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Evaluation(TenantRecord, Base):
    __tablename__ = "evaluations"
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    benchmark_id: Mapped[str] = mapped_column(ForeignKey("benchmarks.id"))
    model_ref: Mapped[str] = mapped_column(String(200))
    external_run_ref: Mapped[str] = mapped_column(String(400))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    artifact: Mapped[dict[str, Any]] = mapped_column(JSONB)
    imported_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class Feedback(TenantRecord, Base):
    __tablename__ = "training_feedback"
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("evaluations.id"))
    proposal: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    decision_note: Mapped[str | None] = mapped_column(Text)


class SearchEntry(TenantRecord, Base):
    __tablename__ = "search_entries"
    __table_args__ = (
        UniqueConstraint("version_id", "sample_index"),
        Index("ix_search_entries_vector", "search_vector", postgresql_using="gin"),
    )
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    sample_index: Mapped[int] = mapped_column(Integer)
    sample_id: Mapped[str] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64), index=True, default="", server_default="")
    excerpt: Mapped[str] = mapped_column(String(1000))
    search_text: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple'::regconfig, search_text)", persisted=True)
    )


class GovernancePolicy(TenantRecord, Base):
    __tablename__ = "governance_policies"
    __table_args__ = (UniqueConstraint("organization_id", "number"),)
    number: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class ApprovalRequest(TenantRecord, Base):
    __tablename__ = "approval_requests"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    action: Mapped[str] = mapped_column(String(40))
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    note: Mapped[str] = mapped_column(Text)
    decision_note: Mapped[str | None] = mapped_column(Text)


class ErasureRequest(TenantRecord, Base):
    __tablename__ = "erasure_requests"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    ready_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="PENDING_APPROVAL")
    reason: Mapped[str] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class ScimToken(TenantRecord, Base):
    __tablename__ = "scim_tokens"
    name: Mapped[str] = mapped_column(String(160))
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_domain: Mapped[str] = mapped_column(
        String(254), default="foundry.local", server_default="foundry.local"
    )


class ScimIdentity(TenantRecord, Base):
    __tablename__ = "scim_identities"
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id"),
        UniqueConstraint("organization_id", "user_id"),
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    external_id: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Reconciliation(TenantRecord, Base):
    __tablename__ = "reconciliations"
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


class Incident(TenantRecord, Base):
    __tablename__ = "incidents"
    __table_args__ = (UniqueConstraint("organization_id", "source_ref"),)
    source_ref: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(String(400))
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationalProof(TenantRecord, Base):
    __tablename__ = "operational_proofs"
    kind: Mapped[str] = mapped_column(String(40))
    source_sha256: Mapped[str] = mapped_column(String(64))
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    operator_signature: Mapped[str] = mapped_column(String(64))


class WorkflowSchedule(TenantRecord, Base):
    __tablename__ = "workflow_schedules"
    __table_args__ = (
        CheckConstraint(
            "max_runs BETWEEN 1 AND 100 AND launched_runs BETWEEN 0 AND max_runs AND skipped_runs >= 0 AND revision >= 1",
            name="ck_schedule_counts",
        ),
        CheckConstraint(
            "run_budget_micro >= 0 AND total_budget_micro >= 0 AND admitted_micro BETWEEN 0 AND total_budget_micro",
            name="ck_schedule_budgets",
        ),
    )
    name: Mapped[str] = mapped_column(String(160))
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    recipe_revision_id: Mapped[str] = mapped_column(ForeignKey("recipe_revisions.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    authorized_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    authorized_key_id: Mapped[str | None] = mapped_column(ForeignKey("api_keys.id"))
    authorized_scopes: Mapped[list[str]] = mapped_column(JSONB)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(30), default="ACTIVE", index=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_runs: Mapped[int] = mapped_column(Integer)
    launched_runs: Mapped[int] = mapped_column(Integer, default=0)
    skipped_runs: Mapped[int] = mapped_column(Integer, default=0)
    run_budget_micro: Mapped[int] = mapped_column(BigInteger)
    total_budget_micro: Mapped[int] = mapped_column(BigInteger)
    admitted_micro: Mapped[int] = mapped_column(BigInteger, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error: Mapped[str | None] = mapped_column(String(400))


class ScheduleOccurrence(TenantRecord, Base):
    __tablename__ = "schedule_occurrences"
    __table_args__ = (UniqueConstraint("schedule_id", "scheduled_at"),)
    schedule_id: Mapped[str] = mapped_column(ForeignKey("workflow_schedules.id"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40))
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"))
    code: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(String(400))
    estimate_micro: Mapped[int] = mapped_column(BigInteger, default=0)


class Notification(TenantRecord, Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "event_key"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    event_key: Mapped[str] = mapped_column(String(180))
    kind: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(400))
    resource_kind: Mapped[str] = mapped_column(String(30))
    resource_id: Mapped[str] = mapped_column(String(64))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReadinessReport(TenantRecord, Base):
    __tablename__ = "readiness_reports"
    status: Mapped[str] = mapped_column(String(40))
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))


# Enforce the tenant component of every resource reference at the database layer.
for table in list(Base.metadata.tables.values()):
    if "organization_id" in table.c and "id" in table.c:
        table.append_constraint(UniqueConstraint("id", "organization_id", name=f"uq_{table.name}_id_org"))
        for column in list(table.columns):
            for foreign_key in list(column.foreign_keys):
                parent = foreign_key.column.table
                if foreign_key.column.name == "id" and "organization_id" in parent.c:
                    table.append_constraint(
                        ForeignKeyConstraint(
                            [column.name, "organization_id"],
                            [f"{parent.name}.id", f"{parent.name}.organization_id"],
                            name=f"fk_{table.name}_{column.name}_org",
                        )
                    )
