import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
from conftest import dataset, definition, pipeline, post, wait
from datafoundry import DataFoundry, verify_webhook
from foundry.config import settings
from foundry.db import Session
from foundry.models import Usage, Version
from jsonschema import validate
from sqlalchemy import func, select

pytestmark = pytest.mark.integration


def configure_receiver(hook, fail=False):
    response = httpx.post(
        "http://localhost:9100/configure",
        headers={"X-Receiver-Control": settings().app_secret},
        json={"webhook_id": hook["id"], "secret": hook["signing_secret"], "fail": fail},
        trust_env=False,
    )
    response.raise_for_status()


def test_complete_sdk_export_webhook_and_cli(owners, tmp_path):
    owner = owners[0]
    receiver = owner.get("/v1/overview").json()["local_webhook_url"]
    hook = post(
        owner, "/webhooks", {"url": receiver, "events": ["dataset.version.published", "export.ready"]}
    )
    configure_receiver(hook)
    key = post(
        owner,
        "/api-keys",
        {"name": "SDK integration", "scopes": ["datasets:read", "datasets:write", "runs:execute"]},
    )
    project = owner.get("/v1/projects").json()["items"][0]["id"]
    with DataFoundry(api_key=key["secret"]) as api:
        data = api.datasets.create(
            name="SDK: verified 100-sample dataset",
            project_id=project,
            policy={"origin": "local-synthetic", "license": "local-synthetic", "allowed_training_use": True},
        )
        recipe = api.recipes.create(project_id=project, definition=definition())
        run = api.runs.create(dataset_id=data.id, recipe_revision_id=recipe.revision.id)
        result = api.runs.wait(run.id)
        assert result.status == "SUCCEEDED", result.error
        assert result.version.sample_count == 100
        output = api.datasets.download(result.version.id, tmp_path / "dataset.jsonl")
        rows = [json.loads(line) for line in output.read_text().splitlines()]
        assert len(rows) == 100
        assert all(
            row["payload"]["response"].isdigit() and row["generation_run_id"] == run.id for row in rows
        )
        manifest = result.version.manifest
        assert hashlib.sha256(output.read_bytes()).hexdigest() == manifest["data_artifact"]["sha256"]
        event_schema = json.loads(Path("contracts/job-event.schema.json").read_text())
        for _ in range(50):
            receipts = httpx.get(
                "http://localhost:9100/receipts",
                headers={"X-Receiver-Control": settings().app_secret},
                trust_env=False,
            ).json()["items"]
            matched = [
                receipt
                for receipt in receipts
                if receipt["webhook_id"] == hook["id"]
                and receipt["payload"]["event_type"] == "dataset.version.published"
            ]
            if matched:
                break
            time.sleep(0.3)
        assert matched and matched[0]["valid"]
        receipt = matched[0]
        event = verify_webhook(
            hook["signing_secret"], receipt["raw"].encode(), receipt["timestamp"], receipt["signature"]
        )
        validate(event, event_schema)
        assert event["data"]["version_id"] == result.version.id
        replay = post(owner, f"/webhook-deliveries/{receipt['delivery_id']}/replay", expected=200)
        assert replay["status"] == "PENDING"
        environment = {**os.environ, "FOUNDRY_API_KEY": key["secret"]}
        cli = subprocess.run(
            [sys.executable, "-m", "foundry.cli", "--help"], env=environment, capture_output=True, text=True
        )
        assert cli.returncode == 0
        cli = subprocess.run(
            [str(Path(sys.executable).parent / "datafoundry"), "runs", "watch", run.id],
            env=environment,
            capture_output=True,
            text=True,
        )
        assert cli.returncode == 0, cli.stderr
        assert json.loads(cli.stdout)["status"] == "SUCCEEDED"
    owner.delete(f"/v1/api-keys/{key['id']}")
    owner.delete(f"/v1/webhooks/{hook['id']}")


def test_real_multipart_upload_and_publication(owners, tmp_path):
    owner = owners[0]
    key = post(
        owner,
        "/api-keys",
        {"name": "Multipart integration", "scopes": ["datasets:read", "datasets:write", "runs:execute"]},
    )
    data, project = dataset(owner, "Multipart: 100 source records")
    file = tmp_path / "source.jsonl"
    file.write_text(
        "".join(
            json.dumps({"prompt": f"Record {index}: " + "text " * 12000, "response": str(index)}) + "\n"
            for index in range(100)
        )
    )
    assert file.stat().st_size > 5 * 1024 * 1024
    with DataFoundry(api_key=key["secret"]) as api:
        uploaded = api.datasets.upload(data["id"], file)
        assert uploaded["status"] == "COMPLETED" and uploaded["sample_count"] == 100
        recipe = api.recipes.create(project_id=project, definition=definition(upload_id=uploaded["id"]))
        result = api.runs.wait(
            api.runs.create(dataset_id=data["id"], recipe_revision_id=recipe.revision.id).id
        )
        assert result.status == "SUCCEEDED", result.error
        assert len(api.request("GET", f"/v1/datasets/{data['id']}/samples")["items"]) == 10
    owner.delete(f"/v1/api-keys/{key['id']}")


