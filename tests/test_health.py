import asyncio
import socket

import httpx
import pytest
from foundry import health, storage
from foundry.api import app


@pytest.mark.parametrize("failed", [None, "database", "object_storage", "workflow"])
def test_readiness_reports_each_dependency_even_when_another_fails(monkeypatch, failed):
    checked = set()

    def probe(name):
        async def check():
            checked.add(name)
            if name == failed:
                raise OSError("test-only dependency failure")

        return check

    for name in ["database", "object_storage", "workflow"]:
        monkeypatch.setattr(health, f"check_{name}", probe(name))

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as api:
            response = await api.get("/v1/health/ready")
        assert response.status_code == (503 if failed else 200)
        assert response.json() == {
            "status": "degraded" if failed else "ready",
            "dependencies": {name: name != failed for name in checked},
        }
        assert response.headers["cache-control"] == "no-store"
        assert "test-only" not in response.text

    asyncio.run(exercise())
    assert checked == {"database", "object_storage", "workflow"}


def test_readiness_timeout_cancels_probe_and_keeps_liveness_responsive(monkeypatch):
    async def exercise():
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def stalled():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def healthy():
            return None

        monkeypatch.setattr(health, "PROBE_TIMEOUT", 0.1)
        monkeypatch.setattr(health, "check_database", stalled)
        monkeypatch.setattr(health, "check_object_storage", healthy)
        monkeypatch.setattr(health, "check_workflow", healthy)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as api:
            pending = asyncio.create_task(api.get("/v1/health/ready"))
            await asyncio.wait_for(started.wait(), timeout=1)
            live = await asyncio.wait_for(api.get("/v1/health/live"), timeout=1)
            assert live.status_code == 200
            response = await asyncio.wait_for(pending, timeout=1)
        assert cancelled.is_set()
        assert response.status_code == 503
        assert response.json()["dependencies"] == {
            "database": False,
            "object_storage": True,
            "workflow": True,
        }

    asyncio.run(exercise())


@pytest.mark.integration
def test_live_readiness_probes_real_services():
    assert asyncio.run(health.dependencies()) == {
        "database": True,
        "object_storage": True,
        "workflow": True,
    }


@pytest.mark.integration
def test_unreachable_storage_does_not_hide_healthy_database_and_workflow(monkeypatch):
    # Reserve an unused local port without listening. Only this probe's S3
    # endpoint changes; the actual services continue serving other tests.
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        config = storage.settings().model_copy(
            update={"s3_endpoint": f"http://127.0.0.1:{unavailable.getsockname()[1]}"}
        )
        monkeypatch.setattr(storage, "settings", lambda: config)
        assert asyncio.run(health.dependencies()) == {
            "database": True,
            "object_storage": False,
            "workflow": True,
        }
