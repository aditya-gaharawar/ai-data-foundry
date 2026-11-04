import asyncio
import hashlib
import hmac
import json
import logging
import math
import secrets
import time
from datetime import timedelta
from typing import Annotated

from botocore.exceptions import ClientError
from fastapi import Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session as DBSession
from starlette.exceptions import HTTPException
from temporalio.client import Client as TemporalClient

from . import schemas as s
from .config import settings
from .curation_api import register as register_curation
from .db import now, session, uid
from .dto import (
    DatasetOut,
    ExportOut,
    KeyOut,
    Page,
    ProblemOut,
    RecipeOut,
    RevisionOut,
    RunOut,
    UploadOut,
    VersionOut,
    WebhookOut,
)
from .errors import Problem
from .media import prepare_image
from .models import (
    ApiKey,
    Audit,
    Curation,
    Dataset,
    Delivery,
    Export,
    Heartbeat,
    Idempotency,
    LoginSession,
    Membership,
    Organization,
    Outbox,
    Project,
    Recipe,
    RecipeRevision,
    Run,
    RunEvent,
    Upload,
    Usage,
    User,
    Version,
    Webhook,
)
from .openapi import enrich
from .recipes import GenerateConfig, compile_recipe, parse_jsonl, validate_sample_schema
from .security import (
    ROLES,
    SCOPES,
    Principal,
    canonical,
    cipher,
    digest,
    passwords,
    principal,
    rate_limit,
    read_token,
    signed_token,
    validate_webhook_url,
    verify_password,
)
from .storage import client as s3client
from .storage import read_artifact

app = FastAPI(
    title="AI Data Foundry API",
    version="0.1.0",
    description="Local text/image dataset lifecycle, curation and human review. External engines are unavailable.",
    openapi_url="/v1/openapi.json",
    docs_url="/v1/docs",
    redoc_url=None,
    responses={
        code: {
            "description": "Deterministic Problem Details error",
            "content": {"application/problem+json": {"schema": ProblemOut.model_json_schema()}},
        }
        for code in [400, 401, 402, 403, 404, 409, 422, 429, 500, 503]
    },
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-CSRF-Token",
        "X-Organization-Id",
        "X-Request-Id",
    ],
    expose_headers=["X-Request-Id", "X-Content-SHA256", "Content-Disposition"],
)
DB = Annotated[DBSession, Depends(session)]
Auth = Annotated[Principal, Depends(principal)]
logger = logging.getLogger("foundry.api")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())
logger.propagate = False
DUMMY_PASSWORD = passwords.hash(secrets.token_urlsafe(24))
base_openapi = app.openapi


def contract_openapi():
    if app.openapi_schema is None:
        return enrich(base_openapi())
    return app.openapi_schema


app.openapi = contract_openapi


