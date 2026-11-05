"""Prepared external protocols; execution stays blocked without operator setup.

Contract tests exercise these codecs against in-memory responses. They are not
evidence of a live provider, Slurm queue, Kubernetes cluster, or Isaac episode.
"""

import base64
import binascii
import json
import re
import shutil
import subprocess
from urllib.parse import urlsplit

import httpx
from jsonschema import Draft202012Validator

from .config import settings
from .errors import Problem


class StructuredHTTPAdapter:
    """Bounded OpenAI-compatible structured-text and base64-image codecs."""

    @staticmethod
    def text_request(model, instructions, schema, max_tokens=256):
        return {
            "model": model,
            "messages": [{"role": "user", "content": instructions}],
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "foundry_sample", "strict": True, "schema": schema},
            },
        }

    @staticmethod
    def parse_text(response, schema):
        try:
            content = response["choices"][0]["message"]["content"]
            if not isinstance(content, str) or len(content.encode()) > 65536:
                raise ValueError
            payload = json.loads(content)
            Draft202012Validator(schema).validate(payload)
            usage = response["usage"]
            tokens = {name: usage[name] for name in ("prompt_tokens", "completion_tokens", "total_tokens")}
            if (
                any(type(value) is not int or value < 0 for value in tokens.values())
                or tokens["total_tokens"] != tokens["prompt_tokens"] + tokens["completion_tokens"]
            ):
                raise ValueError
            return {
                "payload": payload,
                "usage": tokens,
                "provider_request_id": str(response.get("id", ""))[:200],
            }
        except Exception:
            # A normalized message must never include provider responses/secrets.
            raise Problem(
                422,
                "PROVIDER_OUTPUT_INVALID",
                "The provider output or usage record did not match the configured contract.",
            ) from None

    @staticmethod
    def image_request(model, instructions):
        return {"model": model, "prompt": instructions, "n": 1, "response_format": "b64_json"}

    @staticmethod
    def parse_image(response):
        try:
            encoded = response["data"][0]["b64_json"]
            if not isinstance(encoded, str) or len(encoded) > 7 * 1024 * 1024:
                raise ValueError
            raw = base64.b64decode(encoded, validate=True)
            if not raw or len(raw) > 5 * 1024 * 1024:
                raise ValueError
            # Decode/normalize through media.prepare_image before attaching it.
            return raw
        except (KeyError, IndexError, TypeError, ValueError, binascii.Error):
            raise Problem(
                422,
                "PROVIDER_OUTPUT_INVALID",
                "A bounded base64 image is required; remote image URLs are not fetched.",
            ) from None

    @staticmethod
    def send(endpoint, api_secret, body, *, transport=None):
        config = settings()
        parsed = urlsplit(endpoint)
        allowlist = [item.strip() for item in config.provider_http_allowlist.split(",") if item.strip()]
        if not config.allow_external_provider_calls or endpoint not in allowlist:
            raise Problem(
                409,
                "BLOCKED_EXTERNAL",
                "This endpoint has no explicit operator authorization and reviewed pricing; no call was sent.",
            )
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise Problem(
                422,
                "INVALID_PROVIDER_ENDPOINT",
                "Operator-approved HTTPS endpoints must not contain credentials, query strings, or fragments.",
            )
        # Only exact operator-managed endpoints; never follow response redirects.
        with httpx.Client(timeout=30, follow_redirects=False, transport=transport) as http:
            with http.stream(
                "POST", endpoint, headers={"Authorization": "Bearer " + api_secret}, json=body
            ) as result:
                if not result.is_success:
                    raise Problem(
                        502,
                        "PROVIDER_HTTP_ERROR",
                        f"Provider returned HTTP {result.status_code}; inspect the operator's redacted request record.",
                    )
                raw = bytearray()
                for chunk in result.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 8 * 1024 * 1024:
                        raise Problem(
                            422,
                            "PROVIDER_OUTPUT_TOO_LARGE",
                            "The provider response exceeded its configured bound.",
                        )
                try:
                    return json.loads(raw)
                except ValueError:
                    raise Problem(
                        422, "PROVIDER_OUTPUT_INVALID", "The provider did not return valid JSON."
                    ) from None


