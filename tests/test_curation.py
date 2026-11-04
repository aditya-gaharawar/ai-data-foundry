import io
import json
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from conftest import definition, post, wait
from foundry.curation import duplicate_analysis, validate_annotation
from foundry.db import engine
from foundry.errors import Problem
from foundry.media import prepare_image
from foundry.security import canonical, digest
from PIL import Image, ImageDraw
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

CARD = {
    "purpose": "Local curation acceptance evidence",
    "intended_use": "Synthetic fixture testing only",
    "limitations": "Small human-reviewed fixture; no measured ground-truth accuracy",
    "content_risks": "Synthetic text and geometric shapes only",
    "restrictions": "No external distribution asserted",
}


def test_dedupe_is_reproducible_and_separates_exact_from_lexical_matches():
    first = {
        "prompt": "The quick brown fox jumps over the lazy dog by the river every morning",
        "response": "OK",
    }
    near = {"prompt": first["prompt"].upper(), "response": "ok"}
    other = {"prompt": "Choose a prime number", "response": "17"}
    samples = [{"payload": item} for item in [first, first, near, other]]
    report = duplicate_analysis(samples, "text", {"dedupe": "near"})
    assert report == duplicate_analysis(samples, "text", {"dedupe": "near"})
    assert (report["exact_duplicates"], report["near_duplicates"], report["retained"]) == (1, 1, 2)
    assert report["excluded"] == {
        "1": {"reason": "exact_duplicate", "representative": 0},
        "2": {"reason": "near_duplicate", "representative": 0},
    }
    assert duplicate_analysis(samples, "text", {"dedupe": "none"})["retained"] == 4


@pytest.mark.parametrize(
    "box",
    [
        {"label": "object", "x": -1, "y": 0, "width": 2, "height": 2},
        {"label": "object", "x": 60, "y": 0, "width": 8, "height": 2},
        {"label": "object", "x": 0, "y": 0, "width": 0, "height": 2},
        {"label": "unknown", "x": 0, "y": 0, "width": 2, "height": 2},
        {"label": "object", "x": float("nan"), "y": 0, "width": 2, "height": 2},
    ],
)
def test_corrupt_boxes_never_pass_annotation_validation(box):
    with pytest.raises(Problem, match="known text category"):
        validate_annotation(
            {"kind": "boxes", "boxes": [box]}, {"image": {"width": 64, "height": 48}}, "image", ["object"]
        )


def test_image_decoder_rejects_wrong_type_and_dimensions_before_storage():
    with pytest.raises(Problem) as error:
        prepare_image(b"<svg onload=alert(1)></svg>", "image/png", "unused")
    assert error.value.code == "INVALID_IMAGE"
    raw = io.BytesIO()
    Image.new("RGB", (5000, 1)).save(raw, format="PNG")
    with pytest.raises(Problem, match="4096"):
        prepare_image(raw.getvalue(), "image/png", "unused")


@pytest.fixture(scope="module")
def review_team(owners):
    clients = []
    identities = []
    for index in range(2):
        email = f"curation-{uuid.uuid4().hex}@foundry.local"
        password = "local-review-" + uuid.uuid4().hex
        user = post(
            owners[0],
            "/members",
            {
                "email": email,
                "name": f"Curation reviewer {index + 1}",
                "password": password,
                "role": "Labeler",
            },
        )
        client = httpx.Client(
            base_url="http://localhost:8000",
            headers={"Origin": "http://localhost:3000"},
            trust_env=False,
            timeout=30,
        )
        response = client.post("/v1/auth/login", json={"email": email, "password": password})
        response.raise_for_status()
        login = response.json()
        client.headers.update(
            {"X-CSRF-Token": login["csrf_token"], "X-Organization-Id": login["organizations"][0]["id"]}
        )
        clients.append(client)
        identities.append(user["id"])
    yield clients, identities
    for client, identifier in zip(clients, identities, strict=True):
        client.close()
        owners[0].delete(f"/v1/members/{identifier}")


