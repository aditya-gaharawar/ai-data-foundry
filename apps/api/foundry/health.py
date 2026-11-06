"""Independent, bounded dependency checks without borrowing request sessions."""

import asyncio
import logging
from datetime import timedelta

from botocore.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from temporalio.api.workflowservice.v1 import GetSystemInfoRequest
from temporalio.client import Client

from .config import settings
from .storage import client

logger = logging.getLogger("foundry.api")
PROBE_TIMEOUT = 4.0


def _database():
    # A separate connection keeps a saturated application pool from hiding
    # dependency health, and native timeouts bound work after cancellation.
    engine = create_engine(
        settings().database_url,
        poolclass=NullPool,
        connect_args={"connect_timeout": 2, "options": "-c statement_timeout=1000"},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def _object_storage():
    config = Config(connect_timeout=1, read_timeout=1, retries={"total_max_attempts": 1})
    storage = client(config=config)
    try:
        storage.head_bucket(Bucket=settings().s3_bucket)
    finally:
        storage.close()


async def check_database():
    await asyncio.to_thread(_database)


async def check_object_storage():
    await asyncio.to_thread(_object_storage)


async def check_workflow():
    connection = await Client.connect(settings().temporal_address)
    await connection.workflow_service.get_system_info(GetSystemInfoRequest(), timeout=timedelta(seconds=2))


async def dependencies() -> dict[str, bool]:
    async def probe(name, check):
        try:
            await asyncio.wait_for(check(), timeout=PROBE_TIMEOUT)
            return True
        except Exception:
            # Do not expose service URLs or credential-bearing exception text.
            logger.warning("readiness_dependency_unavailable dependency=%s", name)
            return False

    checks = {
        "database": check_database,
        "object_storage": check_object_storage,
        "workflow": check_workflow,
    }
    results = await asyncio.gather(*(probe(name, check) for name, check in checks.items()))
    return dict(zip(checks, results, strict=True))
