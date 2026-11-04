from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


class DatasetOut(BaseModel):
    id: str
    organization_id: str
    project_id: str
    name: str
    description: str
    modality: Literal["text"]
    schema_definition: dict = Field(alias="schema")
    policy: dict
    archived: bool
    created_at: datetime
    versions_count: int | None = None


class VersionOut(BaseModel):
    id: str
    organization_id: str
    dataset_id: str
    run_id: str
    number: int
    sample_count: int
    manifest_hash: str
    manifest: dict
    created_at: datetime


class RunOut(BaseModel):
    id: str
    organization_id: str
    dataset_id: str
    recipe_revision_id: str
    status: Literal["QUEUED", "RUNNING", "VERIFYING", "PUBLISHING", "SUCCEEDED", "FAILED", "CANCELLED"]
    sample_count: int
    processed: int
    spent_usd: float
    reserved_usd: float
    max_budget_usd: float
    status_url: str
    cancel_requested: bool
    error: str | None = None
    quality: dict | None = None
    version: VersionOut | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class RevisionOut(BaseModel):
    id: str
    organization_id: str
    recipe_id: str
    digest: str
    definition: dict
    created_at: datetime


class RecipeOut(BaseModel):
    id: str
    organization_id: str
    project_id: str
    name: str
    created_at: datetime
    revision: RevisionOut | None = None
    revisions: list[RevisionOut] = Field(default_factory=list)


class UploadOut(BaseModel):
    id: str
    organization_id: str
    dataset_id: str
    filename: str
    content_type: str
    expected_bytes: int
    expected_sha256: str
    status: str
    sample_count: int
    error: str | None = None
    created_at: datetime
    part_size: int | None = None
    expires_in: int | None = None
    upload_urls: list[str] | None = None


class ExportOut(BaseModel):
    id: str
    organization_id: str
    version_id: str
    format: Literal["jsonl"]
    status: Literal["READY"]
    created_at: datetime
    download_url: str | None = None
    expires_in: int | None = None


class KeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    organization_id: str
    user_id: str
    scopes: list[str]
    revoked: bool
    created_at: datetime
    secret: str | None = None


class WebhookOut(BaseModel):
    id: str
    organization_id: str
    url: str
    events: list[str]
    active: bool
    created_at: datetime
    signing_secret: str | None = None


class ProblemOut(BaseModel):
    type: str
    title: str
    status: int
    code: str
    detail: str
    request_id: str
