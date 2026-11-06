"""Local operational evidence. Signatures attest to this operator, not an external audit."""

import hashlib
import hmac
from datetime import timedelta
from pathlib import Path
from typing import Literal

from fastapi import Request
from pydantic import Field
from sqlalchemy import func, select

from .config import settings
from .db import now, uid
from .errors import Problem
from .models import (
    ComputeAgent,
    Heartbeat,
    Incident,
    OperationalProof,
    Organization,
    ReadinessReport,
    Reconciliation,
    Run,
    Usage,
)
from .schemas import Strict
from .security import canonical


def source_fingerprint():
    root = Path(__file__).resolve().parents[3]
    paths = []
    for folder in (
        "apps/api",
        "apps/web/src",
        "packages/sdk-python",
        "packages/sdk-ts/src",
        "scripts",
        "tests",
        "contracts",
        "infra",
        ".github/workflows",
    ):
        paths.extend(
            path
            for path in (root / folder).rglob("*")
            if path.is_file()
            and path.suffix
            in {".py", ".ts", ".tsx", ".css", ".json", ".yml", ".yaml", ".toml", ".ini", ".Dockerfile"}
            and "__pycache__" not in path.parts
        )
    paths += [
        root / name
        for name in (
            "uv.lock",
            "pnpm-lock.yaml",
            "pyproject.toml",
            "docker-compose.yml",
            "Makefile",
            "package.json",
            "pnpm-workspace.yaml",
            "alembic.ini",
            "playwright.config.ts",
            "apps/web/package.json",
            "apps/web/next.config.ts",
            "apps/web/postcss.config.mjs",
            "apps/web/tsconfig.json",
            "packages/sdk-ts/package.json",
            "packages/sdk-ts/tsconfig.json",
        )
        if (root / name).is_file()
    ]
    result = hashlib.sha256()
    for path in sorted(set(paths)):
        result.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    return result.hexdigest()


def sign_proof(kind, source_sha256, report):
    return hmac.new(
        settings().app_secret.encode(),
        canonical({"kind": kind, "source_sha256": source_sha256, "report": report}),
        "sha256",
    ).hexdigest()


class ProofImport(Strict):
    kind: Literal["restore", "load", "security", "regression", "rollback"]
    source_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    report: dict
    operator_signature: str = Field(pattern="^[a-f0-9]{64}$")


def reconcile(db, organization_id):
    # One organization lock provides a consistent view with reservation/spend writes.
    org = db.scalar(select(Organization).where(Organization.id == organization_id).with_for_update())
    runs = db.scalars(select(Run).where(Run.organization_id == organization_id)).all()
    rows = db.execute(
        select(Usage.run_id, func.sum(Usage.internal_cost_micro), func.sum(Usage.external_cost_micro))
        .where(Usage.organization_id == organization_id)
        .group_by(Usage.run_id)
    ).all()
    ledger = {run_id: (int(internal or 0), int(external or 0)) for run_id, internal, external in rows}
    discrepancies = []
    for run in runs:
        recorded = ledger.get(run.id, (0, 0))[0]
        if recorded != run.spent_micro:
            discrepancies.append(
                {
                    "resource_id": run.id,
                    "metric": "internal_spend_micro",
                    "ledger": recorded,
                    "balance": run.spent_micro,
                }
            )
        if run.status in {"SUCCEEDED", "FAILED", "CANCELLED"} and run.reserved_micro:
            discrepancies.append(
                {
                    "resource_id": run.id,
                    "metric": "terminal_reservation_micro",
                    "expected": 0,
                    "balance": run.reserved_micro,
                }
            )
    spent, reserved = sum(run.spent_micro for run in runs), sum(run.reserved_micro for run in runs)
    for metric, actual, expected in (
        ("organization_spend_micro", org.spent_micro, spent),
        ("organization_reservation_micro", org.reserved_micro, reserved),
    ):
        if actual != expected:
            discrepancies.append(
                {"resource_id": org.id, "metric": metric, "expected": expected, "balance": actual}
            )
    return {
        "status": "PASS" if not discrepancies else "FAIL",
        "run_count": len(runs),
        "ledger_internal_micro": sum(v[0] for v in ledger.values()),
        "ledger_external_micro": sum(v[1] for v in ledger.values()),
        "organization_spent_micro": org.spent_micro,
        "organization_reserved_micro": org.reserved_micro,
        "discrepancies": discrepancies,
        "billing_status": "UNBILLED_LOCAL",
        "changes_applied": False,
        "recorded_at": now().isoformat(),
    }


