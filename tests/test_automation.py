"""P13: calendar boundaries and actual Postgres → worker → Temporal → inbox flows."""

import json
import os
import signal
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from conftest import dataset, definition, pipeline, post, wait
from foundry.automation import ScheduleDefinition, dispatch_due, next_occurrence
from foundry.config import settings
from foundry.db import Session, now
from foundry.models import Notification, Outbox, Run, Usage, Version
from foundry.notifications import materialize_run_notice
from pydantic import ValidationError
from sqlalchemy import func, select, text

EVIDENCE = Path("verification/evidence/p13")


def save(name, value):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / (name + ".json")).write_text(json.dumps(value, indent=2, default=str) + "\n")


def eventually(fn, predicate, timeout=45):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = fn()
        if predicate(result):
            return result
        time.sleep(0.2)
    raise AssertionError(f"Condition not reached; last value: {result}")


def schedule_body(data, recipe, *, delay=3, max_runs=1):
    start = now() + timedelta(seconds=delay)
    return {
        "name": "Verified bounded automation",
        "dataset_id": data["id"],
        "recipe_revision_id": recipe["revision"]["id"],
        "definition": {
            "mode": "interval",
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(minutes=10)).isoformat(),
            "interval_seconds": 10,
            "timezone": "Asia/Kolkata",
        },
        "max_runs": max_runs,
        "run_budget_usd": "1",
        "total_budget_usd": "2",
    }


@pytest.mark.parametrize(
    "day,clock,after,expected",
    [
        ("2026-03-07", "09:00", "2026-03-07T14:00:00+00:00", "2026-03-08T13:00:00+00:00"),
        ("2026-10-31", "09:00", "2026-10-31T13:00:00+00:00", "2026-11-01T14:00:00+00:00"),
        ("2026-03-08", "02:30", "2026-03-08T00:00:00+00:00", "2026-03-09T06:30:00+00:00"),
        ("2026-11-01", "01:30", "2026-11-01T05:30:00+00:00", "2026-11-02T06:30:00+00:00"),
    ],
)
def test_daily_calendar_dst_gap_fold_and_23_25_hour_days(day, clock, after, expected):
    start = datetime.fromisoformat(day).replace(tzinfo=UTC)
    definition = ScheduleDefinition(
        mode="daily",
        daily_time=clock,
        timezone="America/New_York",
        starts_at=start,
        ends_at=start + timedelta(days=3),
    )
    assert next_occurrence(definition, datetime.fromisoformat(after)).isoformat() == expected


def test_interval_bounds_no_catchup_and_definition_validation():
    stamp = now()
    definition = ScheduleDefinition(
        mode="interval", interval_seconds=10, starts_at=stamp, ends_at=stamp + timedelta(seconds=30)
    )
    assert next_occurrence(definition, stamp, inclusive=True) == stamp
    assert next_occurrence(definition, stamp + timedelta(seconds=21)) is None
    assert next_occurrence(definition, stamp + timedelta(seconds=19)) == stamp + timedelta(seconds=20)
    for changes in [
        {"timezone": "../UTC"},
        {"starts_at": stamp.replace(tzinfo=None)},
        {"interval_seconds": 9},
        {"ends_at": stamp + timedelta(days=31)},
        {"daily_time": "09:00"},
    ]:
        with pytest.raises(ValidationError):
            ScheduleDefinition.model_validate({**definition.model_dump(), **changes})


