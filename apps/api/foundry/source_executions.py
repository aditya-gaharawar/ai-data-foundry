"""Durable accepted source artifacts for real model and renderer executions."""

import json

from sqlalchemy import select

from .db import Session, uid
from .errors import Problem
from .models import ProviderConnection, Run, RunEvent, Usage
from .providers import ImageGenerateConfig, TeacherConfig, infer_local, require_provider
from .security import canonical, digest
from .simulations import SimulationConfig, render_scene
from .storage import put_immutable, read_artifact


def prepare_source(run_id, organization_id, node, heartbeat):
    from .references import reference_guard

    with reference_guard(organization_id):
        return _prepare_source(run_id, organization_id, node, heartbeat)


def _prepare_source(run_id, organization_id, node, heartbeat):
    with Session() as db:
        run = db.scalar(select(Run).where(Run.id == run_id, Run.organization_id == organization_id))
        if run.checkpoint.get("source_artifact"):
            return json.loads(read_artifact(run.checkpoint["source_artifact"]))

    def cancelled():
        with Session() as db:
            run = db.scalar(select(Run).where(Run.id == run_id, Run.organization_id == organization_id))
            if run.cancel_requested or run.status in {"FAILED", "CANCELLED"}:
                return True
            if node["type"] in {"teacher", "image_generate"}:
                provider = db.scalar(
                    select(ProviderConnection).where(
                        ProviderConnection.id == node["config"]["connection_id"],
                        ProviderConnection.organization_id == organization_id,
                    )
                )
                if not provider or provider.revoked:
                    raise Problem(
                        403, "PROVIDER_REVOKED", "The provider connection was revoked during execution."
                    )
            return False

    if node["type"] in {"teacher", "image_generate"}:
        config = (
            (TeacherConfig if node["type"] == "teacher" else ImageGenerateConfig)
            .model_validate(node["config"])
            .model_dump()
        )
        with Session() as db:
            provider = db.scalar(
                select(ProviderConnection).where(
                    ProviderConnection.id == config["connection_id"],
                    ProviderConnection.organization_id == organization_id,
                )
            )
            if not provider:
                raise Problem(404, "NOT_FOUND", "Provider connection not found.")
            require_provider(provider, "structured_text" if node["type"] == "teacher" else "image")
            rights, provider_id = provider.rights, provider.id
        result = infer_local(config, heartbeat, cancelled)
        prepared = {
            "samples": [
                {"payload": sample, "review_status": "UNREVIEWED_MODEL"} for sample in result["samples"]
            ],
            "metadata": {
                "engine": "local.llama.cpp@0.3.19",
                "connection_id": provider_id,
                "model": result["model"],
                "rights": rights,
                "usage": result["usage"],
                "duration_ms": result["duration_ms"],
                "instructions_sha256": digest(config["instructions"]),
                "verification": "JSON schema only; not factual accuracy",
                "external_cost_usd": 0,
            },
        }
    else:
        config = SimulationConfig.model_validate(node["config"]).model_dump()
        prepared = render_scene(config, organization_id, heartbeat, cancelled)
    artifact = put_immutable(organization_id, canonical(prepared), "application/json")
    with Session.begin() as db:
        run = db.scalar(
            select(Run).where(Run.id == run_id, Run.organization_id == organization_id).with_for_update()
        )
        if run.cancel_requested:
            raise Problem(409, "CANCELLED", "Source completion was cancelled before acceptance.")
        if run.checkpoint.get("source_artifact"):
            return json.loads(read_artifact(run.checkpoint["source_artifact"]))
        run.checkpoint = {
            **run.checkpoint,
            "source_artifact": artifact,
            "source_metadata": prepared["metadata"],
        }
        db.add(
            RunEvent(
                id=uid("log"),
                organization_id=organization_id,
                run_id=run_id,
                event_type="source.accepted",
                message="Real source output persisted with engine provenance and checksums.",
                data={"artifact_sha256": artifact["sha256"], "engine": prepared["metadata"]["engine"]},
            )
        )
        for metric, quantity in prepared["metadata"].get("usage", {}).items():
            db.add(
                Usage(
                    id=uid("use"),
                    organization_id=organization_id,
                    run_id=run_id,
                    metric="provider_accepted_" + metric,
                    quantity=quantity,
                    dedupe_key="accepted-source",
                )
            )
        db.add(
            Usage(
                id=uid("use"),
                organization_id=organization_id,
                run_id=run_id,
                metric="source_execution_ms",
                quantity=prepared["metadata"]["duration_ms"],
                dedupe_key="accepted-source",
            )
        )
    return prepared
