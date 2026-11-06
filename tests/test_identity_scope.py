"""API keys must never widen into the owner's other organization memberships."""

import httpx
import pytest
from conftest import post
from foundry.db import Session
from foundry.models import Membership

pytestmark = pytest.mark.security


@pytest.mark.parametrize("route", ["/v1/organizations", "/v1/auth/session"])
def test_key_identity_is_limited_to_its_organization_and_scopes(owners, route):
    owner, other = owners
    user = owner.get("/v1/me").json()
    other_org = other.get("/v1/me").json()["organization_id"]
    identity = {"user_id": user["id"], "organization_id": other_org}
    with Session.begin() as db:
        assert db.get(Membership, identity) is None
        db.add(Membership(**identity, role="Owner"))
    key = None
    try:
        key = post(owner, "/api-keys", {"name": "Identity isolation regression", "scopes": ["datasets:read"]})
        with httpx.Client(
            base_url="http://localhost:8000",
            headers={"Authorization": "Bearer " + key["secret"]},
            trust_env=False,
        ) as client:
            result = client.get(route)
            assert result.status_code == 200
            data = result.json()
            organizations = data["items"] if route.endswith("organizations") else data["organizations"]
            assert [item["id"] for item in organizations] == [user["organization_id"]]
            if route.endswith("session"):
                assert organizations[0]["scopes"] == ["datasets:read"]
                assert data["csrf_token"] == ""
            assert client.get(route, headers={"X-Organization-Id": other_org}).status_code == 404
        # A real browser session still supports the owner's legitimate org switcher.
        browser = owner.get("/v1/auth/session").json()
        assert other_org in {item["id"] for item in browser["organizations"]}
    finally:
        if key:
            owner.delete("/v1/api-keys/" + key["id"])
        with Session.begin() as db:
            db.delete(db.get(Membership, identity))