@app.middleware("http")
async def correlation(request: Request, call_next):
    request.state.request_id = uid("req")
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed request_id=%s", request.state.request_id)
        response = problem_response(
            request,
            Problem(
                500, "INTERNAL_ERROR", "The operation failed. Use the request ID to find its server log."
            ),
        )
    response.headers["X-Request-Id"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    logger.info(
        json.dumps(
            {
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        )
    )
    return response


def problem_response(request, error: Problem):
    return JSONResponse(
        status_code=error.status,
        media_type="application/problem+json",
        content={
            "type": f"urn:foundry:problem:{error.code.lower()}",
            "title": error.code.replace("_", " ").title(),
            "status": error.status,
            "code": error.code,
            "detail": error.message,
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )


@app.exception_handler(Problem)
async def handle_problem(request: Request, error: Problem):
    return problem_response(request, error)


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, error: RequestValidationError):
    # Never echo raw request inputs (passwords, keys, dataset contents) in validation errors.
    message = "; ".join(".".join(map(str, item["loc"])) + ": " + item["msg"] for item in error.errors())
    return problem_response(request, Problem(422, "VALIDATION_ERROR", message))


@app.exception_handler(HTTPException)
async def handle_http(request: Request, error: HTTPException):
    return problem_response(
        request,
        Problem(
            error.status_code, "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR", str(error.detail)
        ),
    )


def get(db: DBSession, cls, identifier: str, org: str):
    record = db.scalar(select(cls).where(cls.id == identifier, cls.organization_id == org))
    if not record:
        raise Problem(404, "NOT_FOUND", "Resource not found.")
    return record


def audit(db: DBSession, p: Principal, request: Request, action: str, resource: str):
    db.add(
        Audit(
            id=uid("aud"),
            organization_id=p.organization_id,
            actor_id=p.key_id or p.user_id,
            action=action,
            resource_id=resource,
            request_id=request.state.request_id,
        )
    )


def public(record):
    fields = [column.key for column in record.__table__.columns]
    hidden = {
        "password_hash",
        "secret_hash",
        "secret_encrypted",
        "multipart_id",
        "object_key",
        "object_version",
    }
    value = {key: getattr(record, key) for key in fields if key not in hidden}
    for key, item in list(value.items()):
        if hasattr(item, "isoformat"):
            value[key] = item.isoformat()
    if isinstance(record, Dataset):
        value["schema"] = value.pop("sample_schema")
    if isinstance(record, Run):
        value.update(
            spent_usd=record.spent_micro / 1e6,
            reserved_usd=record.reserved_micro / 1e6,
            max_budget_usd=record.max_budget_micro / 1e6,
            status_url=f"/v1/runs/{record.id}",
        )
    return value


def page(db, cls, p, limit=25, cursor=None, extra=()):
    query = select(cls).where(cls.organization_id == p.organization_id, *extra)
    if cursor:
        value = read_token(cursor)
        if value.get("org") != p.organization_id or value.get("entity") != cls.__tablename__:
            raise Problem(404, "INVALID_CURSOR", "Cursor not found.")
        query = query.where(cls.id < value["last"])
    rows = db.scalars(query.order_by(cls.id.desc()).limit(limit + 1)).all()
    more = len(rows) > limit
    rows = rows[:limit]
    token = (
        signed_token(
            {
                "org": p.organization_id,
                "entity": cls.__tablename__,
                "last": rows[-1].id,
                "exp": int(time.time()) + 86400,
            }
        )
        if more
        else None
    )
    return {"items": [public(row) for row in rows], "next_cursor": token}


def replay(db, p, request, payload):
    key = request.headers.get("idempotency-key", "")
    if not key or len(key) > 128:
        raise Problem(422, "IDEMPOTENCY_KEY_REQUIRED", "Provide an Idempotency-Key of 1–128 characters.")
    operation = request.method + " " + request.url.path
    lock = int.from_bytes(
        hashlib.sha256(f"{p.organization_id}:{p.key_id or p.user_id}:{operation}:{key}".encode()).digest()[
            :8
        ],
        signed=True,
    )
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
    identity = {
        "organization_id": p.organization_id,
        "actor_id": p.key_id or p.user_id,
        "operation": operation,
        "key": key,
    }
    record = db.get(Idempotency, identity)
    try:
        request.state.idempotency = (
            identity,
            hmac.new(settings().app_secret.encode(), canonical(payload), "sha256").hexdigest(),
        )
    except (ValueError, TypeError, RecursionError):
        raise Problem(
            422, "INVALID_JSON", "Use finite JSON values within supported nesting limits."
        ) from None
    if record:
        if record.request_hash != request.state.idempotency[1]:
            raise Problem(409, "IDEMPOTENCY_CONFLICT", "This key was already used with another payload.")
        return JSONResponse(status_code=record.status_code, content=record.response)
    return None


def commit(db, request, value, status=201, stored=None):
    identity, request_hash = request.state.idempotency
    db.add(
        Idempotency(
            **identity,
            request_hash=request_hash,
            response=value if stored is None else stored,
            status_code=status,
        )
    )
    db.commit()
    return JSONResponse(status_code=status, content=value)


def emit(db, org, event_type, resource_id, data):
    event_id = uid("evt")
    db.add(
        Outbox(
            id=event_id,
            organization_id=org,
            kind="event",
            resource_id=resource_id,
            payload={
                "event_id": event_id,
                "event_type": event_type,
                "occurred_at": now().isoformat(),
                "schema_version": "1.0",
                "organization_id": org,
                "resource_id": resource_id,
                "data": data,
            },
        )
    )


@app.get("/v1/health/live", tags=["Health"])
def live():
    return {"status": "ok"}


@app.get("/v1/health/ready", tags=["Health"])
async def ready(db: DB):
    dependencies = {"database": False, "object_storage": False, "workflow": False}
    try:
        db.execute(text("SELECT 1"))
        dependencies["database"] = True
        await asyncio.to_thread(s3client().head_bucket, Bucket=settings().s3_bucket)
        dependencies["object_storage"] = True
        connection = await asyncio.wait_for(TemporalClient.connect(settings().temporal_address), timeout=3)
        await connection.workflow_service.get_system_info(
            __import__(
                "temporalio.api.workflowservice.v1", fromlist=["GetSystemInfoRequest"]
            ).GetSystemInfoRequest()
        )
        dependencies["workflow"] = True
    except Exception:
        logger.warning("readiness_dependency_unavailable")
    return JSONResponse(
        status_code=200 if all(dependencies.values()) else 503,
        content={
            "status": "ready" if all(dependencies.values()) else "degraded",
            "dependencies": dependencies,
        },
    )


def session_info(db, user, token):
    memberships = db.execute(
        select(Membership, Organization)
        .join(Organization)
        .where(Membership.user_id == user.id)
        .order_by(Organization.name)
    ).all()
    csrf = hmac.new(settings().app_secret.encode(), token.encode(), "sha256").hexdigest()
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "organizations": [
            {"id": org.id, "name": org.name, "role": member.role, "scopes": ROLES[member.role]}
            for member, org in memberships
        ],
        "csrf_token": csrf,
        "environment": "local",
        "demo_data": True,
    }


@app.post("/v1/auth/login", tags=["Identity"])
def login(body: s.Login, request: Request, response: Response, db: DB):
    if request.headers.get("origin") not in settings().origins:
        raise Problem(403, "CSRF_REJECTED", "Sign in from an allowed local application origin.")
    rate_limit("login:" + body.email.lower(), 30)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    valid = verify_password(user.password_hash if user else DUMMY_PASSWORD, body.password)
    if not user or not user.active or not valid:
        raise Problem(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
    token = secrets.token_urlsafe(48)
    info = session_info(db, user, token)
    if not info["organizations"]:
        raise Problem(
            403,
            "NO_ORGANIZATION_ACCESS",
            "Your account has no organization access. Contact your administrator.",
        )
    db.add(
        LoginSession(
            token_hash=digest(token),
            user_id=user.id,
            csrf_hash=digest(info["csrf_token"]),
            expires_at=now() + timedelta(hours=12),
        )
    )
    db.commit()
    response.set_cookie(
        "foundry_session", token, max_age=43200, httponly=True, samesite="lax", secure=False, path="/"
    )
    return info


@app.get("/v1/auth/session", tags=["Identity"])
def current_session(request: Request, p: Auth, db: DB):
    return session_info(db, db.get(User, p.user_id), request.cookies.get("foundry_session", ""))


@app.post("/v1/auth/logout", tags=["Identity"], status_code=204)
def logout(request: Request, response: Response, db: DB):
    token = request.cookies.get("foundry_session", "")
    record = db.get(LoginSession, digest(token))
    if request.headers.get("origin") not in settings().origins:
        raise Problem(403, "CSRF_REJECTED", "Sign out from an allowed local origin.")
    if record and not hmac.compare_digest(digest(request.headers.get("x-csrf-token", "")), record.csrf_hash):
        raise Problem(403, "CSRF_REJECTED", "The CSRF token is invalid.")
    if record:
        db.delete(record)
    db.commit()
    response.delete_cookie("foundry_session", path="/")


@app.get("/v1/me", tags=["Identity"])
def me(p: Auth, db: DB):
    user = db.get(User, p.user_id)
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "organization_id": p.organization_id,
        "role": p.role,
        "scopes": p.scopes,
    }


@app.get("/v1/organizations", tags=["Identity"])
def organizations(p: Auth, db: DB):
    return {
        "items": [
            {"id": org.id, "name": org.name, "role": membership.role}
            for org, membership in db.execute(
                select(Organization, Membership).join(Membership).where(Membership.user_id == p.user_id)
            )
        ]
    }


@app.get("/v1/projects", tags=["Projects"])
def projects(p: Auth, db: DB):
    p.require("datasets:read")
    return page(db, Project, p, 100)


@app.post("/v1/projects", tags=["Projects"])
def create_project(body: s.NameCreate, request: Request, p: Auth, db: DB):
    p.require("members:manage")
    if cached := replay(db, p, request, body.model_dump()):
        return cached
    if db.scalar(
        select(Project).where(Project.organization_id == p.organization_id, Project.name == body.name)
    ):
        raise Problem(409, "PROJECT_EXISTS", "A project with this name already exists.")
    record = Project(id=uid("prj"), organization_id=p.organization_id, name=body.name)
    db.add(record)
    audit(db, p, request, "project.created", record.id)
    db.flush()
    return commit(db, request, public(record))


@app.get("/v1/datasets", tags=["Datasets"], response_model=Page[DatasetOut])
def datasets(
    p: Auth,
    db: DB,
    limit: int = Query(25, ge=1, le=100),
    cursor: str | None = None,
    q: str = Query("", max_length=160),
    project_id: str | None = None,
):
    p.require("datasets:read")
    extra = [Dataset.archived.is_(False)]
    if q:
        extra.append(Dataset.name.ilike("%" + q.replace("%", "\\%").replace("_", "\\_") + "%"))
    if project_id:
        get(db, Project, project_id, p.organization_id)
        extra.append(Dataset.project_id == project_id)
    result = page(db, Dataset, p, limit, cursor, extra)
    for value in result["items"]:
        value["versions_count"] = db.scalar(
            select(func.count())
            .select_from(Version)
            .where(Version.dataset_id == value["id"], Version.organization_id == p.organization_id)
        )
    return result


@app.post("/v1/datasets", tags=["Datasets"], response_model=DatasetOut, status_code=201)
def create_dataset(body: s.DatasetCreate, request: Request, p: Auth, db: DB):
    p.require("datasets:write")
    if cached := replay(db, p, request, body.model_dump(mode="json", by_alias=True)):
        return cached
    get(db, Project, body.project_id, p.organization_id)
    validate_sample_schema(body.schema_definition)
    record = Dataset(
        id=uid("ds"),
        organization_id=p.organization_id,
        project_id=body.project_id,
        name=body.name.strip(),
        description=body.description,
        modality=body.modality,
        sample_schema=body.schema_definition,
        policy=body.policy,
    )
    if not record.name:
        raise Problem(422, "INVALID_NAME", "Dataset name must contain visible characters.")
    db.add(record)
    audit(db, p, request, "dataset.created", record.id)
    db.flush()
    return commit(db, request, public(record))


@app.get("/v1/datasets/{dataset_id}", tags=["Datasets"], response_model=DatasetOut)
def dataset(dataset_id: str, p: Auth, db: DB):
    p.require("datasets:read")
    return public(get(db, Dataset, dataset_id, p.organization_id))


@app.patch("/v1/datasets/{dataset_id}", tags=["Datasets"])
def edit_dataset(dataset_id: str, body: s.DatasetPatch, request: Request, p: Auth, db: DB):
    p.require("datasets:write")
    record = get(db, Dataset, dataset_id, p.organization_id)
    for key, value in body.model_dump(exclude_none=True).items():
        if key == "name" and not value.strip():
            raise Problem(422, "INVALID_NAME", "Name cannot be blank.")
        setattr(record, key, value)
    audit(db, p, request, "dataset.updated", record.id)
    db.commit()
    return public(record)


@app.post("/v1/uploads", tags=["Uploads"], response_model=UploadOut, status_code=201)
def start_upload(body: s.UploadCreate, request: Request, p: Auth, db: DB):
    p.require("datasets:write")
    if cached := replay(db, p, request, body.model_dump()):
        return cached
    target = get(db, Dataset, body.dataset_id, p.organization_id)
    if target.archived:
        raise Problem(409, "DATASET_ARCHIVED", "Restore the dataset before uploading.")
    image_type = body.content_type in {"image/png", "image/jpeg"}
    suffixes = (
        (".png",) if body.content_type == "image/png" else (".jpg", ".jpeg") if image_type else (".jsonl",)
    )
    if (
        not body.filename.lower().endswith(suffixes)
        or "/" in body.filename
        or "\\" in body.filename
        or any(ord(char) < 32 for char in body.filename)
        or (target.modality == "image") != image_type
    ):
        raise Problem(
            422,
            "UNSUPPORTED_FILE",
            "Use a JSONL file for text or a PNG/JPEG for an image dataset; directory components are forbidden.",
        )
    upload_id = uid("upl")
    key = f"org/{p.organization_id}/datasets/{target.id}/sources/{upload_id}{suffixes[0]}"
    multipart = s3client().create_multipart_upload(
        Bucket=settings().s3_bucket, Key=key, ContentType=body.content_type
    )
    record = Upload(
        id=upload_id,
        organization_id=p.organization_id,
        dataset_id=target.id,
        filename=body.filename,
        content_type=body.content_type,
        expected_bytes=body.bytes,
        expected_sha256=body.sha256,
        object_key=key,
        multipart_id=multipart["UploadId"],
    )
    db.add(record)
    db.flush()
    result = public(record)
    part_size = 5 * 1024 * 1024
    result.update(
        part_size=part_size,
        expires_in=600,
        upload_urls=[
            s3client(public=True).generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": settings().s3_bucket,
                    "Key": key,
                    "UploadId": record.multipart_id,
                    "PartNumber": part + 1,
                },
                ExpiresIn=600,
            )
            for part in range(math.ceil(body.bytes / part_size))
        ],
    )
    audit(db, p, request, "upload.started", record.id)
    return commit(db, request, result)


