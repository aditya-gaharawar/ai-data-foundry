import uuid

import httpx
import pytest
from foundry.config import settings


@pytest.fixture(scope="session")
def owners():
    clients = []
    for email in ["alex@foundry.local", "blair@foundry.local"]:
        client = httpx.Client(
            base_url="http://localhost:8000",
            headers={"Origin": "http://localhost:3000"},
            timeout=30,
            trust_env=False,
        )
        response = client.post("/v1/auth/login", json={"email": email, "password": settings().dev_password})
        response.raise_for_status()
        value = response.json()
        client.headers.update(
            {"X-CSRF-Token": value["csrf_token"], "X-Organization-Id": value["organizations"][0]["id"]}
        )
        clients.append(client)
    yield clients
    for client in clients:
        client.close()


def post(client, path, body=None, key=None, expected=201):
    response = client.post("/v1" + path, json=body, headers={"Idempotency-Key": key or uuid.uuid4().hex})
    assert response.status_code == expected, response.text
    return response.json()


def definition(count=100, seed=42, upload_id=None, minimum=None):
    return {
        "name": "Verified integration pipeline",
        "schema_version": "1.0",
        "nodes": [
            {
                "id": "source",
                "type": "ingest" if upload_id else "generate",
                "config": {"upload_id": upload_id}
                if upload_id
                else {"engine": "deterministic.text@1", "count": count, "seed": seed},
            },
            {
                "id": "validate",
                "type": "validate",
                "config": {
                    "minimum_samples": minimum or count,
                    "max_duplicate_ratio": 0,
                    "max_invalid_ratio": 0,
                },
            },
            {"id": "publish", "type": "publish", "config": {}},
        ],
        "edges": [{"from": "source", "to": "validate"}, {"from": "validate", "to": "publish"}],
        "budget": {"currency": "USD", "maximum": 20},
    }


def dataset(client, name="Integration dataset", permitted=True):
    project = client.get("/v1/projects").json()["items"][0]["id"]
    record = post(
        client,
        "/datasets",
        {
            "name": name,
            "project_id": project,
            "policy": {
                "origin": "local-synthetic",
                "license": "local-synthetic",
                "allowed_training_use": permitted,
            },
        },
    )
    return record, project


def pipeline(client, *, count=100, upload_id=None, minimum=None):
    data, project = dataset(client)
    recipe = post(
        client,
        "/recipes",
        {"project_id": project, "definition": definition(count, upload_id=upload_id, minimum=minimum)},
    )
    return data, recipe


def wait(client, run_id, timeout=90):
    import time

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        response = client.get("/v1/runs/" + run_id)
        assert response.is_success, response.text
        result = response.json()
        if result["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return result
        time.sleep(0.3)
    raise AssertionError(f"Run did not finish: {run_id}")
