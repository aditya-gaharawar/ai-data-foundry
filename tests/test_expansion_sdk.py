import json
import os
import subprocess
import uuid
from pathlib import Path

import pytest
from conftest import post
from datafoundry import DataFoundry
from datafoundry.models import ProviderCreate

pytestmark = pytest.mark.integration


def test_python_domains_scim_etags_and_cli_are_real_http(owners):
    client = owners[0]
    key = post(
        client,
        "/api-keys",
        {
            "name": "Expansion Python parity",
            "scopes": [
                "datasets:read",
                "providers:manage",
                "compute:manage",
                "operations:manage",
                "governance:manage",
                "members:manage",
            ],
        },
    )
    try:
        with DataFoundry(api_key=key["secret"]) as api:
            catalog = api.providers.catalog()
            local = next(item for item in catalog["items"] if item["kind"] == "local.gguf")
            provider = api.providers.create(
                ProviderCreate(
                    name="Python permitted CPU model",
                    kind="local.gguf",
                    model_ref=local["model_ref"],
                    permitted_training_use=True,
                    consent_to_processing=True,
                    terms_version="Apache-2.0",
                    rights_evidence="Pinned Apache-2.0 local synthetic SDK proof",
                )
            )
            assert provider["state"] == "READY"
            assert api.providers.retrieve(provider["id"])["id"] == provider["id"]
            assert api.simulations.capabilities()["items"][0]["state"] == "READY"
            pool = api.compute.register_pool({"name": "Python outbound CPU"})
            agent = api.compute.enroll({"pool_id": pool["id"], "name": "Python scoped identity"})
            assert agent["agent_token"].startswith("foundry_agent_")
            assert api.compute.revoke(agent["id"])["revoked"]
            assert api.governance.policy()["sha256"]
            token = api.governance.create_provisioning_token({"name": "Python SCIM"})
            with DataFoundry(api_key=token["provisioning_token"]) as provisioner:
                assert provisioner.scim.configuration()["etag"]["supported"]
                email = "sdk-scim-" + uuid.uuid4().hex + "@foundry.local"
                user = provisioner.scim.create({"userName": email})
                changed = provisioner.scim.patch(
                    user["id"],
                    [{"op": "replace", "path": "active", "value": False}],
                    etag=user["meta"]["version"],
                )
                assert changed["active"] is False
                provisioner.scim.delete(user["id"], etag=changed["meta"]["version"])
            api.governance.revoke_provisioning_token(token["id"])
            assert api.operations.reconcile()["report"]["status"] == "PASS"
            assert api.operations.status()["environment"] == "local"
            assert api.operations.sign_readiness()["report"]["production_release"] == "BLOCKED_EXTERNAL"
            api.providers.revoke(provider["id"])
            command = subprocess.run(
                [".venv/bin/datafoundry", "api", "GET", "/v1/simulations/capabilities"],
                env={**os.environ, "FOUNDRY_API_KEY": key["secret"]},
                capture_output=True,
                text=True,
            )
            assert command.returncode == 0, command.stderr
            assert json.loads(command.stdout)["items"][0]["state"] == "READY"
    finally:
        client.delete(f"/v1/api-keys/{key['id']}")


def test_typescript_new_domains_and_provisioning_lifecycle(owners):
    owner = owners[0]
    key = post(
        owner,
        "/api-keys",
        {
            "name": "Expansion TypeScript parity",
            "scopes": [
                "datasets:read",
                "providers:manage",
                "compute:manage",
                "operations:manage",
                "governance:manage",
                "members:manage",
            ],
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
                ".local/expansion-sdk-ts",
            ],
            check=True,
            capture_output=True,
        )
        Path(".local/expansion-sdk-ts/package.json").write_text('{"type":"module"}')
        script = """
        import {DataFoundry} from './.local/expansion-sdk-ts/index.js';
        const api=new DataFoundry({baseUrl:'http://localhost:8000',apiKey:process.env.FOUNDRY_API_KEY});
        const local=(await api.providers.catalog()).items.find(item=>item.kind==='local.gguf');
        const provider=await api.providers.create({name:'TS permitted CPU model',kind:'local.gguf',model_ref:local.model_ref,permitted_training_use:true,consent_to_processing:true,terms_version:'Apache-2.0',rights_evidence:'Pinned local SDK permission evidence'});
        if(provider.state!=='READY')throw Error('Provider not ready');
        const pool=await api.compute.registerPool({name:'TypeScript local CPU'});
        const agent=await api.compute.enroll({pool_id:pool.id,name:'TypeScript scoped identity'});
        await api.compute.revoke(agent.id);
        if((await api.simulations.capabilities()).items[0].state!=='READY')throw Error('Blender missing');
        const token=await api.governance.createProvisioningToken({name:'TypeScript SCIM'});
        const scim=new DataFoundry({baseUrl:'http://localhost:8000',apiKey:token.provisioning_token});
        const user=await scim.scim.create({userName:'ts-scim-'+crypto.randomUUID()+'@foundry.local'});
        const changed=await scim.scim.patch(user.id,{Operations:[{op:'replace',path:'active',value:false}]},user.meta.version);
        await scim.scim.delete(user.id,changed.meta.version);
        await api.governance.revokeProvisioningToken(token.id);
        const ledger=await api.operations.reconcile();
        if(ledger.report.status!=='PASS')throw Error('Ledger mismatch');
        await api.providers.revoke(provider.id);
        console.log(JSON.stringify({provider_state:provider.state,agent_revoked:true,scim_lifecycle:'PASS',ledger_status:ledger.report.status}));
        """
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            env={**os.environ, "FOUNDRY_API_KEY": key["secret"]},
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["scim_lifecycle"] == "PASS"
    finally:
        owner.delete(f"/v1/api-keys/{key['id']}")
