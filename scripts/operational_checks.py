"""Run bounded local load and real isolated database/object restore checks.

Recovery archives contain private metadata. They stay in ignored .local/backups,
mode 0600. Only disposable resources created by this process are dropped.
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import socket
import statistics
import subprocess
import time
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path

import httpx
from foundry.config import settings
from foundry.db import Session, now
from foundry.models import Base, ComputeJob, Dataset, Organization, Run, Version
from foundry.operations import sign_proof, source_fingerprint
from foundry.security import canonical
from foundry.storage import client
from sqlalchemy import create_engine, func, select, text


@contextmanager
def auth_client():
    http = httpx.Client(
        base_url="http://localhost:8000",
        headers={"Origin": "http://localhost:3000"},
        trust_env=False,
        timeout=60,
    )
    try:
        result = http.post(
            "/v1/auth/login", json={"email": "alex@foundry.local", "password": settings().dev_password}
        )
        result.raise_for_status()
        session = result.json()
        http.headers.update(
            {"X-CSRF-Token": session["csrf_token"], "X-Organization-Id": session["organizations"][0]["id"]}
        )
        yield http
    finally:
        http.close()


def save_proof(kind, report, *, publish=True):
    fingerprint = source_fingerprint()
    report = {"scope": "local", "recorded_at": now().isoformat(), **report}
    envelope = {
        "kind": kind,
        "source_sha256": fingerprint,
        "report": report,
        "operator_signature": sign_proof(kind, fingerprint, report),
    }
    private = Path(".local/evidence/p07-p12")
    private.mkdir(parents=True, exist_ok=True)
    target = private / f"{kind}.json"
    target.write_bytes(canonical(envelope))
    target.chmod(0o600)
    if publish:
        with auth_client() as http:
            result = http.post(
                "/v1/operations/proofs", json=envelope, headers={"Idempotency-Key": uuid.uuid4().hex}
            )
            result.raise_for_status()
    # HMAC signatures and credential-containing recovery archives stay private.
    print(json.dumps({"kind": kind, "source_sha256": fingerprint, "report": report}, indent=2))
    return envelope


def bounded_load(requests=60, concurrency=4):
    if not 10 <= requests <= 120 or not 1 <= concurrency <= 8:
        raise ValueError("Local proof is limited to 10–120 requests and 1–8 concurrent readers.")
    durations, statuses = [], []
    with auth_client() as http:
        started = time.monotonic()

        def read(index):
            begin = time.monotonic()
            response = http.get(["/v1/datasets?limit=10", "/v1/overview", "/v1/runs?limit=10"][index % 3])
            return (time.monotonic() - begin) * 1000, response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            for duration, status in pool.map(read, range(requests)):
                durations.append(duration)
                statuses.append(status)
    elapsed = time.monotonic() - started
    ordered = sorted(durations)
    errors = sum(status != 200 for status in statuses)
    return {
        "status": "PASS" if errors == 0 and ordered[int(len(ordered) * 0.95) - 1] < 5000 else "FAIL",
        "requests": requests,
        "concurrency": concurrency,
        "errors": errors,
        "p50_ms": round(statistics.median(ordered), 2),
        "p95_ms": round(ordered[int(len(ordered) * 0.95) - 1], 2),
        "elapsed_seconds": round(elapsed, 2),
        "requests_per_second": round(requests / elapsed, 2),
        "acceptance": "0 non-200 responses; local p95 <5000ms",
        "limits": "Single local host, synthetic fixtures, bounded read traffic; not a production SLA.",
    }


def restore_drill():
    identity = uuid.uuid4().hex[:12]
    database, bucket = "foundry_recovery_" + identity, "foundry-recovery-" + identity
    root = Path(".local/backups")
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    archive = root / (identity + ".zip")
    marker = Path(".local/maintenance.json")
    # Exclusive marker prevents concurrent drills and API writes during snapshot.
    with marker.open("x") as stream:
        json.dump({"operation": "isolated_recovery_drill", "id": identity}, stream)
    marker.chmod(0o600)
    cfg, s3 = settings(), client()
    original_url = create_engine(cfg.database_url).url
    admin = create_engine(original_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    restored = None
    created_db = created_bucket = False
    started = time.monotonic()
    try:
        with Session() as db:
            active = db.scalar(
                select(func.count())
                .select_from(Run)
                .where(Run.status.not_in(["SUCCEEDED", "FAILED", "CANCELLED"]))
            )
            active += db.scalar(
                select(func.count())
                .select_from(ComputeJob)
                .where(ComputeJob.status.in_(["QUEUED", "LEASED"]))
            )
            if active:
                raise RuntimeError(
                    "Finish/cancel active dataset and compute jobs before a consistent local drill."
                )
            counts = {
                table.name: db.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
                if table.name
                not in {
                    "rate_limits",
                    "heartbeats",
                    "login_sessions",
                    "idempotency",
                    "audit_events",
                    "webhook_deliveries",
                }
            }
            tenants = {
                row.id: db.scalar(
                    select(func.count()).select_from(Dataset).where(Dataset.organization_id == row.id)
                )
                for row in db.scalars(select(Organization))
            }
            expected_versions = [(row.id, row.manifest_hash) for row in db.scalars(select(Version))]
        dump = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "sh",
                "-c",
                'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl',
            ],
            capture_output=True,
            check=True,
        ).stdout
        objects = []
        descriptor = os.open(archive, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            bundle.writestr("metadata.dump", dump)
            for page in s3.get_paginator("list_object_versions").paginate(Bucket=cfg.s3_bucket):
                for item in page.get("Versions", []):
                    record = s3.get_object(Bucket=cfg.s3_bucket, Key=item["Key"], VersionId=item["VersionId"])
                    raw = record["Body"].read()
                    path = f"objects/{len(objects)}"
                    bundle.writestr(path, raw)
                    objects.append(
                        {
                            "path": path,
                            "key": item["Key"],
                            "original_version_id": item["VersionId"],
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "bytes": len(raw),
                            "content_type": record.get("ContentType", "application/octet-stream"),
                        }
                    )
            bundle.writestr(
                "manifest.json",
                canonical(
                    {
                        "database_counts": counts,
                        "tenant_dataset_counts": tenants,
                        "objects": objects,
                        "app_secret_included": False,
                        "scope": "metadata and immutable object versions; Temporal service history is outside this snapshot",
                    }
                ),
            )
        with admin.connect() as connection:
            # Names are generated internally from a hex UUID, never user input.
            connection.execute(text(f'CREATE DATABASE "{database}"'))
        created_db = True
        subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "sh",
                "-c",
                'pg_restore -U "$POSTGRES_USER" --dbname "$1" --no-owner --no-acl --exit-on-error',
                "restore",
                database,
            ],
            input=dump,
            capture_output=True,
            check=True,
        )
        s3.create_bucket(Bucket=bucket)
        created_bucket = True
        s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
        mapping, verified_bytes = {}, 0
        with zipfile.ZipFile(archive) as bundle:
            for item in objects:
                raw = bundle.read(item["path"])
                if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                    raise RuntimeError("Recovery archive checksum mismatch.")
                response = s3.put_object(
                    Bucket=bucket, Key=item["key"], Body=raw, ContentType=item["content_type"]
                )
                version = response.get("VersionId")
                recovered = s3.get_object(Bucket=bucket, Key=item["key"], VersionId=version)["Body"].read()
                if recovered != raw:
                    raise RuntimeError("Restored object checksum mismatch.")
                mapping[(item["key"], item["original_version_id"])] = version
                verified_bytes += len(raw)
        restored = create_engine(original_url.set(database=database))
        with restored.connect() as connection:
            for table in Base.metadata.sorted_tables:
                if (
                    table.name in counts
                    and connection.scalar(select(func.count()).select_from(table)) != counts[table.name]
                ):
                    raise RuntimeError("Restored metadata row count differs: " + table.name)
            for org, count in tenants.items():
                if (
                    connection.scalar(
                        select(func.count()).select_from(Dataset).where(Dataset.organization_id == org)
                    )
                    != count
                ):
                    raise RuntimeError("Restored tenant boundary count mismatch.")
            for version_id, expected_hash in expected_versions:
                row = (
                    connection.execute(select(Version.__table__).where(Version.id == version_id))
                    .mappings()
                    .one()
                )
                if hashlib.sha256(canonical(row["manifest"])).hexdigest() != expected_hash:
                    raise RuntimeError("Restored immutable manifest seal mismatch.")
                artifact = row["manifest"]["data_artifact"]
                # Erased datasets intentionally retain metadata without raw bytes.
                erased = connection.scalar(select(Dataset.erased_at).where(Dataset.id == row["dataset_id"]))
                if not erased:
                    recovered = s3.get_object(
                        Bucket=bucket,
                        Key=artifact["key"],
                        VersionId=mapping[(artifact["key"], artifact["version_id"])],
                    )["Body"].read()
                    if hashlib.sha256(recovered).hexdigest() != artifact["sha256"]:
                        raise RuntimeError("Restored dataset artifact seal mismatch.")
        report = {
            "status": "PASS",
            "database_tables_verified": len(counts),
            "tenant_count": len(tenants),
            "version_manifests_verified": len(expected_versions),
            "object_versions_verified": len(objects),
            "object_bytes_verified": verified_bytes,
            "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "archive_permissions": "0600; private local metadata only",
            "checks": [
                "pg_dump/pg_restore into isolated database",
                "every restored object byte checksum",
                "immutable version manifest seals",
                "per-tenant dataset boundaries",
                "original object-version references mapped without modifying manifests",
            ],
            "limits": "Local PostgreSQL+S3 recovery. Temporal dev-server workflow history and external KMS/SSO are not backed up here. Operator secret is a separately managed recovery prerequisite. Maintenance blocks API writes; no active jobs allowed.",
        }
        # A genuine local configuration rollback: the recovery API reads restored
        # DB and bucket using a version remap, then is stopped; live config is untouched.
        remap_file = root / (identity + "-version-map.json")
        remap_file.write_bytes(
            canonical(
                {
                    key + "\0" + version: restored_version
                    for (key, version), restored_version in mapping.items()
                }
            )
        )
        remap_file.chmod(0o600)
        env = {
            **os.environ,
            "DATABASE_URL": original_url.set(database=database).render_as_string(hide_password=False),
            "S3_BUCKET": bucket,
            "S3_RESTORE_MAP_FILE": str(remap_file.resolve()),
        }
        log = (root / (identity + "-api.log")).open("wb")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            recovery_port = listener.getsockname()[1]
        process = subprocess.Popen(
            [
                str(Path(".venv/bin/python").absolute()),
                "-m",
                "uvicorn",
                "foundry.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(recovery_port),
                "--no-access-log",
            ],
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{recovery_port}",
                trust_env=False,
                timeout=30,
                headers={"Origin": "http://localhost:3000"},
            ) as http:
                for _ in range(40):
                    if process.poll() is not None:
                        raise RuntimeError("The isolated recovery API exited before verification.")
                    try:
                        if http.get("/v1/health/live").is_success:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.25)
                login = http.post(
                    "/v1/auth/login", json={"email": "alex@foundry.local", "password": cfg.dev_password}
                )
                login.raise_for_status()
                own_org = login.json()["organizations"][0]["id"]
                http.headers.update({"X-Organization-Id": own_org})
                listed = http.get("/v1/datasets")
                listed.raise_for_status()
                if any(item["organization_id"] != own_org for item in listed.json()["items"]):
                    raise RuntimeError("Recovery API crossed tenant boundary.")
                with restored.connect() as connection:
                    other = connection.scalar(
                        select(Dataset.id)
                        .where(Dataset.organization_id != own_org, Dataset.erased_at.is_(None))
                        .limit(1)
                    )
                    live_version = connection.execute(
                        select(Version.id, Version.dataset_id)
                        .join(Dataset, Version.dataset_id == Dataset.id)
                        .where(
                            Version.organization_id == own_org,
                            Dataset.erased_at.is_(None),
                            Dataset.protection != "holdout",
                        )
                        .limit(1)
                    ).first()
                if other and http.get("/v1/datasets/" + other).status_code != 404:
                    raise RuntimeError("Recovery API cross-tenant negative failed.")
                if live_version:
                    response = http.get(
                        f"/v1/datasets/{live_version.dataset_id}/samples",
                        params={"version_id": live_version.id},
                    )
                    response.raise_for_status()
                report["restored_api_auth_and_tenant_isolation"] = "PASS"
                report["restored_api_sample_read"] = "PASS" if live_version else "NO_VERSION"
        finally:
            process.terminate()
            process.wait(timeout=15)
            log.close()
        rollback = {
            "status": "PASS",
            "scope": "local",
            "checks": [
                f"isolated restored API launched on loopback port {recovery_port}",
                "local password auth",
                "tenant-negative read",
                "restored immutable sample read",
                "isolated API terminated; live 8000 configuration unchanged",
            ],
            "limits": "Recovery configuration rehearsal only. No staging release/traffic rollback is claimed.",
            "archive_sha256": report["archive_sha256"],
        }
        return report, rollback
    finally:
        if restored:
            restored.dispose()
        if created_db:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        admin.dispose()
        if created_bucket:
            for page in s3.get_paginator("list_object_versions").paginate(Bucket=bucket):
                for item in [*page.get("Versions", []), *page.get("DeleteMarkers", [])]:
                    s3.delete_object(Bucket=bucket, Key=item["Key"], VersionId=item["VersionId"])
            s3.delete_bucket(Bucket=bucket)
        if marker.exists() and json.loads(marker.read_text()).get("id") == identity:
            marker.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["load", "restore"])
    parser.add_argument("--requests", type=int, default=60)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    if args.kind == "load":
        value = bounded_load(args.requests, args.concurrency)
        save_proof("load", value)
        raise SystemExit(0 if value["status"] == "PASS" else 1)
    recovery, rollback = restore_drill()
    save_proof("restore", recovery)
    save_proof("rollback", rollback)