def fixture_upload(client, dataset_id, raw, content_type="application/x-ndjson", filename="curation.jsonl"):
    upload = post(
        client,
        "/uploads",
        {
            "dataset_id": dataset_id,
            "filename": filename,
            "content_type": content_type,
            "bytes": len(raw),
            "sha256": digest(raw),
        },
    )
    response = httpx.put(upload["upload_urls"][0], content=raw, trust_env=False)
    response.raise_for_status()
    return post(
        client,
        f"/uploads/{upload['id']}/complete",
        {"parts": [{"part_number": 1, "etag": response.headers["etag"]}]},
        expected=200,
    )


def fixture_curation(owner, *, modality="text", samples=None, config=None, required_reviews=2):
    project = owner.get("/v1/projects").json()["items"][0]["id"]
    data = post(
        owner,
        "/datasets",
        {
            "project_id": project,
            "name": f"P06 {modality} {uuid.uuid4().hex[:8]}",
            "modality": modality,
            "policy": {"allowed_training_use": True, "license": "local-synthetic-fixture", "origin": "test"},
        },
    )
    if modality == "image":
        image = Image.new("RGB", (64, 48), "white")
        ImageDraw.Draw(image).rectangle((8, 6, 39, 29), fill="blue")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        uploaded = fixture_upload(owner, data["id"], buffer.getvalue(), "image/png", "shape.png")
    else:
        samples = samples or [{"prompt": "Choose a prime number", "response": "17"}]
        uploaded = fixture_upload(
            owner, data["id"], b"".join(canonical(sample) + b"\n" for sample in samples)
        )
    profile = post(
        owner,
        "/quality-profiles",
        {"name": "P06 immutable quality profile", "modality": modality, "config": config or {}},
    )
    curation = post(
        owner,
        "/curations",
        {
            "dataset_id": data["id"],
            "profile_id": profile["id"],
            "name": "Human review acceptance",
            "upload_ids": [uploaded["id"]],
            "categories": ["object", "other"],
            "required_reviews": required_reviews,
            "data_card": CARD,
        },
    )
    tasks = owner.get(f"/v1/annotation-tasks?curation_id={curation['id']}&limit=100").json()["items"]
    return data, uploaded, profile, curation, sorted(tasks, key=lambda task: task["sample_index"])


def vote(client, task, annotation, *, decision="accept", expected=200):
    return post(
        client,
        f"/annotation-tasks/{task['id']}/decision",
        {
            "expected_revision": task["revision"],
            "decision": decision,
            "annotation": annotation,
            "note": "Reviewed the actual source sample and corrected its label.",
        },
        expected=expected,
    )


def freeze(owner, identifier):
    current = owner.get(f"/v1/curations/{identifier}").json()
    return post(
        owner,
        f"/curations/{identifier}/freeze",
        {"expected_revision": current["revision"], "approved_for_publication": True},
        expected=200,
    )


def run_curation(owner, data, curation):
    recipe = definition(count=1)
    recipe["nodes"][0] = {"id": "source", "type": "curate", "config": {"curation_id": curation["id"]}}
    recipe["nodes"][1]["config"]["minimum_samples"] = 1
    saved = post(owner, "/recipes", {"project_id": data["project_id"], "definition": recipe})
    run = post(
        owner,
        "/runs",
        {"dataset_id": data["id"], "recipe_revision_id": saved["revision"]["id"], "max_budget_usd": 1},
        expected=202,
    )
    return wait(owner, run["id"])


