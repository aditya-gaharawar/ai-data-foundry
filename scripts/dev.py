"""Resource-efficient development runner; infrastructure remains in Compose."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
os.chdir(root)
load_dotenv(root / ".env")
os.environ["NEXT_TELEMETRY_DISABLED"] = "1"
subprocess.run(["docker", "compose", "up", "-d", "--wait", "postgres", "minio", "temporal"], check=True)
for _ in range(30):
    try:
        import asyncio

        from temporalio.client import Client

        asyncio.run(Client.connect(os.environ["TEMPORAL_ADDRESS"]))
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("Temporal did not become ready.")
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
subprocess.run([sys.executable, "-m", "foundry.bootstrap"], check=True)
(root / ".local").mkdir(exist_ok=True)
(root / ".local" / "dev.pid").write_text(str(os.getpid()))
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
    "web": ["pnpm", "dev"],
    "receiver": [sys.executable, "scripts/webhook_receiver.py"],
}
processes = {}


def stop(*_):
    for process in processes.values():
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    raise SystemExit(0)


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
for name, command in commands.items():
    log = (root / ".local" / f"{name}.log").open("a")
    processes[name] = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    (root / ".local" / f"{name}.pid").write_text(str(processes[name].pid))
print("Foundry: http://localhost:3000 · API: http://localhost:8000/v1/docs", flush=True)
print("Local processes and logs: .local/ · Ctrl+C stops application processes.", flush=True)
while True:
    for name, process in list(processes.items()):
        if process.poll() is not None:
            if name in {"worker", "api", "receiver"}:
                log = (root / ".local" / f"{name}.log").open("a")
                processes[name] = subprocess.Popen(
                    commands[name], stdout=log, stderr=subprocess.STDOUT, start_new_session=True
                )
                (root / ".local" / f"{name}.pid").write_text(str(processes[name].pid))
            else:
                print(f"{name} exited ({process.returncode}); see .local/{name}.log", flush=True)
                stop()
    time.sleep(1)