@app.get("/v1/uploads", tags=["Uploads"], response_model=Page[UploadOut])
def uploads(p: Auth, db: DB, dataset_id: str):
    p.require("datasets:read")
    get(db, Dataset, dataset_id, p.organization_id)
    return page(db, Upload, p, 100, extra=[Upload.dataset_id == dataset_id])


@app.get(
    "/v1/uploads/{upload_id}", tags=["Uploads"], response_model=UploadOut, response_model_exclude_none=True
)
def get_upload(upload_id: str, p: Auth, db: DB):
    p.require("datasets:read")
    return public(get(db, Upload, upload_id, p.organization_id))


@app.post("/v1/uploads/{upload_id}/complete", tags=["Uploads"])
def complete_upload(upload_id: str, body: s.UploadComplete, request: Request, p: Auth, db: DB):
    p.require("datasets:write")
    if cached := replay(db, p, request, body.model_dump()):
        return cached
    record = get(db, Upload, upload_id, p.organization_id)
    if record.status == "COMPLETED":
        return commit(db, request, public(record), 200)
    if record.status != "UPLOADING":
        raise Problem(409, "UPLOAD_NOT_ACTIVE", "This upload is not active.")
    expected_parts = math.ceil(record.expected_bytes / (5 * 1024 * 1024))
    if sorted(part.part_number for part in body.parts) != list(range(1, expected_parts + 1)):
        raise Problem(422, "INVALID_PARTS", "Provide each expected part exactly once.")
    s3 = s3client()
    try:
        result = s3.complete_multipart_upload(
            Bucket=settings().s3_bucket,
            Key=record.object_key,
            UploadId=record.multipart_id,
            MultipartUpload={
                "Parts": [
                    {"PartNumber": part.part_number, "ETag": part.etag}
                    for part in sorted(body.parts, key=lambda part: part.part_number)
                ]
            },
        )
        record.object_version = result.get("VersionId")
    except ClientError as error:
        if error.response["Error"]["Code"] != "NoSuchUpload":
            raise Problem(
                422, "UPLOAD_PART_ERROR", "Object storage rejected the supplied upload parts."
            ) from None
        # Completion may have committed in S3 just before an API crash. Reconcile the object.
    artifact = s3.get_object(Bucket=settings().s3_bucket, Key=record.object_key)
    if artifact["ContentLength"] > settings().max_upload_bytes:
        raise Problem(422, "UPLOAD_TOO_LARGE", "Uploaded object exceeds the local limit.")
    raw = artifact["Body"].read(settings().max_upload_bytes + 1)
    record.object_version = artifact.get("VersionId")
    if len(raw) != record.expected_bytes or digest(raw) != record.expected_sha256:
        record.status = "REJECTED"
        record.error = "Checksum or size mismatch."
        db.commit()
        raise Problem(
            422, "UPLOAD_CHECKSUM_MISMATCH", "Uploaded bytes do not match the declared size and SHA-256."
        )
    try:
        if record.content_type.startswith("image/"):
            record.media = prepare_image(raw, record.content_type, p.organization_id)
            samples = [{"image": record.media}]
        else:
            samples = parse_jsonl(raw)
    except Problem as error:
        record.status, record.error = "REJECTED", error.message
        db.commit()
        raise
    record.status, record.sample_count = "COMPLETED", len(samples)
    audit(db, p, request, "upload.completed", record.id)
    return commit(db, request, public(record), 200)