@pytest.mark.integration
def test_text_curation_consensus_edits_adjudication_and_immutable_publication(owners, review_team):
    owner = owners[0]
    (first, second), identities = review_team
    sample = {
        "prompt": "The quick brown fox jumps over the lazy dog by the river every morning",
        "response": "OK",
    }
    data, _, profile, curation, tasks = fixture_curation(
        owner,
        samples=[
            sample,
            sample,
            {"prompt": sample["prompt"].upper(), "response": "ok"},
            {"prompt": "Choose a prime number", "response": "17"},
        ],
        config={"dedupe": "near", "minimum_samples": 2},
    )
    assert [task["status"] for task in tasks] == ["NEW", "EXCLUDED", "EXCLUDED", "NEW"]
    blocked = post(
        owner,
        f"/curations/{curation['id']}/freeze",
        {"expected_revision": curation["revision"], "approved_for_publication": True},
        expected=409,
    )
    assert blocked["code"] == "CURATION_GATE_FAILED"
    task = post(
        owner,
        f"/annotation-tasks/{tasks[0]['id']}/assign",
        {"expected_revision": 1, "user_id": identities[0]},
        expected=200,
    )
    assert (
        vote(second, task, {"kind": "category", "label": "object"}, expected=403)["code"] == "TASK_ASSIGNED"
    )
    task = vote(first, task, {"kind": "category", "label": "object"})
    task = vote(first, task, {"kind": "category", "label": "other"})
    assert task["status"] == "NEEDS_REVIEW" and len(task["reviews"]) == 2
    task = vote(second, task, {"kind": "category", "label": "object"})
    assert task["status"] == "NEEDS_ADJUDICATION"
    task = post(
        owner,
        f"/annotation-tasks/{task['id']}/adjudicate",
        {
            "expected_revision": task["revision"],
            "decision": "accept",
            "annotation": {"kind": "category", "label": "other"},
            "note": "Independent adjudication of the conflicting labels.",
        },
        expected=200,
    )
    assert task["status"] == "ADJUDICATED" and task["annotation"]["label"] == "other"
    accepted = vote(
        second,
        vote(first, tasks[3], {"kind": "category", "label": "object"}),
        {"kind": "category", "label": "object"},
    )
    assert accepted["status"] == "ACCEPTED"
    frozen = freeze(owner, curation["id"])
    assert frozen["quality"]["accepted"] == 2 and frozen["quality"]["review_coverage"] == 1
    assert frozen["quality"]["agreement"] == {"paired_tasks": 2, "agreed": 1, "ratio": 0.5}
    result = run_curation(owner, data, frozen)
    assert result["status"] == "SUCCEEDED", result["error"]
    manifest = result["version"]["manifest"]
    assert manifest["curation_id"] == curation["id"] and manifest["review_count"] == 6
    assert manifest["data_card"]["purpose"] == CARD["purpose"]
    assert manifest["publication_approval"]["approved_for_publication"] is True
    samples = owner.get(f"/v1/datasets/{data['id']}/samples").json()["items"]
    assert {sample["annotation"]["label"] for sample in samples} == {"object", "other"}
    assert len({sample["sample_id"] for sample in samples}) == 2
    assert (
        vote(first, accepted, {"kind": "category", "label": "other"}, expected=409)["code"]
        == "CURATION_FROZEN"
    )
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            text("UPDATE quality_profiles SET name='tamper' WHERE id=:id"), {"id": profile["id"]}
        )
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            text("UPDATE annotation_reviews SET note='tamper' WHERE task_id=:id"), {"id": task["id"]}
        )
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            text("UPDATE annotation_tasks SET annotation='{}' WHERE id=:id"), {"id": task["id"]}
        )


@pytest.mark.integration
def test_real_image_review_corrupt_label_gate_and_matching_coco_yolo_exports(owners, review_team):
    owner, other = owners
    (first, second), _ = review_team
    data, uploaded, _, curation, tasks = fixture_curation(owner, modality="image")
    task = tasks[0]
    assert uploaded["media"]["width"] == 64 and uploaded["media"]["height"] == 48
    invalid = {"kind": "boxes", "boxes": [{"label": "object", "x": 60, "y": 6, "width": 32, "height": 24}]}
    assert vote(first, task, invalid, expected=422)["code"] == "INVALID_ANNOTATION"
    assert owner.get(f"/v1/annotation-tasks/{task['id']}").json()["revision"] == 1
    blocked = post(
        owner,
        f"/curations/{curation['id']}/freeze",
        {"expected_revision": curation["revision"], "approved_for_publication": True},
        expected=409,
    )
    assert blocked["code"] == "CURATION_GATE_FAILED"
    annotation = {"kind": "boxes", "boxes": [{"label": "object", "x": 8, "y": 6, "width": 32, "height": 24}]}
    task = vote(second, vote(first, task, annotation), annotation)
    frozen = freeze(owner, curation["id"])
    result = run_curation(owner, data, frozen)
    assert result["status"] == "SUCCEEDED", result["error"]
    assert set(result["version"]["manifest"]["exports"]) == {"coco", "yolo"}
    preview = owner.get(f"/v1/annotation-tasks/{task['id']}/media")
    assert Image.open(io.BytesIO(preview.content)).size == (64, 48)
    for kind in ("coco", "yolo"):
        export = post(
            owner, "/exports", {"version_id": result["version"]["id"], "format": kind}, expected=202
        )
        grant = owner.get(f"/v1/exports/{export['id']}").json()["download_url"]
        assert other.get(grant).status_code == 404
        downloaded = owner.get(grant)
        assert digest(downloaded.content) == downloaded.headers["X-Content-SHA256"]
        with zipfile.ZipFile(io.BytesIO(downloaded.content)) as bundle:
            names = bundle.namelist()
            image_path = next(name for name in names if name.startswith("images/"))
            assert bundle.read(image_path) == preview.content
            assert json.loads(bundle.read("data-card.json"))["purpose"] == CARD["purpose"]
            if kind == "coco":
                coco = json.loads(bundle.read("annotations.json"))
                assert coco["annotations"][0]["bbox"] == [8, 6, 32, 24]
                assert coco["categories"][0]["name"] == "object"
                assert coco["images"][0]["file_name"] == image_path
            else:
                row = bundle.read(next(name for name in names if name.startswith("labels/"))).decode().split()
                assert row == ["0", "0.375", "0.375", "0.5", "0.5"]
                assert json.loads(bundle.read("data.yaml"))["names"] == ["object", "other"]


