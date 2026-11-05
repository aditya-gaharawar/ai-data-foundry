import asyncio
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import httpx
from sqlalchemy import func, select
from temporalio import activity
from temporalio.client import Client
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError
from temporalio.worker import Worker

from .config import settings
from .curation import frozen_input, image_exports
from .db import Session, now, uid
from .errors import Problem
from .media import upload_samples
from .models import (
    Audit,
    Curation,
    Dataset,
    Delivery,
    Export,
    Heartbeat,
    Organization,
    Outbox,
    RecipeRevision,
    Run,
    RunEvent,
    Upload,
    Usage,
    Version,
    Webhook,
)
from .policies import check_publication_policy, pii_transform
from .recipes import GenerateConfig, compile_recipe, generate_text, parse_jsonl, quality_report
from .retention import erase_artifacts, fail_erasure
from .security import canonical, cipher, digest, validate_webhook_url, webhook_signature
from .source_executions import prepare_source
from .storage import put_immutable, read_artifact
from .workflows import ArtifactErasureWorkflow, DatasetWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("foundry.worker")
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}
CODE_DIGEST = digest(
    b"".join(path.name.encode() + path.read_bytes() for path in sorted(Path(__file__).parent.glob("*.py")))
    + Path("uv.lock").read_bytes()
)


def emit(db, run, event_type, data):
    event_id = uid("evt")
    db.add(
        Outbox(
            id=event_id,
            organization_id=run.organization_id,
            kind="event",
            resource_id=run.id,
            payload={
                "event_id": event_id,
                "event_type": event_type,
                "occurred_at": now().isoformat(),
                "schema_version": "1.0",
                "organization_id": run.organization_id,
                "resource_id": run.id,
                "data": data,
            },
        )
    )


def log(db, run, kind, message, data=None):
    db.add(
        RunEvent(
            id=uid("log"),
            organization_id=run.organization_id,
            run_id=run.id,
            event_type=kind,
            message=message,
            data=data or {},
        )
    )
    logger.info(
        json.dumps(
            {"organization_id": run.organization_id, "run_id": run.id, "event_type": kind, "message": message}
        )
    )


def release(db, run):
    org = db.scalar(select(Organization).where(Organization.id == run.organization_id).with_for_update())
    org.reserved_micro -= run.reserved_micro
    run.reserved_micro = 0


def terminate(db, run, state, code, message):
    if run.status in TERMINAL:
        return
    release(db, run)
    run.status, run.error, run.finished_at = state, f"{code}: {message}", now()
    log(db, run, "run.failed" if state == "FAILED" else "run.cancelled", run.error)
    if state == "FAILED":
        emit(db, run, "run.failed", {"run_id": run.id, "code": code})


def owned(db, cls, identifier, org):
    row = db.scalar(select(cls).where(cls.id == identifier, cls.organization_id == org))
    if not row:
        raise Problem(404, "NOT_FOUND", "A required tenant-owned execution resource is unavailable.")
    return row


@activity.defn
def process_run(run_id: str):
    activity.heartbeat("starting")
    try:
        _process(run_id)
    except Problem as error:
        with Session.begin() as db:
            run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
            terminate(
                db, run, "CANCELLED" if error.code == "CANCELLED" else "FAILED", error.code, error.message
            )
        raise ApplicationError(error.code, non_retryable=True) from None


