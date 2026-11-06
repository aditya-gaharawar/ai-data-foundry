"""Immutable governance policies, independent approvals, holdouts and retention."""

from datetime import timedelta
from typing import Literal

from fastapi import Request
from pydantic import Field
from sqlalchemy import func, select

from .db import now, uid
from .errors import Problem
from .evaluation import holdout_lock, index_version, version_samples
from .models import (
    ApprovalRequest,
    ComputeJob,
    Dataset,
    ErasureRequest,
    GovernancePolicy,
    Outbox,
    Run,
    SearchEntry,
    Version,
)
from .policies import PolicyDefinition, current_policy
from .retention import erasure_plan, public_erasure
from .schemas import Strict


class GovernancePolicyCreate(Strict):
    definition: PolicyDefinition


class DatasetGovernance(Strict):
    expected_revision: int = Field(ge=1)
    action: Literal["protect_holdout", "place_legal_hold", "request_hold_release"]
    note: str = Field(min_length=1, max_length=2000)


class ApprovalDecision(Strict):
    decision: Literal["approve", "reject"]
    note: str = Field(min_length=1, max_length=2000)


class ErasureCreate(Strict):
    dataset_id: str
    trigger: Literal["user_request", "retention_expiry"] = "user_request"
    reason: str = Field(min_length=8, max_length=2000)


class ErasureExecute(Strict):
    confirm_dataset_name: str
    plan_sha256: str = Field(pattern="^[a-f0-9]{64}$")


def reject_active_schedules(db, target):
    from .models import WorkflowSchedule

    # Dataset is already locked. Do not lock schedule rows in the reverse order.
    if db.scalar(
        select(func.count())
        .select_from(WorkflowSchedule)
        .where(
            WorkflowSchedule.organization_id == target.organization_id,
            WorkflowSchedule.dataset_id == target.id,
            WorkflowSchedule.state == "ACTIVE",
        )
    ):
        raise Problem(
            409,
            "DATASET_SCHEDULED",
            "Pause or cancel active schedules before protecting or erasing this dataset.",
        )


