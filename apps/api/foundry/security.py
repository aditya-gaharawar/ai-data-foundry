import base64
import hashlib
import hmac
import ipaddress
import json
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from cryptography.fernet import Fernet
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session as DBSession

from .config import settings
from .db import Session, now, session
from .errors import Problem
from .models import ApiKey, LoginSession, Membership, RateLimit, User

passwords = PasswordHasher()
SCOPES = [
    "datasets:read",
    "datasets:write",
    "runs:execute",
    "keys:manage",
    "members:manage",
    "webhooks:manage",
    "audit:read",
    "budgets:manage",
]
ROLES = {
    "Owner": SCOPES,
    "Admin": SCOPES,
    "Engineer": ["datasets:read", "datasets:write", "runs:execute"],
    "Viewer": ["datasets:read"],
}


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def verify_password(encoded: str, value: str) -> bool:
    try:
        return passwords.verify(encoded, value)
    except VerificationError:
        return False


def rate_limit(identity: str, maximum: int):
    from datetime import timedelta

    stamp = int(time.time() // 60)
    key = digest(f"{identity}:{stamp}")
    with Session.begin() as db:
        query = insert(RateLimit).values(key=key, count=1, expires_at=now() + timedelta(minutes=2))
        count = db.scalar(
            query.on_conflict_do_update(
                index_elements=[RateLimit.key], set_={"count": RateLimit.count + 1}
            ).returning(RateLimit.count)
        )
    if count > maximum:
        raise Problem(429, "RATE_LIMITED", "Request limit reached. Retry after the current minute.")


def cipher() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings().app_secret.encode()).digest()))


def signed_token(data: dict) -> str:
    body = base64.urlsafe_b64encode(canonical(data)).decode().rstrip("=")
    signature = hmac.new(settings().app_secret.encode(), body.encode(), "sha256").hexdigest()
    return f"{body}.{signature}"


def read_token(value: str) -> dict:
    try:
        body, signature = value.rsplit(".", 1)
        expected = hmac.new(settings().app_secret.encode(), body.encode(), "sha256").hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if data.get("exp", 0) < time.time():
            raise ValueError
        return data
    except (ValueError, KeyError, TypeError):
        raise Problem(403, "INVALID_GRANT", "The signed grant is invalid or expired.") from None


def webhook_signature(secret: str, timestamp: str, body: bytes) -> str:
    return "v1=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, "sha256").hexdigest()


def validate_webhook_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.fragment or not parsed.hostname:
        raise Problem(422, "INVALID_WEBHOOK_URL", "Use a URL without embedded credentials or fragments.")
    allowed_local = settings().webhook_local_hosts.split(",")
    if parsed.hostname in allowed_local and settings().app_env == "local":
        if parsed.scheme not in ("http", "https"):
            raise Problem(422, "INVALID_WEBHOOK_URL", "Use HTTP or HTTPS.")
        return
    # This milestone deliberately has no external network delivery surface.
    # The allowlist is exact and is checked again immediately before dispatch.
    raise Problem(
        422, "EXTERNAL_DELIVERY_DISABLED", "Local mode allows only configured local webhook receivers."
    )


def check_public_address(host: str) -> bool:
    """Reserved for future reviewed external delivery; never used to bypass the local allowlist."""
    try:
        return all(ipaddress.ip_address(row[4][0]).is_global for row in socket.getaddrinfo(host, None))
    except socket.gaierror:
        return False


@dataclass
class Principal:
    user_id: str
    organization_id: str
    role: str
    scopes: list[str]
    key_id: str | None = None

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise Problem(403, "INSUFFICIENT_SCOPE", f"This action requires {scope}.")


def principal(request: Request, db: DBSession = Depends(session)) -> Principal:
    authorization = request.headers.get("authorization", "")
    key = None
    login = None
    if authorization:
        if not authorization.startswith("Bearer foundry_"):
            raise Problem(401, "UNAUTHENTICATED", "A valid API key is required.")
        key = db.scalar(
            select(ApiKey).where(ApiKey.secret_hash == digest(authorization[7:]), ApiKey.revoked.is_(False))
        )
        if not key:
            raise Problem(401, "UNAUTHENTICATED", "The API key is invalid or revoked.")
        user_id = key.user_id
    else:
        token = request.cookies.get("foundry_session", "")
        login = db.get(LoginSession, digest(token)) if token else None
        if not login or login.expires_at <= now():
            raise Problem(401, "UNAUTHENTICATED", "Sign in to continue.")
        user_id = login.user_id
    user = db.get(User, user_id)
    if not user or not user.active:
        raise Problem(401, "UNAUTHENTICATED", "This account is unavailable.")
    rate_limit("api:" + (key.id if key else user.id), 600)
    org_id = request.headers.get("x-organization-id") or (key.organization_id if key else None)
    query = select(Membership).where(Membership.user_id == user_id)
    if org_id:
        query = query.where(Membership.organization_id == org_id)
    membership = db.scalar(query.order_by(Membership.organization_id))
    if not membership or (key and key.organization_id != membership.organization_id):
        raise Problem(404, "NOT_FOUND", "Organization not found.")
    if login and request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        csrf = request.headers.get("x-csrf-token", "")
        if origin not in settings().origins or not hmac.compare_digest(digest(csrf), login.csrf_hash):
            raise Problem(403, "CSRF_REJECTED", "The request origin or CSRF token is invalid.")
    scopes = ROLES[membership.role]
    if key:
        scopes = [s for s in scopes if s in key.scopes]
    return Principal(user_id, membership.organization_id, membership.role, scopes, key.id if key else None)
