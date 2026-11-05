"""Measured version reports, PostgreSQL lexical search and imported evaluation evidence."""

import math
from collections import Counter

from fastapi import Query, Request
from pydantic import Field, model_validator
from sqlalchemy import func, select, text

from .db import uid
from .errors import Problem
from .models import Benchmark, Dataset, Evaluation, Feedback, SearchEntry, Version
from .policies import visible_condition
from .recipes import parse_jsonl
from .schemas import Strict
from .security import canonical, digest
from .storage import put_immutable, read_artifact


def version_samples(version):
    if digest(canonical(version.manifest)) != version.manifest_hash:
        raise Problem(409, "MANIFEST_CORRUPT", "Version evidence failed its sealed manifest checksum.")
    return parse_jsonl(read_artifact(version.manifest["data_artifact"]))


def index_version(db, version, samples):
    if db.scalar(
        select(SearchEntry.id)
        .where(SearchEntry.version_id == version.id, SearchEntry.organization_id == version.organization_id)
        .limit(1)
    ):
        return 0
    for index, sample in enumerate(samples):
        payload = sample["payload"]
        text = " ".join(value for value in payload.values() if isinstance(value, str))
        tags = [tag for tag in payload.get("tags", []) if isinstance(tag, str)]
        annotation = sample.get("annotation", {})
        labels = (
            [annotation["label"]]
            if annotation.get("kind") == "category"
            else [box["label"] for box in annotation.get("boxes", [])]
        )
        content = " ".join([text, *tags, *labels])[:8192]
        db.add(
            SearchEntry(
                id=uid("idx"),
                organization_id=version.organization_id,
                version_id=version.id,
                dataset_id=version.dataset_id,
                sample_index=index,
                sample_id=sample["sample_id"],
                content_hash=sample["content_hash"],
                excerpt=content[:400],
                search_text=content,
            )
        )
    return len(samples)


def holdout_lock(db, org):
    key = int.from_bytes(
        __import__("hashlib").sha256((org + ":holdout-admission").encode()).digest()[:8], signed=True
    )
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def reject_contamination(db, org, samples, target):
    if target.protection == "holdout":
        return
    hashes = {digest(canonical(sample)) for sample in samples}
    protected = (
        select(SearchEntry.content_hash)
        .join(Dataset, SearchEntry.dataset_id == Dataset.id)
        .where(
            SearchEntry.organization_id == org,
            Dataset.protection == "holdout",
            Dataset.erased_at.is_(None),
            SearchEntry.content_hash.in_(hashes),
        )
    )
    if db.scalar(protected.limit(1)):
        raise Problem(
            403,
            "CONTAMINATION_BLOCKED",
            "An exact sample hash overlaps a protected holdout. No held-out solution text was exposed to the generation worker.",
        )


def distribution(samples):
    modalities, tags, classes = Counter(), Counter(), Counter()
    bins = {"0–32": 0, "33–128": 0, "129–512": 0, "513+": 0}
    box_count = annotated = 0
    hashes = []
    for sample in samples:
        payload = sample["payload"]
        modalities[sample.get("modality", "unknown")] += 1
        hashes.append(sample["content_hash"])
        tags.update(tag for tag in payload.get("tags", []) if isinstance(tag, str))
        length = len(str(payload.get("prompt", "")))
        bins[
            "0–32" if length <= 32 else "33–128" if length <= 128 else "129–512" if length <= 512 else "513+"
        ] += 1
        annotation = sample.get("annotation")
        if annotation:
            annotated += 1
            if annotation["kind"] == "category":
                classes[annotation["label"]] += 1
            else:
                classes.update(box["label"] for box in annotation["boxes"])
                box_count += len(annotation["boxes"])
    return {
        "sample_count": len(samples),
        "modalities": dict(modalities),
        "tag_counts": dict(tags),
        "class_counts": dict(classes),
        "annotated_samples": annotated,
        "box_count": box_count,
        "class_denominator": "label objects for boxes; samples for categories",
        "prompt_length_bins": bins,
        "exact_duplicate_records": len(hashes) - len(set(hashes)),
        "limitations": "Descriptive counts only; no model accuracy, bias or semantic equivalence is inferred.",
    }