@app.post("/v1/uploads/{upload_id}/abort", tags=["Uploads"])
def abort_upload(upload_id: str, request: Request, p: Auth, db: DB):
    p.require("datasets:write")
    record = get(db, Upload, upload_id, p.organization_id)
    if record.status != "UPLOADING":
        raise Problem(409, "UPLOAD_NOT_ACTIVE", "Only active uploads can be aborted.")
    s3client().abort_multipart_upload(
        Bucket=settings().s3_bucket, Key=record.object_key, UploadId=record.multipart_id
    )
    record.status = "ABORTED"
    audit(db, p, request, "upload.aborted", record.id)
    db.commit()
    return public(record)


@app.get("/v1/uploads/{upload_id}/media", tags=["Uploads"])
def upload_media(upload_id: str, p: Auth, db: DB, thumbnail: bool = True):
    p.require("datasets:read")
    record = get(db, Upload, upload_id, p.organization_id)
    if record.status != "COMPLETED" or not record.media:
        raise Problem(404, "NOT_FOUND", "Verified image preview not found.")
    data = read_artifact(record.media["thumbnail" if thumbnail else "artifact"])
    return Response(
        data,
        media_type="image/png",
        headers={"X-Content-SHA256": digest(data), "Content-Security-Policy": "default-src 'none'; sandbox"},
    )


@app.post("/v1/recipes/validate", tags=["Recipes"])
def validate_recipe(body: dict, p: Auth):
    p.require("datasets:read")
    order = compile_recipe(body)
    return {
        "valid": True,
        "execution_order": [node["id"] for node in order],
        "digest": digest(canonical(body)),
    }


@app.get("/v1/recipes", tags=["Recipes"], response_model=Page[RecipeOut])
def recipes(p: Auth, db: DB, limit: int = Query(25, ge=1, le=100), cursor: str | None = None):
    p.require("datasets:read")
    result = page(db, Recipe, p, limit, cursor)
    for row in result["items"]:
        row["revisions"] = [
            public(rev)
            for rev in db.scalars(
                select(RecipeRevision)
                .where(
                    RecipeRevision.recipe_id == row["id"], RecipeRevision.organization_id == p.organization_id
                )
                .order_by(RecipeRevision.created_at.desc())
            )
        ]
    return result


@app.get("/v1/recipes/{recipe_id}", tags=["Recipes"], response_model=RecipeOut)
def recipe(recipe_id: str, p: Auth, db: DB):
    p.require("datasets:read")
    record = get(db, Recipe, recipe_id, p.organization_id)
    return {
        **public(record),
        "revisions": [
            public(rev)
            for rev in db.scalars(
                select(RecipeRevision)
                .where(
                    RecipeRevision.recipe_id == record.id, RecipeRevision.organization_id == p.organization_id
                )
                .order_by(RecipeRevision.created_at.desc())
            )
        ],
    }


@app.post("/v1/recipes", tags=["Recipes"], response_model=RecipeOut, status_code=201)
def create_recipe(body: s.RecipeCreate, request: Request, p: Auth, db: DB):
    p.require("datasets:write")
    if cached := replay(db, p, request, body.model_dump()):
        return cached
    get(db, Project, body.project_id, p.organization_id)
    order = compile_recipe(body.definition)
    if order[0]["type"] == "ingest":
        get(db, Upload, order[0]["config"]["upload_id"], p.organization_id)
    elif order[0]["type"] == "curate":
        get(db, Curation, order[0]["config"]["curation_id"], p.organization_id)
    record = Recipe(
        id=uid("rcp"),
        organization_id=p.organization_id,
        project_id=body.project_id,
        name=body.definition["name"],
    )
    db.add(record)
    db.flush()
    revision = RecipeRevision(
        id=uid("rev"),
        organization_id=p.organization_id,
        recipe_id=record.id,
        digest=digest(canonical(body.definition)),
        definition=body.definition,
    )
    db.add(revision)
    audit(db, p, request, "recipe.created", record.id)
    db.flush()
    return commit(db, request, {**public(record), "revision": public(revision)})


