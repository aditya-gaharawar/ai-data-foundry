def enrich(schema):
    schema["servers"] = [{"url": "http://localhost:8000", "description": "Local development only"}]
    schema["components"]["securitySchemes"] = {
        "bearerAuth": {"type": "http", "scheme": "bearer", "description": "Scoped foundry_ API key"},
        "sessionAuth": {"type": "apiKey", "in": "cookie", "name": "foundry_session"},
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
    }
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if method not in ["get", "post", "patch", "delete"]:
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