def version_diff(left, right):
    a, b = (
        Counter(sample["content_hash"] for sample in left),
        Counter(sample["content_hash"] for sample in right),
    )
    annotations_a = {sample["content_hash"]: canonical(sample.get("annotation")) for sample in left}
    annotations_b = {sample["content_hash"]: canonical(sample.get("annotation")) for sample in right}
    shared = a.keys() & b.keys()
    return {
        "left_count": len(left),
        "right_count": len(right),
        "added": sum((b - a).values()),
        "removed": sum((a - b).values()),
        "shared_records": sum(min(a[key], b[key]) for key in shared),
        "annotation_changed_content_hashes": [
            key for key in sorted(shared) if annotations_a[key] != annotations_b[key]
        ],
        "added_content_hashes": list((b - a).keys())[:100],
        "removed_content_hashes": list((a - b).keys())[:100],
        "left_distribution": distribution(left),
        "right_distribution": distribution(right),
    }


def wilson(correct, total):
    z = 1.959963984540054
    proportion = correct / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return [max(0, center - radius), min(1, center + radius)]


class BenchmarkCreate(Strict):
    name: str = Field(min_length=1, max_length=160)
    version_id: str
    external_ref: str = Field(min_length=1, max_length=400)
    source_kind: str = Field(pattern="^(external_holdout|synthetic_fixture)$")
    independent_of_training: bool


class SliceResult(Strict):
    name: str = Field(min_length=1, max_length=100)
    correct: int = Field(ge=0)
    total: int = Field(ge=1, le=100000000)

    @model_validator(mode="after")
    def counts(self):
        if self.correct > self.total:
            raise ValueError("Correct count cannot exceed the denominator.")
        return self


class EvaluationCreate(Strict):
    version_id: str
    benchmark_id: str
    model_ref: str = Field(min_length=1, max_length=200)
    external_run_ref: str = Field(min_length=1, max_length=400)
    result: SliceResult
    slices: list[SliceResult] = Field(default_factory=list, max_length=100)
    evidence_note: str = Field(min_length=8, max_length=4000)


class FeedbackCreate(Strict):
    evaluation_id: str
    maximum_new_samples: int = Field(default=100, ge=1, le=1000)
    maximum_internal_budget_usd: float = Field(default=1, ge=0, le=100, allow_inf_nan=False)
    require_manual_approval: bool = True


class FeedbackDecision(Strict):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str = Field(min_length=1, max_length=2000)