@app.post("/v1/recipes/{recipe_id}/revisions", tags=["Recipes"], response_model=RevisionOut, status_code=201)
def revise_recipe(recipe_id: str, body: dict, request: Request, p: Auth, db: DB):
    p.require("datasets:write")
    if cached := replay(db, p, request, body):
        return cached
    get(db, Recipe, recipe_id, p.organization_id)
    order = compile_recipe(body)
    if order[0]["type"] == "ingest":
        get(db, Upload, order[0]["config"]["upload_id"], p.organization_id)
    elif order[0]["type"] == "curate":
        get(db, Curation, order[0]["config"]["curation_id"], p.organization_id)
    record = RecipeRevision(
        id=uid("rev"),
        organization_id=p.organization_id,
        recipe_id=recipe_id,
        digest=digest(canonical(body)),
        definition=body,
    )
    db.add(record)
    audit(db, p, request, "recipe.revised", record.id)
    db.flush()
    return commit(db, request, public(record))


def estimate(db, p, revision):
    order = compile_recipe(revision.definition)
    if order[0]["type"] == "generate":
        count = GenerateConfig.model_validate(order[0]["config"]).count
    elif order[0]["type"] == "curate":
        source = get(db, Curation, order[0]["config"]["curation_id"], p.organization_id)
        if source.state != "FROZEN":
            raise Problem(409, "CURATION_NOT_FROZEN", "Complete and approve human review before launching.")
        count = source.quality["accepted"]
    else:
        source = get(db, Upload, order[0]["config"]["upload_id"], p.organization_id)
        if source.status != "COMPLETED":
            raise Problem(409, "UPLOAD_NOT_COMPLETE", "Complete and verify the upload before running.")
        count = source.sample_count
    return count, count * settings().local_rate_micro_usd


@app.post("/v1/recipes/{recipe_id}/estimate", tags=["Recipes"])
def estimate_recipe(recipe_id: str, p: Auth, db: DB):
    p.require("datasets:read")
    get(db, Recipe, recipe_id, p.organization_id)
    revision = db.scalar(
        select(RecipeRevision)
        .where(RecipeRevision.recipe_id == recipe_id, RecipeRevision.organization_id == p.organization_id)
        .order_by(RecipeRevision.created_at.desc())
    )
    count, cost = estimate(db, p, revision)
    return {
        "sample_count": count,
        "internal_estimate_usd": cost / 1e6,
        "external_cost_usd": 0,
        "rate_micro_usd": settings().local_rate_micro_usd,
        "pricing_basis": "Configured nonbillable local rate card; no external charges.",
    }


@app.post("/v1/runs", tags=["Runs"], response_model=RunOut, status_code=202)
def submit_run(body: s.RunCreate, request: Request, p: Auth, db: DB):
    p.require("runs:execute")
    if cached := replay(db, p, request, body.model_dump(mode="json")):
        return cached
    target = get(db, Dataset, body.dataset_id, p.organization_id)
    revision = get(db, RecipeRevision, body.recipe_revision_id, p.organization_id)
    recipe_record = get(db, Recipe, revision.recipe_id, p.organization_id)
    if target.project_id != recipe_record.project_id:
        raise Problem(422, "PROJECT_MISMATCH", "Recipe and dataset must belong to the same project.")
    if target.archived:
        raise Problem(409, "DATASET_ARCHIVED", "Restore the dataset before launching a run.")
    if target.policy.get("allowed_training_use") is not True:
        raise Problem(403, "POLICY_BLOCKED", "Source-use rights must permit the intended training use.")
    if body.compute_constraints:
        raise Problem(
            422, "CAPABILITY_UNAVAILABLE", "Only the configured local CPU text worker is available."
        )
    count, cost = estimate(db, p, revision)
    order = compile_recipe(revision.definition)
    if order[0]["type"] == "generate" and target.modality != "text":
        raise Problem(
            422,
            "CAPABILITY_UNAVAILABLE",
            "The deterministic generator produces text only. Upload real images and curate them.",
        )
    if order[0]["type"] == "ingest":
        upload = get(db, Upload, order[0]["config"]["upload_id"], p.organization_id)
        if upload.dataset_id != target.id:
            raise Problem(422, "SOURCE_DATASET_MISMATCH", "The upload must belong to the target dataset.")
    elif order[0]["type"] == "curate":
        source = get(db, Curation, order[0]["config"]["curation_id"], p.organization_id)
        if source.dataset_id != target.id:
            raise Problem(
                422, "SOURCE_DATASET_MISMATCH", "The frozen curation must belong to the target dataset."
            )
    budget = int(body.max_budget_usd * 1_000_000)
    recipe_budget = int(
        __import__("decimal").Decimal(str(revision.definition["budget"]["maximum"])) * 1_000_000
    )
    organization = db.scalar(
        select(Organization).where(Organization.id == p.organization_id).with_for_update()
    )
    if (
        cost > min(budget, recipe_budget)
        or organization.spent_micro + organization.reserved_micro + cost > organization.budget_micro
    ):
        raise Problem(402, "BUDGET_EXCEEDED", "The estimate exceeds the recipe, run, or organization budget.")
    organization.reserved_micro += cost
    record = Run(
        id=uid("run"),
        organization_id=p.organization_id,
        dataset_id=target.id,
        recipe_revision_id=revision.id,
        max_budget_micro=min(budget, recipe_budget),
        reserved_micro=cost,
        sample_count=count,
        checkpoint={"chunks": [], "rate_micro_usd": settings().local_rate_micro_usd},
    )
    db.add(record)
    db.flush()
    db.add(
        Outbox(
            id=uid("obx"),
            organization_id=p.organization_id,
            kind="run",
            resource_id=record.id,
            payload={"run_id": record.id},
        )
    )
    db.add(
        RunEvent(
            id=uid("log"),
            organization_id=p.organization_id,
            run_id=record.id,
            event_type="run.queued",
            message="Run accepted durably; waiting for the CPU worker.",
        )
    )
    emit(db, p.organization_id, "run.queued", record.id, {"run_id": record.id})
    audit(db, p, request, "run.submitted", record.id)
    result = commit(db, request, public(record), 202)
    result.headers["Location"] = f"/v1/runs/{record.id}"
    return result


