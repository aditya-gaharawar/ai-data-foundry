"""Private in-app notices materialized from durable facts; never external delivery."""

import time
from datetime import datetime

from fastapi import Query, Request
from pydantic import AwareDatetime
from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert

from .db import now, uid
from .dto import Page
from .errors import Problem
from .models import Notification, Run, WorkflowSchedule
from .schemas import Strict
from .security import read_token, signed_token


class NotificationOut(Strict):
    id: str
    organization_id: str
    created_at: datetime
    kind: str
    title: str
    body: str
    read_at: datetime | None
    target: str | None


class NotificationSummary(Strict):
    unread_count: int
    as_of: datetime


class ReadAll(Strict):
    before: AwareDatetime


class ReadAllOut(Strict):
    marked_read: int
    before: datetime


def notify(db, *, org, user, event_key, kind, title, body, resource_kind, resource_id):
    db.execute(
        insert(Notification)
        .values(
            id=uid("ntf"),
            organization_id=org,
            user_id=user,
            event_key=event_key,
            kind=kind,
            title=title,
            body=body,
            resource_kind=resource_kind,
            resource_id=resource_id,
            created_at=now(),
        )
        .on_conflict_do_nothing(index_elements=["organization_id", "user_id", "event_key"])
    )


def materialize_run_notice(db, event):
    kind = event.payload.get("event_type")
    outcomes = {
        "run.succeeded": ("Run published", "Your run completed and published an immutable dataset version."),
        "run.failed": ("Run failed", "Your run stopped. Open the run to review its diagnostic events."),
        "run.cancelled": (
            "Run cancelled",
            "Your run was cancelled and its unused budget reservation was released.",
        ),
    }
    if kind not in outcomes:
        return
    run = db.scalar(
        select(Run).where(Run.id == event.resource_id, Run.organization_id == event.organization_id)
    )
    if not run or not run.submitted_by:
        return  # Legacy jobs have no reliable recipient; never invent one.
    title, body = outcomes[kind]
    notify(
        db,
        org=run.organization_id,
        user=run.submitted_by,
        event_key=f"run:{run.id}:{kind}",
        kind=kind,
        title=title,
        body=body,
        resource_kind="run",
        resource_id=run.id,
    )


def output(db, p, record):
    from .api import get

    target = None
    kind = record.resource_kind
    scope = "datasets:read" if kind == "run" else "schedules:manage"
    if scope in p.scopes and kind in {"run", "schedule"}:
        try:
            get(db, Run if kind == "run" else WorkflowSchedule, record.resource_id, p.organization_id)
            target = (
                f"/runs/{record.resource_id}"
                if kind == "run"
                else f"/schedules?selected={record.resource_id}"
            )
        except Problem:
            pass  # A notice must not grant access to a subsequently protected/erased resource.
    return NotificationOut(
        id=record.id,
        organization_id=record.organization_id,
        created_at=record.created_at,
        kind=record.kind,
        title=record.title,
        body=record.body,
        read_at=record.read_at,
        target=target,
    ).model_dump(mode="json")


def register(app):
    from .api import DB, Auth, commit, replay

    def owned(db, p, identifier):
        record = db.scalar(
            select(Notification)
            .where(
                Notification.id == identifier,
                Notification.organization_id == p.organization_id,
                Notification.user_id == p.user_id,
            )
            .with_for_update()
        )
        if not record:
            raise Problem(404, "NOT_FOUND", "Notification not found.")
        return record

    @app.get("/v1/notifications/summary", tags=["Notifications"], response_model=NotificationSummary)
    def notification_summary(p: Auth, db: DB):
        p.require("notifications:read")
        stamp = now()
        count = db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.organization_id == p.organization_id,
                Notification.user_id == p.user_id,
                Notification.read_at.is_(None),
                Notification.created_at <= stamp,
            )
        )
        return {"unread_count": count, "as_of": stamp}

    @app.get("/v1/notifications", tags=["Notifications"], response_model=Page[NotificationOut])
    def list_notifications(
        p: Auth, db: DB, unread: bool = False, limit: int = Query(25, ge=1, le=100), cursor: str | None = None
    ):
        p.require("notifications:read")
        query = select(Notification).where(
            Notification.organization_id == p.organization_id, Notification.user_id == p.user_id
        )
        if unread:
            query = query.where(Notification.read_at.is_(None))
        if cursor:
            data = read_token(cursor)
            if (data.get("org"), data.get("user"), data.get("entity"), data.get("unread")) != (
                p.organization_id,
                p.user_id,
                "notifications",
                unread,
            ):
                raise Problem(404, "INVALID_CURSOR", "Cursor not found.")
            try:
                stamp = datetime.fromisoformat(data["created_at"])
                if stamp.tzinfo is None:
                    raise ValueError
                query = query.where(
                    tuple_(Notification.created_at, Notification.id) < tuple_(stamp, data["last"])
                )
            except (KeyError, ValueError, TypeError):
                raise Problem(
                    422, "INVALID_CURSOR", "Refresh the inbox to obtain a current cursor."
                ) from None
        rows = db.scalars(
            query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
        ).all()
        more, rows = len(rows) > limit, rows[:limit]
        token = (
            signed_token(
                {
                    "org": p.organization_id,
                    "user": p.user_id,
                    "entity": "notifications",
                    "unread": unread,
                    "created_at": rows[-1].created_at.isoformat(),
                    "last": rows[-1].id,
                    "exp": int(time.time()) + 86400,
                }
            )
            if more
            else None
        )
        return {"items": [output(db, p, record) for record in rows], "next_cursor": token}

    @app.post("/v1/notifications/read-all", tags=["Notifications"], response_model=ReadAllOut)
    def read_all_notifications(body: ReadAll, request: Request, p: Auth, db: DB):
        p.require("notifications:read")
        if cached := replay(db, p, request, body.model_dump(mode="json")):
            return cached
        if body.before > now():
            raise Problem(422, "FUTURE_CUTOFF", "Use the as_of value from the inbox summary.")
        from sqlalchemy import update

        result = db.execute(
            update(Notification)
            .where(
                Notification.organization_id == p.organization_id,
                Notification.user_id == p.user_id,
                Notification.read_at.is_(None),
                Notification.created_at <= body.before,
            )
            .values(read_at=now())
        )
        return commit(db, request, {"marked_read": result.rowcount, "before": body.before.isoformat()}, 200)

    @app.post(
        "/v1/notifications/{notification_id}/read", tags=["Notifications"], response_model=NotificationOut
    )
    def read_notification(notification_id: str, request: Request, p: Auth, db: DB):
        p.require("notifications:read")
        record = owned(db, p, notification_id)
        if replay(db, p, request, {}):
            # A prior read acknowledgement must not restore a now-protected navigation target.
            return output(db, p, record)
        record.read_at = record.read_at or now()
        return commit(db, request, output(db, p, record), 200)
