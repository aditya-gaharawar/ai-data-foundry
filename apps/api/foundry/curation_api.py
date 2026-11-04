"""Tenant-scoped human review API, sharing core authorization and idempotency."""

from datetime import datetime

from fastapi import Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from .curation import (
    MAX_CURATION_BYTES,
    MAX_CURATION_SAMPLES,
    RESOLVED,
    CardUpdate,
    CurationCreate,
    FreezeCuration,
    QualityProfileCreate,
    ReviewDecision,
    TaskAssignment,
    TaskReopen,
    duplicate_analysis,
    evaluate_curation,
    latest_votes,
    source_samples,
    task_reviews,
    validate_annotation,
)
from .db import now, uid
from .dto import Page
from .errors import Problem
from .media import upload_samples
from .models import (
    AnnotationReview,
    AnnotationTask,
    Curation,
    Dataset,
    Membership,
    QualityProfile,
    Upload,
    User,
    Version,
)
from .recipes import parse_jsonl
from .security import ROLES, canonical, digest
from .storage import put_immutable, read_artifact


class QualityProfileOut(BaseModel):
    id: str
    organization_id: str
    name: str
    modality: str
    config: dict
    created_at: datetime


class CurationOut(BaseModel):
    id: str
    organization_id: str
    dataset_id: str
    profile_id: str
    source_version_id: str | None = None
    name: str
    categories: list[str]
    required_reviews: int
    dedupe_report: dict
    data_card: dict
    state: str
    revision: int
    quality: dict | None = None
    frozen_by: str | None = None
    frozen_at: datetime | None = None
    created_at: datetime


class AnnotationTaskOut(BaseModel):
    id: str
    organization_id: str
    curation_id: str
    sample_index: int
    source_sample_id: str
    status: str
    revision: int
    round: int
    assigned_to: str | None = None
    annotation: dict | None = None
    accepted: bool | None = None
    excluded_reason: str | None = None
    created_at: datetime
    payload: dict | None = None
    categories: list[str] = Field(default_factory=list)
    required_reviews: int | None = None
    modality: str | None = None
    curation_state: str | None = None
    reviews: list[dict] = Field(default_factory=list)
    media_url: str | None = None


