"""SCIM 2.0 Users subset with tenant-bound provisioning tokens and local role limits."""

import re
import secrets
from typing import Annotated, Literal

from fastapi import Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError, field_validator
from sqlalchemy import func, select

from .db import session, uid
from .errors import Problem
from .models import ApiKey, Audit, Membership, ScimIdentity, ScimToken, User
from .schemas import Strict
from .security import digest, passwords, rate_limit

CORE_USER = "urn:ietf:params:scim:schemas:core:2.0:User"
PATCH = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
LIST = "urn:ietf:params:scim:api:messages:2.0:ListResponse"


class SCIMResponse(JSONResponse):
    media_type = "application/scim+json"


class ScimTokenCreate(Strict):
    name: str = Field(min_length=1, max_length=160)
    allowed_domain: str = Field(
        default="foundry.local", pattern=r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", max_length=254
    )


class ScimName(Strict):
    givenName: str = Field(default="", max_length=160)
    familyName: str = Field(default="", max_length=160)
    formatted: str = Field(default="", max_length=320)


class ScimRole(Strict):
    value: Literal["Engineer", "Labeler", "Viewer"] = "Viewer"


class ScimUser(Strict):
    schemas: list[str] = Field(default_factory=lambda: [CORE_USER], max_length=10)
    externalId: str | None = Field(default=None, min_length=1, max_length=200)
    userName: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    displayName: str = Field(default="", max_length=320)
    name: ScimName = Field(default_factory=ScimName)
    active: bool = True
    roles: list[ScimRole] = Field(default_factory=lambda: [ScimRole()], max_length=1)

    @field_validator("schemas")
    @classmethod
    def supported_schema(cls, value):
        if value != [CORE_USER]:
            raise ValueError("Only the SCIM core User schema is supported.")
        return value


class PatchOperation(Strict):
    op: str = Field(pattern="^(add|replace|remove|Add|Replace|Remove)$")
    path: str = Field(min_length=1, max_length=100)
    value: object = None


class ScimPatch(Strict):
    schemas: list[str] = Field(default_factory=lambda: [PATCH], max_length=3)
    Operations: list[PatchOperation] = Field(min_length=1, max_length=20)

    @field_validator("schemas")
    @classmethod
    def supported_schema(cls, value):
        if value != [PATCH]:
            raise ValueError("The SCIM PatchOp schema is required.")
        return value


def scim_auth(request: Request, db=Depends(session)):
    value = request.headers.get("authorization", "")
    if not value.startswith("Bearer foundry_scim_"):
        raise Problem(401, "SCIM_UNAUTHENTICATED", "A scoped SCIM provisioning token is required.")
    token = db.scalar(
        select(ScimToken)
        .where(ScimToken.secret_hash == digest(value[7:]), ScimToken.revoked.is_(False))
        .with_for_update()
    )
    if not token:
        raise Problem(401, "SCIM_UNAUTHENTICATED", "This provisioning token is invalid or revoked.")
    rate_limit("scim:" + token.id, 240)
    return token


