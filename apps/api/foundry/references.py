"""Serialize shared artifact attachment and erasure within each organization."""

import hashlib
from contextlib import contextmanager

from sqlalchemy import text

from .db import Session


def reference_lock(db, organization_id):
    key = int.from_bytes(
        hashlib.sha256((organization_id + ":artifact-references").encode()).digest()[:8], signed=True
    )
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


@contextmanager
def reference_guard(organization_id):
    with Session.begin() as db:
        reference_lock(db, organization_id)
        yield db
