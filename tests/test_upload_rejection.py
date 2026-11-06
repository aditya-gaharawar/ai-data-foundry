import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from foundry import api, schemas
from foundry.config import settings
from foundry.errors import Problem


def test_oversized_completed_object_is_rejected_and_body_closed(monkeypatch):
    record = SimpleNamespace(status="UPLOADING", expected_bytes=1, object_key="test", multipart_id="test")
    stream = io.BytesIO(b"unread")
    storage = Mock()
    storage.complete_multipart_upload.return_value = {}
    storage.get_object.return_value = {"ContentLength": settings().max_upload_bytes + 1, "Body": stream}
    monkeypatch.setattr(api, "s3client", lambda: storage)
    monkeypatch.setattr(api, "replay", lambda *args: None)
    monkeypatch.setattr(api, "get", lambda *args: record)
    db = Mock()
    actor = Mock(organization_id="org_test")
    body = schemas.UploadComplete(parts=[{"part_number": 1, "etag": "etag"}])
    with pytest.raises(Problem) as error:
        api.complete_upload("upload_test", body, Mock(), actor, db)
    assert error.value.code == "UPLOAD_TOO_LARGE"
    assert record.status == "REJECTED"
    assert stream.closed
    db.commit.assert_called_once()
