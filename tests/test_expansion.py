"""P07–P12 real local engines, lease fencing, evaluation and governance proofs."""

import hashlib
import io
import json
import os
import subprocess
import time
import uuid
import zipfile

import httpx
import pytest
from conftest import dataset, definition, post, wait
from foundry.compute import compatibility
from foundry.errors import Problem
from foundry.evaluation import wilson
from foundry.external_adapters import SlurmAdapter, StructuredHTTPAdapter, kubernetes_job
from foundry.policies import pii_transform
from PIL import Image


def test_capability_checks_reject_compute_only_gpu_and_missing_engine():
    requirements = {"engine": "isaac.sim", "cpu_cores": 1, "memory_gib": 1}
    for model in ["NVIDIA H100", "H200", "A100"]:
        allowed, reason = compatibility(
            {
                "cpu_cores": 8,
                "memory_gib": 64,
                "accelerators": [{"model": model, "rt_cores": True}],
                "engines": {"isaac.sim": "6"},
            },
            requirements,
        )
        assert not allowed and "RT cores" in reason
    assert not compatibility(
        {"engines": {}}, {"engine": "artifact.verify@1", "cpu_cores": 1, "memory_gib": 0.5}
    )[0]
    assert compatibility({}, {"engine": "artifact.verify@1", "cpu_cores": 1, "memory_gib": 0.5})[0]


def test_privacy_rules_and_wilson_intervals_are_measured():
    payloads = [{"prompt": "Contact test@example.com or 555-123-4567", "response": "123-45-6789"}]
    redacted, report = pii_transform(payloads, "redact")
    assert "test@example.com" not in json.dumps(redacted)
    assert payloads[0]["response"] == "123-45-6789"
    assert report["detected"] == 3
    low, high = wilson(8, 10)
    assert 0.49 < low < 0.50 and 0.94 < high < 0.95