def kubernetes_job(*, job_name, namespace, queue, image, secret_name, cpu=1, memory_mib=512):
    for value in (job_name, namespace, queue, secret_name):
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", value):
            raise Problem(422, "INVALID_SCHEDULER_RESOURCE", "Kubernetes names must be bounded DNS labels.")
    if not re.fullmatch(r"[A-Za-z0-9./:_-]+@sha256:[a-f0-9]{64}", image):
        raise Problem(
            422, "PINNED_WORKER_REQUIRED", "Provide an operator-built worker image pinned by SHA-256."
        )
    if not 1 <= cpu <= 8 or not 256 <= memory_mib <= 16384:
        raise Problem(422, "INVALID_RESOURCES", "Artifact verification resource bounds were exceeded.")
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": namespace,
            "labels": {"kueue.x-k8s.io/queue-name": queue},
        },
        "spec": {
            "suspend": True,
            "backoffLimit": 0,
            "activeDeadlineSeconds": 300,
            "ttlSecondsAfterFinished": 3600,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 10001,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [
                        {
                            "name": "verifier",
                            "image": image,
                            "command": ["python", "-m", "foundry.agent", "--once"],
                            "envFrom": [{"secretRef": {"name": secret_name}}],
                            "resources": {
                                "requests": {"cpu": str(cpu), "memory": f"{memory_mib}Mi"},
                                "limits": {"cpu": str(cpu), "memory": f"{memory_mib}Mi"},
                            },
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]},
                            },
                        }
                    ],
                }
            },
        },
    }


class SlurmAdapter:
    @staticmethod
    def script(partition, *, cpu=1, memory_mib=512):
        if (
            not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", partition)
            or not 1 <= cpu <= 8
            or not 256 <= memory_mib <= 16384
        ):
            raise Problem(
                422,
                "INVALID_SLURM_RESOURCES",
                "Use an operator-approved partition and bounded verification resources.",
            )
        return f'#!/bin/sh\n#SBATCH --partition={partition}\n#SBATCH --cpus-per-task={cpu}\n#SBATCH --mem={memory_mib}M\n#SBATCH --time=00:05:00\nset -eu\n: "${{FOUNDRY_AGENT_TOKEN:?inject enrolled agent credential}}"\nexec python -m foundry.agent --once\n'

    @staticmethod
    def parse_submission(output):
        match = re.fullmatch(r"([0-9]+)(?:;[A-Za-z0-9_.-]+)?\s*", output)
        if not match:
            raise Problem(502, "SLURM_INVALID_RESPONSE", "sbatch did not return a parsable job identifier.")
        return match[1]

    @staticmethod
    def parse_accounting(output):
        records = []
        for line in output.splitlines():
            fields = line.split("|")
            if len(fields) != 4 or not fields[0].isdigit() or not fields[2].isdigit():
                raise Problem(
                    502,
                    "SLURM_INVALID_RESPONSE",
                    "Expected JobIDRaw|State|ElapsedRaw|ExitCode accounting fields.",
                )
            records.append(
                {
                    "job_id": fields[0],
                    "state": fields[1],
                    "elapsed_seconds": int(fields[2]),
                    "exit_code": fields[3],
                }
            )
        return records

    @staticmethod
    def inspect(job_id, *, operator_enabled=False):
        if not operator_enabled or not shutil.which("sacct"):
            raise Problem(
                409, "BLOCKED_EXTERNAL", "No approved local Slurm client/cluster identity is configured."
            )
        if not re.fullmatch(r"[0-9]{1,18}", job_id):
            raise Problem(422, "INVALID_SLURM_JOB", "Use the scheduler-issued numeric job ID.")
        result = subprocess.run(
            ["sacct", "-n", "-P", "-X", "-j", job_id, "--format=JobIDRaw,State,ElapsedRaw,ExitCode"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        return SlurmAdapter.parse_accounting(result.stdout)
