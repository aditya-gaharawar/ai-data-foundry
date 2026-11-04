import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import definition, post
from datafoundry import DataFoundry
from test_curation import CARD

pytestmark = pytest.mark.integration


def test_python_sdk_and_cli_review_to_publication(owners, tmp_path):
    owner = owners[0]
    key = post(
        owner,
        "/api-keys",
        {
            "name": "P06 Python SDK",
            "scopes": [
                "datasets:read",
                "datasets:write",
                "runs:execute",
                "annotations:manage",
                "annotations:review",
            ],
        },
    )
    project = owner.get("/v1/projects").json()["items"][0]["id"]
    try:
        with DataFoundry(api_key=key["secret"]) as api:
            data = api.datasets.create(
                name="SDK reviewed text",
                project_id=project,
                policy={"origin": "synthetic-test", "allowed_training_use": True},
            )
            source = tmp_path / "source.jsonl"
            source.write_text('{"prompt":"Choose a prime number","response":"17"}\n')
            upload = api.datasets.upload(data.id, source)
            profile = api.quality_profiles.create(name="SDK text profile", modality="text")
            curation = api.curations.create(
                dataset_id=data.id,
                profile_id=profile.id,
                name="SDK explicit single-review fixture",
                categories=["object"],
                required_reviews=1,
                upload_ids=[upload["id"]],
                data_card=CARD,
            )
            task = next(api.annotations.list(curation_id=curation.id))
            task = api.annotations.assign(
                task.id, expected_revision=task.revision, user_id=api.request("GET", "/v1/me")["id"]
            )
            task = api.annotations.review(
                task.id,
                expected_revision=task.revision,
                decision="accept",
                note="Explicit SDK fixture review",
                annotation={"kind": "category", "label": "object"},
            )
            assert task.status == "ACCEPTED"
            current = api.curations.get(curation.id)
            current = api.curations.update_card(
                curation.id,
                expected_revision=current.revision,
                data_card={**CARD, "purpose": "SDK data card correction persisted"},
            )
            frozen = api.curations.freeze(
                curation.id, expected_revision=current.revision, approved_for_publication=True
            )
            assert frozen.state == "FROZEN"
            recipe = definition(count=1)
            recipe["nodes"][0] = {"id": "source", "type": "curate", "config": {"curation_id": curation.id}}
            saved = api.recipes.create(project_id=project, definition=recipe)
            result = api.runs.wait(
                api.runs.create(dataset_id=data.id, recipe_revision_id=saved.revision.id).id
            )
            assert result.status == "SUCCEEDED", result.error
            downloaded = api.datasets.download(result.version.id, tmp_path / "reviewed.jsonl")
            assert json.loads(downloaded.read_text())["annotation"]["label"] == "object"
            assert result.version.manifest["data_card"]["purpose"] == "SDK data card correction persisted"
            cli = subprocess.run(
                [str(Path(sys.executable).parent / "datafoundry"), "annotations", "get", task.id],
                env={**os.environ, "FOUNDRY_API_KEY": key["secret"]},
                capture_output=True,
                text=True,
            )
            assert cli.returncode == 0, cli.stderr
            assert json.loads(cli.stdout)["annotation"]["label"] == "object"
    finally:
        owner.delete(f"/v1/api-keys/{key['id']}")


def test_typescript_sdk_upload_review_publish_and_coco_download(owners):
    owner = owners[0]
    key = post(
        owner,
        "/api-keys",
        {
            "name": "P06 TypeScript SDK",
            "scopes": [
                "datasets:read",
                "datasets:write",
                "runs:execute",
                "annotations:manage",
                "annotations:review",
            ],
        },
    )
    project = owner.get("/v1/projects").json()["items"][0]["id"]
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
                ".local/p06-sdk-ts",
            ],
            check=True,
            capture_output=True,
        )
        Path(".local/p06-sdk-ts/package.json").write_text('{"type":"module"}')
        script = """
        import {DataFoundry} from './.local/p06-sdk-ts/index.js';
        import {readFileSync} from 'node:fs';
        const api=new DataFoundry({baseUrl:'http://localhost:8000',apiKey:process.env.FOUNDRY_API_KEY});
        const project=process.env.FOUNDRY_PROJECT;
        const data=await api.datasets.create({name:'SDK reviewed image',project_id:project,modality:'image',policy:{allowed_training_use:true,origin:'synthetic-test'}});
        const upload=await api.datasets.upload(data.id,'shape.png',new Uint8Array(readFileSync('tests/fixtures/p06-shape.png')));
        const profile=await api.qualityProfiles.create({name:'SDK image profile',modality:'image'});
        const curation=await api.curations.create({dataset_id:data.id,profile_id:profile.id,name:'SDK explicit single-review image fixture',categories:['object'],required_reviews:1,upload_ids:[upload.id],data_card:JSON.parse(process.env.FOUNDRY_CARD)});
        let task=(await api.annotations.list(curation.id)).items[0];
        task=await api.annotations.review(task.id,{expected_revision:task.revision,decision:'accept',note:'Explicit SDK fixture review',annotation:{kind:'boxes',boxes:[{label:'object',x:8,y:6,width:32,height:24}]}});
        const current=await api.curations.get(curation.id);
        await api.curations.freeze(curation.id,{expected_revision:current.revision,approved_for_publication:true});
        const definition=JSON.parse(process.env.FOUNDRY_RECIPE);
        definition.nodes[0]={id:'source',type:'curate',config:{curation_id:curation.id}};
        const recipe=await api.recipes.create({project_id:project,definition});
        const result=await api.runs.wait((await api.runs.create({dataset_id:data.id,recipe_revision_id:recipe.revision.id,max_budget_usd:1})).id);
        if(result.status!=='SUCCEEDED')throw Error(result.error);
        const bytes=await api.datasets.download(result.version.id,'coco');
        if(bytes[0]!==0x50||bytes[1]!==0x4b)throw Error('Expected a verified ZIP artifact');
        console.log(JSON.stringify({status:result.status,format:'coco',bytes:bytes.length,task_status:task.status}));
        """
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            env={
                **os.environ,
                "FOUNDRY_API_KEY": key["secret"],
                "FOUNDRY_PROJECT": project,
                "FOUNDRY_CARD": json.dumps(CARD),
                "FOUNDRY_RECIPE": json.dumps(definition(count=1)),
            },
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["task_status"] == "ACCEPTED"
    finally:
        owner.delete(f"/v1/api-keys/{key['id']}")