def register(app):
    from .api import DB, Auth, audit, commit, get, page, public, replay

    ScimAuth = Annotated[ScimToken, Depends(scim_auth)]

    def record_audit(db, token, request, action, resource):
        db.add(
            Audit(
                id=uid("aud"),
                organization_id=token.organization_id,
                actor_id="scim:" + token.id,
                action=action,
                resource_id=resource,
                request_id=request.state.request_id,
            )
        )

    def lookup(db, token, identifier, write=False):
        query = select(ScimIdentity).where(
            ScimIdentity.id == identifier, ScimIdentity.organization_id == token.organization_id
        )
        row = db.scalar(query.with_for_update().execution_options(populate_existing=True) if write else query)
        if not row or row.attributes.get("deleted"):
            raise Problem(404, "NOT_FOUND", "Provisioned user not found.")
        return row

    def check_etag(request, row):
        supplied = request.headers.get("if-match")
        if supplied is None:
            raise Problem(
                428, "PRECONDITION_REQUIRED", "Provide this resource's If-Match ETag before editing it."
            )
        if supplied != f'W/"{row.revision}"':
            raise Problem(412, "STALE_SCIM_RESOURCE", "The provisioned user changed. Refresh its ETag.")

    def resource(row):
        attributes = {key: value for key, value in row.attributes.items() if key != "deleted"}
        return {
            **attributes,
            "schemas": [CORE_USER],
            "id": row.id,
            "externalId": row.external_id,
            "active": row.active,
            "meta": {
                "resourceType": "User",
                "created": row.created_at.isoformat(),
                "version": f'W/"{row.revision}"',
                "location": f"/v1/scim/v2/Users/{row.id}",
            },
        }

    def synchronize(db, row, body, token):
        email = body.userName.lower()
        if email.split("@", 1)[1] != token.allowed_domain:
            raise Problem(
                403,
                "SCIM_DOMAIN_FORBIDDEN",
                "This provisioning token is restricted to its configured domain.",
            )
        member = db.scalar(
            select(Membership)
            .where(Membership.organization_id == token.organization_id, Membership.user_id == row.user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if member and member.role in {"Owner", "Admin"}:
            raise Problem(
                403, "SCIM_PRIVILEGED_USER", "SCIM tokens cannot modify privileged organization memberships."
            )
        if row.attributes.get("userName", email) != email:
            raise Problem(
                400, "SCIM_IMMUTABLE_USERNAME", "userName is immutable for this local SCIM binding."
            )
        row.attributes, row.active = {**body.model_dump(), "userName": email}, body.active
        if body.active:
            role = body.roles[0].value if body.roles else "Viewer"
            if member:
                member.role = role
            else:
                db.add(Membership(organization_id=token.organization_id, user_id=row.user_id, role=role))
        else:
            if member:
                db.delete(member)
            for key in db.scalars(
                select(ApiKey).where(
                    ApiKey.organization_id == token.organization_id, ApiKey.user_id == row.user_id
                )
            ):
                key.revoked = True

    @app.post("/v1/governance/scim-tokens", tags=["Provisioning"], status_code=201)
    def create_scim_token(body: ScimTokenCreate, request: Request, p: Auth, db: DB):
        p.require("members:manage")
        if cached := replay(db, p, request, body.model_dump()):
            return cached
        secret = "foundry_scim_" + secrets.token_urlsafe(36)
        record = ScimToken(
            id=uid("sct"),
            organization_id=p.organization_id,
            name=body.name,
            allowed_domain=body.allowed_domain.lower(),
            secret_hash=digest(secret),
        )
        db.add(record)
        audit(db, p, request, "scim.token.created", record.id)
        db.flush()
        return commit(db, request, {**public(record), "provisioning_token": secret}, stored=public(record))

    @app.get("/v1/governance/scim-tokens", tags=["Provisioning"])
    def scim_tokens(p: Auth, db: DB):
        p.require("members:manage")
        return page(db, ScimToken, p, 100)

    @app.post("/v1/governance/scim-tokens/{token_id}/revoke", tags=["Provisioning"])
    def revoke_scim_token(token_id: str, request: Request, p: Auth, db: DB):
        p.require("members:manage")
        if cached := replay(db, p, request, {}):
            return cached
        token = get(db, ScimToken, token_id, p.organization_id)
        token.revoked = True
        audit(db, p, request, "scim.token.revoked", token.id)
        db.flush()
        return commit(db, request, public(token), 200)

    @app.get("/v1/scim/v2/ServiceProviderConfig", tags=["SCIM 2.0"], response_class=SCIMResponse)
    def service_provider_config(token: ScimAuth):
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
            "patch": {"supported": True},
            "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
            "filter": {"supported": True, "maxResults": 100},
            "changePassword": {"supported": False},
            "sort": {"supported": False},
            "etag": {"supported": True},
            "authenticationSchemes": [
                {
                    "type": "oauthbearertoken",
                    "name": "Tenant provisioning token",
                    "description": "Locally enrolled scoped bearer token",
                    "primary": True,
                }
            ],
            "documentationUri": "/v1/docs",
        }

    @app.get("/v1/scim/v2/ResourceTypes", tags=["SCIM 2.0"], response_class=SCIMResponse)
    def resource_types(token: ScimAuth):
        return {
            "schemas": [LIST],
            "totalResults": 1,
            "Resources": [
                {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
                    "id": "User",
                    "name": "User",
                    "endpoint": "/Users",
                    "schema": CORE_USER,
                }
            ],
        }

    @app.post("/v1/scim/v2/Users", tags=["SCIM 2.0"], status_code=201, response_class=SCIMResponse)
    def provision_user(body: ScimUser, request: Request, response: Response, token: ScimAuth, db: DB):
        if body.userName.lower().split("@", 1)[1] != token.allowed_domain:
            raise Problem(
                403,
                "SCIM_DOMAIN_FORBIDDEN",
                "This provisioning token is restricted to its configured domain.",
            )
        external_id = body.externalId or body.userName.lower()
        if db.scalar(
            select(ScimIdentity.id).where(
                ScimIdentity.organization_id == token.organization_id, ScimIdentity.external_id == external_id
            )
        ):
            raise Problem(409, "SCIM_USER_EXISTS", "This external identity is already provisioned.")
        user = db.scalar(select(User).where(User.email == body.userName.lower()))
        if not user:
            display = (
                body.displayName
                or body.name.formatted
                or " ".join([body.name.givenName, body.name.familyName]).strip()
                or body.userName
            )
            user = User(
                id=uid("usr"),
                email=body.userName.lower(),
                name=display[:160],
                password_hash=passwords.hash(secrets.token_urlsafe(48)),
            )
            db.add(user)
            db.flush()
        if db.scalar(
            select(ScimIdentity.id).where(
                ScimIdentity.organization_id == token.organization_id, ScimIdentity.user_id == user.id
            )
        ):
            raise Problem(409, "SCIM_USER_EXISTS", "This user already has a provisioning binding.")
        record = ScimIdentity(
            id=uid("susr"),
            organization_id=token.organization_id,
            user_id=user.id,
            external_id=external_id,
            attributes={},
        )
        synchronize(db, record, body, token)
        db.add(record)
        record_audit(db, token, request, "scim.user.provisioned", record.id)
        db.flush()
        data = resource(record)
        db.commit()
        response.headers["ETag"] = data["meta"]["version"]
        response.headers["Location"] = data["meta"]["location"]
        return data

    @app.get("/v1/scim/v2/Users", tags=["SCIM 2.0"], response_class=SCIMResponse)
    def list_provisioned_users(
        token: ScimAuth,
        db: DB,
        startIndex: int = Query(1, ge=1, le=10000),
        count: int = Query(25, ge=1, le=100),
        filter: str | None = Query(None, max_length=500),
    ):
        query = select(ScimIdentity).where(
            ScimIdentity.organization_id == token.organization_id,
            ScimIdentity.attributes["deleted"].as_boolean().is_not(True),
        )
        if filter:
            match = re.fullmatch(r'userName eq "([^"\s]+)"', filter)
            if not match:
                raise Problem(
                    400, "SCIM_INVALID_FILTER", 'Supported filter: userName eq "address@example.com".'
                )
            query = query.where(ScimIdentity.attributes["userName"].as_string() == match[1].lower())
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        selected = db.scalars(query.order_by(ScimIdentity.id).offset(startIndex - 1).limit(count)).all()
        return {
            "schemas": [LIST],
            "totalResults": total,
            "startIndex": startIndex,
            "itemsPerPage": len(selected),
            "Resources": [resource(row) for row in selected],
        }

    @app.get("/v1/scim/v2/Users/{user_id}", tags=["SCIM 2.0"], response_class=SCIMResponse)
    def provisioned_user(user_id: str, response: Response, token: ScimAuth, db: DB):
        row = lookup(db, token, user_id)
        response.headers["ETag"] = f'W/"{row.revision}"'
        return resource(row)

    @app.put("/v1/scim/v2/Users/{user_id}", tags=["SCIM 2.0"], response_class=SCIMResponse)
    def replace_provisioned_user(
        user_id: str, body: ScimUser, request: Request, response: Response, token: ScimAuth, db: DB
    ):
        row = lookup(db, token, user_id, write=True)
        check_etag(request, row)
        if body.externalId not in (None, row.external_id):
            raise Problem(400, "SCIM_IMMUTABLE_EXTERNAL_ID", "externalId is immutable for this binding.")
        synchronize(db, row, body, token)
        row.revision += 1
        record_audit(db, token, request, "scim.user.replaced", row.id)
        db.commit()
        response.headers["ETag"] = f'W/"{row.revision}"'
        return resource(row)

    @app.patch("/v1/scim/v2/Users/{user_id}", tags=["SCIM 2.0"], response_class=SCIMResponse)
    def patch_provisioned_user(
        user_id: str, body: ScimPatch, request: Request, response: Response, token: ScimAuth, db: DB
    ):
        row = lookup(db, token, user_id, write=True)
        check_etag(request, row)
        data = {key: value for key, value in row.attributes.items() if key != "deleted"}
        for operation in body.Operations:
            if operation.path not in {"active", "roles", "displayName", "name"}:
                raise Problem(
                    400, "SCIM_INVALID_PATH", "Only active, roles, displayName and name are writable."
                )
            if operation.op.lower() == "remove":
                if operation.path != "roles":
                    raise Problem(
                        400,
                        "SCIM_INVALID_PATH",
                        "Only roles can be removed; active requires explicit replacement.",
                    )
                data["roles"] = [{"value": "Viewer"}]
            else:
                data[operation.path] = operation.value
        try:
            updated = ScimUser.model_validate(data)
        except ValidationError:
            raise Problem(
                400, "SCIM_INVALID_VALUE", "The patch does not conform to the supported User schema."
            ) from None
        synchronize(db, row, updated, token)
        row.revision += 1
        record_audit(db, token, request, "scim.user.patched", row.id)
        db.commit()
        response.headers["ETag"] = f'W/"{row.revision}"'
        return resource(row)

    @app.delete("/v1/scim/v2/Users/{user_id}", tags=["SCIM 2.0"], status_code=204)
    def delete_provisioned_user(user_id: str, request: Request, token: ScimAuth, db: DB):
        row = lookup(db, token, user_id, write=True)
        check_etag(request, row)
        data = {key: value for key, value in row.attributes.items() if key != "deleted"}
        data["active"] = False
        synchronize(db, row, ScimUser.model_validate(data), token)
        row.attributes = {**row.attributes, "deleted": True}
        row.revision += 1
        record_audit(db, token, request, "scim.user.deleted", row.id)
        db.commit()
