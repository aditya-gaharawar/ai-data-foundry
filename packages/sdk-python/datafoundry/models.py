"""Generated from packages/contracts/openapi.json. Do not edit."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnnotationTaskOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    curation_id: str = Field(..., alias="curation_id")
    sample_index: int = Field(..., alias="sample_index")
    source_sample_id: str = Field(..., alias="source_sample_id")
    status: str = Field(..., alias="status")
    revision: int = Field(..., alias="revision")
    round: int = Field(..., alias="round")
    assigned_to: str | None = Field(None, alias="assigned_to")
    annotation: dict[str, Any] | None = Field(None, alias="annotation")
    accepted: bool | None = Field(None, alias="accepted")
    excluded_reason: str | None = Field(None, alias="excluded_reason")
    created_at: str = Field(..., alias="created_at")
    payload: dict[str, Any] | None = Field(None, alias="payload")
    categories: list[str] | None = Field(None, alias="categories")
    required_reviews: int | None = Field(None, alias="required_reviews")
    modality: str | None = Field(None, alias="modality")
    curation_state: str | None = Field(None, alias="curation_state")
    reviews: list[dict[str, Any]] | None = Field(None, alias="reviews")
    media_url: str | None = Field(None, alias="media_url")


class BudgetPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    maximum_usd: float | str = Field(..., alias="maximum_usd")


class CardUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    expected_revision: int = Field(..., alias="expected_revision")
    data_card: DataCard = Field(..., alias="data_card")


class CurationCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    dataset_id: str = Field(..., alias="dataset_id")
    profile_id: str = Field(..., alias="profile_id")
    name: str = Field(..., alias="name")
    categories: list[str] = Field(..., alias="categories")
    required_reviews: Literal[1, 2] | None = Field(None, alias="required_reviews")
    source_version_id: str | None = Field(None, alias="source_version_id")
    upload_ids: list[str] | None = Field(None, alias="upload_ids")
    data_card: DataCard | None = Field(None, alias="data_card")


class CurationOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    dataset_id: str = Field(..., alias="dataset_id")
    profile_id: str = Field(..., alias="profile_id")
    source_version_id: str | None = Field(None, alias="source_version_id")
    name: str = Field(..., alias="name")
    categories: list[str] = Field(..., alias="categories")
    required_reviews: int = Field(..., alias="required_reviews")
    dedupe_report: dict[str, Any] = Field(..., alias="dedupe_report")
    data_card: dict[str, Any] = Field(..., alias="data_card")
    state: str = Field(..., alias="state")
    revision: int = Field(..., alias="revision")
    quality: dict[str, Any] | None = Field(None, alias="quality")
    frozen_by: str | None = Field(None, alias="frozen_by")
    frozen_at: str | None = Field(None, alias="frozen_at")
    created_at: str = Field(..., alias="created_at")


class DataCard(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    purpose: str = Field(..., alias="purpose")
    intended_use: str = Field(..., alias="intended_use")
    limitations: str = Field(..., alias="limitations")
    content_risks: str = Field(..., alias="content_risks")
    restrictions: str = Field(..., alias="restrictions")


class DatasetCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    project_id: str = Field(..., alias="project_id")
    name: str = Field(..., alias="name")
    description: str | None = Field(None, alias="description")
    modality: Literal["text", "image"] | None = Field(None, alias="modality")
    schema_: dict[str, Any] | None = Field(None, alias="schema")
    policy: dict[str, Any] | None = Field(None, alias="policy")


class DatasetOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    project_id: str = Field(..., alias="project_id")
    name: str = Field(..., alias="name")
    description: str = Field(..., alias="description")
    modality: Literal["text", "image"] = Field(..., alias="modality")
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
    format: Literal["jsonl", "coco", "yolo"] | None = Field(None, alias="format")


class ExportOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    version_id: str = Field(..., alias="version_id")
    format: Literal["jsonl", "coco", "yolo"] = Field(..., alias="format")
    status: str = Field(..., alias="status")
    created_at: str = Field(..., alias="created_at")
    download_url: str | None = Field(None, alias="download_url")
    expires_in: int | None = Field(None, alias="expires_in")


class FreezeCuration(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    expected_revision: int = Field(..., alias="expected_revision")
    approved_for_publication: bool = Field(..., alias="approved_for_publication")


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
    role: Literal["Admin", "Engineer", "Labeler", "Viewer"] | None = Field(None, alias="role")


class MemberPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    role: Literal["Admin", "Engineer", "Labeler", "Viewer"] = Field(..., alias="role")


class NameCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str = Field(..., alias="name")


class Page_AnnotationTaskOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[AnnotationTaskOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_CurationOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[CurationOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_DatasetOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[DatasetOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_KeyOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[KeyOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_QualityProfileOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[QualityProfileOut] = Field(..., alias="items")
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


class ProfileConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    dedupe: Literal["none", "exact", "near"] | None = Field(None, alias="dedupe")
    text_similarity: float | None = Field(None, alias="text_similarity")
    image_hamming_distance: int | None = Field(None, alias="image_hamming_distance")
    minimum_samples: int | None = Field(None, alias="minimum_samples")
    minimum_acceptance_ratio: float | None = Field(None, alias="minimum_acceptance_ratio")
    max_duplicate_ratio: float | None = Field(None, alias="max_duplicate_ratio")
    max_near_duplicate_ratio: float | None = Field(None, alias="max_near_duplicate_ratio")


class QualityProfileCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str = Field(..., alias="name")
    modality: Literal["text", "image"] = Field(..., alias="modality")
    config: ProfileConfig | None = Field(None, alias="config")


class QualityProfileOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    name: str = Field(..., alias="name")
    modality: str = Field(..., alias="modality")
    config: dict[str, Any] = Field(..., alias="config")
    created_at: str = Field(..., alias="created_at")


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


class ReviewDecision(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    expected_revision: int = Field(..., alias="expected_revision")
    decision: Literal["accept", "reject"] = Field(..., alias="decision")
    annotation: dict[str, Any] | None = Field(None, alias="annotation")
    note: str = Field(..., alias="note")


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


class TaskAssignment(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    expected_revision: int = Field(..., alias="expected_revision")
    user_id: str | None = Field(None, alias="user_id")


class TaskReopen(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    expected_revision: int = Field(..., alias="expected_revision")
    note: str = Field(..., alias="note")


class UploadComplete(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    parts: list[UploadPart] = Field(..., alias="parts")


class UploadCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    dataset_id: str = Field(..., alias="dataset_id")
    filename: str = Field(..., alias="filename")
    content_type: Literal[
        "application/x-ndjson", "application/jsonl", "text/plain", "image/png", "image/jpeg"
    ] = Field(..., alias="content_type")
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
    media: dict[str, Any] | None = Field(None, alias="media")
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


AnnotationTaskOut.model_rebuild()
BudgetPatch.model_rebuild()
CardUpdate.model_rebuild()
CurationCreate.model_rebuild()
CurationOut.model_rebuild()
DataCard.model_rebuild()
DatasetCreate.model_rebuild()
DatasetOut.model_rebuild()
DatasetPatch.model_rebuild()
ExportCreate.model_rebuild()
ExportOut.model_rebuild()
FreezeCuration.model_rebuild()
KeyCreate.model_rebuild()
KeyOut.model_rebuild()
Login.model_rebuild()
MemberCreate.model_rebuild()
MemberPatch.model_rebuild()
NameCreate.model_rebuild()
Page_AnnotationTaskOut_.model_rebuild()
Page_CurationOut_.model_rebuild()
Page_DatasetOut_.model_rebuild()
Page_KeyOut_.model_rebuild()
Page_QualityProfileOut_.model_rebuild()
Page_RecipeOut_.model_rebuild()
Page_RunOut_.model_rebuild()
Page_UploadOut_.model_rebuild()
Page_VersionOut_.model_rebuild()
Page_WebhookOut_.model_rebuild()
ProfileConfig.model_rebuild()
QualityProfileCreate.model_rebuild()
QualityProfileOut.model_rebuild()
RecipeCreate.model_rebuild()
RecipeOut.model_rebuild()
ReviewDecision.model_rebuild()
RevisionOut.model_rebuild()
RunCreate.model_rebuild()
RunOut.model_rebuild()
TaskAssignment.model_rebuild()
TaskReopen.model_rebuild()
UploadComplete.model_rebuild()
UploadCreate.model_rebuild()
UploadOut.model_rebuild()
UploadPart.model_rebuild()
VersionOut.model_rebuild()
WebhookCreate.model_rebuild()
WebhookOut.model_rebuild()
