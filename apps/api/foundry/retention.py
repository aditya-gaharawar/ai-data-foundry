"""Two-phase artifact erasure. Tombstones commit before retryable object deletion."""

import json

from botocore.exceptions import ClientError
from sqlalchemy import delete, select
from temporalio import activity

from .config import settings
from .db import Session, now, uid
from .errors import Problem
from .models import Audit, Curation, Dataset, ErasureRequest, Evaluation, Run, SearchEntry, Upload, Version
from .security import canonical, digest
from .storage import client, read_artifact


def dataset_keys(db, dataset):
    keys = set()
    prefix = f"org/{dataset.organization_id}/"

    def add(artifact):
        if (
            isinstance(artifact, dict)
            and isinstance(artifact.get("key"), str)
            and artifact["key"].startswith(prefix)
        ):
            keys.add(artifact["key"])

    def images(samples):
        if dataset.modality != "image":
            return
        for sample in samples:
            payload = sample["payload"]
            for kind in ("artifact", "thumbnail"):
                add(payload.get("image", {}).get(kind))
            for kind in ("mask_artifact", "scene_artifact"):
                add(payload.get("simulation", {}).get(kind))

    def jsonl(artifact):
        from .recipes import parse_jsonl

        add(artifact)
        if dataset.modality == "image":
            images(parse_jsonl(read_artifact(artifact)))

    versions = db.scalars(
        select(Version).where(
            Version.dataset_id == dataset.id, Version.organization_id == dataset.organization_id
        )
    ).all()
    for version in versions:
        jsonl(version.manifest["data_artifact"])
        for artifact in version.manifest.get("exports", {}).values():
            add(artifact)
        for field in ("curation_snapshot", "review_history_artifact"):
            add(version.manifest.get(field))
    for upload in db.scalars(
        select(Upload).where(
            Upload.dataset_id == dataset.id, Upload.organization_id == dataset.organization_id
        )
    ):
        if upload.object_key.startswith(prefix):
            keys.add(upload.object_key)
        for field in ("artifact", "thumbnail"):
            add(upload.media.get(field))
    for run in db.scalars(
        select(Run).where(Run.dataset_id == dataset.id, Run.organization_id == dataset.organization_id)
    ):
        for chunk in run.checkpoint.get("chunks", []):
            jsonl(chunk)
        source = run.checkpoint.get("source_artifact")
        if source:
            add(source)
            if dataset.modality == "image":
                images(json.loads(read_artifact(source))["samples"])
    for curation in db.scalars(
        select(Curation).where(
            Curation.dataset_id == dataset.id, Curation.organization_id == dataset.organization_id
        )
    ):
        jsonl(curation.source_artifact)
        if curation.snapshot:
            add(curation.snapshot)
            if dataset.modality == "image":
                images(json.loads(read_artifact(curation.snapshot))["samples"])
    if versions:
        for evaluation in db.scalars(
            select(Evaluation).where(
                Evaluation.organization_id == dataset.organization_id,
                Evaluation.version_id.in_([version.id for version in versions]),
            )
        ):
            add(evaluation.artifact)
    return keys


def erasure_plan(db, dataset):
    own = dataset_keys(db, dataset)
    shared = set()
    for other in db.scalars(
        select(Dataset).where(
            Dataset.organization_id == dataset.organization_id,
            Dataset.id != dataset.id,
            Dataset.erased_at.is_(None),
        )
    ):
        shared.update(own & dataset_keys(db, other))
    objects = []
    s3 = client()
    for key in sorted(own - shared):
        for page in s3.get_paginator("list_object_versions").paginate(
            Bucket=settings().s3_bucket, Prefix=key
        ):
            for item in [*page.get("Versions", []), *page.get("DeleteMarkers", [])]:
                if item["Key"] == key:
                    objects.append({"key": key, "version_id": item["VersionId"]})
    if len(objects) > 10000:
        raise Problem(
            422,
            "ERASURE_PLAN_TOO_LARGE",
            "The local erasure operator supports at most 10,000 object versions.",
        )
    uploads = db.scalars(
        select(Upload).where(
            Upload.dataset_id == dataset.id,
            Upload.organization_id == dataset.organization_id,
            Upload.status == "UPLOADING",
        )
    ).all()
    plan = {
        "dataset_id": dataset.id,
        "governance_revision": dataset.governance_revision,
        "objects": sorted(objects, key=lambda row: (row["key"], row["version_id"])),
        "shared_keys_preserved": len(shared),
        "uploads": [{"key": upload.object_key, "multipart_id": upload.multipart_id} for upload in uploads],
    }
    return plan, digest(canonical(plan))