@app.get("/v1/runs", tags=["Runs"], response_model=Page[RunOut])
def runs(
    p: Auth,
    db: DB,
    limit: int = Query(25, ge=1, le=100),
    cursor: str | None = None,
    dataset_id: str | None = None,
    status: str | None = None,
):
    p.require("datasets:read")
    extra = []
    if dataset_id:
        get(db, Dataset, dataset_id, p.organization_id)
        extra.append(Run.dataset_id == dataset_id)
    if status:
        extra.append(Run.status == status)
    return page(db, Run, p, limit, cursor, extra)


@app.get("/v1/runs/{run_id}", tags=["Runs"], response_model=RunOut)
def run(run_id: str, p: Auth, db: DB):
    p.require("datasets:read")
    record = get(db, Run, run_id, p.organization_id)
    version = db.scalar(
        select(Version).where(Version.run_id == record.id, Version.organization_id == p.organization_id)
    )
    return {**public(record), "version": public(version) if version else None}


@app.get("/v1/runs/{run_id}/events", tags=["Runs"])
def run_events(run_id: str, p: Auth, db: DB, limit: int = Query(100, ge=1, le=1000)):
    p.require("datasets:read")
    get(db, Run, run_id, p.organization_id)
    return {
        "items": [
            public(event)
            for event in db.scalars(
                select(RunEvent)
                .where(RunEvent.run_id == run_id, RunEvent.organization_id == p.organization_id)
                .order_by(RunEvent.created_at, RunEvent.id)
                .limit(limit)
            )
        ]
    }


@app.post("/v1/runs/{run_id}/cancel", tags=["Runs"])
def cancel_run(run_id: str, request: Request, p: Auth, db: DB):
    p.require("runs:execute")
    record = db.scalar(
        select(Run).where(Run.id == run_id, Run.organization_id == p.organization_id).with_for_update()
    )
    if not record:
        raise Problem(404, "NOT_FOUND", "Run not found.")
    if record.status in ("SUCCEEDED", "FAILED", "CANCELLED"):
        raise Problem(409, "RUN_TERMINAL", "This run has already finished.")
    record.cancel_requested = True
    audit(db, p, request, "run.cancel_requested", record.id)
    db.commit()
    return public(record)


@app.post("/v1/runs/{run_id}/retry", tags=["Runs"])
def retry_run(run_id: str, request: Request, p: Auth, db: DB):
    record = get(db, Run, run_id, p.organization_id)
    if record.status not in ("FAILED", "CANCELLED"):
        raise Problem(409, "RUN_NOT_RETRYABLE", "Only failed or cancelled runs can be retried.")
    return submit_run(
        s.RunCreate(
            dataset_id=record.dataset_id,
            recipe_revision_id=record.recipe_revision_id,
            max_budget_usd=__import__("decimal").Decimal(record.max_budget_micro) / 1000000,
        ),
        request,
        p,
        db,
    )


@app.get("/v1/datasets/{dataset_id}/versions", tags=["Versions"], response_model=Page[VersionOut])
def versions(dataset_id: str, p: Auth, db: DB):
    p.require("datasets:read")
    get(db, Dataset, dataset_id, p.organization_id)
    return {
        "items": [
            public(record)
            for record in db.scalars(
                select(Version)
                .where(Version.dataset_id == dataset_id, Version.organization_id == p.organization_id)
                .order_by(Version.number.desc())
            )
        ]
    }


@app.get("/v1/datasets/{dataset_id}/versions/{version_id}/manifest", tags=["Versions"])
def manifest(dataset_id: str, version_id: str, p: Auth, db: DB):
    p.require("datasets:read")
    get(db, Dataset, dataset_id, p.organization_id)
    record = get(db, Version, version_id, p.organization_id)
    if record.dataset_id != dataset_id:
        raise Problem(404, "NOT_FOUND", "Version not found.")
    if digest(canonical(record.manifest)) != record.manifest_hash:
        raise Problem(409, "MANIFEST_CORRUPT", "Manifest integrity verification failed.")
    return {"sha256": record.manifest_hash, "manifest": record.manifest}


@app.get("/v1/datasets/{dataset_id}/samples", tags=["Datasets"])
def samples(
    dataset_id: str,
    p: Auth,
    db: DB,
    version_id: str | None = None,
    offset: int = Query(0, ge=0, le=10000),
    limit: int = Query(10, ge=1, le=100),
):
    p.require("datasets:read")
    get(db, Dataset, dataset_id, p.organization_id)
    if version_id:
        version = get(db, Version, version_id, p.organization_id)
        if version.dataset_id != dataset_id:
            raise Problem(404, "NOT_FOUND", "Version not found.")
    else:
        version = db.scalar(
            select(Version)
            .where(Version.dataset_id == dataset_id, Version.organization_id == p.organization_id)
            .order_by(Version.number.desc())
        )
    if not version:
        return {"items": [], "total": 0, "offset": offset, "next_offset": None}
    values = parse_jsonl(read_artifact(version.manifest["data_artifact"]))
    return {
        "items": values[offset : offset + limit],
        "total": len(values),
        "offset": offset,
        "next_offset": offset + limit if offset + limit < len(values) else None,
    }


@app.get("/v1/datasets/{dataset_id}/versions/{version_id}/samples/{sample_id}/image", tags=["Versions"])
def sample_image(dataset_id: str, version_id: str, sample_id: str, p: Auth, db: DB):
    p.require("datasets:read")
    version = get(db, Version, version_id, p.organization_id)
    if version.dataset_id != dataset_id or version.manifest.get("modality") != "image":
        raise Problem(404, "NOT_FOUND", "Image not found.")
    values = parse_jsonl(read_artifact(version.manifest["data_artifact"]))
    sample = next((value for value in values if value["sample_id"] == sample_id), None)
    if not sample:
        raise Problem(404, "NOT_FOUND", "Image not found.")
    data = read_artifact(sample["payload"]["image"]["artifact"])
    return Response(
        data,
        media_type="image/png",
        headers={"X-Content-SHA256": digest(data), "Content-Security-Policy": "default-src 'none'; sandbox"},
    )