def register(app):
    # Imported after core route initialization; execution modules never import the HTTP app.
    from .api import DB, Auth, audit, commit, get, page, public, replay

    def editable(db, identifier, org):
        record = db.scalar(
            select(Curation)
            .where(Curation.id == identifier, Curation.organization_id == org)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not record:
            raise Problem(404, "NOT_FOUND", "Curation not found.")
        if record.state != "OPEN":
            raise Problem(
                409,
                "CURATION_FROZEN",
                "Frozen review evidence is immutable. Create another curation to correct it.",
            )
        return record

    def task_for_update(db, identifier, org, expected):
        initial = get(db, AnnotationTask, identifier, org)
        curation = editable(db, initial.curation_id, org)
        task = db.scalar(
            select(AnnotationTask)
            .where(AnnotationTask.id == identifier, AnnotationTask.organization_id == org)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if task.revision != expected:
            raise Problem(
                409, "STALE_REVIEW", "This task changed. Refresh before submitting another decision."
            )
        return curation, task

    def detail(db, task):
        curation = get(db, Curation, task.curation_id, task.organization_id)
        dataset = get(db, Dataset, curation.dataset_id, task.organization_id)
        sample = source_samples(curation)[task.sample_index]
        return {
            **public(task),
            "payload": sample["payload"],
            "categories": curation.categories,
            "required_reviews": curation.required_reviews,
            "modality": dataset.modality,
            "curation_state": curation.state,
            "reviews": [public(review) for review in task_reviews(db, task)],
            "media_url": f"/v1/annotation-tasks/{task.id}/media" if dataset.modality == "image" else None,
        }

    @app.post("/v1/quality-profiles", tags=["Curation"], response_model=QualityProfileOut, status_code=201)
    def create_quality_profile(body: QualityProfileCreate, request: Request, p: Auth, db: DB):
        p.require("annotations:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        if not body.name.strip():
            raise Problem(422, "INVALID_NAME", "Profile name must contain visible characters.")
        record = QualityProfile(
            id=uid("qpf"),
            organization_id=p.organization_id,
            name=body.name.strip(),
            modality=body.modality,
            config=body.config.model_dump(),
        )
        db.add(record)
        audit(db, p, request, "quality_profile.created", record.id)
        db.flush()
        return commit(db, request, public(record))

    @app.get("/v1/quality-profiles", tags=["Curation"], response_model=Page[QualityProfileOut])
    def quality_profiles(
        p: Auth,
        db: DB,
        modality: str | None = None,
        limit: int = Query(25, ge=1, le=100),
        cursor: str | None = None,
    ):
        p.require("datasets:read")
        return page(
            db, QualityProfile, p, limit, cursor, [QualityProfile.modality == modality] if modality else []
        )

    @app.get("/v1/quality-profiles/{profile_id}", tags=["Curation"], response_model=QualityProfileOut)
    def quality_profile(profile_id: str, p: Auth, db: DB):
        p.require("datasets:read")
        return public(get(db, QualityProfile, profile_id, p.organization_id))

    @app.get("/v1/annotations/reviewers", tags=["Annotation"])
    def reviewers(p: Auth, db: DB):
        p.require("datasets:read")
        return {
            "items": [
                {"id": user.id, "name": user.name, "role": member.role}
                for user, member in db.execute(
                    select(User, Membership)
                    .join(Membership)
                    .where(Membership.organization_id == p.organization_id, User.active.is_(True))
                    .order_by(User.name)
                )
                if "annotations:review" in ROLES[member.role]
            ]
        }

    @app.post("/v1/curations", tags=["Curation"], response_model=CurationOut, status_code=201)
    def create_curation(body: CurationCreate, request: Request, p: Auth, db: DB):
        p.require("annotations:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        target = get(db, Dataset, body.dataset_id, p.organization_id)
        profile = get(db, QualityProfile, body.profile_id, p.organization_id)
        if profile.modality != target.modality or not body.name.strip():
            raise Problem(
                422,
                "INVALID_CURATION",
                "Use a named curation and a quality profile matching its dataset modality.",
            )
        if target.archived or target.policy.get("allowed_training_use") is not True:
            raise Problem(403, "POLICY_BLOCKED", "Use an active dataset with declared source-use rights.")
        samples = []
        source_bytes = 0
        if body.source_version_id:
            version = get(db, Version, body.source_version_id, p.organization_id)
            if version.dataset_id != target.id:
                raise Problem(
                    422, "SOURCE_DATASET_MISMATCH", "The source version must belong to this dataset."
                )
            if version.sample_count > MAX_CURATION_SAMPLES:
                raise Problem(
                    422, "CURATION_SAMPLE_LIMIT", "Local curation is limited to 500 samples per session."
                )
            source_bytes = version.manifest["data_artifact"]["bytes"]
            if source_bytes > MAX_CURATION_BYTES:
                raise Problem(422, "CURATION_SIZE_LIMIT", "Local curation source limit is 20 MiB.")
            samples = parse_jsonl(read_artifact(version.manifest["data_artifact"]))
        else:
            for identifier in body.upload_ids:
                upload = get(db, Upload, identifier, p.organization_id)
                if upload.dataset_id != target.id or upload.status != "COMPLETED":
                    raise Problem(422, "INVALID_SOURCE", "Use completed uploads belonging to this dataset.")
                source_bytes += max(upload.expected_bytes, upload.media.get("artifact", {}).get("bytes", 0))
                if (
                    source_bytes > MAX_CURATION_BYTES
                    or len(samples) + upload.sample_count > MAX_CURATION_SAMPLES
                ):
                    raise Problem(
                        422,
                        "CURATION_SAMPLE_LIMIT",
                        "Local sessions support at most 500 samples and 20 MiB of source bytes.",
                    )
                for index, payload in enumerate(upload_samples(upload)):
                    samples.append(
                        {
                            "sample_id": f"{upload.id}:{index}",
                            "payload": payload,
                            "source_refs": [
                                {"upload_id": upload.id, "sha256": upload.expected_sha256, "row": index}
                            ],
                        }
                    )
        if not samples or len(samples) > MAX_CURATION_SAMPLES:
            raise Problem(422, "CURATION_SAMPLE_LIMIT", "Choose between 1 and 500 source samples.")
        if (
            target.modality == "image"
            and sum(sample["payload"]["image"]["artifact"]["bytes"] for sample in samples)
            > MAX_CURATION_BYTES
        ):
            raise Problem(
                422, "CURATION_SIZE_LIMIT", "Normalized image bytes are limited to 20 MiB per local session."
            )
        report = duplicate_analysis(samples, target.modality, profile.config)
        identifier = uid("cur")
        artifact = put_immutable(
            p.organization_id,
            b"".join(canonical(sample) + b"\n" for sample in samples),
            "application/x-ndjson",
        )
        record = Curation(
            id=identifier,
            organization_id=p.organization_id,
            dataset_id=target.id,
            profile_id=profile.id,
            name=body.name.strip(),
            source_version_id=body.source_version_id,
            categories=body.categories,
            required_reviews=body.required_reviews,
            source_artifact=artifact,
            dedupe_report=report,
            data_card=body.data_card.model_dump() if body.data_card else {},
        )
        db.add(record)
        db.flush()
        for index, sample in enumerate(samples):
            excluded = report["excluded"].get(str(index))
            db.add(
                AnnotationTask(
                    id=uid("ant"),
                    organization_id=p.organization_id,
                    curation_id=identifier,
                    sample_index=index,
                    source_sample_id=sample["sample_id"],
                    status="EXCLUDED" if excluded else "NEW",
                    excluded_reason=f"{excluded['reason']} of source row {excluded['representative'] + 1}"
                    if excluded
                    else None,
                    annotation=sample.get("annotation"),
                    accepted=False if excluded else None,
                )
            )
        audit(db, p, request, "curation.created", record.id)
        db.flush()
        return commit(db, request, public(record))

    @app.get("/v1/curations", tags=["Curation"], response_model=Page[CurationOut])
    def curations(
        p: Auth,
        db: DB,
        dataset_id: str | None = None,
        limit: int = Query(25, ge=1, le=100),
        cursor: str | None = None,
    ):
        p.require("datasets:read")
        if dataset_id:
            get(db, Dataset, dataset_id, p.organization_id)
        return page(db, Curation, p, limit, cursor, [Curation.dataset_id == dataset_id] if dataset_id else [])

    @app.get("/v1/curations/{curation_id}", tags=["Curation"], response_model=CurationOut)
    def curation(curation_id: str, p: Auth, db: DB):
        p.require("datasets:read")
        record = get(db, Curation, curation_id, p.organization_id)
        report = record.quality if record.state == "FROZEN" else evaluate_curation(db, record)[0]
        return {**public(record), "quality": report}

    @app.patch("/v1/curations/{curation_id}/data-card", tags=["Curation"], response_model=CurationOut)
    def update_data_card(curation_id: str, body: CardUpdate, request: Request, p: Auth, db: DB):
        p.require("annotations:manage")
        record = editable(db, curation_id, p.organization_id)
        if record.revision != body.expected_revision:
            raise Problem(
                409, "STALE_CURATION", "This curation changed. Refresh before saving the data card."
            )
        record.data_card = body.data_card.model_dump()
        record.revision += 1
        audit(db, p, request, "curation.data_card.updated", record.id)
        db.commit()
        return public(record)

    @app.post("/v1/curations/{curation_id}/freeze", tags=["Curation"], response_model=CurationOut)
    def freeze_curation(curation_id: str, body: FreezeCuration, request: Request, p: Auth, db: DB):
        p.require("annotations:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        record = editable(db, curation_id, p.organization_id)
        if record.revision != body.expected_revision:
            raise Problem(
                409, "STALE_CURATION", "Review evidence changed. Refresh before approving publication."
            )
        report, selected, history = evaluate_curation(db, record)
        record.quality = report
        if not report["passed"]:
            audit(db, p, request, "curation.quality_blocked", record.id)
            db.commit()
            raise Problem(409, "CURATION_GATE_FAILED", " ".join(report["reasons"]))
        target = get(db, Dataset, record.dataset_id, p.organization_id)
        profile = get(db, QualityProfile, record.profile_id, p.organization_id)
        frozen_at = now()
        snapshot = {
            "schema_version": "1.0",
            "curation_id": record.id,
            "dataset_id": target.id,
            "source_artifact": record.source_artifact,
            "source_version_id": record.source_version_id,
            "profile": public(profile),
            "categories": record.categories,
            "required_reviews": record.required_reviews,
            "data_card": {
                **record.data_card,
                "policy": target.policy,
                "sources": [s["source_refs"] for s in selected],
            },
            "quality": report,
            "samples": selected,
            "review_history": history,
            "policy": target.policy,
            "approval": {
                "user_id": p.user_id,
                "api_key_id": p.key_id,
                "at": frozen_at.isoformat(),
                "approved_for_publication": True,
            },
        }
        record.snapshot = put_immutable(p.organization_id, canonical(snapshot), "application/json")
        record.state, record.frozen_by, record.frozen_at = "FROZEN", p.user_id, frozen_at
        record.revision += 1
        audit(db, p, request, "curation.approved", record.id)
        db.flush()
        return commit(db, request, public(record), 200)

    @app.get("/v1/annotation-tasks", tags=["Annotation"], response_model=Page[AnnotationTaskOut])
    def annotation_tasks(
        p: Auth,
        db: DB,
        curation_id: str | None = None,
        status: str | None = None,
        assigned_to: str | None = None,
        limit: int = Query(25, ge=1, le=100),
        cursor: str | None = None,
    ):
        p.require("datasets:read")
        extra = []
        if curation_id:
            get(db, Curation, curation_id, p.organization_id)
            extra.append(AnnotationTask.curation_id == curation_id)
        if status:
            extra.append(AnnotationTask.status == status)
        if assigned_to:
            extra.append(AnnotationTask.assigned_to == assigned_to)
        return page(db, AnnotationTask, p, limit, cursor, extra)

    @app.get("/v1/annotation-tasks/{task_id}", tags=["Annotation"], response_model=AnnotationTaskOut)
    def annotation_task(task_id: str, p: Auth, db: DB):
        p.require("datasets:read")
        return detail(db, get(db, AnnotationTask, task_id, p.organization_id))

    @app.get("/v1/annotation-tasks/{task_id}/media", tags=["Annotation"])
    def annotation_media(task_id: str, p: Auth, db: DB, thumbnail: bool = False):
        from fastapi import Response

        p.require("datasets:read")
        task = get(db, AnnotationTask, task_id, p.organization_id)
        record = get(db, Curation, task.curation_id, p.organization_id)
        target = get(db, Dataset, record.dataset_id, p.organization_id)
        if target.modality != "image":
            raise Problem(404, "NOT_FOUND", "This task has no image preview.")
        image = source_samples(record)[task.sample_index]["payload"]["image"]
        data = read_artifact(image["thumbnail" if thumbnail else "artifact"])
        return Response(
            data,
            media_type="image/png",
            headers={
                "X-Content-SHA256": digest(data),
                "Content-Security-Policy": "default-src 'none'; sandbox",
            },
        )

    @app.post("/v1/annotation-tasks/{task_id}/assign", tags=["Annotation"], response_model=AnnotationTaskOut)
    def assign_annotation(task_id: str, body: TaskAssignment, request: Request, p: Auth, db: DB):
        p.require("annotations:review")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        record, task = task_for_update(db, task_id, p.organization_id, body.expected_revision)
        if task.status in RESOLVED or task.status == "NEEDS_ADJUDICATION":
            raise Problem(409, "TASK_RESOLVED", "Only open review tasks can be assigned.")
        if "annotations:manage" not in p.scopes and (
            body.user_id != p.user_id or task.assigned_to not in (None, p.user_id)
        ):
            raise Problem(
                403, "ASSIGNMENT_FORBIDDEN", "Labelers can only claim unassigned tasks for themselves."
            )
        if body.user_id:
            member = db.get(Membership, (p.organization_id, body.user_id))
            user = db.get(User, body.user_id)
            if not member or not user or not user.active or "annotations:review" not in ROLES[member.role]:
                raise Problem(404, "NOT_FOUND", "Eligible reviewer not found in this organization.")
        task.assigned_to = body.user_id
        task.revision += 1
        record.revision += 1
        audit(db, p, request, "annotation.assigned", task.id)
        db.flush()
        return commit(db, request, detail(db, task), 200)

    def decision(task_id, body, request, p, db, adjudicate=False):
        p.require("annotations:adjudicate" if adjudicate else "annotations:review")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        record, task = task_for_update(db, task_id, p.organization_id, body.expected_revision)
        reviews = task_reviews(db, task)
        votes = latest_votes(reviews, task.round)
        if adjudicate:
            if task.status != "NEEDS_ADJUDICATION":
                raise Problem(
                    409, "ADJUDICATION_NOT_NEEDED", "Only disagreeing reviews require adjudication."
                )
            if p.user_id in {review.user_id for review in votes}:
                raise Problem(
                    403,
                    "INDEPENDENT_ADJUDICATOR_REQUIRED",
                    "An adjudicator must be independent of this round's reviewers.",
                )
        else:
            if task.status in RESOLVED or task.status == "NEEDS_ADJUDICATION":
                raise Problem(
                    409,
                    "TASK_RESOLVED",
                    "This task needs adjudication or an authorized reopen before another review.",
                )
            if task.assigned_to and task.assigned_to != p.user_id:
                raise Problem(403, "TASK_ASSIGNED", "This task is assigned to another reviewer.")
        if not body.note.strip():
            raise Problem(422, "REVIEW_NOTE_REQUIRED", "Record a reason for this decision.")
        target = get(db, Dataset, record.dataset_id, p.organization_id)
        payload = source_samples(record)[task.sample_index]["payload"]
        annotation = (
            validate_annotation(body.annotation, payload, target.modality, record.categories)
            if body.decision == "accept"
            else None
        )
        task.revision += 1
        review = AnnotationReview(
            id=uid("revw"),
            organization_id=p.organization_id,
            task_id=task.id,
            user_id=p.user_id,
            api_key_id=p.key_id,
            round=task.round,
            task_revision=task.revision,
            decision=("adjudicate_" if adjudicate else "") + body.decision,
            annotation=annotation,
            note=body.note.strip(),
        )
        db.add(review)
        db.flush()
        task.annotation, task.assigned_to = annotation, None
        if adjudicate:
            task.status, task.accepted = "ADJUDICATED", body.decision == "accept"
        else:
            current = latest_votes([*reviews, review], task.round)
            if len(current) < record.required_reviews:
                task.status, task.accepted = "NEEDS_REVIEW", None
            elif len({canonical((vote.decision, vote.annotation)) for vote in current}) == 1:
                task.status, task.accepted = (
                    ("ACCEPTED" if body.decision == "accept" else "REJECTED"),
                    body.decision == "accept",
                )
            else:
                task.status, task.accepted = "NEEDS_ADJUDICATION", None
        record.revision += 1
        audit(db, p, request, "annotation.adjudicated" if adjudicate else "annotation.reviewed", task.id)
        db.flush()
        return commit(db, request, detail(db, task), 200)

    @app.post(
        "/v1/annotation-tasks/{task_id}/decision", tags=["Annotation"], response_model=AnnotationTaskOut
    )
    def review_annotation(task_id: str, body: ReviewDecision, request: Request, p: Auth, db: DB):
        return decision(task_id, body, request, p, db)

    @app.post(
        "/v1/annotation-tasks/{task_id}/adjudicate", tags=["Annotation"], response_model=AnnotationTaskOut
    )
    def adjudicate_annotation(task_id: str, body: ReviewDecision, request: Request, p: Auth, db: DB):
        return decision(task_id, body, request, p, db, adjudicate=True)

    @app.post("/v1/annotation-tasks/{task_id}/reopen", tags=["Annotation"], response_model=AnnotationTaskOut)
    def reopen_annotation(task_id: str, body: TaskReopen, request: Request, p: Auth, db: DB):
        p.require("annotations:adjudicate")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        record, task = task_for_update(db, task_id, p.organization_id, body.expected_revision)
        if task.status == "EXCLUDED" or not body.note.strip():
            raise Problem(
                422,
                "INVALID_REOPEN",
                "Duplicate exclusions are fixed by the profile; other tasks require a reason to reopen.",
            )
        task.round += 1
        task.revision += 1
        task.status, task.accepted, task.assigned_to = "NEW", None, None
        db.add(
            AnnotationReview(
                id=uid("revw"),
                organization_id=p.organization_id,
                task_id=task.id,
                user_id=p.user_id,
                api_key_id=p.key_id,
                round=task.round,
                task_revision=task.revision,
                decision="reopen",
                note=body.note.strip(),
            )
        )
        record.revision += 1
        audit(db, p, request, "annotation.reopened", task.id)
        db.flush()
        return commit(db, request, detail(db, task), 200)
