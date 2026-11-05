def enrich(schema):
    schema["servers"] = [{"url": "http://localhost:8000", "description": "Local development only"}]
    schema["components"]["securitySchemes"] = {
        "bearerAuth": {"type": "http", "scheme": "bearer", "description": "Scoped foundry_ API key"},
        "sessionAuth": {"type": "apiKey", "in": "cookie", "name": "foundry_session"},
        "agentAuth": {
            "type": "http",
            "scheme": "bearer",
            "description": "Enrolled foundry_agent_ identity, scoped to one tenant and compute pool",
        },
        "scimAuth": {
            "type": "http",
            "scheme": "bearer",
            "description": "Domain-restricted foundry_scim_ provisioning identity",
        },
    }
    creates = {
        "create_dataset",
        "create_recipe",
        "revise_recipe",
        "start_upload",
        "complete_upload",
        "submit_run",
        "retry_run",
        "create_key",
        "create_webhook",
        "create_export",
        "create_project",
        "create_member",
        "create_quality_profile",
        "create_curation",
        "freeze_curation",
        "assign_annotation",
        "review_annotation",
        "adjudicate_annotation",
        "reopen_annotation",
        "create_provider",
        "revoke_provider",
        "create_compute_pool",
        "enroll_agent",
        "revoke_agent",
        "create_compute_job",
        "cancel_compute_job",
        "reindex_version",
        "create_benchmark",
        "import_evaluation",
        "create_feedback",
        "decide_feedback",
        "create_governance_policy",
        "govern_dataset",
        "decide_approval",
        "request_erasure",
        "approve_erasure",
        "preview_erasure",
        "execute_erasure",
        "retry_erasure",
        "create_scim_token",
        "revoke_scim_token",
        "create_reconciliation",
        "scan_incidents",
        "acknowledge_incident",
        "import_proof",
        "create_readiness",
    }
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if method not in ["get", "post", "put", "patch", "delete"]:
                continue
            if path.startswith("/v1/compute/agent/"):
                operation["security"] = [{"agentAuth": []}]
                if "/jobs/" in path:
                    operation.setdefault("parameters", []).append(
                        {
                            "name": "X-Lease-Token",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Secret fencing token from the current unexpired claim.",
                        }
                    )
                continue
            if path.startswith("/v1/scim/v2/"):
                operation["security"] = [{"scimAuth": []}]
                for code, response in operation.get("responses", {}).items():
                    if code.isdigit() and int(code) >= 400:
                        response["description"] = "SCIM protocol error with request correlation"
                        response["content"] = {
                            "application/scim+json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["schemas", "status", "detail"],
                                    "properties": {
                                        "schemas": {"type": "array", "items": {"type": "string"}},
                                        "status": {"type": "string"},
                                        "detail": {"type": "string"},
                                        "code": {"type": "string"},
                                        "request_id": {"type": "string"},
                                    },
                                }
                            }
                        }
                if method in {"put", "patch", "delete"}:
                    operation.setdefault("parameters", []).append(
                        {
                            "name": "If-Match",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Current weak resource ETag from meta.version or response ETag.",
                        }
                    )
                continue
            if "/auth/" not in path and "/health/" not in path:
                operation["security"] = [{"bearerAuth": []}, {"sessionAuth": []}]
            operation.setdefault("parameters", []).append(
                {
                    "name": "X-Organization-Id",
                    "in": "header",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Must be an organization of the authenticated principal.",
                }
            )
            if method == "post" and operation["operationId"].split("_v1_")[0] in creates:
                operation["parameters"].append(
                    {
                        "name": "Idempotency-Key",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string", "maxLength": 128},
                    }
                )
    return schema
