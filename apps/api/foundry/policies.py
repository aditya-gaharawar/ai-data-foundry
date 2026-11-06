"""Central dataset visibility and bounded native PII rules shared by all interfaces."""

import re
from typing import Literal

from pydantic import Field
from sqlalchemy import select

from .errors import Problem
from .models import (
    AnnotationReview,
    AnnotationTask,
    Benchmark,
    ComputeJob,
    Curation,
    Dataset,
    Evaluation,
    Export,
    Feedback,
    GovernancePolicy,
    Run,
    SearchEntry,
    Upload,
    Version,
    WorkflowSchedule,
)
from .schemas import Strict
from .security import canonical, digest


class PolicyDefinition(Strict):
    pii_mode: Literal["allow", "block", "redact"] = "allow"
    allowed_licenses: list[str] = Field(default_factory=list, max_length=100)
    require_human_review: bool = False
    erasure_delay_seconds: int = Field(default=86400, ge=0, le=365 * 86400)
    retention_days: int = Field(default=30, ge=1, le=3650)


def current_policy(db, organization_id):
    record = db.scalar(
        select(GovernancePolicy)
        .where(GovernancePolicy.organization_id == organization_id)
        .order_by(GovernancePolicy.number.desc())
    )
    definition = PolicyDefinition.model_validate(record.definition if record else {}).model_dump()
    return {
        "id": record.id if record else None,
        "number": record.number if record else 0,
        "definition": definition,
        "sha256": digest(canonical(definition)),
    }


def dataset_of(db, record):
    if isinstance(record, Dataset):
        return record
    identifier = getattr(record, "dataset_id", None)
    if identifier:
        query = (
            select(Dataset)
            .where(Dataset.id == identifier, Dataset.organization_id == record.organization_id)
            .execution_options(populate_existing=True)
        )
        return db.scalar(query.with_for_update() if db.info.get("mutation") else query)
    if isinstance(record, (Export, Evaluation, Benchmark, ComputeJob)):
        parent = db.scalar(
            select(Version).where(
                Version.id == record.version_id, Version.organization_id == record.organization_id
            )
        )
    elif isinstance(record, AnnotationTask):
        parent = db.scalar(
            select(Curation).where(
                Curation.id == record.curation_id, Curation.organization_id == record.organization_id
            )
        )
    elif isinstance(record, AnnotationReview):
        parent = db.scalar(
            select(AnnotationTask).where(
                AnnotationTask.id == record.task_id, AnnotationTask.organization_id == record.organization_id
            )
        )
    elif isinstance(record, Feedback):
        parent = db.scalar(
            select(Evaluation).where(
                Evaluation.id == record.evaluation_id, Evaluation.organization_id == record.organization_id
            )
        )
    else:
        return None
    return dataset_of(db, parent) if parent else None


def enforce_resource(db, record, *, include_erased=False):
    p = db.info.get("principal")
    if not p:
        return
    dataset = dataset_of(db, record)
    if dataset:
        if dataset.erased_at and not include_erased:
            raise Problem(
                410,
                "DATASET_ERASED",
                "This dataset's artifacts have been erased under its retention decision.",
            )
        if dataset.protection == "holdout" and "holdouts:read" not in p.scopes:
            raise Problem(403, "HOLDOUT_PROTECTED", "Holdout solutions require explicit evaluation access.")


def visible_condition(cls, p):
    accessible = select(Dataset.id).where(
        Dataset.organization_id == p.organization_id, Dataset.erased_at.is_(None)
    )
    if "holdouts:read" not in p.scopes:
        accessible = accessible.where(Dataset.protection != "holdout")
    if cls is Dataset:
        return Dataset.id.in_(accessible)
    if cls in (Run, Upload, Version, Curation, SearchEntry, WorkflowSchedule):
        return cls.dataset_id.in_(accessible)
    versions = select(Version.id).where(
        Version.organization_id == p.organization_id, Version.dataset_id.in_(accessible)
    )
    if cls in (Export, Benchmark, Evaluation, ComputeJob):
        return cls.version_id.in_(versions)
    if cls is AnnotationTask:
        return cls.curation_id.in_(
            select(Curation.id).where(
                Curation.organization_id == p.organization_id, Curation.dataset_id.in_(accessible)
            )
        )
    return True


PATTERNS = {
    "email": re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?!\w)"),
    "us_ssn": re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
    "phone": re.compile(r"(?<!\w)(?:\+?\d{1,3}[- .]?)?(?:\(\d{3}\)|\d{3})[- .]\d{3}[- .]\d{4}(?!\w)"),
}


def pii_transform(samples, mode):
    counts = {key: 0 for key in PATTERNS}

    def visit(value):
        if isinstance(value, str):
            for kind, pattern in PATTERNS.items():
                matches = list(pattern.finditer(value))
                counts[kind] += len(matches)
                if mode == "redact":
                    value = pattern.sub(f"[REDACTED_{kind.upper()}]", value)
            return value
        if isinstance(value, dict):
            return {key: visit(item) for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value

    result = [visit(sample) for sample in samples]
    report = {
        "mode": mode,
        "detected": sum(counts.values()),
        "counts": counts,
        "redacted": mode == "redact",
        "limitations": "Native email/US-SSN/formatted-phone patterns only; not a complete PII or safety classifier.",
    }
    if mode == "block" and report["detected"]:
        raise Problem(
            403,
            "PII_POLICY_BLOCKED",
            "Native PII patterns matched this source. No data was published; review the source or use an approved redaction policy.",
        )
    return result, report


def check_publication_policy(db, target, source_kind):
    if target.erased_at:
        raise Problem(410, "DATASET_ERASED", "Erased datasets cannot be processed.")
    if target.protection == "holdout":
        raise Problem(
            403,
            "HOLDOUT_PROTECTED",
            "Training data workers cannot consume or target protected held-out solutions. Register a separate independent source before protecting it.",
        )
    policy = current_policy(db, target.organization_id)
    definition = policy["definition"]
    if definition["allowed_licenses"] and target.policy.get("license") not in definition["allowed_licenses"]:
        raise Problem(
            403,
            "LICENSE_POLICY_BLOCKED",
            "The declared source license is outside the organization allowlist.",
        )
    if definition["require_human_review"] and source_kind != "curate" and target.protection != "holdout":
        raise Problem(
            403,
            "REVIEW_POLICY_BLOCKED",
            "This organization requires an approved human-review snapshot before publication.",
        )
    return policy