def readiness(db, org):
    fingerprint = source_fingerprint()
    heartbeat = db.get(Heartbeat, "cpu")
    fresh = bool(heartbeat and heartbeat.seen_at > now() - timedelta(seconds=20))
    checks = [{"gate": "durable_local_worker", "state": "PASS" if fresh else "FAIL"}]
    scheduler = db.get(Heartbeat, "scheduler")
    checks.append(
        {
            "gate": "bounded_schedule_worker",
            "state": "PASS" if scheduler and scheduler.seen_at > now() - timedelta(seconds=20) else "FAIL",
        }
    )
    ledger = reconcile(db, org)
    checks.append({"gate": "ledger_reconciliation", "state": ledger["status"]})
    for kind in ("restore", "load", "security", "regression", "rollback"):
        proof = db.scalar(
            select(OperationalProof)
            .where(
                OperationalProof.organization_id == org,
                OperationalProof.kind == kind,
                OperationalProof.source_sha256 == fingerprint,
                OperationalProof.created_at > now() - timedelta(days=1),
            )
            .order_by(OperationalProof.created_at.desc())
        )
        checks.append(
            {
                "gate": "local_" + kind,
                "state": proof.report.get("status", "FAIL") if proof else "MISSING",
                "proof_id": proof.id if proof else None,
            }
        )
    external = [
        {"gate": name, "state": "BLOCKED_EXTERNAL", "reason": reason}
        for name, reason in (
            (
                "staging_release_and_rollback",
                "No approved staging target, release identity or demonstration is configured.",
            ),
            (
                "production_identity",
                "SSO/IdP and hardened production session deployment are unconfigured; auth is local only.",
            ),
            (
                "independent_security_review",
                "No independent penetration test or audit has been commissioned.",
            ),
            (
                "optional_native_dependency_advisory",
                "The optional local model wrapper includes an unfixed diskcache pickle advisory. Disk caching is refused and unreachable in this app; remove/replace the dependency before production.",
            ),
            (
                "external_compute_and_providers",
                "Paid model providers, Kubernetes/Kueue, Slurm and certified RTX Isaac runtimes are unconfigured.",
            ),
            ("remote_ci_and_review", "No Git remote or hosted CI/reviewer is configured."),
            ("production_sla", "Local bounded measurements cannot establish a production availability SLA."),
        )
    ]
    status = (
        "LOCAL_CHECKS_PASSED" if all(row["state"] == "PASS" for row in checks) else "LOCAL_CHECKS_INCOMPLETE"
    )
    report = {
        "status": status,
        "source_sha256": fingerprint,
        "recorded_at": now().isoformat(),
        "checks": checks,
        "release_gates": external,
        "production_release": "BLOCKED_EXTERNAL",
        "scope": "local synthetic-data validation; no compliance or scientific-performance certification",
    }
    report["operator_signature"] = sign_proof("readiness", fingerprint, report)
    return report