def register(app):
    from .api import DB, Auth, audit, commit, get, page, public, replay

    def locked_erasure(db, identifier, p, include_erased=False):
        row = get(db, ErasureRequest, identifier, p.organization_id, include_erased=include_erased)
        return db.scalar(
            select(ErasureRequest)
            .where(ErasureRequest.id == row.id, ErasureRequest.organization_id == p.organization_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    @app.get("/v1/governance/policy", tags=["Governance"])
    def governance_policy(p: Auth, db: DB):
        p.require("datasets:read")
        return current_policy(db, p.organization_id)

    @app.post("/v1/governance/policies", tags=["Governance"], status_code=201)
    def create_governance_policy(body: GovernancePolicyCreate, request: Request, p: Auth, db: DB):
        p.require("governance:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        from .models import Organization

        db.scalar(select(Organization).where(Organization.id == p.organization_id).with_for_update())
        number = (
            db.scalar(
                select(func.max(GovernancePolicy.number)).where(
                    GovernancePolicy.organization_id == p.organization_id
                )
            )
            or 0
        ) + 1
        record = GovernancePolicy(
            id=uid("pol"),
            organization_id=p.organization_id,
            number=number,
            definition=body.definition.model_dump(),
            created_by=p.user_id,
        )
        db.add(record)
        audit(db, p, request, "governance.policy.created", record.id)
        db.flush()
        return commit(db, request, public(record))

    @app.get("/v1/governance/policies", tags=["Governance"])
    def governance_policies(p: Auth, db: DB):
        p.require("governance:manage")
        return page(db, GovernancePolicy, p, 100)

    @app.post("/v1/governance/datasets/{dataset_id}", tags=["Governance"])
    def govern_dataset(dataset_id: str, body: DatasetGovernance, request: Request, p: Auth, db: DB):
        p.require("governance:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        target = get(db, Dataset, dataset_id, p.organization_id)
        if target.governance_revision != body.expected_revision:
            raise Problem(409, "STALE_GOVERNANCE", "Dataset policy changed. Refresh before another decision.")
        if body.action == "request_hold_release":
            if not target.legal_hold:
                raise Problem(409, "NO_LEGAL_HOLD", "This dataset has no legal hold to release.")
            approval = ApprovalRequest(
                id=uid("apr"),
                organization_id=p.organization_id,
                dataset_id=target.id,
                action="release_legal_hold",
                requested_by=p.user_id,
                note=body.note,
            )
            db.add(approval)
            audit(db, p, request, "legal_hold.release.requested", approval.id)
            db.flush()
            return commit(db, request, public(approval), 202)
        if body.action == "place_legal_hold":
            target.legal_hold = True
        else:
            reject_active_schedules(db, target)
            if db.scalar(
                select(func.count())
                .select_from(Run)
                .where(
                    Run.dataset_id == target.id,
                    Run.organization_id == p.organization_id,
                    Run.status.not_in(["SUCCEEDED", "FAILED", "CANCELLED"]),
                )
            ):
                raise Problem(
                    409, "DATASET_BUSY", "Finish or cancel active runs before protecting a holdout."
                )
            from .references import reference_lock

            reference_lock(db, p.organization_id)
            holdout_lock(db, p.organization_id)
            versions = db.scalars(
                select(Version).where(
                    Version.dataset_id == target.id, Version.organization_id == p.organization_id
                )
            ).all()
            if versions and db.scalar(
                select(ComputeJob.id)
                .where(
                    ComputeJob.organization_id == p.organization_id,
                    ComputeJob.version_id.in_([item.id for item in versions]),
                    ComputeJob.status.in_(["QUEUED", "LEASED"]),
                )
                .limit(1)
            ):
                raise Problem(
                    409,
                    "DATASET_BUSY",
                    "Finish or cancel active compute jobs before protecting this holdout.",
                )
            for version in versions:
                index_version(db, version, version_samples(version))
            db.flush()
            own_hashes = select(SearchEntry.content_hash).where(
                SearchEntry.dataset_id == target.id, SearchEntry.organization_id == p.organization_id
            )
            if db.scalar(
                select(SearchEntry.id)
                .where(
                    SearchEntry.organization_id == p.organization_id,
                    SearchEntry.dataset_id != target.id,
                    SearchEntry.content_hash.in_(own_hashes),
                )
                .limit(1)
            ):
                raise Problem(
                    403,
                    "HOLDOUT_ALREADY_CONTAMINATED",
                    "This source overlaps another indexed dataset. Use an independent held-out benchmark.",
                )
            # Earlier milestones predate SearchEntry. Check those immutable
            # versions too, without leaking their solutions or materializing a
            # second persistent search index during this administrative action.
            own_values = set(db.scalars(own_hashes))
            legacy = db.scalars(
                select(Version)
                .join(Dataset, Version.dataset_id == Dataset.id)
                .where(
                    Version.organization_id == p.organization_id,
                    Dataset.organization_id == p.organization_id,
                    Dataset.id != target.id,
                    Dataset.erased_at.is_(None),
                    ~select(SearchEntry.id)
                    .where(
                        SearchEntry.version_id == Version.id, SearchEntry.organization_id == p.organization_id
                    )
                    .exists(),
                )
                .limit(1001)
            ).all()
            if len(legacy) > 1000:
                raise Problem(
                    409,
                    "HOLDOUT_BACKFILL_REQUIRED",
                    "More than 1,000 legacy versions need an operator-run search backfill before holdout protection.",
                )
            for version in legacy:
                if any(sample["content_hash"] in own_values for sample in version_samples(version)):
                    raise Problem(
                        403,
                        "HOLDOUT_ALREADY_CONTAMINATED",
                        "An immutable legacy version already contains this sample. Choose an independent source.",
                    )
            target.protection = "holdout"
        target.governance_revision += 1
        audit(db, p, request, "dataset." + body.action, target.id)
        db.flush()
        return commit(db, request, public(target), 200)

    @app.get("/v1/governance/approvals", tags=["Governance"])
    def approval_requests(p: Auth, db: DB):
        p.require("governance:manage")
        return page(db, ApprovalRequest, p, 100)

    @app.post("/v1/governance/approvals/{approval_id}/decision", tags=["Governance"])
    def decide_approval(approval_id: str, body: ApprovalDecision, request: Request, p: Auth, db: DB):
        p.require("governance:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        initial = get(db, ApprovalRequest, approval_id, p.organization_id)
        record = db.scalar(
            select(ApprovalRequest)
            .where(ApprovalRequest.id == initial.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if record.status != "PENDING" or record.requested_by == p.user_id:
            raise Problem(
                409,
                "INDEPENDENT_APPROVAL_REQUIRED",
                "A different authorized administrator must decide this pending request.",
            )
        target = get(db, Dataset, record.dataset_id, p.organization_id)
        record.status, record.decided_by, record.decision_note = (
            ("APPROVED" if body.decision == "approve" else "REJECTED"),
            p.user_id,
            body.note,
        )
        if body.decision == "approve":
            target.legal_hold = False
            target.governance_revision += 1
        audit(db, p, request, "approval.decided", record.id)
        db.flush()
        return commit(db, request, public(record), 200)

    @app.get("/v1/governance/retention-plan", tags=["Governance"])
    def retention_candidates(p: Auth, db: DB):
        p.require("governance:manage")
        policy = current_policy(db, p.organization_id)
        cutoff = now() - timedelta(days=policy["definition"]["retention_days"])
        rows = db.scalars(
            select(Dataset)
            .where(
                Dataset.organization_id == p.organization_id,
                Dataset.erased_at.is_(None),
                Dataset.created_at <= cutoff,
            )
            .order_by(Dataset.created_at)
            .limit(100)
        ).all()
        return {
            "policy": policy,
            "items": [
                {
                    "dataset_id": item.id,
                    "name": item.name,
                    "legal_hold": item.legal_hold,
                    "eligible_for_request": not item.legal_hold,
                }
                for item in rows
            ],
            "automatic_deletion": False,
            "required_action": "Independent approval and a sealed artifact plan are required.",
        }

    @app.post("/v1/governance/erasures", tags=["Governance"], status_code=201)
    def request_erasure(body: ErasureCreate, request: Request, p: Auth, db: DB):
        p.require("governance:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        target = get(db, Dataset, body.dataset_id, p.organization_id)
        if target.legal_hold:
            raise Problem(
                409,
                "LEGAL_HOLD",
                "Release the legal hold through an independent approval before requesting erasure.",
            )
        policy = current_policy(db, p.organization_id)["definition"]
        ready = now() + timedelta(seconds=policy["erasure_delay_seconds"])
        if body.trigger == "retention_expiry":
            ready = max(ready, target.created_at + timedelta(days=policy["retention_days"]))
        record = ErasureRequest(
            id=uid("ers"),
            organization_id=p.organization_id,
            dataset_id=target.id,
            requested_by=p.user_id,
            ready_after=ready,
            reason=body.reason,
            result={"trigger": body.trigger},
        )
        db.add(record)
        audit(db, p, request, "erasure.requested", record.id)
        db.flush()
        return commit(db, request, public_erasure(record))

    @app.get("/v1/governance/erasures", tags=["Governance"])
    def erasures(p: Auth, db: DB):
        p.require("governance:manage")
        return {
            "items": [
                public_erasure(row)
                for row in db.scalars(
                    select(ErasureRequest)
                    .where(ErasureRequest.organization_id == p.organization_id)
                    .order_by(ErasureRequest.created_at.desc())
                    .limit(100)
                )
            ]
        }

    @app.get("/v1/governance/erasures/{erasure_id}", tags=["Governance"])
    def erasure(erasure_id: str, p: Auth, db: DB):
        p.require("governance:manage")
        return public_erasure(get(db, ErasureRequest, erasure_id, p.organization_id, include_erased=True))

    @app.post("/v1/governance/erasures/{erasure_id}/decision", tags=["Governance"])
    def approve_erasure(erasure_id: str, body: ApprovalDecision, request: Request, p: Auth, db: DB):
        p.require("governance:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        record = locked_erasure(db, erasure_id, p)
        if record.requested_by == p.user_id or record.status != "PENDING_APPROVAL":
            raise Problem(
                409,
                "INDEPENDENT_APPROVAL_REQUIRED",
                "A different authorized administrator must decide the pending erasure.",
            )
        target = get(db, Dataset, record.dataset_id, p.organization_id)
        if target.legal_hold:
            raise Problem(409, "LEGAL_HOLD", "A legal hold blocks approval.")
        record.status, record.approved_by = (
            ("APPROVED" if body.decision == "approve" else "REJECTED"),
            p.user_id,
        )
        record.result = {**record.result, "approval_note": body.note}
        audit(db, p, request, "erasure.decided", record.id)
        db.flush()
        return commit(db, request, public_erasure(record), 200)

    @app.post("/v1/governance/erasures/{erasure_id}/preview", tags=["Governance"])
    def preview_erasure(erasure_id: str, request: Request, p: Auth, db: DB):
        p.require("governance:manage")
        if cached := replay(db, p, request, {}):
            return cached
        record = locked_erasure(db, erasure_id, p)
        target = get(db, Dataset, record.dataset_id, p.organization_id)
        if record.status != "APPROVED" or target.legal_hold:
            raise Problem(
                409, "ERASURE_NOT_APPROVED", "An approved request without a legal hold is required."
            )
        from .references import reference_lock

        reference_lock(db, p.organization_id)
        plan, sha = erasure_plan(db, target)
        record.result = {
            **record.result,
            "plan": plan,
            "plan_sha256": sha,
            "object_versions_planned": len(plan["objects"]),
            "shared_keys_preserved": plan["shared_keys_preserved"],
        }
        audit(db, p, request, "erasure.plan.prepared", record.id)
        db.flush()
        return commit(db, request, {**public_erasure(record), "confirm_dataset_name": target.name}, 200)

    @app.post("/v1/governance/erasures/{erasure_id}/execute", tags=["Governance"], status_code=202)
    def execute_erasure(erasure_id: str, body: ErasureExecute, request: Request, p: Auth, db: DB):
        p.require("governance:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        record = locked_erasure(db, erasure_id, p)
        target = get(db, Dataset, record.dataset_id, p.organization_id)
        reject_active_schedules(db, target)
        if (
            record.status != "APPROVED"
            or record.ready_after > now()
            or target.legal_hold
            or body.confirm_dataset_name != target.name
        ):
            raise Problem(
                409,
                "ERASURE_NOT_READY",
                "Check the independent approval, delay, legal hold and exact dataset-name confirmation.",
            )
        if db.scalar(
            select(func.count())
            .select_from(Run)
            .where(
                Run.dataset_id == target.id,
                Run.organization_id == p.organization_id,
                Run.status.not_in(["SUCCEEDED", "FAILED", "CANCELLED"]),
            )
        ):
            raise Problem(409, "DATASET_BUSY", "Cancel or finish active runs before erasing artifacts.")
        versions = select(Version.id).where(
            Version.dataset_id == target.id, Version.organization_id == p.organization_id
        )
        if db.scalar(
            select(func.count())
            .select_from(ComputeJob)
            .where(
                ComputeJob.version_id.in_(versions),
                ComputeJob.organization_id == p.organization_id,
                ComputeJob.status.in_(["QUEUED", "LEASED"]),
            )
        ):
            raise Problem(409, "DATASET_BUSY", "Cancel or finish queued/leased compute jobs before erasure.")
        from .references import reference_lock

        reference_lock(db, p.organization_id)
        plan, sha = erasure_plan(db, target)
        if sha != body.plan_sha256 or record.result.get("plan_sha256") != sha:
            raise Problem(
                409,
                "ERASURE_PLAN_CHANGED",
                "Artifacts changed after preview. Prepare and review a fresh plan.",
            )
        target.erased_at, target.archived = now(), True
        target.governance_revision += 1
        record.status = "ERASING"
        record.result = {**record.result, "plan": plan, "object_versions_processed": 0}
        db.add(
            Outbox(
                id=uid("obx"),
                organization_id=p.organization_id,
                kind="erasure",
                resource_id=record.id,
                payload={"erasure_id": record.id},
            )
        )
        audit(db, p, request, "erasure.started", record.id)
        db.flush()
        return commit(db, request, public_erasure(record), 202)

    @app.post("/v1/governance/erasures/{erasure_id}/retry", tags=["Governance"], status_code=202)
    def retry_erasure(erasure_id: str, request: Request, p: Auth, db: DB):
        p.require("governance:manage")
        if cached := replay(db, p, request, {}):
            return cached
        record = locked_erasure(db, erasure_id, p, include_erased=True)
        if record.status != "ERASURE_FAILED":
            raise Problem(
                409, "ERASURE_NOT_RETRYABLE", "Only a failed physical erasure can resume its sealed plan."
            )
        record.status = "ERASING"
        db.add(
            Outbox(
                id=uid("obx"),
                organization_id=p.organization_id,
                kind="erasure",
                resource_id=record.id,
                payload={"erasure_id": record.id},
            )
        )
        audit(db, p, request, "erasure.retry", record.id)
        db.flush()
        return commit(db, request, public_erasure(record), 202)