def _process(run_id):
    with Session.begin() as db:
        run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if run.status in TERMINAL:
            return
        if run.cancel_requested:
            raise Problem(409, "CANCELLED", "Cancelled before processing.")
        if not run.started_at:
            run.started_at = now()
            emit(db, run, "run.started", {"run_id": run.id})
        run.status = "RUNNING"
        target = owned(db, Dataset, run.dataset_id, run.organization_id)
        revision = owned(db, RecipeRevision, run.recipe_revision_id, run.organization_id)
        order = compile_recipe(revision.definition)
        governance = check_publication_policy(db, target, order[0]["type"])
        admitted = run.checkpoint.get("admitted_policy", governance)
        if admitted["sha256"] != governance["sha256"]:
            raise Problem(
                409,
                "POLICY_CHANGED",
                "The organization policy changed after admission. Retry under the current policy.",
            )
        policy, schema = target.policy, target.sample_schema
        org_id = run.organization_id
        curated, curation_snapshot = [], None
        deferred = order[0]["type"] in {"teacher", "image_generate", "simulate"}
        if policy.get("allowed_training_use") is not True:
            raise Problem(403, "POLICY_BLOCKED", "Source rights do not permit this operation.")
        if order[0]["type"] == "ingest":
            source = owned(db, Upload, order[0]["config"]["upload_id"], org_id)
            if source.dataset_id != target.id or source.status != "COMPLETED":
                raise Problem(422, "INVALID_SOURCE", "Use a completed upload belonging to this dataset.")
            samples = upload_samples(source)
            origin = {
                "engine": "ingest.image@1" if target.modality == "image" else "ingest.jsonl@1",
                "upload_id": source.id,
                "sha256": source.expected_sha256,
            }
        elif order[0]["type"] == "curate":
            curation = owned(db, Curation, order[0]["config"]["curation_id"], org_id)
            curated, curation_snapshot = frozen_input(curation, target)
            samples = [sample["payload"] for sample in curated]
            origin = {"engine": "curation.human@1", "curation_id": curation.id, "snapshot": curation.snapshot}
        elif deferred:
            samples, origin = [], {}
        else:
            if target.modality != "text":
                raise Problem(
                    422, "CAPABILITY_UNAVAILABLE", "The deterministic generator supports text only."
                )
            config = GenerateConfig.model_validate(order[0]["config"])
            samples = generate_text(config.count, config.seed)
            origin = {"engine": config.engine, "seed": config.seed, "reproducibility": "deterministic"}
        log(db, run, "run.started", "CPU execution started; durable checkpoints enabled.")
    if deferred:
        prepared = prepare_source(run_id, org_id, order[0], lambda: activity.heartbeat("source-execution"))
        curated = prepared["samples"]
        samples = [sample["payload"] for sample in curated]
        origin = prepared["metadata"]
    transformed, pii_report = pii_transform(samples, governance["definition"]["pii_mode"])
    if curation_snapshot and transformed != samples:
        raise Problem(
            409,
            "REVIEW_POLICY_CHANGED",
            "Redaction would change an approved review source. Create and review a new curation under the current policy.",
        )
    samples = transformed
    version_id = "ver_" + run_id.removeprefix("run_")
    for index in range(0, len(samples), 100):
        activity.heartbeat({"offset": index})
        started = time.monotonic()
        with Session.begin() as db:
            run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
            if run.status in TERMINAL:
                return
            if run.cancel_requested:
                raise Problem(409, "CANCELLED", "Cancellation acknowledged at a safe checkpoint.")
            checkpoint = dict(run.checkpoint)
            chunks = list(checkpoint["chunks"])
            chunk_number = index // 100
            if len(chunks) > chunk_number:
                continue
            batch = samples[index : index + 100]
            cost = len(batch) * checkpoint["rate_micro_usd"]
            if cost > run.reserved_micro or run.spent_micro + cost > run.max_budget_micro:
                emit(db, run, "budget.exhausted", {"run_id": run.id})
                raise Problem(402, "BUDGET_EXCEEDED", "Processing stopped before the hard budget cap.")
            envelopes = [
                {
                    "sample_id": curated[index + offset].get(
                        "sample_id", "smp_" + digest(canonical(sample))[:32]
                    )
                    if curated
                    else "smp_" + digest(canonical(sample))[:32],
                    "dataset_version_id": version_id,
                    "schema_version": "1.0",
                    "modality": target.modality,
                    "payload": sample,
                    "source_refs": [
                        *(curated[index + offset].get("source_refs", []) if curated else []),
                        origin,
                    ],
                    "generation_run_id": run_id,
                    "content_hash": digest(canonical(sample)),
                    "license_policy": policy,
                    **(
                        {
                            **(
                                {"annotation": curated[index + offset]["annotation"]}
                                if "annotation" in curated[index + offset]
                                else {}
                            ),
                            **(
                                {"annotation_task_id": curated[index + offset]["annotation_task_id"]}
                                if "annotation_task_id" in curated[index + offset]
                                else {}
                            ),
                            "review_status": curated[index + offset].get("review_status", "UNREVIEWED_MODEL"),
                        }
                        if curated
                        else {}
                    ),
                }
                for offset, sample in enumerate(batch)
            ]
            artifact = put_immutable(
                org_id, b"".join(canonical(value) + b"\n" for value in envelopes), "application/x-ndjson"
            )
            chunks.append(artifact)
            checkpoint["chunks"] = chunks
            run.checkpoint = checkpoint
            run.processed += len(batch)
            org = db.scalar(select(Organization).where(Organization.id == org_id).with_for_update())
            run.reserved_micro -= cost
            run.spent_micro += cost
            org.reserved_micro -= cost
            org.spent_micro += cost
            db.add(
                Usage(
                    id=uid("use"),
                    organization_id=org_id,
                    run_id=run_id,
                    metric="processed_samples",
                    quantity=len(batch),
                    dedupe_key=f"chunk:{chunk_number}",
                    internal_cost_micro=cost,
                )
            )
            db.add(
                Usage(
                    id=uid("use"),
                    organization_id=org_id,
                    run_id=run_id,
                    metric="checkpoint_processing_ms",
                    quantity=round((time.monotonic() - started) * 1000),
                    dedupe_key=f"chunk:{chunk_number}",
                )
            )
            log(
                db,
                run,
                "run.progress",
                f"Checkpoint persisted: {run.processed}/{run.sample_count} samples.",
                {"processed": run.processed},
            )
    activity.heartbeat("verifying")
    report = quality_report(samples, schema, order[1]["config"])
    report["pii"] = pii_report
    if curation_snapshot:
        report["passed"] = report["passed"] and curation_snapshot["quality"]["passed"]
        report["curation"] = curation_snapshot["quality"]
        report["checks"] = list(dict.fromkeys([*report["checks"], *curation_snapshot["quality"]["checks"]]))
        report["limitations"] = curation_snapshot["quality"]["limitations"]
    with Session.begin() as db:
        run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if run.status in TERMINAL:
            return
        run.status, run.quality = "VERIFYING", report
        log(db, run, "run.verifying", "Quality gates evaluated.", report)
        if not report["passed"]:
            terminate(
                db,
                run,
                "FAILED",
                "QUALITY_GATE_FAILED",
                "No version was published; inspect the stored quality report.",
            )