@pytest.mark.integration
def test_bounded_schedule_real_publication_inbox_idempotency_and_cutoff(owners):
    owner = owners[0]
    data, recipe = pipeline(owner, count=3)
    payload = schedule_body(data, recipe, max_runs=2)
    with Session() as db:
        previous = db.scalar(select(func.count()).select_from(Run))
    preview = owner.post("/v1/schedules/preview", json=payload)
    assert preview.status_code == 200, preview.text
    assert len(preview.json()["next_occurrences"]) == 2
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Run)) == previous
    key = uuid.uuid4().hex
    body = {**payload, "approved_for_scheduled_execution": True}
    schedule = post(owner, "/schedules", body, key=key)
    assert post(owner, "/schedules", body, key=key)["id"] == schedule["id"]
    assert owner.get("/v1/schedules").status_code == 200
    result = eventually(
        lambda: owner.get(f"/v1/schedules/{schedule['id']}").json(),
        lambda value: value["state"] == "COMPLETED",
    )
    occurrences = owner.get(f"/v1/schedules/{schedule['id']}/occurrences").json()["items"]
    assert len(occurrences) == 2 and all(item["status"] == "LAUNCHED" for item in occurrences)
    runs = [wait(owner, item["run_id"]) for item in occurrences]
    assert all(run["status"] == "SUCCEEDED" and run["schedule_id"] == schedule["id"] for run in runs)
    assert result["admitted_micro"] == preview.json()["estimate_micro"] * 2
    ids = [run["id"] for run in runs]
    notices = eventually(
        lambda: owner.get("/v1/notifications?limit=100").json()["items"],
        lambda items: all(
            any(item["target"] == f"/runs/{identifier}" for item in items) for identifier in ids
        ),
    )
    found = [item for item in notices if item["target"] in {f"/runs/{identifier}" for identifier in ids}]
    with Session.begin() as db:
        events = db.scalars(select(Outbox).where(Outbox.resource_id.in_(ids), Outbox.kind == "event")).all()
        for event in events:
            materialize_run_notice(db, event)
            materialize_run_notice(db, event)
    with Session() as db:
        assert (
            db.scalar(select(func.count()).select_from(Notification).where(Notification.resource_id.in_(ids)))
            == 2
        )
        assert db.scalar(select(func.count()).select_from(Version).where(Version.run_id.in_(ids))) == 2
        assert (
            db.scalar(
                select(func.sum(Usage.quantity)).where(
                    Usage.run_id.in_(ids), Usage.metric == "processed_samples"
                )
            )
            == 6
        )
    cutoff = owner.get("/v1/notifications/summary").json()["as_of"]
    for item in found:
        first = post(owner, f"/notifications/{item['id']}/read", {}, expected=200)
        assert (
            post(owner, f"/notifications/{item['id']}/read", {}, expected=200)["read_at"] == first["read_at"]
        )
    # The cutoff cannot consume a later, real run outcome.
    newer = post(
        owner,
        "/runs",
        {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
        expected=202,
    )
    assert wait(owner, newer["id"])["status"] == "SUCCEEDED"
    recent = eventually(
        lambda: owner.get("/v1/notifications?unread=true&limit=100").json()["items"],
        lambda items: any(item["target"] == f"/runs/{newer['id']}" for item in items),
    )
    post(owner, "/notifications/read-all", {"before": cutoff}, expected=200)
    remaining = owner.get("/v1/notifications?unread=true&limit=100").json()["items"]
    assert any(item["target"] == f"/runs/{newer['id']}" for item in remaining)
    assert recent
    save(
        "scheduled-lifecycle",
        {
            "schedule": result,
            "occurrences": occurrences,
            "run_ids": ids,
            "version_hashes": [run["version"]["manifest_hash"] for run in runs],
            "duplicate_notification_count": 2,
            "cutoff_kept_new_notice": True,
        },
    )


@pytest.mark.integration
def test_schedule_controls_restart_duplicate_tick_overlap_and_backlog(owners, monkeypatch):
    owner = owners[0]
    data, recipe = pipeline(owner, count=2)
    body = schedule_body(data, recipe, delay=5, max_runs=2)
    schedule = post(owner, "/schedules", {**body, "approved_for_scheduled_execution": True})
    path = f"/schedules/{schedule['id']}/control"
    paused = post(owner, path, {"action": "pause", "expected_revision": schedule["revision"]}, expected=200)
    assert paused["next_run_at"] is None
    assert (
        owner.post(
            "/v1" + path,
            json={
                "action": "resume",
                "expected_revision": schedule["revision"],
                "approved_for_scheduled_execution": True,
            },
            headers={"Idempotency-Key": uuid.uuid4().hex},
        ).status_code
        == 409
    )
    resumed = post(
        owner,
        path,
        {
            "action": "resume",
            "expected_revision": paused["revision"],
            "approved_for_scheduled_execution": True,
        },
        expected=200,
    )
    pid_file = Path(".local/worker.pid")
    pid = int(pid_file.read_text())
    assert b"foundry.worker" in Path(f"/proc/{pid}/cmdline").read_bytes()
    os.kill(pid, signal.SIGTERM)
    replacement = eventually(lambda: int(pid_file.read_text()), lambda value: value != pid)
    os.kill(replacement, signal.SIGSTOP)
    try:
        due = datetime.fromisoformat(resumed["next_run_at"])
        while now() < due:
            time.sleep(0.1)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: dispatch_due(), range(4)))
        first = owner.get(f"/v1/schedules/{schedule['id']}/occurrences").json()["items"]
        assert len(first) == 1 and first[0]["status"] == "LAUNCHED"
        import foundry.automation as automation

        monkeypatch.setattr(automation, "now", lambda: due + timedelta(seconds=11))
        dispatch_due()
        overlap = owner.get(f"/v1/schedules/{schedule['id']}/occurrences").json()["items"]
        assert len(overlap) == 2 and overlap[0]["code"] == "OVERLAP"
        monkeypatch.setattr(automation, "now", lambda: due + timedelta(seconds=200))
        dispatch_due()
        backlog = owner.get(f"/v1/schedules/{schedule['id']}/occurrences").json()["items"]
        assert len(backlog) == 3 and backlog[0]["code"] == "LATE_TICK"
        current = owner.get(f"/v1/schedules/{schedule['id']}").json()
        post(owner, path, {"action": "cancel", "expected_revision": current["revision"]}, expected=200)
    finally:
        os.kill(replacement, signal.SIGCONT)
    assert wait(owner, first[0]["run_id"])["status"] == "SUCCEEDED"
    save(
        "scheduler-recovery",
        {
            "worker_replaced": pid != replacement,
            "duplicate_dispatchers": 4,
            "occurrences": backlog,
            "one_admitted_run": True,
            "clock_advance_scope": "Direct scheduler process only for overlap/backlog; real persisted run and worker execution.",
        },
    )