@pytest.mark.integration
def test_review_concurrency_reopen_independence_and_schema_failure(owners, review_team):
    owner = owners[0]
    (first, second), _ = review_team
    data, _, _, curation, tasks = fixture_curation(owner, samples=[{"prompt": 17}])
    task = tasks[0]
    annotation = {"kind": "category", "label": "object"}
    # Competing edits with the same task revision cannot silently overwrite each other.
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: first.post(
                    f"/v1/annotation-tasks/{task['id']}/decision",
                    json={
                        "expected_revision": 1,
                        "decision": "accept",
                        "annotation": annotation,
                        "note": "Concurrent first decision",
                    },
                    headers={"Idempotency-Key": uuid.uuid4().hex},
                ),
                range(2),
            )
        )
    assert sorted(response.status_code for response in results) == [200, 409]
    task = owner.get(f"/v1/annotation-tasks/{task['id']}").json()
    task = vote(second, task, annotation)
    task = post(
        owner,
        f"/annotation-tasks/{task['id']}/reopen",
        {"expected_revision": task["revision"], "note": "Re-review invalid source"},
        expected=200,
    )
    assert task["round"] == 2 and len(task["reviews"]) == 3
    task = vote(owner, task, annotation)
    task = vote(first, task, {"kind": "category", "label": "other"})
    assert (
        post(
            owner,
            f"/annotation-tasks/{task['id']}/adjudicate",
            {
                "expected_revision": task["revision"],
                "decision": "accept",
                "annotation": annotation,
                "note": "Cannot adjudicate my own vote",
            },
            expected=403,
        )["code"]
        == "INDEPENDENT_ADJUDICATOR_REQUIRED"
    )
    # An invalid payload stays blocked even if human labels agree in a later round.
    task = post(
        owner,
        f"/annotation-tasks/{task['id']}/reopen",
        {"expected_revision": task["revision"], "note": "Re-review"},
        expected=200,
    )
    task = vote(second, vote(first, task, annotation), annotation)
    current = owner.get(f"/v1/curations/{curation['id']}").json()
    assert current["quality"]["invalid"] == 1 and not current["quality"]["passed"]
    assert (
        post(
            owner,
            f"/curations/{curation['id']}/freeze",
            {"expected_revision": current["revision"], "approved_for_publication": True},
            expected=409,
        )["code"]
        == "CURATION_GATE_FAILED"
    )
    assert owner.get(f"/v1/datasets/{data['id']}/versions").json()["items"] == []