@activity.defn
def publish_run(run_id: str):
    with Session.begin() as db:
        run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if run.status in TERMINAL:
            return
        if run.cancel_requested:
            terminate(db, run, "CANCELLED", "CANCELLED", "Cancelled before publication.")
            return
        if not run.quality or not run.quality.get("passed"):
            raise ApplicationError("Quality evidence missing.", non_retryable=True)
        target = db.scalar(
            select(Dataset)
            .where(Dataset.id == run.dataset_id, Dataset.organization_id == run.organization_id)
            .with_for_update()
        )
        revision = owned(db, RecipeRevision, run.recipe_revision_id, run.organization_id)
        source_kind = compile_recipe(revision.definition)[0]["type"]
        try:
            governance = check_publication_policy(db, target, source_kind)
            if run.checkpoint.get("admitted_policy", governance)["sha256"] != governance["sha256"]:
                raise Problem(
                    409,
                    "POLICY_CHANGED",
                    "Policy changed before publication; retry under the current policy.",
                )
        except Problem as error:
            terminate(db, run, "FAILED", error.code, error.message)
            return
        if target.policy.get("allowed_training_use") is not True:
            terminate(db, run, "FAILED", "POLICY_BLOCKED", "Publication rights are unavailable.")
            return
        run.status = "PUBLISHING"
        from .references import reference_lock

        reference_lock(db, run.organization_id)
        raw = b"".join(read_artifact(chunk) for chunk in run.checkpoint["chunks"])
        from .evaluation import holdout_lock, reject_contamination

        holdout_lock(db, run.organization_id)
        try:
            reject_contamination(
                db, run.organization_id, [item["payload"] for item in parse_jsonl(raw)], target
            )
        except Problem as error:
            terminate(db, run, "FAILED", error.code, error.message)
            return
        data_artifact = put_immutable(run.organization_id, raw, "application/x-ndjson")
        number = (
            db.scalar(
                select(func.max(Version.number)).where(
                    Version.dataset_id == target.id, Version.organization_id == run.organization_id
                )
            )
            or 0
        ) + 1
        version_id = "ver_" + run.id.removeprefix("run_")
        curation_evidence = {}
        order = compile_recipe(revision.definition)
        if source_kind in {"teacher", "image_generate"}:
            from .models import ProviderConnection
            from .providers import require_provider

            connection = db.scalar(
                select(ProviderConnection)
                .where(
                    ProviderConnection.id == order[0]["config"]["connection_id"],
                    ProviderConnection.organization_id == run.organization_id,
                )
                .with_for_update()
            )
            try:
                require_provider(connection, "structured_text" if source_kind == "teacher" else "image")
            except Problem as error:
                terminate(db, run, "FAILED", error.code, error.message)
                return
        if source_kind == "simulate":
            rendered = parse_jsonl(raw)
            categories = sorted(
                {box["label"] for sample in rendered for box in sample["annotation"]["boxes"]}
            )
            data_card = {
                "purpose": revision.definition["name"],
                "intended_use": "User-declared synthetic perception training",
                "limitations": "Scripted primitive scenes and visible-mask boxes; no robot dynamics or real-world accuracy claim.",
                "content_risks": "Procedural geometry only; no external assets.",
                "restrictions": target.policy,
                "source": run.checkpoint["source_metadata"],
            }
            curation_evidence = {
                "data_card": data_card,
                "annotation_categories": categories,
                "exports": image_exports(run.organization_id, rendered, categories, data_card),
            }
        if order[0]["type"] == "curate":
            curation = owned(db, Curation, order[0]["config"]["curation_id"], run.organization_id)
            curated, snapshot = frozen_input(curation, target)
            curation_evidence = {
                "curation_id": curation.id,
                "curation_snapshot": curation.snapshot,
                "data_card": snapshot["data_card"],
                "quality_profile": snapshot["profile"],
                "publication_approval": snapshot["approval"],
                "annotation_categories": snapshot["categories"],
                "review_history_artifact": curation.snapshot,
                "review_count": sum(review["decision"] != "reopen" for review in snapshot["review_history"]),
                "exports": image_exports(
                    run.organization_id, curated, snapshot["categories"], snapshot["data_card"]
                )
                if target.modality == "image"
                else {},
            }
            db.add(
                Usage(
                    id=uid("use"),
                    organization_id=run.organization_id,
                    run_id=run.id,
                    metric="annotation_review_units",
                    quantity=curation_evidence["review_count"],
                    dedupe_key="publication",
                )
            )
        manifest = {
            "schema_version": "1.0",
            "dataset_id": target.id,
            "dataset_version_id": version_id,
            "version": number,
            "organization_id": run.organization_id,
            "sample_count": run.processed,
            "modality": target.modality,
            "sample_schema": target.sample_schema,
            "sample_format": "foundry.sample-envelope/1.0",
            "data_artifact": data_artifact,
            "recipe_revision_id": revision.id,
            "recipe_sha256": revision.digest,
            "recipe": revision.definition,
            "run_id": run.id,
            "policy": target.policy,
            "quality": run.quality,
            "created_at": run.started_at.isoformat(),
            "engine_version": "datafoundry-cpu/0.1.0",
            "reproducibility": "deterministic payloads; run-specific provenance",
            "worker_image": None,
            "execution_environment": {
                "kind": "local-cpu-runtime",
                "python": sys.version.split()[0],
                "source_sha256": CODE_DIGEST,
            },
            "code_revision": "worktree:sha256:" + CODE_DIGEST,
            "governance_policy": governance,
            "source_execution": run.checkpoint.get("source_metadata"),
            **curation_evidence,
        }
        manifest_bytes = canonical(manifest)
        put_immutable(run.organization_id, manifest_bytes, "application/json")
        version = Version(
            id=version_id,
            organization_id=run.organization_id,
            dataset_id=target.id,
            run_id=run.id,
            number=number,
            sample_count=run.processed,
            manifest_hash=digest(manifest_bytes),
            manifest=manifest,
        )
        db.add(version)
        db.flush()
        from .evaluation import index_version

        index_version(db, version, parse_jsonl(raw))
        db.add(
            Audit(
                id=uid("aud"),
                organization_id=run.organization_id,
                actor_id="worker:local-cpu",
                action="dataset.version.published",
                resource_id=version.id,
                request_id=run.id,
            )
        )
        release(db, run)
        run.status, run.finished_at = "SUCCEEDED", now()
        db.add(
            Usage(
                id=uid("use"),
                organization_id=run.organization_id,
                run_id=run.id,
                metric="published_bytes",
                quantity=len(raw),
                dedupe_key="publication",
            )
        )
        log(
            db,
            run,
            "dataset.version.published",
            f"Published immutable version v{number} with {run.processed} samples.",
            {"version_id": version.id, "manifest_hash": version.manifest_hash},
        )
        emit(
            db,
            run,
            "dataset.version.published",
            {"run_id": run.id, "version_id": version.id, "manifest_hash": version.manifest_hash},
        )
        emit(db, run, "run.succeeded", {"run_id": run.id, "version_id": version.id})
        if any(node["type"] == "export" for node in revision.definition["nodes"]):
            export = Export(id=uid("exp"), organization_id=run.organization_id, version_id=version.id)
            db.add(export)
            db.flush()
            emit(db, run, "export.ready", {"export_id": export.id, "version_id": version.id})


