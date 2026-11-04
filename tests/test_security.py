import time
import uuid

import httpx
import pytest
from conftest import dataset, pipeline, post, wait
from foundry.db import engine
from foundry.security import signed_token
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.security


def test_removed_member_loses_access_and_can_end_session(owners):
    owner = owners[0]
    password = "revocation-test-" + uuid.uuid4().hex
    email = "removed-" + uuid.uuid4().hex + "@foundry.local"
    user = post(
        owner, "/members", {"email": email, "name": "Revocation test", "password": password, "role": "Viewer"}
    )
    with httpx.Client(
        base_url="http://localhost:8000", headers={"Origin": "http://localhost:3000"}, trust_env=False
    ) as member:
        result = member.post("/v1/auth/login", json={"email": email, "password": password})
        assert result.is_success
        member.headers["X-CSRF-Token"] = result.json()["csrf_token"]
        assert member.get("/v1/datasets").status_code == 200
        assert owner.delete(f"/v1/members/{user['id']}").status_code == 200
        assert member.get("/v1/datasets").status_code == 404
        assert member.post("/v1/auth/logout").status_code == 204
        assert "foundry_session" not in member.cookies
        denied = member.post("/v1/auth/login", json={"email": email, "password": password})
        assert denied.status_code == 403 and denied.json()["code"] == "NO_ORGANIZATION_ACCESS"


