"""Stop only the verified Foundry host supervisor in this checkout."""

import os
import signal
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
pid_file = root / ".local/dev.pid"
if pid_file.exists():
    pid = int(pid_file.read_text())
    command = Path(f"/proc/{pid}/cmdline")
    if (
        command.exists()
        and b"scripts/dev.py" in command.read_bytes()
        and Path(f"/proc/{pid}/cwd").resolve() == root
    ):
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if not command.exists():
                break
            time.sleep(0.1)
        print("Stopped this checkout's host application processes.")
    pid_file.unlink(missing_ok=True)
