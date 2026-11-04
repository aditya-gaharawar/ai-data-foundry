"""Generated from packages/contracts/openapi.json. Do not edit."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BudgetPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    maximum_usd: float | str = Field(..., alias="maximum_usd")


class DatasetCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    project_id: str = Field(..., alias="project_id")
    name: str = Field(..., alias="name")
    description: str | None = Field(None, alias="description")
    modality: str | None = Field(None, alias="modality")
    schema_: dict[str, Any] | None = Field(None, alias="schema")
    policy: dict[str, Any] | None = Field(None, alias="policy")


class DatasetOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    project_id: str = Field(..., alias="project_id")
    name: str = Field(..., alias="name")
    description: str = Field(..., alias="description")
    modality: str = Field(..., alias="modality")
    schema_: dict[str, Any] = Field(..., alias="schema")
    policy: dict[str, Any] = Field(..., alias="policy")
    archived: bool = Field(..., alias="archived")
    created_at: str = Field(..., alias="created_at")
    versions_count: int | None = Field(None, alias="versions_count")


class DatasetPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str | None = Field(None, alias="name")
    description: str | None = Field(None, alias="description")
    archived: bool | None = Field(None, alias="archived")


class ExportCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    version_id: str = Field(..., alias="version_id")
    format: str | None = Field(None, alias="format")


class ExportOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    version_id: str = Field(..., alias="version_id")
    format: str = Field(..., alias="format")
    status: str = Field(..., alias="status")
    created_at: str = Field(..., alias="created_at")
    download_url: str | None = Field(None, alias="download_url")
    expires_in: int | None = Field(None, alias="expires_in")


class KeyCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str = Field(..., alias="name")
    scopes: list[str] = Field(..., alias="scopes")


class KeyOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    name: str = Field(..., alias="name")
    prefix: str = Field(..., alias="prefix")
    organization_id: str = Field(..., alias="organization_id")
    user_id: str = Field(..., alias="user_id")
    scopes: list[str] = Field(..., alias="scopes")
    revoked: bool = Field(..., alias="revoked")
    created_at: str = Field(..., alias="created_at")
    secret: str | None = Field(None, alias="secret")


class Login(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    email: str = Field(..., alias="email")
    password: str = Field(..., alias="password")


class MemberCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    email: str = Field(..., alias="email")
    name: str = Field(..., alias="name")
    password: str = Field(..., alias="password")
    role: Literal["Admin", "Engineer", "Viewer"] | None = Field(None, alias="role")


class MemberPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    role: Literal["Admin", "Engineer", "Viewer"] = Field(..., alias="role")


class NameCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str = Field(..., alias="name")


class Page_DatasetOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[DatasetOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_KeyOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[KeyOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_RecipeOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[RecipeOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_RunOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[RunOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_UploadOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[UploadOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_VersionOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[VersionOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_WebhookOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[WebhookOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class RecipeCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    project_id: str = Field(..., alias="project_id")
    definition: dict[str, Any] = Field(..., alias="definition")


class RecipeOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    project_id: str = Field(..., alias="project_id")
    name: str = Field(..., alias="name")
    created_at: str = Field(..., alias="created_at")
    revision: RevisionOut | None = Field(None, alias="revision")
    revisions: list[RevisionOut] | None = Field(None, alias="revisions")


class RevisionOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    recipe_id: str = Field(..., alias="recipe_id")
    digest: str = Field(..., alias="digest")
    definition: dict[str, Any] = Field(..., alias="definition")
    created_at: str = Field(..., alias="created_at")


class RunCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    dataset_id: str = Field(..., alias="dataset_id")
    recipe_revision_id: str = Field(..., alias="recipe_revision_id")
    max_budget_usd: float | str = Field(..., alias="max_budget_usd")
    compute_constraints: dict[str, Any] | None = Field(None, alias="compute_constraints")


class RunOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    dataset_id: str = Field(..., alias="dataset_id")
    recipe_revision_id: str = Field(..., alias="recipe_revision_id")
    status: Literal["QUEUED", "RUNNING", "VERIFYING", "PUBLISHING", "SUCCEEDED", "FAILED", "CANCELLED"] = (
        Field(..., alias="status")
    )
    sample_count: int = Field(..., alias="sample_count")
    processed: int = Field(..., alias="processed")
    spent_usd: float = Field(..., alias="spent_usd")
    reserved_usd: float = Field(..., alias="reserved_usd")
    max_budget_usd: float = Field(..., alias="max_budget_usd")
    status_url: str = Field(..., alias="status_url")
    cancel_requested: bool = Field(..., alias="cancel_requested")
    error: str | None = Field(None, alias="error")
    quality: dict[str, Any] | None = Field(None, alias="quality")
    version: VersionOut | None = Field(None, alias="version")
    created_at: str = Field(..., alias="created_at")
    started_at: str | None = Field(None, alias="started_at")
    finished_at: str | None = Field(None, alias="finished_at")


class UploadComplete(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    parts: list[UploadPart] = Field(..., alias="parts")


class UploadCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    dataset_id: str = Field(..., alias="dataset_id")
    filename: str = Field(..., alias="filename")
    content_type: Literal["application/x-ndjson", "application/jsonl", "text/plain"] = Field(
        ..., alias="content_type"
    )
    bytes: int = Field(..., alias="bytes")
    sha256: str = Field(..., alias="sha256")


class UploadOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    dataset_id: str = Field(..., alias="dataset_id")
    filename: str = Field(..., alias="filename")
    content_type: str = Field(..., alias="content_type")
    expected_bytes: int = Field(..., alias="expected_bytes")
    expected_sha256: str = Field(..., alias="expected_sha256")
    status: str = Field(..., alias="status")
    sample_count: int = Field(..., alias="sample_count")
    error: str | None = Field(None, alias="error")
    created_at: str = Field(..., alias="created_at")
    part_size: int | None = Field(None, alias="part_size")
    expires_in: int | None = Field(None, alias="expires_in")
    upload_urls: list[str] | None = Field(None, alias="upload_urls")


class UploadPart(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    part_number: int = Field(..., alias="part_number")
    etag: str = Field(..., alias="etag")


class VersionOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    dataset_id: str = Field(..., alias="dataset_id")
    run_id: str = Field(..., alias="run_id")
    number: int = Field(..., alias="number")
    sample_count: int = Field(..., alias="sample_count")
    manifest_hash: str = Field(..., alias="manifest_hash")
    manifest: dict[str, Any] = Field(..., alias="manifest")
    created_at: str = Field(..., alias="created_at")


class WebhookCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    url: str = Field(..., alias="url")
    events: list[
        Literal[
            "run.queued",
            "run.started",
            "run.progress",
            "run.failed",
            "run.succeeded",
            "dataset.version.published",
            "export.ready",
            "budget.exhausted",
        ]
    ] = Field(..., alias="events")


class WebhookOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    url: str = Field(..., alias="url")
    events: list[str] = Field(..., alias="events")
    active: bool = Field(..., alias="active")
    created_at: str = Field(..., alias="created_at")
    signing_secret: str | None = Field(None, alias="signing_secret")


BudgetPatch.model_rebuild()
DatasetCreate.model_rebuild()
DatasetOut.model_rebuild()
DatasetPatch.model_rebuild()
ExportCreate.model_rebuild()
ExportOut.model_rebuild()
KeyCreate.model_rebuild()
KeyOut.model_rebuild()
Login.model_rebuild()
MemberCreate.model_rebuild()
MemberPatch.model_rebuild()
NameCreate.model_rebuild()
Page_DatasetOut_.model_rebuild()
Page_KeyOut_.model_rebuild()
Page_RecipeOut_.model_rebuild()
Page_RunOut_.model_rebuild()
Page_UploadOut_.model_rebuild()
Page_VersionOut_.model_rebuild()
Page_WebhookOut_.model_rebuild()
RecipeCreate.model_rebuild()
RecipeOut.model_rebuild()
RevisionOut.model_rebuild()
RunCreate.model_rebuild()
RunOut.model_rebuild()
UploadComplete.model_rebuild()
UploadCreate.model_rebuild()
UploadOut.model_rebuild()
UploadPart.model_rebuild()
VersionOut.model_rebuild()
WebhookCreate.model_rebuild()
WebhookOut.model_rebuild()