def test_every_core_resource_is_tenant_isolated(owners):
    owner, other = owners
    data, recipe = pipeline(owner)
    run = post(
        owner,
        "/runs",
        {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
        expected=202,
    )
    result = wait(owner, run["id"])
    version = result["version"]
    export = post(owner, "/exports", {"version_id": version["id"], "format": "jsonl"}, expected=202)
    grant = owner.get(f"/v1/exports/{export['id']}").json()["download_url"]
    for path in [
        f"/datasets/{data['id']}",
        f"/runs/{run['id']}",
        f"/runs/{run['id']}/events",
        f"/recipes/{recipe['id']}",
        f"/datasets/{data['id']}/versions/{version['id']}/manifest",
        f"/uploads?dataset_id={data['id']}",
        f"/exports/{export['id']}",
        grant.removeprefix("/v1"),
    ]:
        response = other.get("/v1" + path)
        assert response.status_code == 404, (path, response.text)
        assert data["name"] not in response.text
    response = other.post(
        "/v1/runs",
        json={"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 404
    assert owner.get(grant).status_code == 200
    expired = signed_token(
        {
            "org": data["organization_id"],
            "sub": "irrelevant",
            "export_id": export["id"],
            "exp": int(time.time()) - 1,
        }
    )
    assert owner.get(f"/v1/exports/{export['id']}/download?grant={expired}").status_code == 403
    anonymous = httpx.get(
        "http://localhost:9000/foundry/" + version["manifest"]["data_artifact"]["key"], trust_env=False
    )
    assert anonymous.status_code == 403


def test_scope_key_revocation_and_csrf(owners):
    owner = owners[0]
    key = post(owner, "/api-keys", {"name": "Read-only security key", "scopes": ["datasets:read"]})
    with httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": "Bearer " + key["secret"]},
        trust_env=False,
    ) as client:
        assert client.get("/v1/datasets").status_code == 200
        project = owner.get("/v1/projects").json()["items"][0]["id"]
        response = client.post(
            "/v1/datasets",
            json={"project_id": project, "name": "forbidden"},
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        assert response.status_code == 403
        assert "secret" not in owner.get("/v1/api-keys").text
        owner.delete(f"/v1/api-keys/{key['id']}")
        assert client.get("/v1/datasets").status_code == 401
    response = owner.post(
        "/v1/projects",
        json={"name": "csrf rejection"},
        headers={"X-CSRF-Token": "invalid", "Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 403 and response.json()["code"] == "CSRF_REJECTED"


def test_budget_policy_idempotency_and_hardware_negatives(owners):
    owner = owners[0]
    data, recipe = pipeline(owner)
    body = {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 0}
    assert owner.post("/v1/runs", json=body, headers={"Idempotency-Key": uuid.uuid4().hex}).status_code == 402
    body.update(max_budget_usd=1, compute_constraints={"gpu": "H100"})
    assert (
        owner.post("/v1/runs", json=body, headers={"Idempotency-Key": uuid.uuid4().hex}).json()["code"]
        == "CAPABILITY_UNAVAILABLE"
    )
    blocked, _ = dataset(owner, permitted=False)
    body.update(dataset_id=blocked["id"], compute_constraints={})
    assert (
        owner.post("/v1/runs", json=body, headers={"Idempotency-Key": uuid.uuid4().hex}).json()["code"]
        == "POLICY_BLOCKED"
    )
    project = owner.get("/v1/projects").json()["items"][0]["id"]
    key = uuid.uuid4().hex
    post(owner, "/datasets", {"name": "Original idempotent request", "project_id": project}, key=key)
    response = owner.post(
        "/v1/datasets",
        json={"name": "Changed payload", "project_id": project},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["request_id"] == response.headers["X-Request-Id"]


def test_upload_validation_and_checksum(owners):
    owner = owners[0]
    data, _ = dataset(owner)
    body = {
        "dataset_id": data["id"],
        "filename": "attack.exe",
        "content_type": "application/x-ndjson",
        "bytes": 20,
        "sha256": "0" * 64,
    }
    assert (
        owner.post("/v1/uploads", json=body, headers={"Idempotency-Key": uuid.uuid4().hex}).status_code == 422
    )
    body.update(filename="source.jsonl", bytes=21 * 1024 * 1024)
    assert (
        owner.post("/v1/uploads", json=body, headers={"Idempotency-Key": uuid.uuid4().hex}).status_code == 422
    )
    raw = b'{"prompt":"hello","response":"world"}\n'
    body.update(bytes=len(raw))
    upload = post(owner, "/uploads", body)
    part = httpx.put(upload["upload_urls"][0], content=raw, trust_env=False)
    assert part.is_success
    response = owner.post(
        f"/v1/uploads/{upload['id']}/complete",
        json={"parts": [{"part_number": 1, "etag": part.headers["etag"]}]},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 422 and response.json()["code"] == "UPLOAD_CHECKSUM_MISMATCH"


def test_ssrf_and_external_delivery_are_blocked(owners):
    owner = owners[0]
    for url in [
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/events",
        "https://example.com/events",
        "http://localhost.evil.example/events",
        "http://user:pass@localhost:9100/events",
    ]:
        response = owner.post(
            "/v1/webhooks",
            json={"url": url, "events": ["run.succeeded"]},
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        assert response.status_code == 422
    project = owner.get("/v1/projects").json()["items"][0]["id"]
    result = owner.post(
        "/v1/datasets",
        json={
            "name": "Forbidden reference",
            "project_id": project,
            "schema": {"$ref": "http://169.254.169.254/latest/meta-data"},
        },
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert result.status_code == 422 and result.json()["code"] == "UNSUPPORTED_SCHEMA_REF"


def test_database_blocks_cross_tenant_references_and_version_mutation(owners):
    owner, other = owners
    data, _ = dataset(owner)
    with engine.connect() as connection:
        with pytest.raises(DBAPIError), connection.begin():
            connection.execute(
                text("UPDATE datasets SET organization_id=:org WHERE id=:id"),
                {"org": other.headers["x-organization-id"], "id": data["id"]},
            )
    data, recipe = pipeline(owner)
    run = post(
        owner,
        "/runs",
        {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
        expected=202,
    )
    version = wait(owner, run["id"])["version"]
    with engine.connect() as connection:
        with pytest.raises(DBAPIError), connection.begin():
            connection.execute(
                text("UPDATE dataset_versions SET sample_count=0 WHERE id=:id"), {"id": version["id"]}
            )