@app.post("/v1/exports", tags=["Exports"], response_model=ExportOut, status_code=202)
def create_export(body: s.ExportCreate, request: Request, p: Auth, db: DB):
    p.require("datasets:read")
    if cached := replay(db, p, request, body.model_dump()):
        return cached
    version = get(db, Version, body.version_id, p.organization_id)
    if version.manifest["policy"].get("allowed_training_use") is not True:
        raise Problem(403, "POLICY_BLOCKED", "The published version policy forbids this export.")
    if body.format != "jsonl" and body.format not in version.manifest.get("exports", {}):
        raise Problem(
            422,
            "EXPORT_FORMAT_UNAVAILABLE",
            "COCO/YOLO require an image version published from approved box annotations.",
        )
    record = Export(
        id=uid("exp"), organization_id=p.organization_id, version_id=version.id, format=body.format
    )
    db.add(record)
    db.flush()
    emit(db, p.organization_id, "export.ready", record.id, {"export_id": record.id, "version_id": version.id})
    audit(db, p, request, "export.created", record.id)
    return commit(db, request, public(record), 202)


@app.get("/v1/exports/{export_id}", tags=["Exports"], response_model=ExportOut)
def export(export_id: str, p: Auth, db: DB):
    p.require("datasets:read")
    record = get(db, Export, export_id, p.organization_id)
    token = signed_token(
        {"org": p.organization_id, "sub": p.user_id, "export_id": record.id, "exp": int(time.time()) + 300}
    )
    return {
        **public(record),
        "download_url": f"/v1/exports/{record.id}/download?grant={token}",
        "expires_in": 300,
    }


@app.get("/v1/exports/{export_id}/download", tags=["Exports"])
def download_export(export_id: str, grant: str, request: Request, p: Auth, db: DB):
    p.require("datasets:read")
    record = get(db, Export, export_id, p.organization_id)
    token = read_token(grant)
    if (
        token.get("org") != p.organization_id
        or token.get("sub") != p.user_id
        or token.get("export_id") != record.id
    ):
        raise Problem(403, "INVALID_GRANT", "This signed download belongs to another principal.")
    version = get(db, Version, record.version_id, p.organization_id)
    artifact = (
        version.manifest["data_artifact"]
        if record.format == "jsonl"
        else version.manifest["exports"][record.format]
    )
    data = read_artifact(artifact)
    audit(db, p, request, "export.downloaded", record.id)
    db.commit()
    return Response(
        data,
        media_type="application/x-ndjson" if record.format == "jsonl" else "application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{version.dataset_id}-v{version.number}.{record.format if record.format == "jsonl" else record.format + ".zip"}"',
            "X-Content-SHA256": digest(data),
        },
    )


@app.get("/v1/api-keys", tags=["API Keys"], response_model=Page[KeyOut], response_model_exclude_none=True)
def api_keys(p: Auth, db: DB):
    p.require("keys:manage")
    return page(db, ApiKey, p, 100)


@app.post("/v1/api-keys", tags=["API Keys"], response_model=KeyOut, status_code=201)
def create_key(body: s.KeyCreate, request: Request, p: Auth, db: DB):
    p.require("keys:manage")
    if cached := replay(db, p, request, body.model_dump()):
        return cached
    if any(scope not in p.scopes or scope not in SCOPES for scope in body.scopes):
        raise Problem(403, "SCOPE_ESCALATION", "Keys cannot exceed the creator's permissions.")
    secret = "foundry_" + secrets.token_urlsafe(36)
    record = ApiKey(
        id=uid("key"),
        organization_id=p.organization_id,
        user_id=p.user_id,
        name=body.name,
        prefix=secret[:16],
        secret_hash=digest(secret),
        scopes=body.scopes,
    )
    db.add(record)
    audit(db, p, request, "key.created", record.id)
    db.flush()
    value = public(record)
    return commit(db, request, {**value, "secret": secret}, stored=value)


@app.delete("/v1/api-keys/{key_id}", tags=["API Keys"])
def revoke_key(key_id: str, request: Request, p: Auth, db: DB):
    p.require("keys:manage")
    record = get(db, ApiKey, key_id, p.organization_id)
    record.revoked = True
    audit(db, p, request, "key.revoked", record.id)
    db.commit()
    return public(record)


@app.get("/v1/members", tags=["Members"])
def members(p: Auth, db: DB):
    p.require("members:manage")
    return {
        "items": [
            {"id": user.id, "email": user.email, "name": user.name, "role": membership.role}
            for membership, user in db.execute(
                select(Membership, User)
                .join(User)
                .where(Membership.organization_id == p.organization_id)
                .order_by(User.name)
            )
        ]
    }


@app.post("/v1/members", tags=["Members"])
def create_member(body: s.MemberCreate, request: Request, p: Auth, db: DB):
    p.require("members:manage")
    if cached := replay(
        db, p, request, {**body.model_dump(exclude={"password"}), "password_sha256": digest(body.password)}
    ):
        return cached
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise Problem(409, "ACCOUNT_UNAVAILABLE", "This account cannot be provisioned with this operation.")
    user = User(
        id=uid("usr"), email=body.email.lower(), name=body.name, password_hash=passwords.hash(body.password)
    )
    db.add(user)
    db.flush()
    db.add(Membership(user_id=user.id, organization_id=p.organization_id, role=body.role))
    audit(db, p, request, "member.created", user.id)
    return commit(db, request, {"id": user.id, "email": user.email, "name": user.name, "role": body.role})


@app.patch("/v1/members/{user_id}", tags=["Members"])
def change_member(user_id: str, body: s.MemberPatch, request: Request, p: Auth, db: DB):
    p.require("members:manage")
    membership = db.get(Membership, (p.organization_id, user_id))
    if not membership:
        raise Problem(404, "NOT_FOUND", "Member not found.")
    if membership.role == "Owner" or p.user_id == user_id:
        raise Problem(409, "OWNER_PROTECTED", "The owner and your own membership cannot be changed here.")
    membership.role = body.role
    audit(db, p, request, "member.role_changed", user_id)
    db.commit()
    return {"id": user_id, "role": body.role}


@app.delete("/v1/members/{user_id}", tags=["Members"])
def remove_member(user_id: str, request: Request, p: Auth, db: DB):
    p.require("members:manage")
    membership = db.get(Membership, (p.organization_id, user_id))
    if not membership:
        raise Problem(404, "NOT_FOUND", "Member not found.")
    if membership.role == "Owner" or user_id == p.user_id:
        raise Problem(409, "OWNER_PROTECTED", "The owner and your own membership cannot be removed here.")
    db.delete(membership)
    audit(db, p, request, "member.removed", user_id)
    db.commit()
    return {"removed": True}


