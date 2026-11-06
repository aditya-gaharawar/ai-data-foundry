"""Generated from packages/contracts/openapi.json. Do not edit."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Accelerator(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    model: str = Field(..., alias="model")
    count: int | None = Field(None, alias="count")
    memory_gib: float | None = Field(None, alias="memory_gib")
    rt_cores: bool | None = Field(None, alias="rt_cores")


class AgentCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    pool_id: str = Field(..., alias="pool_id")
    name: str = Field(..., alias="name")


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


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    decision: Literal["approve", "reject"] = Field(..., alias="decision")
    note: str = Field(..., alias="note")


class BenchmarkCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str = Field(..., alias="name")
    version_id: str = Field(..., alias="version_id")
    external_ref: str = Field(..., alias="external_ref")
    source_kind: str = Field(..., alias="source_kind")
    independent_of_training: bool = Field(..., alias="independent_of_training")


class BudgetPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    maximum_usd: float | str = Field(..., alias="maximum_usd")


class Capabilities(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    cpu_cores: int | None = Field(None, alias="cpu_cores")
    memory_gib: float | None = Field(None, alias="memory_gib")
    accelerators: list[Accelerator] | None = Field(None, alias="accelerators")
    engines: dict[str, Any] | None = Field(None, alias="engines")


class CardUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    expected_revision: int = Field(..., alias="expected_revision")
    data_card: DataCard = Field(..., alias="data_card")


class ComputeJobCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    pool_id: str = Field(..., alias="pool_id")
    version_id: str = Field(..., alias="version_id")
    kind: str | None = Field(None, alias="kind")
    cpu_cores: int | None = Field(None, alias="cpu_cores")
    memory_gib: float | None = Field(None, alias="memory_gib")
    lease_seconds: int | None = Field(None, alias="lease_seconds")


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


class DatasetGovernance(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    expected_revision: int = Field(..., alias="expected_revision")
    action: Literal["protect_holdout", "place_legal_hold", "request_hold_release"] = Field(
        ..., alias="action"
    )
    note: str = Field(..., alias="note")


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
    protection: str | None = Field(None, alias="protection")
    legal_hold: bool | None = Field(None, alias="legal_hold")
    erased_at: str | None = Field(None, alias="erased_at")
    governance_revision: int | None = Field(None, alias="governance_revision")


class DatasetPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str | None = Field(None, alias="name")
    description: str | None = Field(None, alias="description")
    archived: bool | None = Field(None, alias="archived")


class ErasureCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    dataset_id: str = Field(..., alias="dataset_id")
    trigger: Literal["user_request", "retention_expiry"] | None = Field(None, alias="trigger")
    reason: str = Field(..., alias="reason")


class ErasureExecute(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    confirm_dataset_name: str = Field(..., alias="confirm_dataset_name")
    plan_sha256: str = Field(..., alias="plan_sha256")


class EvaluationCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    version_id: str = Field(..., alias="version_id")
    benchmark_id: str = Field(..., alias="benchmark_id")
    model_ref: str = Field(..., alias="model_ref")
    external_run_ref: str = Field(..., alias="external_run_ref")
    result: SliceResult = Field(..., alias="result")
    slices: list[SliceResult] | None = Field(None, alias="slices")
    evidence_note: str = Field(..., alias="evidence_note")


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


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    evaluation_id: str = Field(..., alias="evaluation_id")
    maximum_new_samples: int | None = Field(None, alias="maximum_new_samples")
    maximum_internal_budget_usd: float | None = Field(None, alias="maximum_internal_budget_usd")
    require_manual_approval: bool | None = Field(None, alias="require_manual_approval")


class FeedbackDecision(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    decision: str = Field(..., alias="decision")
    note: str = Field(..., alias="note")


class FreezeCuration(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    expected_revision: int = Field(..., alias="expected_revision")
    approved_for_publication: bool = Field(..., alias="approved_for_publication")


class GovernancePolicyCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    definition: PolicyDefinition = Field(..., alias="definition")


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


class LeaseComplete(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    attempt: int = Field(..., alias="attempt")
    sha256: str = Field(..., alias="sha256")
    bytes: int = Field(..., alias="bytes")
    processing_ms: int = Field(..., alias="processing_ms")


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


class NotificationOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    created_at: str = Field(..., alias="created_at")
    kind: str = Field(..., alias="kind")
    title: str = Field(..., alias="title")
    body: str = Field(..., alias="body")
    read_at: str | None = Field(..., alias="read_at")
    target: str | None = Field(..., alias="target")


class NotificationSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    unread_count: int = Field(..., alias="unread_count")
    as_of: str = Field(..., alias="as_of")


class OccurrenceOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    created_at: str = Field(..., alias="created_at")
    schedule_id: str = Field(..., alias="schedule_id")
    scheduled_at: str = Field(..., alias="scheduled_at")
    status: str = Field(..., alias="status")
    run_id: str | None = Field(..., alias="run_id")
    code: str = Field(..., alias="code")
    message: str = Field(..., alias="message")
    estimate_micro: int = Field(..., alias="estimate_micro")


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


class Page_NotificationOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[NotificationOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_OccurrenceOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[OccurrenceOut] = Field(..., alias="items")
    next_cursor: str | None = Field(None, alias="next_cursor")


class Page_ProviderOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[ProviderOut] = Field(..., alias="items")
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


class Page_ScheduleOut_(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    items: list[ScheduleOut] = Field(..., alias="items")
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


class PatchOperation(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    op: str = Field(..., alias="op")
    path: str = Field(..., alias="path")
    value: Any | None = Field(None, alias="value")


class Placement(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    pool_id: str = Field(..., alias="pool_id")
    engine: Literal["artifact.verify@1", "blender.procedural@1", "isaac.sim", "isaac.lab"] = Field(
        ..., alias="engine"
    )
    cpu_cores: int | None = Field(None, alias="cpu_cores")
    memory_gib: float | None = Field(None, alias="memory_gib")


class PolicyDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    pii_mode: Literal["allow", "block", "redact"] | None = Field(None, alias="pii_mode")
    allowed_licenses: list[str] | None = Field(None, alias="allowed_licenses")
    require_human_review: bool | None = Field(None, alias="require_human_review")
    erasure_delay_seconds: int | None = Field(None, alias="erasure_delay_seconds")
    retention_days: int | None = Field(None, alias="retention_days")


class PoolCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str = Field(..., alias="name")
    scheduler: Literal["agent", "kubernetes", "slurm"] | None = Field(None, alias="scheduler")
    capabilities: Capabilities | None = Field(None, alias="capabilities")


class ProfileConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    dedupe: Literal["none", "exact", "near"] | None = Field(None, alias="dedupe")
    text_similarity: float | None = Field(None, alias="text_similarity")
    image_hamming_distance: int | None = Field(None, alias="image_hamming_distance")
    minimum_samples: int | None = Field(None, alias="minimum_samples")
    minimum_acceptance_ratio: float | None = Field(None, alias="minimum_acceptance_ratio")
    max_duplicate_ratio: float | None = Field(None, alias="max_duplicate_ratio")
    max_near_duplicate_ratio: float | None = Field(None, alias="max_near_duplicate_ratio")


class ProofImport(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    kind: Literal["restore", "load", "security", "regression", "rollback"] = Field(..., alias="kind")
    source_sha256: str = Field(..., alias="source_sha256")
    report: dict[str, Any] = Field(..., alias="report")
    operator_signature: str = Field(..., alias="operator_signature")


class ProviderCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str = Field(..., alias="name")
    kind: Literal["local.gguf", "http.structured", "http.image"] = Field(..., alias="kind")
    model_ref: str = Field(..., alias="model_ref")
    endpoint: str | None = Field(None, alias="endpoint")
    api_secret: str | None = Field(None, alias="api_secret")
    permitted_training_use: bool = Field(..., alias="permitted_training_use")
    consent_to_processing: bool = Field(..., alias="consent_to_processing")
    terms_version: str = Field(..., alias="terms_version")
    rights_evidence: str = Field(..., alias="rights_evidence")


class ProviderOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    name: str = Field(..., alias="name")
    kind: str = Field(..., alias="kind")
    model_ref: str = Field(..., alias="model_ref")
    config: dict[str, Any] = Field(..., alias="config")
    rights: dict[str, Any] = Field(..., alias="rights")
    approved_by: str = Field(..., alias="approved_by")
    revoked: bool = Field(..., alias="revoked")
    state: str = Field(..., alias="state")
    reason: str = Field(..., alias="reason")
    capabilities: list[str] = Field(..., alias="capabilities")


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


class ReadAll(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    before: str = Field(..., alias="before")


class ReadAllOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    marked_read: int = Field(..., alias="marked_read")
    before: str = Field(..., alias="before")


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


class ResourceOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    name: str | None = Field(None, alias="name")
    state: str | None = Field(None, alias="state")
    status: str | None = Field(None, alias="status")
    capabilities: dict[str, Any] | None = Field(None, alias="capabilities")
    reason: str | None = Field(None, alias="reason")
    agent_token: str | None = Field(None, alias="agent_token")
    result: dict[str, Any] | None = Field(None, alias="result")


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
    submitted_by: str | None = Field(None, alias="submitted_by")
    schedule_id: str | None = Field(None, alias="schedule_id")
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


class ScheduleControl(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    action: Literal["pause", "resume", "cancel"] = Field(..., alias="action")
    expected_revision: int = Field(..., alias="expected_revision")
    approved_for_scheduled_execution: bool | None = Field(None, alias="approved_for_scheduled_execution")


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str = Field(..., alias="name")
    dataset_id: str = Field(..., alias="dataset_id")
    recipe_revision_id: str = Field(..., alias="recipe_revision_id")
    definition: ScheduleDefinition = Field(..., alias="definition")
    max_runs: int = Field(..., alias="max_runs")
    run_budget_usd: float | str = Field(..., alias="run_budget_usd")
    total_budget_usd: float | str = Field(..., alias="total_budget_usd")
    approved_for_scheduled_execution: bool = Field(..., alias="approved_for_scheduled_execution")


class ScheduleDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    mode: Literal["interval", "daily"] | None = Field(None, alias="mode")
    starts_at: str = Field(..., alias="starts_at")
    ends_at: str = Field(..., alias="ends_at")
    timezone: str | None = Field(None, alias="timezone")
    interval_seconds: int | None = Field(None, alias="interval_seconds")
    daily_time: str | None = Field(None, alias="daily_time")


class ScheduleOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(..., alias="id")
    organization_id: str = Field(..., alias="organization_id")
    created_at: str = Field(..., alias="created_at")
    name: str = Field(..., alias="name")
    dataset_id: str = Field(..., alias="dataset_id")
    recipe_revision_id: str = Field(..., alias="recipe_revision_id")
    created_by: str = Field(..., alias="created_by")
    authorized_by: str = Field(..., alias="authorized_by")
    authorized_key_id: str | None = Field(..., alias="authorized_key_id")
    definition: ScheduleDefinition = Field(..., alias="definition")
    state: Literal["ACTIVE", "PAUSED", "BLOCKED", "COMPLETED", "EXPIRED", "CANCELLED"] = Field(
        ..., alias="state"
    )
    next_run_at: str | None = Field(..., alias="next_run_at")
    last_run_at: str | None = Field(..., alias="last_run_at")
    max_runs: int = Field(..., alias="max_runs")
    launched_runs: int = Field(..., alias="launched_runs")
    skipped_runs: int = Field(..., alias="skipped_runs")
    run_budget_micro: int = Field(..., alias="run_budget_micro")
    total_budget_micro: int = Field(..., alias="total_budget_micro")
    admitted_micro: int = Field(..., alias="admitted_micro")
    revision: int = Field(..., alias="revision")
    last_error_code: str | None = Field(..., alias="last_error_code")
    last_error: str | None = Field(..., alias="last_error")


class SchedulePreview(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str = Field(..., alias="name")
    dataset_id: str = Field(..., alias="dataset_id")
    recipe_revision_id: str = Field(..., alias="recipe_revision_id")
    definition: ScheduleDefinition = Field(..., alias="definition")
    max_runs: int = Field(..., alias="max_runs")
    run_budget_usd: float | str = Field(..., alias="run_budget_usd")
    total_budget_usd: float | str = Field(..., alias="total_budget_usd")


class SchedulePreviewOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    sample_count: int = Field(..., alias="sample_count")
    estimate_micro: int = Field(..., alias="estimate_micro")
    admitted_limit_micro: int = Field(..., alias="admitted_limit_micro")
    affordable_runs: int = Field(..., alias="affordable_runs")
    next_occurrences: list[str] = Field(..., alias="next_occurrences")
    semantics: str = Field(..., alias="semantics")


class SchedulerHealth(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    status: Literal["READY", "UNAVAILABLE"] = Field(..., alias="status")
    last_heartbeat: str | None = Field(..., alias="last_heartbeat")
    late_grace_seconds: int = Field(..., alias="late_grace_seconds")
    minimum_interval_seconds: int = Field(..., alias="minimum_interval_seconds")


class ScimName(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    givenName: str | None = Field(None, alias="givenName")
    familyName: str | None = Field(None, alias="familyName")
    formatted: str | None = Field(None, alias="formatted")


class ScimPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    schemas: list[str] | None = Field(None, alias="schemas")
    Operations: list[PatchOperation] = Field(..., alias="Operations")


class ScimRole(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    value: Literal["Engineer", "Labeler", "Viewer"] | None = Field(None, alias="value")


class ScimTokenCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str = Field(..., alias="name")
    allowed_domain: str | None = Field(None, alias="allowed_domain")


class ScimUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    schemas: list[str] | None = Field(None, alias="schemas")
    externalId: str | None = Field(None, alias="externalId")
    userName: str = Field(..., alias="userName")
    displayName: str | None = Field(None, alias="displayName")
    name: ScimName | None = Field(None, alias="name")
    active: bool | None = Field(None, alias="active")
    roles: list[ScimRole] | None = Field(None, alias="roles")


class SliceResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str = Field(..., alias="name")
    correct: int = Field(..., alias="correct")
    total: int = Field(..., alias="total")


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
            "run.cancelled",
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


Accelerator.model_rebuild()
AgentCreate.model_rebuild()
AnnotationTaskOut.model_rebuild()
ApprovalDecision.model_rebuild()
BenchmarkCreate.model_rebuild()
BudgetPatch.model_rebuild()
Capabilities.model_rebuild()
CardUpdate.model_rebuild()
ComputeJobCreate.model_rebuild()
CurationCreate.model_rebuild()
CurationOut.model_rebuild()
DataCard.model_rebuild()
DatasetCreate.model_rebuild()
DatasetGovernance.model_rebuild()
DatasetOut.model_rebuild()
DatasetPatch.model_rebuild()
ErasureCreate.model_rebuild()
ErasureExecute.model_rebuild()
EvaluationCreate.model_rebuild()
ExportCreate.model_rebuild()
ExportOut.model_rebuild()
FeedbackCreate.model_rebuild()
FeedbackDecision.model_rebuild()
FreezeCuration.model_rebuild()
GovernancePolicyCreate.model_rebuild()
KeyCreate.model_rebuild()
KeyOut.model_rebuild()
LeaseComplete.model_rebuild()
Login.model_rebuild()
MemberCreate.model_rebuild()
MemberPatch.model_rebuild()
NameCreate.model_rebuild()
NotificationOut.model_rebuild()
NotificationSummary.model_rebuild()
OccurrenceOut.model_rebuild()
Page_AnnotationTaskOut_.model_rebuild()
Page_CurationOut_.model_rebuild()
Page_DatasetOut_.model_rebuild()
Page_KeyOut_.model_rebuild()
Page_NotificationOut_.model_rebuild()
Page_OccurrenceOut_.model_rebuild()
Page_ProviderOut_.model_rebuild()
Page_QualityProfileOut_.model_rebuild()
Page_RecipeOut_.model_rebuild()
Page_RunOut_.model_rebuild()
Page_ScheduleOut_.model_rebuild()
Page_UploadOut_.model_rebuild()
Page_VersionOut_.model_rebuild()
Page_WebhookOut_.model_rebuild()
PatchOperation.model_rebuild()
Placement.model_rebuild()
PolicyDefinition.model_rebuild()
PoolCreate.model_rebuild()
ProfileConfig.model_rebuild()
ProofImport.model_rebuild()
ProviderCreate.model_rebuild()
ProviderOut.model_rebuild()
QualityProfileCreate.model_rebuild()
QualityProfileOut.model_rebuild()
ReadAll.model_rebuild()
ReadAllOut.model_rebuild()
RecipeCreate.model_rebuild()
RecipeOut.model_rebuild()
ResourceOut.model_rebuild()
ReviewDecision.model_rebuild()
RevisionOut.model_rebuild()
RunCreate.model_rebuild()
RunOut.model_rebuild()
ScheduleControl.model_rebuild()
ScheduleCreate.model_rebuild()
ScheduleDefinition.model_rebuild()
ScheduleOut.model_rebuild()
SchedulePreview.model_rebuild()
SchedulePreviewOut.model_rebuild()
SchedulerHealth.model_rebuild()
ScimName.model_rebuild()
ScimPatch.model_rebuild()
ScimRole.model_rebuild()
ScimTokenCreate.model_rebuild()
ScimUser.model_rebuild()
SliceResult.model_rebuild()
TaskAssignment.model_rebuild()
TaskReopen.model_rebuild()
UploadComplete.model_rebuild()
UploadCreate.model_rebuild()
UploadOut.model_rebuild()
UploadPart.model_rebuild()
VersionOut.model_rebuild()
WebhookCreate.model_rebuild()
WebhookOut.model_rebuild()
