"""Outbound agents, scoped artifact jobs, leases and honest capability placement."""

import hmac
import math
import os
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, Query, Request, Response
from pydantic import BaseModel, Field, FiniteFloat
from sqlalchemy import func, select

from .db import now, session, uid
from .errors import Problem
from .models import ComputeAgent, ComputeJob, ComputePool, Dataset, Version
from .schemas import Strict
from .security import digest, rate_limit
from .storage import read_artifact


class Accelerator(Strict):
    model: str = Field(min_length=1, max_length=100)
    count: int = Field(default=1, ge=1, le=16)
    memory_gib: FiniteFloat = Field(default=0, ge=0, le=512)
    rt_cores: bool = False


class Capabilities(Strict):
    cpu_cores: int = Field(default=1, ge=1, le=1024)
    memory_gib: FiniteFloat = Field(default=1, ge=0.25, le=4096)
    accelerators: list[Accelerator] = Field(default_factory=list, max_length=16)
    engines: dict[str, str] = Field(default_factory=lambda: {"artifact.verify@1": "1"})


class PoolCreate(Strict):
    name: str = Field(min_length=1, max_length=160)
    scheduler: Literal["agent", "kubernetes", "slurm"] = "agent"
    capabilities: Capabilities = Field(default_factory=Capabilities)


class AgentCreate(Strict):
    pool_id: str
    name: str = Field(min_length=1, max_length=160)


class Placement(Strict):
    pool_id: str
    engine: Literal["artifact.verify@1", "blender.procedural@1", "isaac.sim", "isaac.lab"]
    cpu_cores: int = Field(default=1, ge=1, le=1024)
    memory_gib: FiniteFloat = Field(default=0.5, ge=0.25, le=4096)


class ComputeJobCreate(Strict):
    pool_id: str
    version_id: str
    kind: Literal["artifact.verify@1"] = "artifact.verify@1"
    cpu_cores: int = Field(default=1, ge=1, le=8)
    memory_gib: FiniteFloat = Field(default=0.5, ge=0.25, le=16)
    lease_seconds: int = Field(default=30, ge=2, le=60)


class LeaseComplete(Strict):
    attempt: int = Field(ge=1)
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    bytes: int = Field(ge=1)
    processing_ms: int = Field(ge=0, le=60000)


class ResourceOut(BaseModel):
    id: str
    organization_id: str
    name: str | None = None
    state: str | None = None
    status: str | None = None
    capabilities: dict | None = None
    reason: str | None = None
    agent_token: str | None = None
    result: dict | None = None


def local_inventory():
    cores = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count() or 1
    memory = 1.0
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota != "max":
            cores = min(cores, max(1, math.ceil(int(quota) / int(period))))
        limit = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        if limit != "max":
            memory = int(limit) / 1024**3
    except (OSError, ValueError):
        pass
    return {
        "cpu_cores": cores,
        "memory_gib": memory,
        "accelerators": [],
        "engines": {"artifact.verify@1": "1"},
    }


def compatibility(capabilities, requirements):
    spec = Capabilities.model_validate(capabilities)
    engine = requirements["engine"]
    if engine.startswith("isaac"):
        suitable = [
            gpu
            for gpu in spec.accelerators
            if gpu.rt_cores
            and not any(name in gpu.model.upper() for name in ("H100", "H200", "A100", "A800"))
        ]
        if not suitable:
            return (
                False,
                "An RTX GPU with RT cores is required; H100/H200/A100 devices cannot render Isaac scenes.",
            )
    if spec.cpu_cores < requirements["cpu_cores"] or spec.memory_gib < requirements["memory_gib"]:
        return False, "CPU or memory capacity is below the requested resources."
    if engine not in spec.engines:
        return False, "The required engine/version is not advertised by this approved pool/agent."
    if engine.startswith("isaac"):
        return False, "No operator-validated Isaac release/driver/container runtime is configured."
    return True, "Resource and engine requirements match the configured capability inventory."