@app.get("/v1/webhooks", tags=["Webhooks"], response_model=Page[WebhookOut], response_model_exclude_none=True)
def webhooks(p: Auth, db: DB):
    p.require("webhooks:manage")
    return page(db, Webhook, p, 100)


@app.post("/v1/webhooks", tags=["Webhooks"], response_model=WebhookOut, status_code=201)
def create_webhook(body: s.WebhookCreate, request: Request, p: Auth, db: DB):
    p.require("webhooks:manage")
    if cached := replay(db, p, request, body.model_dump()):
        return cached
    validate_webhook_url(body.url)
    secret = secrets.token_urlsafe(32)
    record = Webhook(
        id=uid("wh"),
        organization_id=p.organization_id,
        url=body.url,
        events=body.events,
        secret_encrypted=cipher().encrypt(secret.encode()).decode(),
    )
    db.add(record)
    audit(db, p, request, "webhook.created", record.id)
    db.flush()
    value = public(record)
    return commit(db, request, {**value, "signing_secret": secret}, stored=value)


@app.post("/v1/webhooks/{webhook_id}/rotate", tags=["Webhooks"])
def rotate_webhook(webhook_id: str, request: Request, p: Auth, db: DB):
    p.require("webhooks:manage")
    record = get(db, Webhook, webhook_id, p.organization_id)
    secret = secrets.token_urlsafe(32)
    record.secret_encrypted = cipher().encrypt(secret.encode()).decode()
    audit(db, p, request, "webhook.secret_rotated", record.id)
    db.commit()
    return {"id": record.id, "signing_secret": secret}


@app.delete("/v1/webhooks/{webhook_id}", tags=["Webhooks"])
def deactivate_webhook(webhook_id: str, request: Request, p: Auth, db: DB):
    p.require("webhooks:manage")
    record = get(db, Webhook, webhook_id, p.organization_id)
    record.active = False
    audit(db, p, request, "webhook.disabled", record.id)
    db.commit()
    return public(record)


@app.get("/v1/webhook-deliveries", tags=["Webhooks"])
def deliveries(p: Auth, db: DB, limit: int = Query(25, ge=1, le=100), cursor: str | None = None):
    p.require("webhooks:manage")
    return page(db, Delivery, p, limit, cursor)


@app.post("/v1/webhook-deliveries/{delivery_id}/replay", tags=["Webhooks"])
def replay_delivery(delivery_id: str, request: Request, p: Auth, db: DB):
    p.require("webhooks:manage")
    record = get(db, Delivery, delivery_id, p.organization_id)
    webhook = get(db, Webhook, record.webhook_id, p.organization_id)
    if not webhook.active:
        raise Problem(409, "WEBHOOK_DISABLED", "Enable a webhook before replaying its delivery.")
    record.status, record.attempts, record.next_attempt_at = "PENDING", 0, now()
    audit(db, p, request, "webhook.delivery_replayed", record.id)
    db.commit()
    return public(record)


@app.get("/v1/usage", tags=["Usage"])
def usage(p: Auth, db: DB):
    p.require("datasets:read")
    org = db.get(Organization, p.organization_id)
    values = db.execute(
        select(Usage.metric, func.sum(Usage.quantity))
        .where(Usage.organization_id == p.organization_id)
        .group_by(Usage.metric)
    ).all()
    return {
        "meters": dict(values),
        "budget_usd": org.budget_micro / 1e6,
        "reserved_usd": org.reserved_micro / 1e6,
        "internal_spent_usd": org.spent_micro / 1e6,
        "external_cost_usd": 0,
        "billing_status": "UNBILLED_LOCAL",
        "rate_micro_usd_per_sample": settings().local_rate_micro_usd,
    }


@app.patch("/v1/budgets", tags=["Usage"])
def budget(body: s.BudgetPatch, request: Request, p: Auth, db: DB):
    p.require("budgets:manage")
    org = db.scalar(select(Organization).where(Organization.id == p.organization_id).with_for_update())
    maximum = int(body.maximum_usd * 1_000_000)
    if maximum < org.spent_micro + org.reserved_micro:
        raise Problem(
            409, "BUDGET_RESERVED", "The budget cannot be lower than already spent and reserved amounts."
        )
    org.budget_micro = maximum
    audit(db, p, request, "budget.updated", org.id)
    db.commit()
    return {"maximum_usd": maximum / 1e6}


@app.get("/v1/audit-events", tags=["Audit"])
def audit_events(p: Auth, db: DB, limit: int = Query(25, ge=1, le=100), cursor: str | None = None):
    p.require("audit:read")
    return page(db, Audit, p, limit, cursor)


@app.get("/v1/overview", tags=["Overview"])
def overview(p: Auth, db: DB):
    p.require("datasets:read")
    counts = {
        name: db.scalar(select(func.count()).select_from(cls).where(cls.organization_id == p.organization_id))
        for name, cls in [("datasets", Dataset), ("versions", Version), ("runs", Run)]
    }
    recent = db.scalars(
        select(Run).where(Run.organization_id == p.organization_id).order_by(Run.created_at.desc()).limit(5)
    ).all()
    heartbeat = db.get(Heartbeat, "cpu")
    worker_ready = bool(heartbeat and heartbeat.seen_at > now() - timedelta(seconds=20))
    return {
        "counts": counts,
        "recent_runs": [public(record) for record in recent],
        "worker": "READY" if worker_ready else "UNAVAILABLE",
        "usage": usage(p, db),
        "local_webhook_url": settings().local_webhook_url,
        "capabilities": {
            "text_cpu": worker_ready,
            "model_providers": "BLOCKED_EXTERNAL",
            "gpu": "BLOCKED_EXTERNAL",
            "simulation": "BLOCKED_EXTERNAL",
        },
    }


@app.get("/v1/compute/pools", tags=["Compute"])
def compute_pools(p: Auth, db: DB):
    p.require("datasets:read")
    heartbeat = db.get(Heartbeat, "cpu")
    active = bool(heartbeat and heartbeat.seen_at > now() - timedelta(seconds=20))
    return {
        "items": [
            {
                "id": "local-cpu",
                "name": "Local CPU",
                "status": "READY" if active else "UNAVAILABLE",
                "capabilities": [
                    "deterministic.text@1",
                    "ingest.jsonl@1",
                    "ingest.image@1",
                    "quality.text@1",
                    "curation.human@1",
                ],
                "last_heartbeat": heartbeat.seen_at.isoformat() if heartbeat else None,
            }
        ]
    }


register_curation(app)