def test_external_protocol_contracts_do_not_claim_a_live_connection():
    result = StructuredHTTPAdapter.parse_text(
        {
            "choices": [{"message": {"content": '{"value":"ok"}'}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
        },
        {"type": "object", "required": ["value"], "properties": {"value": {"type": "string"}}},
    )
    assert result["usage"]["total_tokens"] == 5
    with pytest.raises(Problem, match="no call was sent"):
        StructuredHTTPAdapter.send("https://example.com/v1", "not-a-real-secret", {})
    with pytest.raises(Problem):
        StructuredHTTPAdapter.parse_image({"data": [{"url": "http://localhost/private"}]})
    job = kubernetes_job(
        job_name="verify",
        namespace="foundry",
        queue="cpu",
        image="registry/worker@sha256:" + "a" * 64,
        secret_name="agent-identity",
    )
    assert job["spec"]["suspend"] and not job["spec"]["template"]["spec"]["automountServiceAccountToken"]
    assert SlurmAdapter.parse_submission("123;test-cluster\n") == "123"
    assert SlurmAdapter.parse_accounting("123|COMPLETED|4|0:0")[0]["elapsed_seconds"] == 4
    with pytest.raises(Problem):
        SlurmAdapter.script("cpu\nexec malicious")


def test_protocol_contracts_document_distinct_auth_and_preconditions():
    from foundry.api import app

    schema = app.openapi()
    paths = schema["paths"]
    assert paths["/v1/compute/agent/claim"]["post"]["security"] == [{"agentAuth": []}]
    patch = paths["/v1/scim/v2/Users/{user_id}"]["patch"]
    assert patch["security"] == [{"scimAuth": []}]
    assert any(parameter["name"] == "If-Match" and parameter["required"] for parameter in patch["parameters"])
    assert any(
        parameter["name"] == "Idempotency-Key" and parameter["required"]
        for parameter in paths["/v1/providers"]["post"]["parameters"]
    )


def test_recipe_errors_do_not_echo_raw_config_secrets():
    from foundry.recipes import compile_recipe

    value = definition(count=1)
    value["nodes"][0]["config"]["count"] = "private-value-never-echo"
    with pytest.raises(Problem) as caught:
        compile_recipe(value)
    assert caught.value.code == "INVALID_NODE_CONFIG"
    assert "private-value-never-echo" not in caught.value.message


@pytest.mark.security
def test_new_controls_require_scope_and_bound_json_requests(local_client):
    key = post(
        local_client, "/api-keys", {"name": "Read-only expansion negatives", "scopes": ["datasets:read"]}
    )
    try:
        with httpx.Client(
            base_url="http://localhost:8000",
            headers={"Authorization": "Bearer " + key["secret"]},
            trust_env=False,
        ) as limited:
            for path, body in [
                ("/operations/reconciliations", {}),
                ("/governance/policies", {"definition": {}}),
                ("/compute/registered-pools", {"name": "Forbidden"}),
                ("/governance/scim-tokens", {"name": "Forbidden"}),
            ]:
                response = limited.post(
                    "/v1" + path, json=body, headers={"Idempotency-Key": uuid.uuid4().hex}
                )
                assert response.status_code == 403, response.text
            large = limited.post(
                "/v1/datasets", content=b"x" * (1024 * 1024 + 1), headers={"Content-Type": "application/json"}
            )
            assert large.status_code == 413
            assert large.headers["x-request-id"] == large.json()["request_id"]
            assert large.headers["cache-control"] == "no-store"
    finally:
        local_client.delete(f"/v1/api-keys/{key['id']}")


def upload(client, data, raw, content_type="application/x-ndjson", filename="fixture.jsonl"):
    target = post(
        client,
        "/uploads",
        {
            "dataset_id": data["id"],
            "filename": filename,
            "content_type": content_type,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
    )
    parts = []
    with httpx.Client(trust_env=False) as s3:
        for index, url in enumerate(target["upload_urls"]):
            part = s3.put(url, content=raw[index * target["part_size"] : (index + 1) * target["part_size"]])
            part.raise_for_status()
            parts.append({"part_number": index + 1, "etag": part.headers["etag"]})
    return post(client, f"/uploads/{target['id']}/complete", {"parts": parts}, expected=200)


@pytest.fixture(scope="module")
def independent_admin(local_client):
    password = "local-admin-" + uuid.uuid4().hex
    email = "governance-" + uuid.uuid4().hex + "@foundry.local"
    post(
        local_client,
        "/members",
        {
            "name": "Independent local governance reviewer",
            "email": email,
            "password": password,
            "role": "Admin",
        },
    )
    with httpx.Client(
        base_url="http://localhost:8000", headers={"Origin": "http://localhost:3000"}, trust_env=False
    ) as client:
        login = client.post("/v1/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        value = login.json()
        client.headers.update(
            {"X-CSRF-Token": value["csrf_token"], "X-Organization-Id": value["organizations"][0]["id"]}
        )
        yield client


@pytest.mark.security
def test_privacy_block_redact_and_source_policy_is_enforced(local_client):
    client = local_client
    try:
        for mode in ["block", "redact"]:
            post(client, "/governance/policies", {"definition": {"pii_mode": mode}})
            data, project = dataset(client, "Privacy " + mode)
            loaded = upload(
                client,
                data,
                b'{"prompt":"Contact fixture@example.com","response":"Synthetic private example"}\n',
            )
            recipe = post(
                client,
                "/recipes",
                {"project_id": project, "definition": definition(count=1, upload_id=loaded["id"])},
            )
            run = post(
                client,
                "/runs",
                {
                    "dataset_id": data["id"],
                    "recipe_revision_id": recipe["revision"]["id"],
                    "max_budget_usd": 1,
                },
                expected=202,
            )
            result = wait(client, run["id"])
            if mode == "block":
                assert result["status"] == "FAILED" and "PII" in result["error"]
            else:
                assert result["status"] == "SUCCEEDED", result
                samples = client.get(f"/v1/datasets/{data['id']}/samples").json()
                assert "fixture@example.com" not in json.dumps(samples)
                assert "REDACTED_EMAIL" in json.dumps(samples)
    finally:
        post(client, "/governance/policies", {"definition": {}})


@pytest.mark.integration
def test_independent_hold_release_and_shared_artifact_erasure(local_client, independent_admin):
    client = local_client
    name = "Disposable erasure proof " + uuid.uuid4().hex[:6]
    project = client.get("/v1/projects").json()["items"][0]["id"]
    first = post(
        client,
        "/datasets",
        {
            "project_id": project,
            "name": name,
            "modality": "image",
            "policy": {"allowed_training_use": True, "origin": "synthetic", "license": "local-synthetic"},
        },
    )
    other = post(
        client,
        "/datasets",
        {
            "project_id": project,
            "name": "Shared image must survive",
            "modality": "image",
            "policy": {"allowed_training_use": True, "origin": "synthetic", "license": "local-synthetic"},
        },
    )
    raw = io.BytesIO()
    Image.new("RGB", (48, 48), (37, 59, 83)).save(raw, format="PNG")
    versions = []
    for item in [first, other]:
        loaded = upload(client, item, raw.getvalue(), "image/png", "shared-primitive.png")
        recipe = post(
            client,
            "/recipes",
            {"project_id": project, "definition": definition(count=1, upload_id=loaded["id"])},
        )
        run = post(
            client,
            "/runs",
            {"dataset_id": item["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
            expected=202,
        )
        result = wait(client, run["id"])
        assert result["status"] == "SUCCEEDED", result
        versions.append(result["version"])
    post(
        client,
        f"/governance/datasets/{first['id']}",
        {"expected_revision": 1, "action": "place_legal_hold", "note": "Local hold approval proof"},
        expected=200,
    )
    rejected = client.post(
        "/v1/governance/erasures",
        json={"dataset_id": first["id"], "reason": "Synthetic fixture removal"},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert rejected.status_code == 409 and rejected.json()["code"] == "LEGAL_HOLD"
    approval = post(
        client,
        f"/governance/datasets/{first['id']}",
        {"expected_revision": 2, "action": "request_hold_release", "note": "Independent test release"},
        expected=202,
    )
    same = client.post(
        f"/v1/governance/approvals/{approval['id']}/decision",
        json={"decision": "approve", "note": "Cannot approve own request"},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert same.status_code == 409
    post(
        independent_admin,
        f"/governance/approvals/{approval['id']}/decision",
        {"decision": "approve", "note": "Reviewed independent synthetic fixture"},
        expected=200,
    )
    try:
        post(client, "/governance/policies", {"definition": {"erasure_delay_seconds": 0}})
        request = post(
            client,
            "/governance/erasures",
            {"dataset_id": first["id"], "reason": "Remove disposable synthetic fixture artifacts"},
        )
        post(
            independent_admin,
            f"/governance/erasures/{request['id']}/decision",
            {"decision": "approve", "note": "Independently reviewed local synthetic erasure"},
            expected=200,
        )
        preview = post(client, f"/governance/erasures/{request['id']}/preview", {}, expected=200)
        assert preview["result"]["shared_keys_preserved"] >= 1
        post(
            client,
            f"/governance/erasures/{request['id']}/execute",
            {"confirm_dataset_name": name, "plan_sha256": preview["result"]["plan_sha256"]},
            expected=202,
        )
        assert client.get(f"/v1/datasets/{first['id']}/samples").status_code == 410
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            terminal = client.get(f"/v1/governance/erasures/{request['id']}").json()
            if terminal["status"] in ["ERASED", "ERASURE_FAILED"]:
                break
            time.sleep(0.3)
        assert terminal["status"] == "ERASED", terminal
        sample = client.get(f"/v1/datasets/{other['id']}/samples").json()["items"][0]
        image = client.get(
            f"/v1/datasets/{other['id']}/versions/{versions[1]['id']}/samples/{sample['sample_id']}/image"
        )
        assert image.is_success and Image.open(io.BytesIO(image.content)).size == (48, 48)
    finally:
        post(client, "/governance/policies", {"definition": {}})


@pytest.fixture(scope="module")
def local_client(owners):
    client = owners[0]
    # Explicitly widen only the nonbillable local synthetic-test ledger.
    response = client.patch("/v1/budgets", json={"maximum_usd": 1000})
    assert response.is_success, response.text
    yield client


def build(client, source=None, config=None, *, count=3, seed=None, modality="text", name="Expansion proof"):
    project = client.get("/v1/projects").json()["items"][0]["id"]
    data = post(
        client,
        "/datasets",
        {
            "project_id": project,
            "name": name,
            "modality": modality,
            "policy": {
                "origin": "local-synthetic",
                "license": "local-synthetic",
                "allowed_training_use": True,
            },
        },
    )
    spec = definition(count=count, seed=seed or int(uuid.uuid4().hex[:7], 16))
    if source:
        spec["nodes"][0] = {"id": "source", "type": source, "config": config}
    recipe = post(client, "/recipes", {"project_id": project, "definition": spec})
    run = post(
        client,
        "/runs",
        {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
        expected=202,
    )
    terminal = wait(client, run["id"], timeout=240)
    assert terminal["status"] == "SUCCEEDED", terminal
    return data, terminal["version"], recipe, terminal


@pytest.mark.integration
def test_genuine_licensed_model_pipeline_and_revocation(local_client, owners):
    client = local_client
    catalog = client.get("/v1/providers/catalog").json()["items"]
    model = next(item for item in catalog if item["kind"] == "local.gguf")
    assert model["state"] == "READY", model
    connection = post(
        client,
        "/providers",
        {
            "name": "Licensed local inference proof",
            "kind": "local.gguf",
            "model_ref": model["model_ref"],
            "permitted_training_use": True,
            "consent_to_processing": True,
            "terms_version": "Apache-2.0",
            "rights_evidence": "Pinned Apache-2.0 public weights; synthetic local smoke only.",
        },
    )
    assert connection["state"] == "READY"
    data, version, recipe, run = build(
        client,
        "teacher",
        {
            "connection_id": connection["id"],
            "instructions": "Write one short instruction and answer about numbers.",
            "count": 1,
            "max_output_tokens": 128,
            "seed": 17,
        },
        count=1,
    )
    samples = client.get(f"/v1/datasets/{data['id']}/samples").json()["items"]
    assert samples[0]["review_status"] == "UNREVIEWED_MODEL"
    assert samples[0]["payload"]["prompt"] and samples[0]["payload"]["response"]
    source = version["manifest"]["source_execution"]
    assert source["usage"]["completion_tokens"] > 0
    assert source["model"]["license"] == "Apache-2.0"
    assert source["external_cost_usd"] == 0
    assert "JSON schema" in source["verification"]
    assert owners[1].get("/v1/providers/" + connection["id"]).status_code == 404
    post(client, f"/providers/{connection['id']}/revoke", {}, expected=200)
    rejected = client.post(
        "/v1/runs",
        json={"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert rejected.status_code == 409 and rejected.json()["code"] == "PROVIDER_NOT_READY"


@pytest.mark.integration
def test_blender_frames_masks_scene_and_export_integrity(local_client):
    client = local_client
    data, version, _, run = build(
        client,
        "simulate",
        {
            "engine": "blender.procedural@1",
            "object_type": "cube",
            "count": 1,
            "frames_per_scene": 2,
            "resolution": 64,
            "fps": 10,
            "seed": 27,
            "render_samples": 2,
        },
        count=2,
        modality="image",
        name="Real Blender episode",
    )
    samples = client.get(f"/v1/datasets/{data['id']}/samples").json()["items"]
    assert len(samples) == 2
    assert all(item["review_status"] == "SIMULATION_DERIVED" for item in samples)
    for sample in samples:
        prefix = f"/v1/versions/{version['id']}/samples/{sample['sample_id']}/artifacts"
        mask = client.get(prefix + "/mask")
        mask.raise_for_status()
        assert Image.open(io.BytesIO(mask.content)).size == (64, 64)
        scene = client.get(prefix + "/scene")
        assert scene.content[:4] == b"glTF"
        assert sample["annotation"]["boxes"][0]["width"] > 0
    exported = post(client, "/exports", {"version_id": version["id"], "format": "coco"}, expected=202)
    ready = client.get(f"/v1/exports/{exported['id']}").json()
    response = client.get(ready["download_url"])
    assert response.is_success
    assert hashlib.sha256(response.content).hexdigest() == response.headers["x-content-sha256"]
    bundle = zipfile.ZipFile(io.BytesIO(response.content))
    assert any(name.endswith(".png") for name in bundle.namelist())
    assert version["manifest"]["source_execution"]["engine"].startswith("blender")


@pytest.fixture(scope="module")
def versions_pair(local_client):
    first = build(local_client, count=3, seed=712345)
    # Same immutable source data in a distinct version gives a reproducible diff.
    data, _, recipe, _ = first
    run = post(
        local_client,
        "/runs",
        {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
        expected=202,
    )
    second = wait(local_client, run["id"])
    assert second["status"] == "SUCCEEDED"
    return first, second["version"]


@pytest.mark.integration
def test_real_agent_execution_and_expired_lease_fencing(local_client, versions_pair):
    client = local_client
    version = versions_pair[0][1]
    pool = post(
        client,
        "/compute/registered-pools",
        {"name": "Outbound test CPU", "capabilities": {"cpu_cores": 2, "memory_gib": 2}},
    )
    agent = post(client, "/compute/agents", {"pool_id": pool["id"], "name": "Real verifier process"})
    job = post(
        client,
        "/compute/jobs",
        {"pool_id": pool["id"], "version_id": version["id"], "lease_seconds": 2},
        expected=202,
    )
    with httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": "Bearer " + agent["agent_token"]},
        trust_env=False,
    ) as worker:
        assert worker.post("/v1/compute/agent/claim").status_code == 409
        assert worker.post("/v1/compute/agent/heartbeat", json={"cpu_cores": 2, "memory_gib": 2}).is_success
        lease = worker.post("/v1/compute/agent/claim").json()["job"]
        assert lease["id"] == job["id"]
        busy = client.post(
            f"/v1/governance/datasets/{versions_pair[0][0]['id']}",
            json={
                "expected_revision": 1,
                "action": "protect_holdout",
                "note": "An active compute lease must block holdout conversion",
            },
            headers={"Idempotency-Key": uuid.uuid4().hex},
        )
        assert busy.status_code == 409 and busy.json()["code"] == "DATASET_BUSY"
        raw = worker.get(lease["artifact_url"], headers={"X-Lease-Token": lease["lease_token"]})
        assert raw.is_success
        time.sleep(2.2)
        assert (
            worker.post(
                f"/v1/compute/agent/jobs/{job['id']}/complete",
                headers={"X-Lease-Token": lease["lease_token"]},
                json={
                    "attempt": lease["attempt"],
                    "sha256": hashlib.sha256(raw.content).hexdigest(),
                    "bytes": len(raw.content),
                    "processing_ms": 2,
                },
            ).status_code
            == 409
        )
    result = subprocess.run(
        [".venv/bin/python", "-m", "foundry.agent", "--once"],
        env={**os.environ, "FOUNDRY_AGENT_TOKEN": agent["agent_token"]},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    completed = client.get(f"/v1/compute/jobs/{job['id']}").json()
    assert completed["status"] == "SUCCEEDED" and completed["attempt"] == 2
    assert completed["result"]["verified_by_api"]
    post(client, f"/compute/agents/{agent['id']}/revoke", {}, expected=200)
    assert (
        httpx.post(
            "http://localhost:8000/v1/compute/agent/claim",
            headers={"Authorization": "Bearer " + agent["agent_token"]},
            trust_env=False,
        ).status_code
        == 401
    )


@pytest.mark.integration
def test_search_diff_benchmark_import_comparison_and_saved_feedback(local_client, versions_pair):
    client = local_client
    first, second = versions_pair
    data, left, _, _ = first
    diff = client.get(
        "/v1/versions/compare", params={"left_version_id": left["id"], "right_version_id": second["id"]}
    )
    assert diff.is_success, diff.text
    assert diff.json()["added"] == 0 and diff.json()["removed"] == 0
    distribution = client.get(f"/v1/versions/{left['id']}/distribution").json()
    assert distribution["sample_count"] == 3
    result = client.get("/v1/search/samples", params={"q": "Example", "dataset_id": data["id"]})
    assert result.is_success and result.json()["items"], result.text
    holdout, holdout_version, _, _ = build(
        client, count=3, seed=int(uuid.uuid4().hex[:7], 16), name="Independent synthetic holdout fixture"
    )
    post(
        client,
        f"/governance/datasets/{holdout['id']}",
        {
            "expected_revision": 1,
            "action": "protect_holdout",
            "note": "Independent fixture, no scientific improvement claim",
        },
        expected=200,
    )
    benchmark = post(
        client,
        "/benchmarks",
        {
            "name": "Fixed held-out fixture",
            "version_id": holdout_version["id"],
            "external_ref": "local:fixture:holdout",
            "source_kind": "synthetic_fixture",
            "independent_of_training": True,
        },
    )
    evaluations = []
    for version, correct in [(left, 6), (second, 8)]:
        evaluations.append(
            post(
                client,
                "/evaluations",
                {
                    "version_id": version["id"],
                    "benchmark_id": benchmark["id"],
                    "model_ref": "external:synthetic-results-fixture",
                    "external_run_ref": "fixture:" + uuid.uuid4().hex,
                    "result": {"name": "overall", "correct": correct, "total": 10},
                    "slices": [{"name": "arithmetic", "correct": 2, "total": 5}],
                    "evidence_note": "Imported synthetic counts exercise protocol, not measured model gains.",
                },
            )
        )
    comparison = client.get(
        "/v1/evaluations/compare",
        params={"baseline_id": evaluations[0]["id"], "candidate_id": evaluations[1]["id"]},
    )
    assert comparison.is_success, comparison.text
    feedback = post(
        client,
        "/feedback",
        {
            "evaluation_id": evaluations[1]["id"],
            "maximum_new_samples": 20,
            "maximum_internal_budget_usd": 0.1,
        },
    )
    assert feedback["status"] == "DRAFT"
    approved = post(
        client,
        f"/feedback/{feedback['id']}/decision",
        {"decision": "approve", "note": "Bounded recommendation only; no automatic launch."},
        expected=200,
    )
    assert approved["status"] == "APPROVED"


@pytest.mark.security
def test_external_provider_and_isaac_admission_remain_blocked(local_client, owners):
    client = local_client
    connection = post(
        client,
        "/providers",
        {
            "name": "Unconfigured image adapter",
            "kind": "http.image",
            "model_ref": "unconfigured",
            "endpoint": "https://example.com/v1",
            "api_secret": "local-test-secret-not-live",
            "permitted_training_use": True,
            "consent_to_processing": True,
            "terms_version": "unconfigured",
            "rights_evidence": "Synthetic local connector boundary test only.",
        },
    )
    assert connection["state"] == "BLOCKED_EXTERNAL" and "secret" not in json.dumps(connection)
    project = client.get("/v1/projects").json()["items"][0]["id"]
    for source, config in [
        (
            "image_generate",
            {"connection_id": connection["id"], "instructions": "Synthetic primitive", "count": 1},
        ),
        ("simulate", {"engine": "isaac.sim", "count": 1}),
    ]:
        spec = definition(count=1)
        spec["nodes"][0] = {"id": "source", "type": source, "config": config}
        recipe = post(client, "/recipes", {"project_id": project, "definition": spec})
        rejected = client.post(f"/v1/recipes/{recipe['id']}/estimate")
        assert rejected.status_code == 409, rejected.text


@pytest.mark.security
def test_scim_lifecycle_etags_role_limits_and_other_tenant_survives(local_client, owners):
    client = local_client
    email = "scim-shared-" + uuid.uuid4().hex + "@foundry.local"
    original = post(
        owners[1],
        "/members",
        {
            "name": "Other tenant identity",
            "email": email,
            "password": "local-original-" + uuid.uuid4().hex,
            "role": "Engineer",
        },
    )
    token = post(client, "/governance/scim-tokens", {"name": "SCIM fixture"})
    with httpx.Client(
        base_url="http://localhost:8000/v1/scim/v2",
        headers={"Authorization": "Bearer " + token["provisioning_token"]},
        trust_env=False,
    ) as scim:
        body = {
            "userName": email,
            "externalId": uuid.uuid4().hex,
            "roles": [{"value": "Engineer"}],
        }
        created = scim.post("/Users", json=body)
        assert created.status_code == 201, created.text
        user = created.json()
        etag = created.headers["etag"]
        assert (
            scim.patch(
                "/Users/" + user["id"],
                json={"Operations": [{"op": "replace", "path": "active", "value": False}]},
            ).status_code
            == 428
        )
        invalid = scim.patch(
            "/Users/" + user["id"],
            headers={"If-Match": etag},
            json={"Operations": [{"op": "replace", "path": "roles", "value": [{"value": "Owner"}]}]},
        )
        assert invalid.status_code == 400 and invalid.json()["schemas"][0].endswith(":Error")
        changed = scim.patch(
            "/Users/" + user["id"],
            headers={"If-Match": etag},
            json={"Operations": [{"op": "replace", "path": "active", "value": False}]},
        )
        assert changed.status_code == 200
        assert scim.delete("/Users/" + user["id"], headers={"If-Match": etag}).status_code == 412
        assert (
            scim.delete("/Users/" + user["id"], headers={"If-Match": changed.headers["etag"]}).status_code
            == 204
        )
        assert scim.get("/Users/" + user["id"]).status_code == 404
        assert owners[1].get("/v1/datasets").is_success
        assert any(
            item["id"] == original["id"] and item["role"] == "Engineer"
            for item in owners[1].get("/v1/members").json()["items"]
        )
    post(client, f"/governance/scim-tokens/{token['id']}/revoke", {}, expected=200)
    assert (
        httpx.get(
            "http://localhost:8000/v1/scim/v2/Users",
            headers={"Authorization": "Bearer " + token["provisioning_token"]},
            trust_env=False,
        ).status_code
        == 401
    )


@pytest.mark.security
def test_holdout_hidden_from_training_key_and_contamination_blocked(local_client):
    client = local_client
    seed = int(uuid.uuid4().hex[:7], 16)
    protected, version, _, _ = build(client, count=2, seed=seed, name="Protected held-out answers")
    post(
        client,
        f"/governance/datasets/{protected['id']}",
        {"expected_revision": 1, "action": "protect_holdout", "note": "Only evaluators may view solutions"},
        expected=200,
    )
    key = post(client, "/api-keys", {"name": "Training reader", "scopes": ["datasets:read"]})
    with httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": "Bearer " + key["secret"]},
        trust_env=False,
    ) as training:
        assert training.get(f"/v1/datasets/{protected['id']}/samples").status_code == 403
        assert training.get(f"/v1/versions/{version['id']}/distribution").status_code == 403
        assert protected["id"] not in json.dumps(training.get("/v1/datasets?limit=100").json())
        assert (
            training.get(
                "/v1/search/samples", params={"q": "Example", "dataset_id": protected["id"]}
            ).status_code
            == 403
        )
    target, project = dataset(client, "Contamination rejection target")
    recipe = post(client, "/recipes", {"project_id": project, "definition": definition(count=2, seed=seed)})
    run = post(
        client,
        "/runs",
        {"dataset_id": target["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
        expected=202,
    )
    terminal = wait(client, run["id"])
    assert terminal["status"] == "FAILED" and "holdout" in terminal["error"]
    assert not client.get(f"/v1/datasets/{target['id']}/versions").json()["items"]


@pytest.mark.integration
def test_ledger_and_signed_readiness_are_persisted(local_client):
    client = local_client
    report = post(client, "/operations/reconciliations", {})
    assert report["report"]["status"] == "PASS", report
    assert report["report"]["ledger_external_micro"] == 0
    readiness = post(client, "/operations/readiness", {})
    assert readiness["report"]["production_release"] == "BLOCKED_EXTERNAL"
    assert len(readiness["report"]["operator_signature"]) == 64
    assert client.get("/v1/operations/readiness").json()["items"][0]["id"] == readiness["id"]
