"""Collect synthetic artifacts and redacted operational reports, never grants or secrets."""

import hashlib
import json
import uuid
from pathlib import Path

from foundry.db import Session, now
from foundry.models import Dataset, Run, Version
from foundry.operations import source_fingerprint
from foundry.security import canonical
from foundry.storage import read_artifact
from operational_checks import auth_client
from sqlalchemy import select


def collect():
    root = Path("verification/evidence/p07-p12")
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    proof = {
        "recorded_at": now().isoformat(),
        "source_sha256": source_fingerprint(),
        "scope": "Local synthetic fixtures only",
        "engines": [],
    }
    with auth_client() as http, Session() as db:
        own = http.headers["X-Organization-Id"]
        for engine in ["local.llama.cpp@0.3.19", "blender.procedural@1"]:
            version = db.scalar(
                select(Version)
                .join(Run, Version.run_id == Run.id)
                .join(Dataset, Version.dataset_id == Dataset.id)
                .where(
                    Version.organization_id == own,
                    Dataset.erased_at.is_(None),
                    Run.checkpoint["source_metadata"]["engine"].as_string() == engine,
                )
                .order_by(Version.created_at.desc())
                .limit(1)
            )
            if not version:
                raise RuntimeError("No real published engine proof: " + engine)
            manifest = version.manifest
            data = read_artifact(manifest["data_artifact"])
            stem = "teacher" if engine.startswith("local") else "blender"
            (artifacts / (stem + ".jsonl")).write_bytes(data)
            row = {
                "engine": engine,
                "run_id": version.run_id,
                "version_id": version.id,
                "dataset_id": version.dataset_id,
                "sample_count": version.sample_count,
                "manifest_sha256": version.manifest_hash,
                "data_sha256": hashlib.sha256(data).hexdigest(),
                "data_bytes": len(data),
                "execution": manifest["source_execution"],
                "quality": manifest["quality"],
                "exports": {},
            }
            (artifacts / (stem + "-manifest.json")).write_bytes(canonical(manifest))
            if stem == "blender":
                first = json.loads(data.splitlines()[0])
                for name, artifact in [
                    ("frame.png", first["payload"]["image"]["artifact"]),
                    ("mask.png", first["payload"]["simulation"]["mask_artifact"]),
                    ("scene.glb", first["payload"]["simulation"]["scene_artifact"]),
                ]:
                    (artifacts / name).write_bytes(read_artifact(artifact))
                for format in ["coco", "yolo"]:
                    created = http.post(
                        "/v1/exports",
                        json={"version_id": version.id, "format": format},
                        headers={"Idempotency-Key": uuid.uuid4().hex},
                    )
                    created.raise_for_status()
                    ready = http.get("/v1/exports/" + created.json()["id"])
                    ready.raise_for_status()
                    response = http.get(ready.json()["download_url"])
                    response.raise_for_status()
                    actual = hashlib.sha256(response.content).hexdigest()
                    if actual != response.headers["x-content-sha256"]:
                        raise RuntimeError("Export proof failed its checksum.")
                    (artifacts / (stem + "-" + format + ".zip")).write_bytes(response.content)
                    row["exports"][format] = {
                        "sha256": actual,
                        "bytes": len(response.content),
                        "export_id": created.json()["id"],
                    }
            proof["engines"].append(row)
        for path, name in [
            ("/operations/status", "operations-status"),
            ("/operations/proofs", "operator-evidence"),
            ("/operations/reconciliations", "reconciliations"),
        ]:
            response = http.get("/v1" + path)
            response.raise_for_status()
            value = response.json()
            if name == "operator-evidence":
                value = {
                    "items": [
                        {key: content for key, content in item.items() if key != "operator_signature"}
                        for item in value["items"]
                    ]
                }
            if name == "operations-status":
                value["readiness"].pop("operator_signature", None)
            (root / (name + ".json")).write_bytes(canonical(value))
    (root / "api-proof.json").write_bytes(canonical(proof))
    print("Collected genuine native artifacts, verified exports and redacted reports.")


if __name__ == "__main__":
    collect()