@pytest.mark.integration
def test_failed_and_cancelled_run_outcomes_create_private_notices(owners):
    owner = owners[0]
    data, recipe = pipeline(owner, count=2, minimum=3)
    failed = post(
        owner,
        "/runs",
        {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
        expected=202,
    )
    assert wait(owner, failed["id"])["status"] == "FAILED"
    data, recipe = pipeline(owner, count=10000)
    pid = int(Path(".local/worker.pid").read_text())
    assert b"foundry.worker" in Path(f"/proc/{pid}/cmdline").read_bytes()
    os.kill(pid, signal.SIGSTOP)
    try:
        cancelled = post(
            owner,
            "/runs",
            {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 10},
            expected=202,
        )
        assert owner.post(f"/v1/runs/{cancelled['id']}/cancel").is_success
    finally:
        os.kill(pid, signal.SIGCONT)
    terminal = wait(owner, cancelled["id"])
    assert terminal["status"] == "CANCELLED" and terminal["reserved_usd"] == 0
    expected = {f"/runs/{failed['id']}": "run.failed", f"/runs/{cancelled['id']}": "run.cancelled"}
    values = eventually(
        lambda: owner.get("/v1/notifications?limit=100").json()["items"],
        lambda items: all(any(item["target"] == target for item in items) for target in expected),
    )
    actual = {item["target"]: item["kind"] for item in values if item["target"] in expected}
    assert actual == expected
    save("terminal-outcomes", {"notices": actual, "cancelled_reservation_usd": terminal["reserved_usd"]})


@pytest.mark.security
def test_schedule_key_revocation_blocks_without_reservation_and_admin_reauthorizes(owners):
    owner, other = owners
    data, recipe = pipeline(owner, count=2)
    key = post(
        owner,
        "/api-keys",
        {"name": "P13 delegated schedule", "scopes": ["datasets:read", "runs:execute", "schedules:manage"]},
    )
    with httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": "Bearer " + key["secret"]},
        trust_env=False,
    ) as delegated:
        assert delegated.get("/v1/notifications").status_code == 403
        schedule = post(
            delegated,
            "/schedules",
            {**schedule_body(data, recipe, delay=3), "approved_for_scheduled_execution": True},
        )
    assert other.get(f"/v1/schedules/{schedule['id']}").status_code == 404
    assert other.get(f"/v1/schedules/{schedule['id']}/occurrences").status_code == 404
    assert owner.delete(f"/v1/api-keys/{key['id']}").is_success
    blocked = eventually(
        lambda: owner.get(f"/v1/schedules/{schedule['id']}").json(), lambda value: value["state"] == "BLOCKED"
    )
    assert blocked["last_error_code"] == "SCHEDULE_AUTH_REVOKED" and blocked["admitted_micro"] == 0
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Run).where(Run.schedule_id == schedule["id"])) == 0
    occurrence = owner.get(f"/v1/schedules/{schedule['id']}/occurrences").json()["items"][0]
    with Session() as db:
        with pytest.raises(Exception, match="immutable evidence"):
            db.execute(
                text("UPDATE schedule_occurrences SET code='changed' WHERE id=:id"), {"id": occurrence["id"]}
            )
        db.rollback()
        with pytest.raises(Exception, match="immutable"):
            db.execute(
                text("UPDATE workflow_schedules SET name='changed' WHERE id=:id"), {"id": schedule["id"]}
            )
        db.rollback()
    resumed = post(
        owner,
        f"/schedules/{schedule['id']}/control",
        {
            "action": "resume",
            "expected_revision": blocked["revision"],
            "approved_for_scheduled_execution": True,
        },
        expected=200,
    )
    assert resumed["authorized_key_id"] is None
    completed = eventually(
        lambda: owner.get(f"/v1/schedules/{schedule['id']}").json(),
        lambda value: value["state"] == "COMPLETED",
    )
    assert completed["launched_runs"] == 1
    launched = owner.get(f"/v1/schedules/{schedule['id']}/occurrences").json()["items"][0]
    assert wait(owner, launched["run_id"])["status"] == "SUCCEEDED"
    save(
        "revoked-authority",
        {"blocked": blocked, "resumed": completed, "no_run_on_block": True, "immutable_history": True},
    )