def register(app):
    from .api import DB, Auth, audit, commit, get, page, public, replay

    @app.get("/v1/versions/{version_id}/distribution", tags=["Evaluation"])
    def version_distribution(version_id: str, p: Auth, db: DB):
        p.require("datasets:read")
        version = get(db, Version, version_id, p.organization_id)
        return {
            "version_id": version.id,
            "manifest_sha256": version.manifest_hash,
            **distribution(version_samples(version)),
        }

    @app.get("/v1/versions/compare", tags=["Evaluation"])
    def compare_versions(left_version_id: str, right_version_id: str, p: Auth, db: DB):
        p.require("datasets:read")
        left, right = (
            get(db, Version, left_version_id, p.organization_id),
            get(db, Version, right_version_id, p.organization_id),
        )
        return {
            "left_version_id": left.id,
            "right_version_id": right.id,
            "left_manifest_sha256": left.manifest_hash,
            "right_manifest_sha256": right.manifest_hash,
            **version_diff(version_samples(left), version_samples(right)),
        }

    @app.post("/v1/versions/{version_id}/index", tags=["Search"])
    def reindex_version(version_id: str, request: Request, p: Auth, db: DB):
        p.require("evaluations:write")
        if cached := replay(db, p, request, {}):
            return cached
        version = db.scalar(
            select(Version)
            .where(Version.id == version_id, Version.organization_id == p.organization_id)
            .with_for_update()
        )
        if not version:
            raise Problem(404, "NOT_FOUND", "Version not found.")
        get(db, Version, version.id, p.organization_id)
        count = index_version(db, version, version_samples(version))
        audit(db, p, request, "search.version.indexed", version.id)
        return commit(db, request, {"version_id": version.id, "records_added": count}, 200)

    @app.get("/v1/search/samples", tags=["Search"])
    def search_samples(
        q: str,
        p: Auth,
        db: DB,
        dataset_id: str | None = None,
        offset: int = Query(0, ge=0, le=10000),
        limit: int = Query(25, ge=1, le=100),
    ):
        p.require("datasets:read")
        if not q.strip() or len(q) > 200:
            raise Problem(422, "INVALID_SEARCH", "Search with 1–200 characters.")
        query = select(
            SearchEntry,
            func.ts_rank_cd(SearchEntry.search_vector, func.plainto_tsquery("simple", q)).label("rank"),
        ).where(
            SearchEntry.organization_id == p.organization_id,
            visible_condition(SearchEntry, p),
            SearchEntry.search_vector.op("@@")(func.plainto_tsquery("simple", q)),
        )
        if dataset_id:
            get(db, Dataset, dataset_id, p.organization_id)
            query = query.where(SearchEntry.dataset_id == dataset_id)
        rows = db.execute(
            query.order_by(__import__("sqlalchemy").desc("rank"), SearchEntry.id)
            .offset(offset)
            .limit(limit + 1)
        ).all()
        return {
            "items": [
                {
                    "dataset_id": row.dataset_id,
                    "version_id": row.version_id,
                    "sample_id": row.sample_id,
                    "sample_index": row.sample_index,
                    "excerpt": row.excerpt,
                    "rank": float(rank),
                }
                for row, rank in rows[:limit]
            ],
            "offset": offset,
            "next_offset": offset + limit if len(rows) > limit else None,
            "search_kind": "PostgreSQL lexical full text; not semantic search",
        }

    @app.post("/v1/benchmarks", tags=["Evaluation"], status_code=201)
    def create_benchmark(body: BenchmarkCreate, request: Request, p: Auth, db: DB):
        p.require("evaluations:write")
        p.require("holdouts:read")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        version = get(db, Version, body.version_id, p.organization_id)
        target = get(db, Dataset, version.dataset_id, p.organization_id)
        if target.protection != "holdout" or not body.independent_of_training:
            raise Problem(
                403,
                "HOLDOUT_POLICY_REQUIRED",
                "Protect the benchmark dataset as a holdout and record its independence before importing evaluations.",
            )
        record = Benchmark(
            id=uid("bmk"),
            organization_id=p.organization_id,
            name=body.name,
            version_id=version.id,
            external_ref=body.external_ref,
            content_sha256=version.manifest_hash,
            source_kind=body.source_kind,
            policy={
                "independent_of_training": True,
                "generation_worker_access": "denied",
                "independence": "user-attested; not independently audited",
            },
        )
        db.add(record)
        audit(db, p, request, "benchmark.frozen", record.id)
        db.flush()
        return commit(db, request, public(record))

    @app.get("/v1/benchmarks", tags=["Evaluation"])
    def benchmarks(p: Auth, db: DB):
        p.require("holdouts:read")
        return page(db, Benchmark, p, 100)

    @app.post("/v1/evaluations", tags=["Evaluation"], status_code=201)
    def import_evaluation(body: EvaluationCreate, request: Request, p: Auth, db: DB):
        p.require("evaluations:write")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        version = get(db, Version, body.version_id, p.organization_id)
        benchmark = get(db, Benchmark, body.benchmark_id, p.organization_id)
        if version.id == benchmark.version_id:
            raise Problem(
                403,
                "EVALUATION_CONTAMINATION",
                "The training version and protected benchmark must be separate.",
            )
        metrics = {
            "correct": body.result.correct,
            "total": body.result.total,
            "accuracy": body.result.correct / body.result.total,
            "wilson_95_interval": wilson(body.result.correct, body.result.total),
            "slices": [item.model_dump() for item in body.slices],
            "source_kind": benchmark.source_kind,
            "evidence_status": "imported_user_attestation",
            "limitations": "Imported counts are not independently executed; a synthetic fixture is not evidence of real model gains. Wilson intervals assume binomial observations.",
        }
        artifact = put_immutable(p.organization_id, canonical(body.model_dump()), "application/json")
        record = Evaluation(
            id=uid("eval"),
            organization_id=p.organization_id,
            version_id=version.id,
            benchmark_id=benchmark.id,
            model_ref=body.model_ref,
            external_run_ref=body.external_run_ref,
            metrics=metrics,
            artifact=artifact,
            imported_by=p.user_id,
        )
        db.add(record)
        audit(db, p, request, "evaluation.imported", record.id)
        db.flush()
        return commit(db, request, public(record))

    @app.get("/v1/evaluations", tags=["Evaluation"])
    def evaluations(p: Auth, db: DB, limit: int = Query(25, ge=1, le=100), cursor: str | None = None):
        p.require("datasets:read")
        return page(db, Evaluation, p, limit, cursor)

    @app.get("/v1/evaluations/compare", tags=["Evaluation"])
    def compare_evaluations(baseline_id: str, candidate_id: str, p: Auth, db: DB):
        p.require("datasets:read")
        baseline, candidate = (
            get(db, Evaluation, baseline_id, p.organization_id),
            get(db, Evaluation, candidate_id, p.organization_id),
        )
        if baseline.benchmark_id != candidate.benchmark_id:
            raise Problem(422, "BENCHMARK_MISMATCH", "Compare results against the same frozen benchmark.")
        return {
            "baseline": public(baseline),
            "candidate": public(candidate),
            "accuracy_delta": candidate.metrics["accuracy"] - baseline.metrics["accuracy"],
            "conclusion": "Descriptive imported comparison; no causal model-improvement or release decision is inferred.",
        }

    @app.get("/v1/evaluations/{evaluation_id}", tags=["Evaluation"])
    def evaluation(evaluation_id: str, p: Auth, db: DB):
        p.require("datasets:read")
        return public(get(db, Evaluation, evaluation_id, p.organization_id))

    @app.post("/v1/feedback", tags=["Evaluation"], status_code=201)
    def create_feedback(body: FeedbackCreate, request: Request, p: Auth, db: DB):
        p.require("evaluations:write")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        evaluation = get(db, Evaluation, body.evaluation_id, p.organization_id)
        if not body.require_manual_approval:
            raise Problem(403, "MANUAL_APPROVAL_REQUIRED", "Feedback never starts unreviewed generation.")
        slices = sorted(evaluation.metrics["slices"], key=lambda item: item["correct"] / item["total"])
        errors = evaluation.metrics["total"] - evaluation.metrics["correct"]
        proposal = {
            "evaluation_id": evaluation.id,
            "evidence_sha256": evaluation.artifact["sha256"],
            "benchmark_id": evaluation.benchmark_id,
            "target_slices": slices[:5],
            "suggested_sample_count": min(body.maximum_new_samples, errors * 2),
            "policy": body.model_dump(),
            "dispatch": "manual-only; no job is launched",
            "limitations": "Recommendations follow imported failure counts; improvement must be measured on independent fixed benchmarks.",
        }
        record = Feedback(
            id=uid("fbk"), organization_id=p.organization_id, evaluation_id=evaluation.id, proposal=proposal
        )
        db.add(record)
        audit(db, p, request, "feedback.proposed", record.id)
        db.flush()
        return commit(db, request, public(record))

    @app.get("/v1/feedback", tags=["Evaluation"])
    def feedback(p: Auth, db: DB):
        p.require("datasets:read")
        return page(db, Feedback, p, 100)

    @app.post("/v1/feedback/{feedback_id}/decision", tags=["Evaluation"])
    def decide_feedback(feedback_id: str, body: FeedbackDecision, request: Request, p: Auth, db: DB):
        p.require("evaluations:write")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        record = get(db, Feedback, feedback_id, p.organization_id)
        record = db.scalar(
            select(Feedback)
            .where(Feedback.id == record.id, Feedback.organization_id == p.organization_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if record.status != "DRAFT":
            raise Problem(409, "FEEDBACK_DECIDED", "This proposal already has a recorded decision.")
        record.status, record.decided_by, record.decision_note = (
            ("APPROVED" if body.decision == "approve" else "REJECTED"),
            p.user_id,
            body.note,
        )
        audit(db, p, request, "feedback.decided", record.id)
        db.flush()
        return commit(db, request, public(record), 200)