@activity.defn
def fail_run(run_id: str):
    with Session.begin() as db:
        run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        terminate(
            db,
            run,
            "FAILED",
            "EXECUTION_FAILED",
            "Durable activity retries were exhausted. Inspect worker logs using the run ID.",
        )


async def dispatch(client):
    while True:
        try:
            with Session.begin() as db:
                rows = db.scalars(
                    select(Outbox)
                    .where(Outbox.dispatched.is_(False))
                    .order_by(Outbox.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(20)
                ).all()
                for row in rows:
                    if row.kind == "run":
                        try:
                            await client.start_workflow(
                                DatasetWorkflow.run,
                                row.resource_id,
                                id=f"dataset:{row.resource_id}",
                                task_queue="foundry-cpu",
                            )
                        except WorkflowAlreadyStartedError:
                            pass
                    elif row.kind == "erasure":
                        try:
                            await client.start_workflow(
                                ArtifactErasureWorkflow.run,
                                row.resource_id,
                                id=f"erasure:{row.resource_id}",
                                task_queue="foundry-cpu",
                            )
                        except WorkflowAlreadyStartedError:
                            pass
                    else:
                        hooks = db.scalars(
                            select(Webhook).where(
                                Webhook.organization_id == row.organization_id, Webhook.active.is_(True)
                            )
                        ).all()
                        for hook in hooks:
                            if row.payload["event_type"] in hook.events:
                                db.add(
                                    Delivery(
                                        id=uid("dlv"),
                                        organization_id=row.organization_id,
                                        webhook_id=hook.id,
                                        event_id=row.id,
                                        next_attempt_at=now(),
                                    )
                                )
                    row.dispatched = True
        except Exception:
            logger.exception("outbox_dispatch_failed")
        await asyncio.sleep(0.5)


async def deliver():
    async with httpx.AsyncClient(timeout=3, follow_redirects=False, trust_env=False) as http:
        while True:
            try:
                with Session.begin() as db:
                    row = db.scalar(
                        select(Delivery)
                        .where(Delivery.status == "PENDING", Delivery.next_attempt_at <= now())
                        .order_by(Delivery.next_attempt_at)
                        .with_for_update(skip_locked=True)
                        .limit(1)
                    )
                    if row:
                        hook = owned(db, Webhook, row.webhook_id, row.organization_id)
                        event = owned(db, Outbox, row.event_id, row.organization_id)
                        row.attempts += 1
                        if not hook.active:
                            row.status, row.error = "DEAD_LETTER", "Webhook disabled."
                        else:
                            try:
                                validate_webhook_url(hook.url)
                                raw = canonical(event.payload)
                                timestamp = str(int(time.time()))
                                secret = cipher().decrypt(hook.secret_encrypted.encode()).decode()
                                response = await http.post(
                                    hook.url,
                                    content=raw,
                                    headers={
                                        "Content-Type": "application/json",
                                        "X-Foundry-Timestamp": timestamp,
                                        "X-Foundry-Delivery-Id": row.id,
                                        "X-Foundry-Event-Id": event.id,
                                        "X-Foundry-Webhook-Id": hook.id,
                                        "X-Foundry-Signature": webhook_signature(secret, timestamp, raw),
                                    },
                                )
                                row.last_status = response.status_code
                                if response.is_success:
                                    row.status, row.error = "DELIVERED", None
                                else:
                                    row.error = f"Receiver returned HTTP {response.status_code}."
                            except Exception:
                                row.error = "Receiver unavailable or URL rejected."
                            if row.status == "PENDING":
                                if row.attempts >= 5:
                                    row.status = "DEAD_LETTER"
                                else:
                                    row.next_attempt_at = now() + timedelta(seconds=2 ** (row.attempts - 1))
            except Exception:
                logger.exception("webhook_delivery_failed")
            await asyncio.sleep(0.3)


async def heartbeat():
    while True:
        try:
            with Session.begin() as db:
                db.merge(Heartbeat(name="cpu", seen_at=now()))
        except Exception:
            logger.exception("heartbeat_failed")
        await asyncio.sleep(2)


async def main():
    client = await Client.connect(settings().temporal_address)
    async with Worker(
        client,
        task_queue="foundry-cpu",
        workflows=[DatasetWorkflow, ArtifactErasureWorkflow],
        activities=[process_run, publish_run, fail_run, erase_artifacts, fail_erasure],
        activity_executor=ThreadPoolExecutor(max_workers=2),
        max_concurrent_activities=2,
    ):
        await asyncio.gather(dispatch(client), deliver(), heartbeat())


if __name__ == "__main__":
    asyncio.run(main())