@pytest.mark.security
def test_schedule_budget_archival_approval_and_governance_guards(owners):
    owner = owners[0]
    data, recipe = pipeline(owner, count=2)
    body = schedule_body(data, recipe, delay=5, max_runs=2)
    for changes in [{"run_budget_usd": "0"}, {"total_budget_usd": "0"}]:
        response = owner.post("/v1/schedules/preview", json={**body, **changes})
        assert response.status_code == 402
    assert (
        owner.post("/v1/schedules", json=body, headers={"Idempotency-Key": uuid.uuid4().hex}).status_code
        == 422
    )
    schedule = post(
        owner, "/schedules", {**body, "total_budget_usd": "0.002", "approved_for_scheduled_execution": True}
    )
    guard = owner.post(
        f"/v1/governance/datasets/{data['id']}",
        json={
            "action": "protect_holdout",
            "expected_revision": data["governance_revision"],
            "note": "P13 active schedule guard",
        },
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert guard.status_code == 409 and guard.json()["code"] == "DATASET_SCHEDULED"
    blocked = eventually(
        lambda: owner.get(f"/v1/schedules/{schedule['id']}").json(), lambda value: value["state"] == "BLOCKED"
    )
    assert blocked["last_error_code"] == "SCHEDULE_BUDGET_EXCEEDED" and blocked["launched_runs"] == 1
    assert blocked["admitted_micro"] == blocked["total_budget_micro"] == 2000
    history = owner.get(f"/v1/schedules/{schedule['id']}/occurrences").json()["items"]
    assert len(history) == 2 and history[0]["run_id"] is None
    assert wait(owner, history[1]["run_id"])["status"] == "SUCCEEDED"
    # Source state is checked again after authorization; creating a schedule isn't a lasting bypass.
    later = post(
        owner,
        "/schedules",
        {**schedule_body(data, recipe, delay=3), "approved_for_scheduled_execution": True},
    )
    assert owner.patch(f"/v1/datasets/{data['id']}", json={"archived": True}).is_success
    archived = eventually(
        lambda: owner.get(f"/v1/schedules/{later['id']}").json(), lambda value: value["state"] == "BLOCKED"
    )
    assert archived["last_error_code"] == "DATASET_ARCHIVED" and archived["admitted_micro"] == 0
    for item in (blocked, archived):
        post(
            owner,
            f"/schedules/{item['id']}/control",
            {"action": "cancel", "expected_revision": item["revision"]},
            expected=200,
        )
    assert owner.patch(f"/v1/datasets/{data['id']}", json={"archived": False}).is_success
    save(
        "bounded-budget-policy",
        {"budget": blocked, "archived_source": archived, "active_schedule_governance_guard": True},
    )


@pytest.mark.security
def test_personal_inbox_role_change_holdout_links_and_cursor_isolation(owners):
    owner, other = owners
    email = f"p13-private-{uuid.uuid4().hex}@foundry.local"
    person = post(
        owner,
        "/members",
        {
            "email": email,
            "name": "P13 private recipient",
            "password": settings().dev_password,
            "role": "Engineer",
        },
    )
    with httpx.Client(
        base_url="http://localhost:8000",
        headers={"Origin": "http://localhost:3000"},
        trust_env=False,
        timeout=30,
    ) as engineer:
        login = engineer.post(
            "/v1/auth/login", json={"email": email, "password": settings().dev_password}
        ).json()
        engineer.headers.update(
            {"X-CSRF-Token": login["csrf_token"], "X-Organization-Id": login["organizations"][0]["id"]}
        )
        data, project = dataset(engineer, name="Private holdout notice source")
        recipe = post(
            engineer,
            "/recipes",
            {"project_id": project, "definition": definition(count=2, seed=uuid.uuid4().int % 2**31)},
        )
        run = post(
            engineer,
            "/runs",
            {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
            expected=202,
        )
        assert wait(engineer, run["id"])["status"] == "SUCCEEDED"
        notice = eventually(
            lambda: engineer.get("/v1/notifications").json()["items"], lambda values: bool(values)
        )[0]
        assert notice["target"] == f"/runs/{run['id']}"
        for outsider in (owner, other):
            response = outsider.post(
                f"/v1/notifications/{notice['id']}/read",
                json={},
                headers={"Idempotency-Key": uuid.uuid4().hex},
            )
            assert response.status_code == 404
        read_key = uuid.uuid4().hex
        post(engineer, f"/notifications/{notice['id']}/read", {}, expected=200, key=read_key)
        scheduled = post(
            engineer,
            "/schedules",
            {**schedule_body(data, recipe, delay=3), "approved_for_scheduled_execution": True},
        )
        assert owner.patch(f"/v1/members/{person['id']}", json={"role": "Viewer"}).is_success
        blocked = eventually(
            lambda: owner.get(f"/v1/schedules/{scheduled['id']}").json(),
            lambda value: value["state"] == "BLOCKED",
        )
        assert blocked["last_error_code"] == "INSUFFICIENT_SCOPE" and blocked["admitted_micro"] == 0
        post(
            owner,
            f"/schedules/{scheduled['id']}/control",
            {"action": "cancel", "expected_revision": blocked["revision"]},
            expected=200,
        )
        protected = post(
            owner,
            f"/governance/datasets/{data['id']}",
            {
                "action": "protect_holdout",
                "expected_revision": data["governance_revision"],
                "note": "P13 private notice links must honor subsequent protection",
            },
            expected=200,
        )
        assert protected["protection"] == "holdout"
        assert engineer.get(f"/v1/runs/{run['id']}").status_code == 403
        assert all(item["target"] is None for item in engineer.get("/v1/notifications").json()["items"])
        assert (
            post(engineer, f"/notifications/{notice['id']}/read", {}, expected=200, key=read_key)["target"]
            is None
        )
        # Obtain a real signed inbox cursor, then try it under a different identity and filter.
        page = owner.get("/v1/notifications?limit=1").json()
        assert page["next_cursor"]
        for outsider in (engineer, other):
            assert (
                outsider.get("/v1/notifications", params={"cursor": page["next_cursor"]}).status_code == 404
            )
        assert (
            owner.get(
                "/v1/notifications", params={"cursor": page["next_cursor"], "unread": "true"}
            ).status_code
            == 404
        )
        assert (
            owner.post(
                "/v1/notifications/read-all",
                json={"before": (now() + timedelta(days=1)).isoformat()},
                headers={"Idempotency-Key": uuid.uuid4().hex},
            ).status_code
            == 422
        )
    assert owner.delete(f"/v1/members/{person['id']}").is_success
    save(
        "private-inbox",
        {
            "recipient": person["id"],
            "notice_id": notice["id"],
            "cross_user_and_tenant": "DENIED",
            "protected_target": None,
            "replayed_acknowledgement_rechecks_visibility": True,
            "cursor_identity_and_filter_bound": True,
        },
    )