def public_erasure(record):
    from .api import public

    data = public(record)
    result = record.result or {}
    data["result"] = {key: value for key, value in result.items() if key != "plan"}
    return data


def _erase_artifacts(request_id: str, guard_db):
    with Session() as db:
        record = db.get(ErasureRequest, request_id)
        if record.status == "ERASED":
            return
        org, dataset_id, plan = record.organization_id, record.dataset_id, record.result["plan"]
    s3 = client()
    other_keys = set()
    for other in guard_db.scalars(
        select(Dataset).where(
            Dataset.organization_id == org, Dataset.id != dataset_id, Dataset.erased_at.is_(None)
        )
    ):
        other_keys.update(dataset_keys(guard_db, other))
    for upload in plan["uploads"]:
        activity.heartbeat("aborting-pending-upload")
        try:
            s3.abort_multipart_upload(
                Bucket=settings().s3_bucket, Key=upload["key"], UploadId=upload["multipart_id"]
            )
        except ClientError as error:
            if error.response["Error"]["Code"] != "NoSuchUpload":
                raise
    for index, artifact in enumerate(plan["objects"]):
        activity.heartbeat({"object_index": index})
        if artifact["key"] in other_keys:
            continue
        with Session() as db:
            target = db.get(Dataset, dataset_id)
            if target.organization_id != org or target.legal_hold:
                raise Problem(409, "LEGAL_HOLD", "Erasure stopped because a legal hold exists.")
        if not artifact["key"].startswith(f"org/{org}/"):
            raise Problem(403, "ERASURE_SCOPE_INVALID", "The erasure plan crossed its tenant boundary.")
        s3.delete_object(Bucket=settings().s3_bucket, Key=artifact["key"], VersionId=artifact["version_id"])
        try:
            s3.head_object(Bucket=settings().s3_bucket, Key=artifact["key"], VersionId=artifact["version_id"])
        except ClientError as error:
            if error.response["Error"]["Code"] not in {"404", "NoSuchKey", "NoSuchVersion"}:
                raise
        else:
            raise Problem(
                409, "ERASURE_INCOMPLETE", "Object storage still exposes a planned version after deletion."
            )
        with Session.begin() as db:
            record = db.scalar(
                select(ErasureRequest).where(ErasureRequest.id == request_id).with_for_update()
            )
            record.result = {**record.result, "object_versions_processed": index + 1}
    with Session.begin() as db:
        record = db.scalar(select(ErasureRequest).where(ErasureRequest.id == request_id).with_for_update())
        db.execute(
            delete(SearchEntry).where(
                SearchEntry.dataset_id == dataset_id, SearchEntry.organization_id == org
            )
        )
        record.status = "ERASED"
        record.result = {
            **record.result,
            "finished_at": now().isoformat(),
            "new_shared_keys_preserved": len({item["key"] for item in plan["objects"]} & other_keys),
            "metadata_retained": "Immutable audit, version manifests and review metadata remain; artifact erasure is not a compliance certification.",
        }
        db.add(
            Audit(
                id=uid("aud"),
                organization_id=org,
                actor_id="worker:artifact-retention",
                action="dataset.artifacts.erased",
                resource_id=dataset_id,
                request_id=request_id,
            )
        )


@activity.defn
def erase_artifacts(request_id: str):
    from .references import reference_guard

    with Session() as db:
        record = db.get(ErasureRequest, request_id)
        organization_id = record.organization_id
    with reference_guard(organization_id) as guard_db:
        _erase_artifacts(request_id, guard_db)


@activity.defn
def fail_erasure(request_id: str):
    with Session.begin() as db:
        record = db.scalar(select(ErasureRequest).where(ErasureRequest.id == request_id).with_for_update())
        if record.status != "ERASED":
            record.status = "ERASURE_FAILED"
            record.result = {
                **record.result,
                "error": "Object deletion retries were exhausted. Tombstone remains; an authorized retry resumes the same sealed plan.",
            }