@pytest.mark.integration
def test_rejected_sources_are_removed_before_publication(owners, review_team):
    owner = owners[0]
    (first, second), _ = review_team
    data, _, _, curation, tasks = fixture_curation(
        owner,
        samples=[{"prompt": "Choose a prime number", "response": "17"}, {"prompt": 17}, {"response": False}],
        config={"minimum_acceptance_ratio": 0.3},
    )
    annotation = {"kind": "category", "label": "object"}
    assert vote(second, vote(first, tasks[0], annotation), annotation)["status"] == "ACCEPTED"
    disagreement = vote(second, vote(first, tasks[1], annotation), None, decision="reject")
    assert disagreement["status"] == "NEEDS_ADJUDICATION"
    rejected = post(
        owner,
        f"/annotation-tasks/{disagreement['id']}/adjudicate",
        {
            "expected_revision": disagreement["revision"],
            "decision": "reject",
            "note": "Independent inspection confirms this source has an invalid payload.",
        },
        expected=200,
    )
    assert rejected["status"] == "ADJUDICATED" and rejected["accepted"] is False
    assert (
        vote(second, vote(first, tasks[2], None, decision="reject"), None, decision="reject")["status"]
        == "REJECTED"
    )
    frozen = freeze(owner, curation["id"])
    assert frozen["quality"]["rejected"] == 2 and frozen["quality"]["accepted"] == 1
    assert frozen["quality"]["invalid"] == 0 and frozen["quality"]["review_coverage"] == 1
    result = run_curation(owner, data, frozen)
    assert result["status"] == "SUCCEEDED" and result["version"]["sample_count"] == 1
    assert result["version"]["manifest"]["review_count"] == 7
    assert owner.get(f"/v1/datasets/{data['id']}/samples").json()["items"][0]["payload"]["response"] == "17"


@pytest.mark.security
def test_curation_tenant_isolation_role_scope_and_idempotency(owners, review_team):
    owner, other = owners
    (labeler, _), identities = review_team
    data, uploaded, profile, curation, tasks = fixture_curation(owner, modality="image")
    task = tasks[0]
    for path in [
        f"/curations/{curation['id']}",
        f"/quality-profiles/{profile['id']}",
        f"/annotation-tasks/{task['id']}",
        f"/annotation-tasks/{task['id']}/media",
        f"/uploads/{uploaded['id']}/media",
        f"/annotation-tasks?curation_id={curation['id']}",
    ]:
        assert other.get("/v1" + path).status_code == 404
    assert (
        post(
            other,
            "/curations",
            {
                "dataset_id": data["id"],
                "profile_id": profile["id"],
                "name": "Forbidden",
                "categories": ["object"],
                "upload_ids": [uploaded["id"]],
            },
            expected=404,
        )["code"]
        == "NOT_FOUND"
    )
    assert (
        post(labeler, "/quality-profiles", {"name": "forbidden", "modality": "text"}, expected=403)["code"]
        == "INSUFFICIENT_SCOPE"
    )
    assert (
        post(
            labeler,
            f"/curations/{curation['id']}/freeze",
            {"expected_revision": 1, "approved_for_publication": True},
            expected=403,
        )["code"]
        == "INSUFFICIENT_SCOPE"
    )
    assert (
        post(
            labeler,
            f"/annotation-tasks/{task['id']}/assign",
            {"expected_revision": 1, "user_id": owner.get("/v1/me").json()["id"]},
            expected=403,
        )["code"]
        == "ASSIGNMENT_FORBIDDEN"
    )
    body = {"expected_revision": 1, "user_id": identities[0]}
    key = uuid.uuid4().hex
    assigned = post(labeler, f"/annotation-tasks/{task['id']}/assign", body, key=key, expected=200)
    assert post(labeler, f"/annotation-tasks/{task['id']}/assign", body, key=key, expected=200) == assigned
    assert (
        post(
            labeler,
            f"/annotation-tasks/{task['id']}/assign",
            {**body, "expected_revision": 2},
            key=key,
            expected=409,
        )["code"]
        == "IDEMPOTENCY_CONFLICT"
    )
    raw = io.BytesIO()
    Image.new("RGB", (10, 10)).save(raw, format="PNG")
    wrong = post(
        owner,
        "/uploads",
        {
            "dataset_id": data["id"],
            "filename": "wrong-type.jpg",
            "content_type": "image/jpeg",
            "bytes": len(raw.getvalue()),
            "sha256": digest(raw.getvalue()),
        },
    )
    part = httpx.put(wrong["upload_urls"][0], content=raw.getvalue(), trust_env=False)
    result = post(
        owner,
        f"/uploads/{wrong['id']}/complete",
        {"parts": [{"part_number": 1, "etag": part.headers["etag"]}]},
        expected=422,
    )
    assert result["code"] == "INVALID_IMAGE"
    assert owner.get(f"/v1/uploads/{wrong['id']}").json()["status"] == "REJECTED"
