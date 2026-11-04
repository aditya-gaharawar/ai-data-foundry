from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
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
