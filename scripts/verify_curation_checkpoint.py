"""Capture synthetic P06 proof across a real, verified local API restart."""

import io
import json
import os
import signal
import time
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from foundry.config import settings
from foundry.db import Session
from foundry.models import Curation
from foundry.security import canonical, digest
from PIL import Image
from sqlalchemy import select

root = Path(__file__).resolve().parents[1]
evidence = root / "verification/evidence/p06"
browser = json.loads((evidence / "browser-image-proof.json").read_text())
dataset_id, curation_id, task_id = (
    browser[key].split("/")[-1] for key in ("dataset_path", "curation_path", "task_path")
)


def fetch(client, method, path, body=None):
    response = client.request(method, path, json=body, headers={"Idempotency-Key": uuid.uuid4().hex})
    if not response.is_success:
        # Signed query strings and credentials never belong in diagnostic output.
        raise RuntimeError(f"{method} {path.split('?')[0]} returned {response.status_code}")
    return response


def get(client, path):
    return fetch(client, "GET", "/v1" + path).json()


def login(email):
    client = httpx.Client(
        base_url="http://localhost:8000",
        timeout=30,
        trust_env=False,
        headers={"Origin": "http://localhost:3000"},
    )
    auth = fetch(
        client, "POST", "/v1/auth/login", {"email": email, "password": settings().dev_password}
    ).json()
    client.headers.update(
        {"X-CSRF-Token": auth["csrf_token"], "X-Organization-Id": auth["organizations"][0]["id"]}
    )
    return client


owner, other = login("alex@foundry.local"), login("blair@foundry.local")
try:
    curation = get(owner, f"/curations/{curation_id}")
    task = get(owner, f"/annotation-tasks/{task_id}")
    assert curation["state"] == "FROZEN" and curation["quality"]["passed"]
    version = next(
        item
        for item in get(owner, f"/datasets/{dataset_id}/versions")["items"]
        if item["manifest"].get("curation_id") == curation_id
    )
    source_root = root / "apps/api/foundry"
    code_sha = digest(
        b"".join(path.name.encode() + path.read_bytes() for path in sorted(source_root.glob("*.py")))
        + (root / "uv.lock").read_bytes()
    )
    assert version["manifest"]["execution_environment"]["source_sha256"] == code_sha
    with Session() as db:
        row = db.scalar(
            select(Curation).where(
                Curation.id == curation_id, Curation.organization_id == curation["organization_id"]
            )
        )
        snapshot_sha = row.snapshot["sha256"]
    samples = get(owner, f"/datasets/{dataset_id}/samples?version_id={version['id']}")["items"]
    assert len(samples) == 1 and samples[0]["annotation"] == task["annotation"]
    (evidence / "sample-reviewed.jsonl").write_bytes(b"".join(canonical(item) + b"\n" for item in samples))
    preview = fetch(owner, "GET", f"/v1/annotation-tasks/{task_id}/media").content
    assert Image.open(io.BytesIO(preview)).size == (64, 48)
    exports, isolation = {}, {}
    for kind in ("coco", "yolo"):
        export = fetch(owner, "POST", "/v1/exports", {"version_id": version["id"], "format": kind}).json()
        grant = get(owner, f"/exports/{export['id']}")["download_url"]
        isolation[f"{kind}_copied_grant"] = other.get(grant).status_code
        assert isolation[f"{kind}_copied_grant"] == 404
        downloaded = fetch(owner, "GET", grant)
        assert digest(downloaded.content) == downloaded.headers["X-Content-SHA256"]
        (evidence / f"sample-{kind}.zip").write_bytes(downloaded.content)
        with zipfile.ZipFile(io.BytesIO(downloaded.content)) as bundle:
            image_path = next(name for name in bundle.namelist() if name.startswith("images/"))
            assert bundle.read(image_path) == preview
            if kind == "coco":
                box = task["annotation"]["boxes"][0]
                assert json.loads(bundle.read("annotations.json"))["annotations"][0]["bbox"] == [
                    box[key] for key in ("x", "y", "width", "height")
                ]
            else:
                label = (
                    bundle.read(next(name for name in bundle.namelist() if name.startswith("labels/")))
                    .decode()
                    .strip()
                )
                assert label == "0 0.375 0.375 0.5 0.5"
        exports[kind] = {
            "bytes": len(downloaded.content),
            "sha256": digest(downloaded.content),
            "normalized_image_sha256": digest(preview),
        }
    for name, path in {
        "curation": f"/curations/{curation_id}",
        "task": f"/annotation-tasks/{task_id}",
        "task_image": f"/annotation-tasks/{task_id}/media",
        "quality_profile": f"/quality-profiles/{curation['profile_id']}",
        "version_image": f"/datasets/{dataset_id}/versions/{version['id']}/samples/{samples[0]['sample_id']}/image",
    }.items():
        isolation[name] = other.get("/v1" + path).status_code
        assert isolation[name] == 404
    pid_file = root / ".local/api.pid"
    old_pid = int(pid_file.read_text())
    if (
        Path(f"/proc/{old_pid}/cwd").resolve() != root
        or b"foundry.api:app" not in Path(f"/proc/{old_pid}/cmdline").read_bytes()
    ):
        raise SystemExit("Refusing to restart an unrelated process.")
    os.kill(old_pid, signal.SIGTERM)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            new_pid = int(pid_file.read_text())
            if new_pid != old_pid and owner.get("/v1/health/live").status_code == 200:
                break
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.2)
    else:
        raise SystemExit("Local API restart timed out.")
    assert get(owner, f"/annotation-tasks/{task_id}") == task
    assert get(owner, f"/curations/{curation_id}") == curation
    assert (
        get(owner, f"/datasets/{dataset_id}/versions/{version['id']}/manifest")["sha256"]
        == version["manifest_hash"]
    )
    proof = {
        "captured_at_ist": datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata")).isoformat(),
        "dataset_id": dataset_id,
        "curation_id": curation_id,
        "task_id": task_id,
        "run_id": version["run_id"],
        "version_id": version["id"],
        "manifest_sha256": version["manifest_hash"],
        "source_sha256_matches_worker": code_sha,
        "frozen_snapshot_sha256": snapshot_sha,
        "annotation_from_api_and_jsonl": task["annotation"],
        "data_card": version["manifest"]["data_card"],
        "approval": version["manifest"]["publication_approval"],
        "quality": curation["quality"],
        "exports": exports,
        "other_tenant_status_codes": isolation,
        "api_restart": {
            "old_pid": old_pid,
            "new_pid": new_pid,
            "task_and_history_equal": True,
            "curation_equal": True,
            "manifest_hash_equal": True,
        },
        "credentials_or_grants_included": False,
    }
    (evidence / "api-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(
        "P06 proof verified: API restart persistence, source/manifest hashes, reviewed labels, real image bundles, tenant and copied-grant denials."
    )
finally:
    owner.close()
    other.close()
