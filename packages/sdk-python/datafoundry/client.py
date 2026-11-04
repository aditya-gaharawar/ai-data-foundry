import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx

from .models import DatasetOut, RecipeOut, RunOut


class FoundryError(Exception):
    def __init__(self, status, body):
        self.status, self.code, self.request_id = status, body.get("code"), body.get("request_id")
        super().__init__(body.get("detail", "Request failed."))


def verify_webhook(secret: str, raw: bytes, timestamp: str, signature: str, tolerance: int = 300) -> dict:
    if abs(time.time() - int(timestamp)) > tolerance:
        raise ValueError("Webhook timestamp is outside the replay window.")
    expected = "v1=" + hmac.new(secret.encode(), timestamp.encode() + b"." + raw, "sha256").hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ValueError("Webhook signature mismatch.")
    return json.loads(raw)


class DataFoundry:
    def __init__(
        self, *, base_url: str = "http://localhost:8000", api_key: str, organization_id: str | None = None
    ):
        headers = {"Authorization": "Bearer " + api_key}
        if organization_id:
            headers["X-Organization-Id"] = organization_id
        self.http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=30,
            follow_redirects=False,
            trust_env=False,
        )
        self.datasets, self.recipes, self.runs = Datasets(self), Recipes(self), Runs(self)

    def request(self, method, path, body=None, *, idempotency_key=None):
        headers = {"Idempotency-Key": idempotency_key or uuid.uuid4().hex} if method == "POST" else {}
        # Only safe reads are retried. Mutations retain caller-controlled idempotency.
        for attempt in range(3 if method == "GET" else 1):
            response = self.http.request(method, path, json=body, headers=headers)
            if response.status_code < 500 or attempt == 2 or method != "GET":
                break
            time.sleep(0.2 * 2**attempt)
        if response.is_error:
            raise FoundryError(response.status_code, response.json())
        return response.json() if response.content else None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.http.close()


class Datasets:
    def __init__(self, client):
        self.client = client

    def create(
        self, *, name: str, project_id: str, policy: dict, idempotency_key: str | None = None, **kwargs
    ) -> DatasetOut:
        return DatasetOut.model_validate(
            self.client.request(
                "POST",
                "/v1/datasets",
                {"name": name, "project_id": project_id, "policy": policy, **kwargs},
                idempotency_key=idempotency_key,
            )
        )

    def get(self, identifier: str) -> DatasetOut:
        return DatasetOut.model_validate(self.client.request("GET", f"/v1/datasets/{identifier}"))

    def list(self) -> Iterator[DatasetOut]:
        path = "/v1/datasets?limit=100"
        while path:
            result = self.client.request("GET", path)
            yield from (DatasetOut.model_validate(item) for item in result["items"])
            path = (
                "/v1/datasets?limit=100&cursor=" + result["next_cursor"]
                if result.get("next_cursor")
                else None
            )

    def upload(self, dataset_id: str, path: str | Path):
        file = Path(path)
        data = file.read_bytes()
        upload = self.client.request(
            "POST",
            "/v1/uploads",
            {
                "dataset_id": dataset_id,
                "filename": file.name,
                "content_type": "application/x-ndjson",
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            },
        )
        parts = []
        # S3 URLs are used without forwarding the control-plane Authorization header.
        with httpx.Client(timeout=60, trust_env=False) as storage:
            for index, url in enumerate(upload["upload_urls"]):
                result = storage.put(
                    url, content=data[index * upload["part_size"] : (index + 1) * upload["part_size"]]
                )
                result.raise_for_status()
                parts.append({"part_number": index + 1, "etag": result.headers["etag"]})
        return self.client.request("POST", f"/v1/uploads/{upload['id']}/complete", {"parts": parts})

    def download(self, version_id: str, path: str | Path) -> Path:
        created = self.client.request("POST", "/v1/exports", {"version_id": version_id, "format": "jsonl"})
        ready = self.client.request("GET", f"/v1/exports/{created['id']}")
        output = Path(path)
        hasher = hashlib.sha256()
        with self.client.http.stream("GET", ready["download_url"]) as result:
            if result.is_error:
                result.read()
                raise FoundryError(result.status_code, result.json())
            with output.open("wb") as file:
                for chunk in result.iter_bytes():
                    hasher.update(chunk)
                    file.write(chunk)
            if hasher.hexdigest() != result.headers["X-Content-SHA256"]:
                output.unlink(missing_ok=True)
                raise ValueError("Export checksum verification failed.")
        return output


class Recipes:
    def __init__(self, client):
        self.client = client

    def create(self, *, project_id: str, definition: dict, idempotency_key=None) -> RecipeOut:
        return RecipeOut.model_validate(
            self.client.request(
                "POST",
                "/v1/recipes",
                {"project_id": project_id, "definition": definition},
                idempotency_key=idempotency_key,
            )
        )

    def validate(self, definition: dict):
        return self.client.request("POST", "/v1/recipes/validate", definition)


class Runs:
    def __init__(self, client):
        self.client = client

    def create(
        self, *, dataset_id: str, recipe_revision_id: str, max_budget_usd=1, idempotency_key=None
    ) -> RunOut:
        return RunOut.model_validate(
            self.client.request(
                "POST",
                "/v1/runs",
                {
                    "dataset_id": dataset_id,
                    "recipe_revision_id": recipe_revision_id,
                    "max_budget_usd": max_budget_usd,
                },
                idempotency_key=idempotency_key,
            )
        )

    def get(self, identifier: str) -> RunOut:
        return RunOut.model_validate(self.client.request("GET", f"/v1/runs/{identifier}"))

    def wait(self, identifier: str, timeout=120, poll_interval=0.5) -> RunOut:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            run = self.get(identifier)
            if run.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                return run
            time.sleep(poll_interval)
        raise TimeoutError(f"Run {identifier} did not finish within {timeout}s.")

    def cancel(self, identifier: str):
        return self.client.request("POST", f"/v1/runs/{identifier}/cancel")
