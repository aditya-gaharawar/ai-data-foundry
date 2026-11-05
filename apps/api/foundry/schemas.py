from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .bootstrap import IMAGE_SCHEMA, TEXT_SCHEMA


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Strict):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class DatasetCreate(Strict):
    project_id: str
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    modality: Literal["text", "image"] = "text"
    schema_definition: dict = Field(default_factory=lambda: TEXT_SCHEMA.copy(), alias="schema")
    policy: dict = Field(default_factory=lambda: {"allowed_training_use": False})

    @model_validator(mode="after")
    def modality_schema(self):
        if self.modality == "image" and "schema_definition" not in self.model_fields_set:
            self.schema_definition = IMAGE_SCHEMA.copy()
        return self


class DatasetPatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    archived: bool | None = None


class UploadCreate(Strict):
    dataset_id: str
    filename: str = Field(min_length=1, max_length=240)
    content_type: Literal[
        "application/x-ndjson", "application/jsonl", "text/plain", "image/png", "image/jpeg"
    ]
    bytes: int = Field(ge=1, le=20 * 1024 * 1024)
    sha256: str = Field(pattern="^[a-f0-9]{64}$")


class UploadPart(Strict):
    part_number: int = Field(ge=1, le=10000)
    etag: str = Field(min_length=1, max_length=200)


class UploadComplete(Strict):
    parts: list[UploadPart] = Field(min_length=1, max_length=5)


class RecipeCreate(Strict):
    project_id: str
    definition: dict


class RunCreate(Strict):
    dataset_id: str
    recipe_revision_id: str
    max_budget_usd: Decimal = Field(ge=0, le=1000000, decimal_places=6)
    compute_constraints: dict = Field(default_factory=dict)


class KeyCreate(Strict):
    name: str = Field(min_length=1, max_length=160)
    scopes: list[str] = Field(min_length=1, max_length=32)


class MemberCreate(Strict):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=200)
    role: Literal["Admin", "Engineer", "Labeler", "Viewer"] = "Engineer"


class MemberPatch(Strict):
    role: Literal["Admin", "Engineer", "Labeler", "Viewer"]


class WebhookCreate(Strict):
    url: str = Field(max_length=2048)
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
    ] = Field(min_length=1, max_length=8)


class ExportCreate(Strict):
    version_id: str
    format: Literal["jsonl", "coco", "yolo"] = "jsonl"


class BudgetPatch(Strict):
    maximum_usd: Decimal = Field(ge=0, le=1000000, decimal_places=6)


class NameCreate(Strict):
    name: str = Field(min_length=1, max_length=160)
