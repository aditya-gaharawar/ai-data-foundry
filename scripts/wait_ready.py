"""Wait for the host supervisor/worker and the HTTP services, with a real deadline."""

import argparse
import time
from pathlib import Path

import httpx
from local_runtime import verify_process


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument(
        "--services-only", action="store_true", help="Check HTTP services for container mode."
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    root = Path(__file__).resolve().parents[1]
    deadline = time.monotonic() + args.timeout
    pending = ["startup"]
    with httpx.Client(trust_env=False) as client:
        while time.monotonic() < deadline:
            pending = []
            if not args.services_only:
                for name, marker in [("dev", "scripts/dev.py"), ("worker", "foundry.worker")]:
                    if not verify_process(root, name, marker):
                        pending.append(name)
            for name, url in [
                ("api", "http://localhost:8000/v1/health/ready"),
                ("web", "http://localhost:3000"),
            ]:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    pending.append(name)
                    break
                try:
                    if client.get(url, timeout=min(5, remaining)).status_code != 200:
                        pending.append(name)
                except httpx.HTTPError:
                    pending.append(name)
            if not pending:
                print(
                    "Local stack ready: "
                    + ("HTTP services." if args.services_only else "supervisor, worker, web and API.")
                )
                return
            time.sleep(min(1, max(0, deadline - time.monotonic())))
    raise SystemExit("Local stack not ready: " + ", ".join(pending) + "; inspect .local logs.")


if __name__ == "__main__":
    main()
