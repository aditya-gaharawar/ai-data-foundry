"""Real HTTP helpers for P07–P12. No automatic generation from feedback."""

from urllib.parse import urlencode


class Domain:
    def __init__(self, client):
        self.client = client

    def get(self, path, **query):
        return self.client.request("GET", "/v1" + path + ("?" + urlencode(query) if query else ""))

    def post(self, path, body=None, *, idempotency_key=None):
        if hasattr(body, "model_dump"):
            body = body.model_dump(mode="json", by_alias=True, exclude_none=True)
        return self.client.request("POST", "/v1" + path, body or {}, idempotency_key=idempotency_key)


class Providers(Domain):
    def catalog(self):
        return self.get("/providers/catalog")

    def list(self, **page):
        return self.get("/providers", **page)

    def create(self, body, **options):
        return self.post("/providers", body, **options)

    def retrieve(self, identifier):
        return self.get(f"/providers/{identifier}")

    def revoke(self, identifier, **options):
        return self.post(f"/providers/{identifier}/revoke", **options)


class Compute(Domain):
    def pools(self, **page):
        return self.get("/compute/registered-pools", **page)

    def register_pool(self, body, **options):
        return self.post("/compute/registered-pools", body, **options)

    def agents(self, **page):
        return self.get("/compute/agents", **page)

    def enroll(self, body, **options):
        return self.post("/compute/agents", body, **options)

    def revoke(self, identifier, **options):
        return self.post(f"/compute/agents/{identifier}/revoke", **options)

    def placement(self, body):
        return self.post("/compute/placement", body)

    def submit(self, body, **options):
        return self.post("/compute/jobs", body, **options)

    def jobs(self, **page):
        return self.get("/compute/jobs", **page)

    def job(self, identifier):
        return self.get(f"/compute/jobs/{identifier}")

    def cancel(self, identifier, **options):
        return self.post(f"/compute/jobs/{identifier}/cancel", **options)


class Simulations(Domain):
    def capabilities(self):
        return self.get("/simulations/capabilities")


class Evaluations(Domain):
    def distribution(self, version_id):
        return self.get(f"/versions/{version_id}/distribution")

    def compare_versions(self, left_version_id, right_version_id):
        return self.get(
            "/versions/compare", left_version_id=left_version_id, right_version_id=right_version_id
        )

    def search(self, query, **options):
        return self.get("/search/samples", q=query, **options)

    def benchmarks(self):
        return self.get("/benchmarks")

    def create_benchmark(self, body, **options):
        return self.post("/benchmarks", body, **options)

    def import_results(self, body, **options):
        return self.post("/evaluations", body, **options)

    def list(self, **page):
        return self.get("/evaluations", **page)

    def retrieve(self, identifier):
        return self.get(f"/evaluations/{identifier}")

    def compare(self, baseline_id, candidate_id):
        return self.get("/evaluations/compare", baseline_id=baseline_id, candidate_id=candidate_id)

    def feedback(self):
        return self.get("/feedback")

    def propose(self, body, **options):
        return self.post("/feedback", body, **options)

    def decide(self, identifier, body, **options):
        return self.post(f"/feedback/{identifier}/decision", body, **options)


class Governance(Domain):
    def policy(self):
        return self.get("/governance/policy")

    def policies(self):
        return self.get("/governance/policies")

    def set_policy(self, definition, **options):
        return self.post("/governance/policies", {"definition": definition}, **options)

    def protect(self, dataset_id, body, **options):
        return self.post(f"/governance/datasets/{dataset_id}", body, **options)

    def approvals(self):
        return self.get("/governance/approvals")

    def decide_approval(self, identifier, body, **options):
        return self.post(f"/governance/approvals/{identifier}/decision", body, **options)

    def retention(self):
        return self.get("/governance/retention-plan")

    def request_erasure(self, body, **options):
        return self.post("/governance/erasures", body, **options)

    def erasures(self):
        return self.get("/governance/erasures")

    def erasure(self, identifier):
        return self.get(f"/governance/erasures/{identifier}")

    def decide_erasure(self, identifier, body, **options):
        return self.post(f"/governance/erasures/{identifier}/decision", body, **options)

    def preview_erasure(self, identifier, **options):
        return self.post(f"/governance/erasures/{identifier}/preview", **options)

    def execute_erasure(self, identifier, body, **options):
        return self.post(f"/governance/erasures/{identifier}/execute", body, **options)

    def retry_erasure(self, identifier, **options):
        return self.post(f"/governance/erasures/{identifier}/retry", **options)

    def provisioning_tokens(self):
        return self.get("/governance/scim-tokens")

    def create_provisioning_token(self, body, **options):
        return self.post("/governance/scim-tokens", body, **options)

    def revoke_provisioning_token(self, identifier, **options):
        return self.post(f"/governance/scim-tokens/{identifier}/revoke", **options)


class Operations(Domain):
    def status(self):
        return self.get("/operations/status")

    def reconcile(self, **options):
        return self.post("/operations/reconciliations", **options)

    def reconciliations(self):
        return self.get("/operations/reconciliations")

    def incidents(self):
        return self.get("/operations/incidents")

    def scan(self, **options):
        return self.post("/operations/incidents/scan", **options)

    def acknowledge(self, identifier, **options):
        return self.post(f"/operations/incidents/{identifier}/acknowledge", **options)

    def proofs(self):
        return self.get("/operations/proofs")

    def import_proof(self, body, **options):
        return self.post("/operations/proofs", body, **options)

    def readiness(self):
        return self.get("/operations/readiness")

    def sign_readiness(self, **options):
        return self.post("/operations/readiness", **options)


class Provisioning(Domain):
    """Use a separate DataFoundry(api_key=provisioning_token) instance."""

    def configuration(self):
        return self.get("/scim/v2/ServiceProviderConfig")

    def users(self, **query):
        return self.get("/scim/v2/Users", **query)

    def user(self, identifier):
        return self.get(f"/scim/v2/Users/{identifier}")

    def create(self, body):
        return self.post("/scim/v2/Users", body)

    def replace(self, identifier, body, *, etag):
        return self.client.request("PUT", f"/v1/scim/v2/Users/{identifier}", body, headers={"If-Match": etag})

    def patch(self, identifier, operations, *, etag):
        return self.client.request(
            "PATCH",
            f"/v1/scim/v2/Users/{identifier}",
            {"schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"], "Operations": operations},
            headers={"If-Match": etag},
        )

    def delete(self, identifier, *, etag):
        return self.client.request("DELETE", f"/v1/scim/v2/Users/{identifier}", headers={"If-Match": etag})
