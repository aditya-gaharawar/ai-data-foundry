import hashlib
import json
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .config import settings
from .errors import Problem


def client(public: bool = False, *, config: Config | None = None):
    s = settings()
    defaults = Config(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 2})
    return boto3.client(
        "s3",
        endpoint_url=s.s3_public_endpoint if public else s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name="us-east-1",
        config=defaults.merge(config) if config is not None else defaults,
    )


def initialize():
    s3, bucket = client(), settings().s3_bucket
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
            raise
        s3.create_bucket(Bucket=bucket)
    s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    s3.put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": settings().origins,
                    "AllowedMethods": ["PUT"],
                    "AllowedHeaders": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 300,
                }
            ]
        },
    )


def put_immutable(organization_id: str, payload: bytes, content_type: str) -> dict:
    sha = hashlib.sha256(payload).hexdigest()
    key = f"org/{organization_id}/blobs/sha256/{sha}"
    s3 = client()
    try:
        result = s3.put_object(
            Bucket=settings().s3_bucket, Key=key, Body=payload, ContentType=content_type, IfNoneMatch="*"
        )
        version = result.get("VersionId")
    except ClientError as error:
        if error.response["Error"]["Code"] not in (
            "PreconditionFailed",
            "ConditionalRequestConflict",
            "412",
            "409",
        ):
            raise
        existing = s3.get_object(Bucket=settings().s3_bucket, Key=key)
        actual = existing["Body"].read()
        if actual != payload:
            raise Problem(409, "ARTIFACT_CONFLICT", "Content-addressed object integrity failed.") from None
        version = existing.get("VersionId")
    return {
        "key": key,
        "version_id": version,
        "sha256": sha,
        "bytes": len(payload),
        "content_type": content_type,
    }


@lru_cache(maxsize=2)
def restore_map(path: str):
    location = Path(path).resolve()
    if not location.is_relative_to(Path(".local/backups").resolve()) or location.stat().st_mode & 0o077:
        raise RuntimeError("Recovery version maps must be private operator files under .local/backups.")
    return json.loads(location.read_text())


def read_artifact(artifact: dict) -> bytes:
    args = {"Bucket": settings().s3_bucket, "Key": artifact["key"]}
    if artifact.get("version_id"):
        args["VersionId"] = artifact["version_id"]
        if settings().s3_restore_map_file:
            key = artifact["key"] + "\0" + artifact["version_id"]
            mapping = restore_map(settings().s3_restore_map_file)
            if key not in mapping:
                raise Problem(
                    409,
                    "RECOVERY_VERSION_MISSING",
                    "This artifact was not included in the operator's recovery snapshot.",
                )
            args["VersionId"] = mapping[key]
    data = client().get_object(**args)["Body"].read()
    if hashlib.sha256(data).hexdigest() != artifact["sha256"] or len(data) != artifact["bytes"]:
        raise Problem(409, "ARTIFACT_CORRUPT", "The artifact no longer matches the immutable manifest.")
    return data