def expire_leases(db, org):
    rows = db.scalars(
        select(ComputeJob)
        .where(
            ComputeJob.organization_id == org,
            ComputeJob.status == "LEASED",
            ComputeJob.lease_expires_at < now(),
        )
        .with_for_update(skip_locked=True)
    ).all()
    for job in rows:
        job.status = "QUEUED" if job.attempt < 3 else "FAILED"
        job.error = (
            "Lease expired; retrying with a fresh fencing token."
            if job.attempt < 3
            else "Agent lease retries exhausted."
        )
        job.lease_secret_hash, job.lease_agent_id, job.lease_expires_at = None, None, None
        if job.status == "FAILED":
            job.finished_at = now()


def agent_auth(request: Request, db=Depends(session)):
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer foundry_agent_"):
        raise Problem(401, "AGENT_UNAUTHENTICATED", "A scoped enrolled agent token is required.")
    agent = db.scalar(
        select(ComputeAgent)
        .where(ComputeAgent.secret_hash == digest(authorization[7:]), ComputeAgent.revoked.is_(False))
        .with_for_update()
    )
    if not agent:
        raise Problem(401, "AGENT_UNAUTHENTICATED", "The agent is unavailable or revoked.")
    pool = db.scalar(
        select(ComputePool).where(
            ComputePool.id == agent.pool_id,
            ComputePool.organization_id == agent.organization_id,
            ComputePool.enabled.is_(True),
        )
    )
    if not pool:
        raise Problem(403, "POOL_DISABLED", "This agent's compute pool is disabled.")
    rate_limit("agent:" + agent.id, 240)
    return agent


