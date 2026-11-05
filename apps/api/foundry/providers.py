"""Rights-aware provider registry. Local inference is isolated from API processes."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Query, Request
from pydantic import BaseModel, Field

from .config import settings
from .dto import Page
from .errors import Problem
from .models import ProviderConnection
from .schemas import Strict
from .security import cipher


class ProviderCreate(Strict):
    name: str = Field(min_length=1, max_length=160)
    kind: Literal["local.gguf", "http.structured", "http.image"]
    model_ref: str = Field(min_length=1, max_length=200)
    endpoint: str | None = Field(default=None, max_length=2000)
    api_secret: str | None = Field(default=None, max_length=4000)
    permitted_training_use: Literal[True]
    consent_to_processing: Literal[True]
    terms_version: str = Field(min_length=1, max_length=200)
    rights_evidence: str = Field(min_length=8, max_length=4000)


class TeacherConfig(Strict):
    connection_id: str
    instructions: str = Field(min_length=1, max_length=4000)
    count: int = Field(default=1, ge=1, le=10)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    max_output_tokens: int = Field(default=256, ge=32, le=512)


class ImageGenerateConfig(Strict):
    connection_id: str
    instructions: str = Field(min_length=1, max_length=4000)
    count: int = Field(default=1, ge=1, le=5)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)


class ProviderOut(BaseModel):
    id: str
    organization_id: str
    name: str
    kind: str
    model_ref: str
    config: dict
    rights: dict
    approved_by: str
    revoked: bool
    state: str
    reason: str
    capabilities: list[str]


@lru_cache(maxsize=4)
def _verified_manifest(path: str, stamp: int, size: int):
    manifest = json.loads(Path(path).read_text())
    root = Path.cwd().resolve()
    model = (root / manifest["path"]).resolve()
    if not model.is_relative_to(root / ".local/models") or model.stat().st_size != manifest["bytes"]:
        raise ValueError("Model path or size does not match the operator manifest.")
    import hashlib

    hasher = hashlib.sha256()
    with model.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    if hasher.hexdigest() != manifest["sha256"] or manifest["license"] != "Apache-2.0":
        raise ValueError("The pinned model checksum/license verification failed.")
    return manifest


def local_model():
    try:
        path = Path(settings().local_model_manifest).resolve()
        stat = path.stat()
        if importlib.util.find_spec("llama_cpp") is None:
            raise ValueError("The optional local-model runtime is not installed.")
        __import__("llama_cpp")
        return _verified_manifest(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, ImportError, RuntimeError):
        return None


def provider_state(record):
    capabilities = ["structured_text"] if record.kind != "http.image" else ["image"]
    if record.revoked:
        return {"state": "REVOKED", "reason": "The connection was revoked.", "capabilities": capabilities}
    if record.rights.get("permitted_training_use") is not True:
        return {
            "state": "BLOCKED_POLICY",
            "reason": "Permitted training-use evidence is required.",
            "capabilities": capabilities,
        }
    if record.kind == "local.gguf":
        model = local_model()
        if model and model["model_ref"] == record.model_ref:
            return {
                "state": "READY",
                "reason": "Pinned Apache-2.0 CPU model verified locally; no external inference.",
                "capabilities": capabilities,
            }
        return {
            "state": "BLOCKED_EXTERNAL",
            "reason": "Run make local-model to install and verify the pinned CPU model.",
            "capabilities": capabilities,
        }
    return {
        "state": "BLOCKED_EXTERNAL",
        "reason": "External inference has no approved runtime/account, usage-price agreement or authorization. No request will be sent.",
        "capabilities": capabilities,
    }


def require_provider(record, expected):
    state = provider_state(record)
    if state["state"] != "READY":
        raise Problem(409, "PROVIDER_NOT_READY", state["reason"])
    if expected not in state["capabilities"]:
        raise Problem(
            422, "PROVIDER_CAPABILITY_MISMATCH", "This connection cannot perform the requested modality."
        )


def infer_local(config: dict, heartbeat, cancelled):
    model = local_model()
    if not model:
        raise Problem(409, "PROVIDER_NOT_READY", "The pinned local inference runtime is unavailable.")
    with tempfile.TemporaryDirectory(prefix="foundry-inference-") as directory:
        base = Path(directory)
        request_path, output_path = base / "request.json", base / "output.json"
        request_path.write_text(json.dumps({**config, "model_path": str(Path(model["path"]).resolve())}))
        request_path.chmod(0o600)
        log_path = base / "runtime.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "foundry.inference_runtime", str(request_path), str(output_path)],
                stdout=log,
                stderr=log,
                start_new_session=True,
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "LANG": "C.UTF-8",
                    "OMP_NUM_THREADS": "2",
                    "OPENBLAS_NUM_THREADS": "2",
                },
            )
            started = time.monotonic()
            try:
                while process.poll() is None:
                    heartbeat()
                    if cancelled():
                        raise Problem(
                            409, "CANCELLED", "Local inference cancelled before another output was accepted."
                        )
                    if time.monotonic() - started > 300:
                        raise Problem(
                            422, "PROVIDER_TIMEOUT", "Local model inference exceeded its five-minute limit."
                        )
                    time.sleep(0.25)
                if process.returncode != 0 or not output_path.exists():
                    raise Problem(
                        422,
                        "PROVIDER_OUTPUT_INVALID",
                        "The model did not produce complete schema-valid output. No version was published.",
                    )
                result = json.loads(output_path.read_text())
                result["model"] = {key: value for key, value in model.items() if key != "path"}
                result["duration_ms"] = round((time.monotonic() - started) * 1000)
                return result
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, __import__("signal").SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, __import__("signal").SIGKILL)
                        process.wait()


def register(app):
    from .api import DB, Auth, audit, commit, get, page, public, replay
    from .db import now, uid

    def output(record):
        return {**public(record), **provider_state(record)}

    @app.get("/v1/providers/catalog", tags=["Providers"])
    def provider_catalog(p: Auth):
        p.require("datasets:read")
        model = local_model()
        return {
            "items": [
                {
                    "kind": "local.gguf",
                    "model_ref": model["model_ref"] if model else "smollm2-135m-instruct-q4_k_m",
                    "state": "READY" if model else "BLOCKED_EXTERNAL",
                    "license": "Apache-2.0",
                    "capabilities": ["structured_text"],
                    "reason": "Local CPU inference, zero external cost."
                    if model
                    else "Run make local-model; weights and runtime are optional.",
                },
                {
                    "kind": "http.structured",
                    "state": "BLOCKED_EXTERNAL",
                    "capabilities": ["structured_text"],
                    "reason": "An authorized account, terms and explicit operator configuration are required.",
                },
                {
                    "kind": "http.image",
                    "state": "BLOCKED_EXTERNAL",
                    "capabilities": ["image"],
                    "reason": "No approved external image account is configured. Blender renders are a separate simulation engine.",
                },
            ]
        }

    @app.post("/v1/providers", tags=["Providers"], response_model=ProviderOut, status_code=201)
    def create_provider(body: ProviderCreate, request: Request, p: Auth, db: DB):
        p.require("providers:manage")
        payload = body.model_dump()
        if cached := replay(db, p, request, payload):
            return cached
        if not body.name.strip() or not body.rights_evidence.strip():
            raise Problem(
                422, "RIGHTS_REQUIRED", "Record a named connection and substantive rights evidence."
            )
        if body.endpoint:
            parsed = urlsplit(body.endpoint)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise Problem(
                    422,
                    "INVALID_PROVIDER_ENDPOINT",
                    "Use an endpoint without embedded credentials, query or fragment.",
                )
        record = ProviderConnection(
            id=uid("pvc"),
            organization_id=p.organization_id,
            name=body.name.strip(),
            kind=body.kind,
            model_ref=body.model_ref,
            config={"endpoint": body.endpoint},
            secret_encrypted=cipher().encrypt(body.api_secret.encode()).decode() if body.api_secret else None,
            rights={
                "permitted_training_use": True,
                "consent_to_processing": True,
                "terms_version": body.terms_version,
                "evidence": body.rights_evidence,
                "approved_at": now().isoformat(),
            },
            approved_by=p.user_id,
        )
        db.add(record)
        audit(db, p, request, "provider.consent.recorded", record.id)
        db.flush()
        return commit(db, request, output(record))

    @app.get("/v1/providers", tags=["Providers"], response_model=Page[ProviderOut])
    def providers(p: Auth, db: DB, limit: int = Query(25, ge=1, le=100), cursor: str | None = None):
        p.require("datasets:read")
        result = page(db, ProviderConnection, p, limit, cursor)
        result["items"] = [
            {**record, **provider_state(get(db, ProviderConnection, record["id"], p.organization_id))}
            for record in result["items"]
        ]
        return result

    @app.get("/v1/providers/{provider_id}", tags=["Providers"], response_model=ProviderOut)
    def provider(provider_id: str, p: Auth, db: DB):
        p.require("datasets:read")
        return output(get(db, ProviderConnection, provider_id, p.organization_id))

    @app.post("/v1/providers/{provider_id}/revoke", tags=["Providers"], response_model=ProviderOut)
    def revoke_provider(provider_id: str, request: Request, p: Auth, db: DB):
        p.require("providers:manage")
        if cached := replay(db, p, request, {}):
            return cached
        record = get(db, ProviderConnection, provider_id, p.organization_id)
        record.revoked = True
        audit(db, p, request, "provider.revoked", record.id)
        db.flush()
        return commit(db, request, output(record), 200)
