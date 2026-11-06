"""Postgres due queue; admitted runs execute through the existing durable Temporal path."""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Query, Request
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import func, select, text

from .db import Session, now, uid
from .dto import Page
from .errors import Problem
from .models import ApiKey, Audit, Heartbeat, Membership, Run, ScheduleOccurrence, User, WorkflowSchedule
from .notifications import notify
from .schemas import RunCreate, Strict
from .security import ROLES, Principal

MAINTENANCE_LOCK = "foundry:automation-maintenance"
LATE_GRACE_SECONDS = 120
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}
REQUIRED_SCOPES = {"datasets:read", "runs:execute", "schedules:manage"}


class ScheduleDefinition(Strict):
    mode: Literal["interval", "daily"] = "interval"
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    timezone: str = Field(default="Asia/Kolkata", max_length=100)
    interval_seconds: int | None = Field(default=None, ge=10, le=30 * 86400)
    daily_time: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def bounded(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use a supported IANA timezone.") from None
        if not timedelta(0) < self.ends_at - self.starts_at <= timedelta(days=30):
            raise ValueError("The schedule window must be positive and at most 30 days.")
        if self.mode == "interval" and (self.interval_seconds is None or self.daily_time is not None):
            raise ValueError("Interval schedules require interval_seconds and no daily_time.")
        if self.mode == "daily" and (self.daily_time is None or self.interval_seconds is not None):
            raise ValueError("Daily schedules require daily_time and no interval_seconds.")
        return self


class SchedulePreview(Strict):
    name: str = Field(min_length=1, max_length=160)
    dataset_id: str
    recipe_revision_id: str
    definition: ScheduleDefinition
    max_runs: int = Field(ge=1, le=100)
    run_budget_usd: Decimal = Field(ge=0, le=1000000, decimal_places=6)
    total_budget_usd: Decimal = Field(ge=0, le=1000000, decimal_places=6)


class ScheduleCreate(SchedulePreview):
    approved_for_scheduled_execution: Literal[True]


class ScheduleControl(Strict):
    action: Literal["pause", "resume", "cancel"]
    expected_revision: int = Field(ge=1)
    approved_for_scheduled_execution: bool = False


class ScheduleOut(Strict):
    id: str
    organization_id: str
    created_at: datetime
    name: str
    dataset_id: str
    recipe_revision_id: str
    created_by: str
    authorized_by: str
    authorized_key_id: str | None
    definition: ScheduleDefinition
    state: Literal["ACTIVE", "PAUSED", "BLOCKED", "COMPLETED", "EXPIRED", "CANCELLED"]
    next_run_at: datetime | None
    last_run_at: datetime | None
    max_runs: int
    launched_runs: int
    skipped_runs: int
    run_budget_micro: int
    total_budget_micro: int
    admitted_micro: int
    revision: int
    last_error_code: str | None
    last_error: str | None


class OccurrenceOut(Strict):
    id: str
    organization_id: str
    created_at: datetime
    schedule_id: str
    scheduled_at: datetime
    status: str
    run_id: str | None
    code: str
    message: str
    estimate_micro: int


class SchedulePreviewOut(Strict):
    sample_count: int
    estimate_micro: int
    admitted_limit_micro: int
    affordable_runs: int
    next_occurrences: list[datetime]
    semantics: str


class SchedulerHealth(Strict):
    status: Literal["READY", "UNAVAILABLE"]
    last_heartbeat: datetime | None
    late_grace_seconds: int
    minimum_interval_seconds: int


def next_occurrence(definition: ScheduleDefinition, after: datetime, *, inclusive=False):
    """UTC instants; daily gaps are skipped and repeated times use the first fold only."""
    start, end = definition.starts_at.astimezone(UTC), definition.ends_at.astimezone(UTC)
    after = after.astimezone(UTC)
    if definition.mode == "interval":
        interval = timedelta(seconds=definition.interval_seconds)
        steps = max(0, (after - start) // interval)
        candidate = start + steps * interval
        if candidate < after or (candidate == after and not inclusive):
            candidate += interval
        return candidate if candidate < end else None
    zone = ZoneInfo(definition.timezone)
    day = max(start, after).astimezone(zone).date()
    hour, minute = map(int, definition.daily_time.split(":"))
    for offset in range(33):
        naive = datetime.combine(day + timedelta(days=offset), time(hour, minute))
        local = naive.replace(tzinfo=zone, fold=0)
        candidate = local.astimezone(UTC)
        if candidate.astimezone(zone).replace(tzinfo=None) != naive:
            continue
        if candidate >= start and (candidate > after or (inclusive and candidate == after)):
            return candidate if candidate < end else None
    return None


def require_authority(p):
    for scope in sorted(REQUIRED_SCOPES):
        p.require(scope)


def delegated_principal(db, record):
    # Revalidate and lock the original delegation; revoked keys/roles cannot keep launching jobs.
    user = db.scalar(select(User).where(User.id == record.authorized_by).with_for_update())
    member = db.scalar(
        select(Membership)
        .where(
            Membership.user_id == record.authorized_by, Membership.organization_id == record.organization_id
        )
        .with_for_update()
    )
    if not user or not user.active or not member:
        raise Problem(403, "SCHEDULE_AUTH_REVOKED", "The authorizing account or membership is unavailable.")
    scopes = set(ROLES.get(member.role, [])) & set(record.authorized_scopes)
    if record.authorized_key_id:
        key = db.scalar(
            select(ApiKey)
            .where(ApiKey.id == record.authorized_key_id, ApiKey.organization_id == record.organization_id)
            .with_for_update()
        )
        if not key or key.revoked or key.user_id != user.id:
            raise Problem(403, "SCHEDULE_AUTH_REVOKED", "The authorizing API key is unavailable or revoked.")
        scopes &= set(key.scopes)
    p = Principal(user.id, record.organization_id, member.role, sorted(scopes), record.authorized_key_id)
    require_authority(p)
    db.info.update(principal=p, mutation=True)
    return p


def preview(db, p, body, *, validate_start=True):
    from .api import plan_run

    require_authority(p)
    stamp = now()
    if validate_start and body.definition.starts_at <= stamp:
        raise Problem(
            422, "SCHEDULE_START_PASSED", "Choose a future start time before authorizing a schedule."
        )
    _, _, count, cost, _, _, _ = plan_run(
        db,
        p,
        RunCreate(
            dataset_id=body.dataset_id,
            recipe_revision_id=body.recipe_revision_id,
            max_budget_usd=body.run_budget_usd,
        ),
    )
    total = int(body.total_budget_usd * 1_000_000)
    if cost > total:
        raise Problem(402, "SCHEDULE_BUDGET_EXCEEDED", "The total cap must cover at least one estimated run.")
    dates, cursor = [], max(body.definition.starts_at, stamp)
    for index in range(min(body.max_runs, 10)):
        candidate = next_occurrence(body.definition, cursor, inclusive=index == 0)
        if candidate is None:
            break
        dates.append(candidate)
        cursor = candidate
    if not dates:
        raise Problem(422, "EMPTY_SCHEDULE", "No future occurrence fits within this schedule window.")
    return {
        "sample_count": count,
        "estimate_micro": cost,
        "admitted_limit_micro": total,
        "affordable_runs": min(body.max_runs, total // cost) if cost else body.max_runs,
        "next_occurrences": dates,
        "semantics": "At most one launch per tick; no overlap. Ticks over 120 seconds late are skipped. "
        "Daily DST gaps are skipped; repeated times use the first occurrence. "
        "Total cap counts admitted estimates, including cancelled/failed runs.",
    }


def schedule_output(record):
    return ScheduleOut.model_validate(record, from_attributes=True).model_dump(mode="json")


def register(app):
    from .api import DB, Auth, audit, commit, get, page, replay
    from .policies import enforce_resource

    def locked(db, p, identifier):
        row = db.scalar(
            select(WorkflowSchedule)
            .where(WorkflowSchedule.id == identifier, WorkflowSchedule.organization_id == p.organization_id)
            .with_for_update()
        )
        if not row:
            raise Problem(404, "NOT_FOUND", "Schedule not found.")
        enforce_resource(db, row)
        if p.role not in {"Owner", "Admin"} and p.user_id not in {row.created_by, row.authorized_by}:
            raise Problem(
                403,
                "SCHEDULE_OWNER_REQUIRED",
                "Only this schedule's owner or an administrator may control it.",
            )
        return row

    @app.get("/v1/schedules/health", tags=["Schedules"], response_model=SchedulerHealth)
    def scheduler_health(p: Auth, db: DB):
        p.require("schedules:manage")
        beat = db.get(Heartbeat, "scheduler")
        return {
            "status": "READY" if beat and beat.seen_at > now() - timedelta(seconds=20) else "UNAVAILABLE",
            "last_heartbeat": beat.seen_at if beat else None,
            "late_grace_seconds": LATE_GRACE_SECONDS,
            "minimum_interval_seconds": 10,
        }

    @app.post("/v1/schedules/preview", tags=["Schedules"], response_model=SchedulePreviewOut)
    def preview_schedule(body: SchedulePreview, p: Auth, db: DB):
        return preview(db, p, body)

    @app.post("/v1/schedules", tags=["Schedules"], response_model=ScheduleOut, status_code=201)
    def create_schedule(body: ScheduleCreate, request: Request, p: Auth, db: DB):
        require_authority(p)
        if cached := replay(db, p, request, body.model_dump(mode="json")):
            return cached
        report = preview(db, p, body)
        # plan_run holds the organization budget row, serializing tenant creation and admission.
        if (
            db.scalar(
                select(func.count())
                .select_from(WorkflowSchedule)
                .where(
                    WorkflowSchedule.organization_id == p.organization_id,
                    WorkflowSchedule.state.in_(["ACTIVE", "PAUSED", "BLOCKED"]),
                )
            )
            >= 100
        ):
            raise Problem(
                409,
                "SCHEDULE_LIMIT",
                "Cancel or finish an existing schedule before adding another (limit 100).",
            )
        record = WorkflowSchedule(
            id=uid("sch"),
            organization_id=p.organization_id,
            name=body.name,
            dataset_id=body.dataset_id,
            recipe_revision_id=body.recipe_revision_id,
            created_by=p.user_id,
            authorized_by=p.user_id,
            authorized_key_id=p.key_id,
            authorized_scopes=list(p.scopes),
            definition=body.definition.model_dump(mode="json"),
            next_run_at=report["next_occurrences"][0],
            max_runs=body.max_runs,
            run_budget_micro=int(body.run_budget_usd * 1_000_000),
            total_budget_micro=int(body.total_budget_usd * 1_000_000),
        )
        db.add(record)
        audit(db, p, request, "schedule.created", record.id)
        db.flush()
        return commit(db, request, schedule_output(record))

    @app.get("/v1/schedules", tags=["Schedules"], response_model=Page[ScheduleOut])
    def list_schedules(p: Auth, db: DB, limit: int = Query(25, ge=1, le=100), cursor: str | None = None):
        p.require("schedules:manage")
        result = page(db, WorkflowSchedule, p, limit, cursor)
        result["items"] = [
            ScheduleOut.model_validate(
                {k: v for k, v in item.items() if k in ScheduleOut.model_fields}
            ).model_dump(mode="json")
            for item in result["items"]
        ]
        return result

    @app.get("/v1/schedules/{schedule_id}", tags=["Schedules"], response_model=ScheduleOut)
    def get_schedule(schedule_id: str, p: Auth, db: DB):
        p.require("schedules:manage")
        return schedule_output(get(db, WorkflowSchedule, schedule_id, p.organization_id))

    @app.post("/v1/schedules/{schedule_id}/control", tags=["Schedules"], response_model=ScheduleOut)
    def control_schedule(schedule_id: str, body: ScheduleControl, request: Request, p: Auth, db: DB):
        p.require("schedules:manage")
        if cached := replay(db, p, request, body.model_dump(mode="json")):
            return cached
        row = locked(db, p, schedule_id)
        if row.revision != body.expected_revision:
            raise Problem(
                409, "STALE_SCHEDULE", "The schedule changed. Refresh before another control action."
            )
        if row.state in {"COMPLETED", "EXPIRED", "CANCELLED"}:
            raise Problem(409, "SCHEDULE_TERMINAL", "Create a new bounded schedule after this one finishes.")
        if body.action == "resume":
            if row.launched_runs + row.skipped_runs >= 1000:
                raise Problem(
                    409, "OCCURRENCE_LIMIT", "Create a replacement after the 1,000 occurrence safety limit."
                )
            if not body.approved_for_scheduled_execution:
                raise Problem(
                    422, "SCHEDULE_APPROVAL_REQUIRED", "Explicitly authorize future launches when resuming."
                )
            if row.state not in {"PAUSED", "BLOCKED"}:
                raise Problem(409, "SCHEDULE_NOT_PAUSED", "Only paused or blocked schedules can resume.")
            definition = ScheduleDefinition.model_validate(row.definition)
            payload = SchedulePreview(
                name=row.name,
                dataset_id=row.dataset_id,
                recipe_revision_id=row.recipe_revision_id,
                definition=definition,
                max_runs=row.max_runs - row.launched_runs,
                run_budget_usd=Decimal(row.run_budget_micro) / 1000000,
                total_budget_usd=Decimal(row.total_budget_micro - row.admitted_micro) / 1000000,
            )
            preview(db, p, payload, validate_start=False)
            row.next_run_at = next_occurrence(definition, now())
            row.state, row.authorized_by, row.authorized_key_id, row.authorized_scopes = (
                "ACTIVE",
                p.user_id,
                p.key_id,
                list(p.scopes),
            )
            row.last_error_code = row.last_error = None
        elif body.action == "pause":
            if row.state != "ACTIVE":
                raise Problem(409, "SCHEDULE_NOT_ACTIVE", "Only active schedules can pause.")
            row.state, row.next_run_at = "PAUSED", None
        else:
            row.state, row.next_run_at = "CANCELLED", None
        row.revision += 1
        audit(db, p, request, f"schedule.{body.action}", row.id)
        return commit(db, request, schedule_output(row), 200)

    @app.get(
        "/v1/schedules/{schedule_id}/occurrences", tags=["Schedules"], response_model=Page[OccurrenceOut]
    )
    def schedule_occurrences(
        schedule_id: str, p: Auth, db: DB, limit: int = Query(25, ge=1, le=100), cursor: str | None = None
    ):
        p.require("schedules:manage")
        get(db, WorkflowSchedule, schedule_id, p.organization_id)
        return page(db, ScheduleOccurrence, p, limit, cursor, [ScheduleOccurrence.schedule_id == schedule_id])


def record_tick(db, row, due, status, code, message, *, run=None):
    db.add(
        ScheduleOccurrence(
            id=uid("occ"),
            organization_id=row.organization_id,
            schedule_id=row.id,
            scheduled_at=due,
            status=status,
            code=code,
            message=message,
            run_id=run.id if run else None,
            estimate_micro=run.reserved_micro if run else 0,
        )
    )
    if status != "LAUNCHED":
        notify(
            db,
            org=row.organization_id,
            user=row.authorized_by,
            event_key=f"schedule:{row.id}:{due.isoformat()}",
            kind=f"schedule.{status.lower()}",
            title="Schedule needs attention" if status == "BLOCKED" else "Scheduled launch skipped",
            body=message,
            resource_kind="schedule",
            resource_id=row.id,
        )


def dispatch_due(maximum=20):
    from .api import admit_run

    processed = 0
    if Path(".local/maintenance.json").exists():
        return processed
    for _ in range(maximum):
        with Session.begin() as db:
            if not db.scalar(
                text("SELECT pg_try_advisory_xact_lock_shared(hashtextextended(:key,0))"),
                {"key": MAINTENANCE_LOCK},
            ):
                break
            stamp = now()
            row = db.scalar(
                select(WorkflowSchedule)
                .where(WorkflowSchedule.state == "ACTIVE", WorkflowSchedule.next_run_at <= stamp)
                .order_by(WorkflowSchedule.next_run_at, WorkflowSchedule.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not row:
                break
            due = row.next_run_at
            definition = ScheduleDefinition.model_validate(row.definition)
            row.revision += 1
            next_due = next_occurrence(definition, stamp)
            if stamp >= definition.ends_at:
                row.state, row.next_run_at = "EXPIRED", None
                record_tick(
                    db,
                    row,
                    due,
                    "MISSED",
                    "SCHEDULE_EXPIRED",
                    "The finite schedule window ended; no run was launched.",
                )
            elif row.launched_runs + row.skipped_runs >= 1000:
                row.state, row.next_run_at = "BLOCKED", None
                row.last_error_code, row.last_error = (
                    "OCCURRENCE_LIMIT",
                    "The schedule reached its 1,000 occurrence safety limit. Create a replacement schedule.",
                )
                record_tick(db, row, due, "BLOCKED", row.last_error_code, row.last_error)
            elif (stamp - due).total_seconds() > LATE_GRACE_SECONDS:
                row.skipped_runs += 1
                record_tick(
                    db,
                    row,
                    due,
                    "MISSED",
                    "LATE_TICK",
                    "The worker missed the 120-second launch window. Backlog was skipped.",
                )
                row.next_run_at = next_due
                if next_due is None:
                    row.state = "COMPLETED"
            elif db.scalar(
                select(Run.id)
                .where(
                    Run.schedule_id == row.id,
                    Run.organization_id == row.organization_id,
                    Run.status.not_in(TERMINAL),
                )
                .limit(1)
            ):
                row.skipped_runs += 1
                record_tick(
                    db,
                    row,
                    due,
                    "SKIPPED",
                    "OVERLAP",
                    "The previous scheduled run is still active. This occurrence was skipped.",
                )
                row.next_run_at = next_due
                if next_due is None:
                    row.state = "COMPLETED"
            else:
                try:
                    with db.begin_nested():
                        p = delegated_principal(db, row)
                        run = admit_run(
                            db,
                            p,
                            RunCreate(
                                dataset_id=row.dataset_id,
                                recipe_revision_id=row.recipe_revision_id,
                                max_budget_usd=Decimal(row.run_budget_micro) / 1000000,
                            ),
                            request_id=f"schedule:{row.id}",
                            schedule_id=row.id,
                        )
                        if row.admitted_micro + run.reserved_micro > row.total_budget_micro:
                            raise Problem(
                                402,
                                "SCHEDULE_BUDGET_EXCEEDED",
                                "The next estimate exceeds the remaining total schedule cap.",
                            )
                        db.flush()
                    row.launched_runs += 1
                    row.admitted_micro += run.reserved_micro
                    row.last_run_at = stamp
                    record_tick(
                        db,
                        row,
                        due,
                        "LAUNCHED",
                        "ADMITTED",
                        "A real run passed current permission, rights, policy and budget admission.",
                        run=run,
                    )
                    row.next_run_at = next_due
                    if row.launched_runs >= row.max_runs or next_due is None:
                        row.state, row.next_run_at = "COMPLETED", None
                except Problem as error:
                    row.state, row.next_run_at = "BLOCKED", None
                    row.last_error_code, row.last_error = error.code, error.message[:400]
                    record_tick(
                        db,
                        row,
                        due,
                        "BLOCKED",
                        error.code,
                        "The schedule was blocked by current permission, source policy or budget checks. Review it before resuming.",
                    )
            db.add(
                Audit(
                    id=uid("aud"),
                    organization_id=row.organization_id,
                    actor_id=row.authorized_key_id or row.authorized_by,
                    action="schedule.tick",
                    resource_id=row.id,
                    request_id=f"schedule:{row.id}",
                )
            )
            processed += 1
    with Session.begin() as db:
        db.merge(Heartbeat(name="scheduler", seen_at=now()))
    return processed
