"""P13 Python/TypeScript/CLI parity over real HTTP, not mocked transports."""

import json
import os
import subprocess
from pathlib import Path

import pytest
from conftest import pipeline, post, wait
from datafoundry import DataFoundry
from datafoundry.models import ScheduleCreate
from test_automation import eventually, schedule_body

pytestmark = pytest.mark.integration


def test_python_schedule_notifications_and_cli(owners, tmp_path):
    owner = owners[0]
    data, recipe = pipeline(owner, count=2)
    key = post(
        owner,
        "/api-keys",
        {
            "name": "P13 Python and CLI parity",
            "scopes": ["datasets:read", "runs:execute", "schedules:manage", "notifications:read"],
        },
    )
    try:
        with DataFoundry(api_key=key["secret"]) as api:
            body = schedule_body(data, recipe, delay=4)
            assert api.schedules.health()["status"] == "READY"
            assert api.schedules.preview(body)["estimate_micro"] == 2000
            record = api.schedules.create(
                ScheduleCreate.model_validate({**body, "approved_for_scheduled_execution": True}),
                idempotency_key="p13-sdk-" + data["id"],
            )
            assert api.schedules.retrieve(record["id"])["state"] == "ACTIVE"
            assert any(item["id"] == record["id"] for item in api.schedules.list()["items"])
            eventually(
                lambda: api.schedules.retrieve(record["id"]), lambda value: value["state"] == "COMPLETED"
            )
            occurrence = api.schedules.occurrences(record["id"])["items"][0]
            assert wait(owner, occurrence["run_id"])["status"] == "SUCCEEDED"
            notices = eventually(
                lambda: api.notifications.list()["items"],
                lambda values: any(item["target"] == f"/runs/{occurrence['run_id']}" for item in values),
            )
            notice = next(item for item in notices if item["target"] == f"/runs/{occurrence['run_id']}")
            assert api.notifications.read(notice["id"])["read_at"]
            assert api.notifications.read_all(api.notifications.summary()["as_of"])["marked_read"] >= 0
            # CLI uses the same scoped key and persisted schedule, with no embedded credentials.
            env = {**os.environ, "FOUNDRY_API_KEY": key["secret"]}
            for args in [
                ["schedules", "list"],
                ["schedules", "occurrences", record["id"]],
                ["notifications", "summary"],
                ["notifications", "list", "--unread"],
                ["notifications", "read", notice["id"]],
            ]:
                command = subprocess.run(
                    [".venv/bin/datafoundry", *args], env=env, capture_output=True, text=True, timeout=30
                )
                assert command.returncode == 0, command.stderr
                assert json.loads(command.stdout) is not None
            later = {**schedule_body(data, recipe, delay=120), "approved_for_scheduled_execution": True}
            path = tmp_path / "schedule.json"
            path.write_text(json.dumps(later))
            command = subprocess.run(
                [".venv/bin/datafoundry", "schedules", "create", str(path)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert command.returncode == 0, command.stderr
            created = json.loads(command.stdout)
            for action in ("pause", "resume", "cancel"):
                changed = api.schedules.control(
                    created["id"],
                    {
                        "action": action,
                        "expected_revision": created["revision"],
                        "approved_for_scheduled_execution": action == "resume",
                    },
                )
                created = changed
            assert created["state"] == "CANCELLED"
    finally:
        assert owner.delete(f"/v1/api-keys/{key['id']}").is_success


def test_typescript_schedule_control_occurrences_and_inbox(owners):
    owner = owners[0]
    data, recipe = pipeline(owner, count=2)
    key = post(
        owner,
        "/api-keys",
        {
            "name": "P13 TypeScript parity",
            "scopes": ["datasets:read", "runs:execute", "schedules:manage", "notifications:read"],
        },
    )
    try:
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
                ".local/p13-sdk-ts",
            ],
            check=True,
            capture_output=True,
        )
        Path(".local/p13-sdk-ts/package.json").write_text('{"type":"module"}')
        script = """
        import {DataFoundry} from './.local/p13-sdk-ts/index.js';
        const api=new DataFoundry({baseUrl:'http://localhost:8000',apiKey:process.env.FOUNDRY_API_KEY});
        const body=JSON.parse(process.env.FOUNDRY_SCHEDULE_BODY);
        if((await api.schedules.health()).status!=='READY') throw Error('Scheduler unavailable');
        if((await api.schedules.preview(body)).estimate_micro!==2000) throw Error('Wrong estimate');
        let row=await api.schedules.create({...body,approved_for_scheduled_execution:true});
        if(!(await api.schedules.list({limit:100})).items.some(item=>item.id===row.id)) throw Error('Not listed');
        if((await api.schedules.retrieve(row.id)).state!=='ACTIVE') throw Error('Not active');
        for(const action of ['pause','resume','cancel']) row=await api.schedules.control(row.id,{action,expected_revision:row.revision,approved_for_scheduled_execution:action==='resume'});
        if(row.state!=='CANCELLED') throw Error('Not cancelled');
        if((await api.schedules.occurrences(row.id)).items.length!==0) throw Error('Unexpected launch');
        const all=await api.notifications.list({limit:1});
        if(all.items[0]) await api.notifications.read(all.items[0].id);
        const summary=await api.notifications.summary();
        await api.notifications.readAll(summary.as_of);
        console.log(JSON.stringify({schedule_id:row.id,state:row.state,inbox:'PASS'}));
        """
        command = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            env={
                **os.environ,
                "FOUNDRY_API_KEY": key["secret"],
                "FOUNDRY_SCHEDULE_BODY": json.dumps(schedule_body(data, recipe, delay=120)),
            },
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert command.returncode == 0, command.stderr
        assert json.loads(command.stdout)["inbox"] == "PASS"
    finally:
        assert owner.delete(f"/v1/api-keys/{key['id']}").is_success
