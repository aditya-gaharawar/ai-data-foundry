"""Verify clean migrations, seeding, restart persistence and isolation in a disposable DB."""

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from foundry.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

database = "foundry_verify_" + secrets.token_hex(6)
base = make_url(settings().database_url)
admin = create_engine(base)
environment = {
    **os.environ,
    "DATABASE_URL": base.set(database=database).render_as_string(hide_password=False),
}
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
Path(".local/evidence").mkdir(parents=True, exist_ok=True)
log = Path(".local/fresh-api.log").open("w")
process = None


def start():
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "foundry.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        env=environment,
        stdout=log,
        stderr=log,
    )
    for _ in range(100):
        try:
            if (
                httpx.get(f"http://127.0.0.1:{port}/v1/health/ready", timeout=3, trust_env=False).status_code
                == 200
            ):
                return process
        except httpx.HTTPError:
            pass
        if process.poll() is not None:
            raise RuntimeError("Fresh API exited; see .local/fresh-api.log")
        time.sleep(0.1)
    process.terminate()
    process.wait(timeout=10)
    raise RuntimeError("Fresh API readiness timed out.")


try:
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    for command in [
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        [sys.executable, "-m", "foundry.bootstrap"],
        [sys.executable, "-m", "alembic", "check"],
    ]:
        subprocess.run(command, env=environment, check=True, capture_output=True)
    process = start()
    with httpx.Client(
        base_url=f"http://127.0.0.1:{port}", headers={"Origin": "http://localhost:3000"}, trust_env=False
    ) as client:
        login = client.post(
            "/v1/auth/login", json={"email": "alex@foundry.local", "password": settings().dev_password}
        )
        login.raise_for_status()
        client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        project = client.get("/v1/projects").json()["items"][0]["id"]
        response = client.post(
            "/v1/datasets",
            headers={"Idempotency-Key": "fresh-database"},
            json={"project_id": project, "name": "Fresh database persistence proof"},
        )
        assert response.status_code == 201
        identifier = response.json()["id"]
        process.terminate()
        process.wait(timeout=15)
        process = start()
        assert client.get(f"/v1/datasets/{identifier}").json()["name"] == "Fresh database persistence proof"
        client.post(
            "/v1/auth/login", json={"email": "blair@foundry.local", "password": settings().dev_password}
        ).raise_for_status()
        assert client.get(f"/v1/datasets/{identifier}").status_code == 404
    result = {
        "clean_migrations": "PASS",
        "alembic_drift": "PASS",
        "seed": "PASS",
        "health": "PASS",
        "restart_persistence": "PASS",
        "cross_tenant": "PASS",
    }
    Path(".local/evidence/fresh-database.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        "Clean database: migrations, drift check, seed, health, API restart persistence, and tenant isolation passed."
    )
finally:
    if process and process.poll() is None:
        process.terminate()
        process.wait(timeout=15)
    log.close()
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{database}"'))
    admin.dispose()