def register(app):
    from .api import DB, Auth, audit, commit, get, page, public, replay

    @app.get("/v1/operations/status", tags=["Operations"])
    def operations_status(p: Auth, db: DB):
        p.require("operations:manage")
        return {
            "source_sha256": source_fingerprint(),
            "environment": "local",
            "identity_provider": "BLOCKED_EXTERNAL",
            "external_billing": "UNBILLED_LOCAL",
            "maintenance": Path(".local/maintenance.json").exists(),
            "readiness": readiness(db, p.organization_id),
        }

    @app.post("/v1/operations/reconciliations", tags=["Operations"], status_code=201)
    def create_reconciliation(request: Request, p: Auth, db: DB):
        p.require("operations:manage")
        if cached := replay(db, p, request, {}):
            return cached
        row = Reconciliation(
            id=uid("rec"),
            organization_id=p.organization_id,
            report=reconcile(db, p.organization_id),
            created_by=p.user_id,
        )
        db.add(row)
        audit(db, p, request, "ledger.reconciled", row.id)
        db.flush()
        return commit(db, request, public(row))

    @app.get("/v1/operations/reconciliations", tags=["Operations"])
    def reconciliations(p: Auth, db: DB):
        p.require("operations:manage")
        return page(db, Reconciliation, p, 100)

    @app.post("/v1/operations/incidents/scan", tags=["Operations"])
    def scan_incidents(request: Request, p: Auth, db: DB):
        p.require("operations:manage")
        if cached := replay(db, p, request, {}):
            return cached
        db.scalar(select(Organization).where(Organization.id == p.organization_id).with_for_update())
        sources = [
            ("run:" + row.id, "Run failed: " + (row.error or "Inspect its run events."))
            for row in db.scalars(
                select(Run)
                .where(Run.organization_id == p.organization_id, Run.status == "FAILED")
                .order_by(Run.created_at.desc())
                .limit(100)
            )
        ]
        sources += [
            ("agent:" + row.id, "Agent heartbeat expired; leases can be retried by another compatible agent.")
            for row in db.scalars(
                select(ComputeAgent).where(
                    ComputeAgent.organization_id == p.organization_id,
                    ComputeAgent.revoked.is_(False),
                    ComputeAgent.seen_at < now() - timedelta(seconds=20),
                )
            )
        ]
        added = 0
        for reference, summary in sources:
            if not db.scalar(
                select(Incident.id).where(
                    Incident.organization_id == p.organization_id, Incident.source_ref == reference
                )
            ):
                db.add(
                    Incident(
                        id=uid("inc"),
                        organization_id=p.organization_id,
                        source_ref=reference,
                        summary=summary[:400],
                    )
                )
                added += 1
        audit(db, p, request, "incidents.scanned", p.organization_id)
        return commit(db, request, {"new_incidents": added}, 200)

    @app.get("/v1/operations/incidents", tags=["Operations"])
    def incidents(p: Auth, db: DB):
        p.require("operations:manage")
        return page(db, Incident, p, 100)

    @app.post("/v1/operations/incidents/{incident_id}/acknowledge", tags=["Operations"])
    def acknowledge_incident(incident_id: str, request: Request, p: Auth, db: DB):
        p.require("operations:manage")
        if cached := replay(db, p, request, {}):
            return cached
        row = get(db, Incident, incident_id, p.organization_id)
        row.status, row.acknowledged_by, row.acknowledged_at = "ACKNOWLEDGED", p.user_id, now()
        audit(db, p, request, "incident.acknowledged", row.id)
        db.flush()
        return commit(db, request, public(row), 200)

    @app.post("/v1/operations/proofs", tags=["Operations"], status_code=201)
    def import_proof(body: ProofImport, request: Request, p: Auth, db: DB):
        p.require("operations:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        if not hmac.compare_digest(
            body.operator_signature, sign_proof(body.kind, body.source_sha256, body.report)
        ):
            raise Problem(403, "INVALID_OPERATOR_PROOF", "This proof was not signed by the local operator.")
        if body.source_sha256 != source_fingerprint():
            raise Problem(
                409,
                "STALE_OPERATOR_PROOF",
                "The source changed after this evidence was measured. Rerun the check.",
            )
        if body.report.get("status") not in {"PASS", "FAIL"} or body.report.get("scope") != "local":
            raise Problem(422, "INVALID_OPERATOR_PROOF", "A measured local PASS/FAIL report is required.")
        row = OperationalProof(id=uid("prf"), organization_id=p.organization_id, **body.model_dump())
        db.add(row)
        audit(db, p, request, "operational.proof.imported", row.id)
        db.flush()
        return commit(db, request, public(row))

    @app.get("/v1/operations/proofs", tags=["Operations"])
    def proofs(p: Auth, db: DB):
        p.require("operations:manage")
        return page(db, OperationalProof, p, 100)

    @app.post("/v1/operations/readiness", tags=["Operations"], status_code=201)
    def create_readiness(request: Request, p: Auth, db: DB):
        p.require("operations:manage")
        if cached := replay(db, p, request, {}):
            return cached
        report = readiness(db, p.organization_id)
        row = ReadinessReport(
            id=uid("rdy"),
            organization_id=p.organization_id,
            status=report["status"],
            report=report,
            created_by=p.user_id,
        )
        db.add(row)
        audit(db, p, request, "readiness.signed", row.id)
        db.flush()
        return commit(db, request, public(row))

    @app.get("/v1/operations/readiness", tags=["Operations"])
    def readiness_reports(p: Auth, db: DB):
        p.require("operations:manage")
        return page(db, ReadinessReport, p, 25)