def register(app):
    from .api import DB, Auth, audit, commit, get, page, public, replay

    AgentAuth = Annotated[ComputeAgent, Depends(agent_auth)]

    def active_pool(db, pool):
        active = db.scalar(
            select(func.count())
            .select_from(ComputeAgent)
            .where(
                ComputeAgent.pool_id == pool.id,
                ComputeAgent.organization_id == pool.organization_id,
                ComputeAgent.revoked.is_(False),
                ComputeAgent.seen_at > now() - timedelta(seconds=20),
            )
        )
        return {
            **public(pool),
            "state": "READY"
            if pool.scheduler == "agent" and active
            else "BLOCKED_EXTERNAL"
            if pool.scheduler != "agent"
            else "NO_ACTIVE_AGENTS",
            "active_agents": active,
            "reason": "Approved outbound agents are reporting heartbeats."
            if active and pool.scheduler == "agent"
            else "No approved external scheduler connection is configured."
            if pool.scheduler != "agent"
            else "Enroll and start an agent; no work is simulated.",
        }

    @app.get("/v1/compute/registered-pools", tags=["Compute"])
    def registered_pools(p: Auth, db: DB, limit: int = Query(25, ge=1, le=100), cursor: str | None = None):
        p.require("datasets:read")
        result = page(db, ComputePool, p, limit, cursor)
        result["items"] = [
            active_pool(db, get(db, ComputePool, item["id"], p.organization_id)) for item in result["items"]
        ]
        return result

    @app.post("/v1/compute/registered-pools", tags=["Compute"], response_model=ResourceOut, status_code=201)
    def create_compute_pool(body: PoolCreate, request: Request, p: Auth, db: DB):
        p.require("compute:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        pool = ComputePool(
            id=uid("pool"),
            organization_id=p.organization_id,
            name=body.name,
            scheduler=body.scheduler,
            capabilities=body.capabilities.model_dump(),
        )
        db.add(pool)
        audit(db, p, request, "compute.pool.created", pool.id)
        db.flush()
        return commit(db, request, active_pool(db, pool))

    @app.get("/v1/compute/agents", tags=["Compute"])
    def compute_agents(p: Auth, db: DB, limit: int = Query(25, ge=1, le=100), cursor: str | None = None):
        p.require("datasets:read")
        return page(db, ComputeAgent, p, limit, cursor)

    @app.post("/v1/compute/agents", tags=["Compute"], status_code=201)
    def enroll_agent(body: AgentCreate, request: Request, p: Auth, db: DB):
        p.require("compute:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        pool = get(db, ComputePool, body.pool_id, p.organization_id)
        if pool.scheduler != "agent":
            raise Problem(
                409, "BLOCKED_EXTERNAL", "A scheduler-backed pool needs its approved external integration."
            )
        token = "foundry_agent_" + secrets.token_urlsafe(36)
        agent = ComputeAgent(
            id=uid("agt"),
            organization_id=p.organization_id,
            pool_id=pool.id,
            name=body.name,
            secret_hash=digest(token),
        )
        db.add(agent)
        audit(db, p, request, "compute.agent.enrolled", agent.id)
        db.flush()
        return commit(db, request, {**public(agent), "agent_token": token}, stored=public(agent))

    @app.post("/v1/compute/agents/{agent_id}/revoke", tags=["Compute"])
    def revoke_agent(agent_id: str, request: Request, p: Auth, db: DB):
        p.require("compute:manage")
        if cached := replay(db, p, request, {}):
            return cached
        agent = get(db, ComputeAgent, agent_id, p.organization_id)
        agent.revoked = True
        audit(db, p, request, "compute.agent.revoked", agent.id)
        db.flush()
        return commit(db, request, public(agent), 200)

    @app.post("/v1/compute/placement", tags=["Compute"])
    def placement(body: Placement, p: Auth, db: DB):
        p.require("datasets:read")
        pool = get(db, ComputePool, body.pool_id, p.organization_id)
        allowed, reason = compatibility(pool.capabilities, body.model_dump())
        agents = db.scalars(
            select(ComputeAgent).where(
                ComputeAgent.pool_id == pool.id,
                ComputeAgent.organization_id == p.organization_id,
                ComputeAgent.revoked.is_(False),
                ComputeAgent.seen_at > now() - timedelta(seconds=20),
            )
        ).all()
        eligible = (
            [agent.id for agent in agents if compatibility(agent.capabilities, body.model_dump())[0]]
            if allowed
            else []
        )
        return {
            "eligible": bool(eligible) and pool.scheduler == "agent",
            "eligible_agent_ids": eligible,
            "reason": reason
            if not allowed
            else "No compatible active agent is available."
            if not eligible
            else reason,
            "state": "READY" if eligible and pool.scheduler == "agent" else "BLOCKED_EXTERNAL",
        }

    @app.post("/v1/compute/jobs", tags=["Compute"], status_code=202)
    def create_compute_job(body: ComputeJobCreate, request: Request, p: Auth, db: DB):
        p.require("runs:execute")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        pool = get(db, ComputePool, body.pool_id, p.organization_id)
        version = get(db, Version, body.version_id, p.organization_id)
        target = get(db, Dataset, version.dataset_id, p.organization_id)
        if target.protection == "holdout":
            raise Problem(403, "HOLDOUT_PROTECTED", "Generic compute agents cannot read held-out solutions.")
        requirements = {
            "engine": body.kind,
            "cpu_cores": body.cpu_cores,
            "memory_gib": body.memory_gib,
            "lease_seconds": body.lease_seconds,
        }
        compatible, reason = compatibility(pool.capabilities, requirements)
        if pool.scheduler != "agent" or not pool.enabled or not compatible:
            raise Problem(
                409,
                "COMPUTE_INCOMPATIBLE",
                reason if not compatible else "An enabled approved outbound-agent pool is required.",
            )
        job = ComputeJob(
            id=uid("cjob"),
            organization_id=p.organization_id,
            pool_id=pool.id,
            version_id=version.id,
            kind=body.kind,
            requirements=requirements,
        )
        db.add(job)
        audit(db, p, request, "compute.job.queued", job.id)
        db.flush()
        return commit(
            db, request, {**public(job), "external_cost_usd": 0, "billing_status": "UNBILLED_LOCAL"}, 202
        )

    @app.get("/v1/compute/jobs", tags=["Compute"])
    def compute_jobs(p: Auth, db: DB, limit: int = Query(25, ge=1, le=100), cursor: str | None = None):
        p.require("datasets:read")
        expire_leases(db, p.organization_id)
        db.commit()
        return page(db, ComputeJob, p, limit, cursor)

    @app.get("/v1/compute/jobs/{job_id}", tags=["Compute"])
    def compute_job(job_id: str, p: Auth, db: DB):
        p.require("datasets:read")
        expire_leases(db, p.organization_id)
        db.commit()
        return public(get(db, ComputeJob, job_id, p.organization_id))

    @app.post("/v1/compute/jobs/{job_id}/cancel", tags=["Compute"])
    def cancel_compute_job(job_id: str, request: Request, p: Auth, db: DB):
        p.require("runs:execute")
        if cached := replay(db, p, request, {}):
            return cached
        job = get(db, ComputeJob, job_id, p.organization_id)
        job = db.scalar(
            select(ComputeJob)
            .where(ComputeJob.id == job.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if job.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            raise Problem(409, "JOB_TERMINAL", "This compute job is already terminal.")
        job.status, job.finished_at, job.lease_secret_hash = "CANCELLED", now(), None
        audit(db, p, request, "compute.job.cancelled", job.id)
        db.flush()
        return commit(db, request, public(job), 200)

    @app.post("/v1/compute/agent/heartbeat", tags=["Agent protocol"])
    def agent_heartbeat(body: Capabilities, agent: AgentAuth, db: DB):
        agent.capabilities, agent.seen_at = body.model_dump(), now()
        db.commit()
        return {"agent_id": agent.id, "heartbeat_interval_seconds": 5}

    @app.post("/v1/compute/agent/claim", tags=["Agent protocol"])
    def agent_claim(agent: AgentAuth, db: DB):
        pool = db.scalar(
            select(ComputePool)
            .where(ComputePool.id == agent.pool_id, ComputePool.organization_id == agent.organization_id)
            .with_for_update()
        )
        expire_leases(db, agent.organization_id)
        if not agent.seen_at or agent.seen_at < now() - timedelta(seconds=20):
            raise Problem(
                409, "HEARTBEAT_REQUIRED", "Send a current capability heartbeat before claiming work."
            )
        active = db.scalars(
            select(ComputeJob).where(
                ComputeJob.pool_id == pool.id,
                ComputeJob.organization_id == agent.organization_id,
                ComputeJob.status == "LEASED",
            )
        ).all()
        used_cpu = sum(job.requirements["cpu_cores"] for job in active)
        used_memory = sum(job.requirements["memory_gib"] for job in active)
        if db.scalar(
            select(func.count())
            .select_from(ComputeJob)
            .where(ComputeJob.lease_agent_id == agent.id, ComputeJob.status == "LEASED")
        ):
            return {"job": None, "reason": "This agent already holds a live lease."}
        rows = db.scalars(
            select(ComputeJob)
            .where(
                ComputeJob.organization_id == agent.organization_id,
                ComputeJob.pool_id == pool.id,
                ComputeJob.status == "QUEUED",
            )
            .order_by(ComputeJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(20)
        ).all()
        for job in rows:
            if (
                used_cpu + job.requirements["cpu_cores"] > pool.capabilities["cpu_cores"]
                or used_memory + job.requirements["memory_gib"] > pool.capabilities["memory_gib"]
            ):
                continue
            if not compatibility(agent.capabilities, job.requirements)[0]:
                continue
            version = db.scalar(
                select(Version).where(
                    Version.id == job.version_id, Version.organization_id == agent.organization_id
                )
            )
            target = db.scalar(
                select(Dataset).where(
                    Dataset.id == version.dataset_id, Dataset.organization_id == agent.organization_id
                )
            )
            if target.erased_at or target.protection == "holdout":
                job.status, job.error = "FAILED", "Source is erased or protected."
                continue
            token = secrets.token_urlsafe(32)
            job.status, job.lease_agent_id, job.lease_secret_hash = "LEASED", agent.id, digest(token)
            job.attempt += 1
            job.lease_expires_at = now() + timedelta(seconds=job.requirements["lease_seconds"])
            job.result = {"lease_started_at": now().isoformat()}
            agent.seen_at = now()
            db.commit()
            return {
                "job": {
                    "id": job.id,
                    "kind": job.kind,
                    "attempt": job.attempt,
                    "lease_token": token,
                    "expires_at": job.lease_expires_at.isoformat(),
                    "artifact_url": f"/v1/compute/agent/jobs/{job.id}/artifact",
                }
            }
        db.commit()
        return {"job": None}

    def leased(db, agent, job_id, request):
        initial = db.scalar(
            select(ComputeJob).where(
                ComputeJob.id == job_id, ComputeJob.organization_id == agent.organization_id
            )
        )
        if not initial:
            raise Problem(409, "STALE_LEASE", "This lease is unavailable.")
        version = db.scalar(
            select(Version).where(
                Version.id == initial.version_id, Version.organization_id == agent.organization_id
            )
        )
        target = db.scalar(
            select(Dataset)
            .where(Dataset.id == version.dataset_id, Dataset.organization_id == agent.organization_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if target.erased_at or target.protection == "holdout":
            raise Problem(
                403, "COMPUTE_SOURCE_PROTECTED", "Agents cannot consume erased or held-out solutions."
            )
        job = db.scalar(
            select(ComputeJob)
            .where(ComputeJob.id == job_id, ComputeJob.organization_id == agent.organization_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        supplied = digest(request.headers.get("x-lease-token", ""))
        if (
            not job
            or job.status != "LEASED"
            or job.lease_agent_id != agent.id
            or not job.lease_secret_hash
            or not hmac.compare_digest(supplied, job.lease_secret_hash)
            or job.lease_expires_at <= now()
        ):
            raise Problem(
                409, "STALE_LEASE", "The lease expired, was replaced, cancelled or belongs to another agent."
            )
        return job

    @app.get("/v1/compute/agent/jobs/{job_id}/artifact", tags=["Agent protocol"])
    def agent_artifact(job_id: str, request: Request, agent: AgentAuth, db: DB):
        job = leased(db, agent, job_id, request)
        version = db.scalar(
            select(Version).where(
                Version.id == job.version_id, Version.organization_id == agent.organization_id
            )
        )
        data = read_artifact(version.manifest["data_artifact"])
        return Response(data, media_type="application/x-ndjson", headers={"X-Content-SHA256": digest(data)})

    @app.post("/v1/compute/agent/jobs/{job_id}/renew", tags=["Agent protocol"])
    def renew_agent_lease(job_id: str, request: Request, agent: AgentAuth, db: DB):
        job = leased(db, agent, job_id, request)
        job.lease_expires_at = now() + timedelta(seconds=job.requirements["lease_seconds"])
        agent.seen_at = now()
        db.commit()
        return {"expires_at": job.lease_expires_at.isoformat()}

    @app.post("/v1/compute/agent/jobs/{job_id}/complete", tags=["Agent protocol"])
    def complete_agent_lease(job_id: str, body: LeaseComplete, request: Request, agent: AgentAuth, db: DB):
        job = leased(db, agent, job_id, request)
        if body.attempt != job.attempt:
            raise Problem(409, "STALE_LEASE", "The result belongs to another attempt.")
        version = db.scalar(
            select(Version).where(
                Version.id == job.version_id, Version.organization_id == agent.organization_id
            )
        )
        data = read_artifact(version.manifest["data_artifact"])
        if body.sha256 != digest(data) or body.bytes != len(data):
            raise Problem(
                422, "COMPUTE_RESULT_MISMATCH", "The result does not match the immutable source artifact."
            )
        job.result = {
            **body.model_dump(),
            "verified_by_api": True,
            "external_cost_usd": 0,
            "duration_source": "agent-reported; nonbillable",
        }
        job.status, job.finished_at, job.lease_secret_hash = "SUCCEEDED", now(), None
        db.commit()
        return {"id": job.id, "status": job.status, "result": job.result}