def test_concurrent_idempotency_has_one_publication_and_usage(owners):
    owner = owners[0]
    data, recipe = pipeline(owner)
    body = {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1}
    key = uuid.uuid4().hex
    with ThreadPoolExecutor(max_workers=4) as pool:
        runs = list(pool.map(lambda _: post(owner, "/runs", body, key=key, expected=202), range(4)))
    assert len({run["id"] for run in runs}) == 1
    result = wait(owner, runs[0]["id"])
    assert result["status"] == "SUCCEEDED"
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Version).where(Version.run_id == result["id"])) == 1
        assert (
            db.scalar(
                select(func.sum(Usage.quantity)).where(
                    Usage.run_id == result["id"], Usage.metric == "processed_samples"
                )
            )
            == 100
        )


def test_failed_quality_gate_never_publishes(owners):
    owner = owners[0]
    data, recipe = pipeline(owner, minimum=101)
    run = post(
        owner,
        "/runs",
        {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
        expected=202,
    )
    result = wait(owner, run["id"])
    assert result["status"] == "FAILED" and not result["quality"]["passed"]
    assert result["version"] is None
    assert owner.get(f"/v1/datasets/{data['id']}/versions").json()["items"] == []


def test_webhook_retries_dead_letters_and_recovers(owners):
    owner = owners[0]
    hook = post(
        owner,
        "/webhooks",
        {
            "url": owner.get("/v1/overview").json()["local_webhook_url"],
            "events": ["dataset.version.published"],
        },
    )
    configure_receiver(hook, fail=True)
    data, recipe = pipeline(owner)
    run = post(
        owner,
        "/runs",
        {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 1},
        expected=202,
    )
    assert wait(owner, run["id"])["status"] == "SUCCEEDED"
    end = time.monotonic() + 40
    target = None
    while time.monotonic() < end:
        deliveries = owner.get("/v1/webhook-deliveries?limit=100").json()["items"]
        target = next(
            (
                value
                for value in deliveries
                if value["webhook_id"] == hook["id"] and value["status"] == "DEAD_LETTER"
            ),
            None,
        )
        if target:
            break
        time.sleep(0.5)
    assert target and target["attempts"] == 5 and target["last_status"] == 500
    configure_receiver(hook)
    post(owner, f"/webhook-deliveries/{target['id']}/replay", expected=200)
    for _ in range(30):
        deliveries = owner.get("/v1/webhook-deliveries?limit=100").json()["items"]
        replayed = next(value for value in deliveries if value["id"] == target["id"])
        if replayed["status"] == "DELIVERED":
            break
        time.sleep(0.3)
    assert replayed["status"] == "DELIVERED"
    owner.delete(f"/v1/webhooks/{hook['id']}")


def test_worker_crash_resumes_without_duplicate_effects(owners):
    owner = owners[0]
    data, recipe = pipeline(owner, count=10000)
    run = post(
        owner,
        "/runs",
        {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 20},
        expected=202,
    )
    end = time.monotonic() + 15
    while time.monotonic() < end:
        current = owner.get(f"/v1/runs/{run['id']}").json()
        if 0 < current["processed"] < current["sample_count"]:
            break
        time.sleep(0.1)
    assert 0 < current["processed"] < current["sample_count"], (
        "Did not observe an active checkpoint before fault injection."
    )
    pid_file = Path(".local/worker.pid")
    if pid_file.exists():
        pid = int(pid_file.read_text())
        command = Path(f"/proc/{pid}/cmdline").read_bytes()
        assert b"foundry.worker" in command
        os.kill(pid, signal.SIGKILL)
    else:
        subprocess.run(
            ["docker", "compose", "kill", "-s", "SIGKILL", "worker"], check=True, capture_output=True
        )
        subprocess.run(["docker", "compose", "up", "-d", "worker"], check=True, capture_output=True)
    result = wait(owner, run["id"], timeout=90)
    assert result["status"] == "SUCCEEDED", result["error"]
    assert result["processed"] == 10000 and result["spent_usd"] == 10
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(Version).where(Version.run_id == run["id"])) == 1
        assert (
            db.scalar(
                select(func.sum(Usage.quantity)).where(
                    Usage.run_id == run["id"], Usage.metric == "processed_samples"
                )
            )
            == 10000
        )


