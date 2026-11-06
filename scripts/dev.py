"""Supervised local applications; persistent infrastructure remains in Compose."""

import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from local_runtime import check_ports, stop_processes, supervisor_lock, write_pid


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    load_dotenv(root / ".env")
    os.environ["NEXT_TELEMETRY_DISABLED"] = "1"
    with supervisor_lock(root):
        check_ports((3000, 8000, 9100))
        processes = {}
        stopping = False

        def stop(*_):
            nonlocal stopping
            stopping = True

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        write_pid(root / ".local/dev.pid", os.getpid())
        try:
            subprocess.run(
                ["docker", "compose", "up", "-d", "--wait", "postgres", "minio", "temporal"], check=True
            )
            from temporalio.client import Client

            for _ in range(30):
                if stopping:
                    return
                try:
                    asyncio.run(asyncio.wait_for(Client.connect(os.environ["TEMPORAL_ADDRESS"]), timeout=3))
                    break
                except Exception:
                    time.sleep(1)
            else:
                raise RuntimeError("Temporal did not become ready.")
            if stopping:
                return
            subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
            subprocess.run([sys.executable, "-m", "foundry.bootstrap"], check=True)
            commands = {
                "api": [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "foundry.api:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                    "--no-access-log",
                ],
                "worker": [sys.executable, "-m", "foundry.worker"],
                "web": ["pnpm", "--filter", "@datafoundry/web", "start"]
                if os.environ.get("FOUNDRY_WEB_MODE") == "production"
                else ["pnpm", "dev"],
                "receiver": [sys.executable, "scripts/webhook_receiver.py"],
            }
            started, retries, restart_at = {}, {}, {}

            def launch(name):
                # Popen duplicates these descriptors; do not leak a log handle on each restart.
                with (root / ".local" / f"{name}.log").open("a") as log:
                    processes[name] = subprocess.Popen(
                        commands[name], stdout=log, stderr=subprocess.STDOUT, start_new_session=True
                    )
                write_pid(root / ".local" / f"{name}.pid", processes[name].pid)
                started[name] = time.monotonic()

            for name in commands:
                if stopping:
                    return
                retries[name] = 0
                launch(name)
            print("Foundry: http://localhost:3000 · API: http://localhost:8000/v1/docs", flush=True)
            while not stopping:
                for name, process in list(processes.items()):
                    if process.poll() is None:
                        continue
                    if name == "web":
                        raise RuntimeError(f"Web exited ({process.returncode}); see .local/web.log.")
                    stamp = time.monotonic()
                    if name not in restart_at:
                        if stamp - started[name] >= 60:
                            retries[name] = 0
                        retries[name] += 1
                        if retries[name] > 5:
                            raise RuntimeError(f"{name} repeatedly crashed; see .local/{name}.log.")
                        delay = min(16, 2 ** (retries[name] - 1))
                        restart_at[name] = stamp + delay
                        print(
                            f"{name} exited ({process.returncode}); retry {retries[name]}/5 in {delay}s.",
                            flush=True,
                        )
                    elif stamp >= restart_at[name]:
                        launch(name)
                        del restart_at[name]
                time.sleep(0.2)
        finally:
            stop_processes(processes)
            for name in ["dev", *processes]:
                (root / ".local" / f"{name}.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
