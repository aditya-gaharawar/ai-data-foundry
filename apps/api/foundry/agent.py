"""Outbound-only CPU agent. Executes one fixed verification operator, never user code."""

import argparse
import hashlib
import os
import time

import httpx

from .compute import local_inventory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    token = os.environ.get("FOUNDRY_AGENT_TOKEN")
    if not token:
        raise SystemExit("Set the one-time enrolled FOUNDRY_AGENT_TOKEN through your secret manager.")
    with httpx.Client(
        base_url=os.environ.get("FOUNDRY_API_URL", "http://localhost:8000"),
        headers={"Authorization": "Bearer " + token},
        timeout=30,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        while True:
            client.post("/v1/compute/agent/heartbeat", json=local_inventory()).raise_for_status()
            response = client.post("/v1/compute/agent/claim")
            response.raise_for_status()
            job = response.json()["job"]
            if job:
                if job["kind"] != "artifact.verify@1":
                    raise SystemExit("Unsupported operator; refusing arbitrary work.")
                started = time.monotonic()
                headers = {"X-Lease-Token": job["lease_token"]}
                data = client.get(job["artifact_url"], headers=headers)
                data.raise_for_status()
                sha = hashlib.sha256(data.content).hexdigest()
                if sha != data.headers["X-Content-SHA256"]:
                    raise SystemExit("Artifact checksum mismatch.")
                result = client.post(
                    f"/v1/compute/agent/jobs/{job['id']}/complete",
                    headers=headers,
                    json={
                        "attempt": job["attempt"],
                        "sha256": sha,
                        "bytes": len(data.content),
                        "processing_ms": round((time.monotonic() - started) * 1000),
                    },
                )
                result.raise_for_status()
                print("Verified immutable artifact; scoped lease completed.", flush=True)
            if args.once:
                break
            time.sleep(2)


if __name__ == "__main__":
    main()