def test_cancel_retry_and_api_restart_preserve_committed_state(owners):
    owner = owners[0]
    data, recipe = pipeline(owner, count=10000)
    created = post(
        owner,
        "/runs",
        {"dataset_id": data["id"], "recipe_revision_id": recipe["revision"]["id"], "max_budget_usd": 20},
        expected=202,
    )
    cancelled = owner.post(f"/v1/runs/{created['id']}/cancel")
    assert cancelled.is_success
    terminal = wait(owner, created["id"])
    assert terminal["status"] == "CANCELLED" and terminal["reserved_usd"] == 0
    assert terminal["version"] is None
    retried = post(owner, f"/runs/{created['id']}/retry", expected=202)
    result = wait(owner, retried["id"])
    assert result["status"] == "SUCCEEDED"
    assert result["version"]["manifest"]["execution_environment"]["source_sha256"]
    pid_file = Path(".local/api.pid")
    if pid_file.exists():
        pid = int(pid_file.read_text())
        assert b"foundry.api" in Path(f"/proc/{pid}/cmdline").read_bytes()
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if int(pid_file.read_text()) != pid:
                break
            time.sleep(0.1)
        assert int(pid_file.read_text()) != pid, "API supervisor did not replace the terminated process."
    else:
        subprocess.run(["docker", "compose", "restart", "api"], check=True, capture_output=True)
    for _ in range(50):
        try:
            response = owner.get(f"/v1/runs/{retried['id']}")
            if response.is_success:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    assert response.json()["version"]["manifest_hash"] == result["version"]["manifest_hash"]


def test_typescript_sdk_executes_the_same_flow(owners):
    owner = owners[0]
    key = post(
        owner,
        "/api-keys",
        {"name": "TypeScript SDK integration", "scopes": ["datasets:read", "datasets:write", "runs:execute"]},
    )
    project = owner.get("/v1/projects").json()["items"][0]["id"]
    subprocess.run(
        [
            "pnpm",
            "exec",
            "tsc",
            "-p",
            "packages/sdk-ts/tsconfig.json",
            "--noEmit",
            "false",
            "--outDir",
            ".local/sdk-ts",
        ],
        check=True,
        capture_output=True,
    )
    Path(".local/sdk-ts/package.json").write_text('{"type":"module"}')
    program = """
    import {DataFoundry} from './.local/sdk-ts/index.js';
    const client = new DataFoundry({baseUrl:'http://localhost:8000',apiKey:process.env.FOUNDRY_API_KEY});
    const dataset = await client.datasets.create({name:'TypeScript SDK: verified text',project_id:process.env.FOUNDRY_PROJECT,policy:{origin:'local-synthetic',allowed_training_use:true}});
    const definition=JSON.parse(process.env.FOUNDRY_RECIPE);
    const recipe=await client.recipes.create({project_id:process.env.FOUNDRY_PROJECT,definition});
    const run=await client.runs.create({dataset_id:dataset.id,recipe_revision_id:recipe.revision.id,max_budget_usd:1});
    const result=await client.runs.wait(run.id);
    if(result.status!=='SUCCEEDED')throw Error(result.error);
    const bytes=await client.datasets.download(result.version.id);
    const count=new TextDecoder().decode(bytes).trim().split('\\n').length;
    if(count!==100)throw Error('Expected 100 records');
    console.log(JSON.stringify({status:result.status,samples:count,run_id:run.id}));
    """
    environment = {
        **os.environ,
        "FOUNDRY_API_KEY": key["secret"],
        "FOUNDRY_PROJECT": project,
        "FOUNDRY_RECIPE": json.dumps(definition()),
    }
    result = subprocess.run(
        ["node", "--input-type=module", "-e", program],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["samples"] == 100
    owner.delete(f"/v1/api-keys/{key['id']}")


def test_python_sdk_installs_in_a_blank_environment(owners, tmp_path):
    key = post(owners[0], "/api-keys", {"name": "Standalone SDK install", "scopes": ["datasets:read"]})
    target = tmp_path / "sdk-venv"
    subprocess.run(["uv", "venv", str(target)], check=True, capture_output=True)
    python = str(target / "bin/python")
    subprocess.run(
        ["uv", "pip", "install", "--python", python, "packages/sdk-python"], check=True, capture_output=True
    )
    script = "from datafoundry import DataFoundry; import os; c=DataFoundry(api_key=os.environ['FOUNDRY_API_KEY']); assert c.request('GET','/v1/me')['id']; print('standalone SDK authenticated')"
    result = subprocess.run(
        [python, "-c", script],
        env={**os.environ, "FOUNDRY_API_KEY": key["secret"]},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    owners[0].delete(f"/v1/api-keys/{key['id']}")
