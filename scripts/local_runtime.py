"""Linux host-runtime ownership, locking and bounded process shutdown."""

import fcntl
import os
import signal
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def supervisor_lock(root: Path):
    directory = root / ".local"
    directory.mkdir(exist_ok=True)
    with (directory / "dev.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Foundry is already starting or running in this checkout.") from None
        yield


def verify_process(root: Path, name: str, marker: str) -> bool:
    try:
        pid = int((root / ".local" / f"{name}.pid").read_text())
        if pid <= 1:
            return False
        process = Path(f"/proc/{pid}")
        args = (process / "cmdline").read_bytes().split(b"\0")
        state = (process / "stat").read_text().rsplit(")", 1)[1].split()[0]
        return (
            marker.encode() in args
            and (process / "cwd").resolve() == root.resolve()
            and state not in {"Z", "T", "t", "X"}
        )
    except (OSError, ValueError, IndexError):
        return False


def check_ports(ports: tuple[int, ...]):
    for port in ports:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise RuntimeError(
                    f"Port {port} is already in use. Stop the existing app before starting Foundry."
                ) from None


def write_pid(path: Path, pid: int):
    temporary = path.with_suffix(".pid.tmp")
    temporary.write_text(str(pid))
    temporary.replace(path)


def stop_processes(processes: dict[str, subprocess.Popen], timeout: float = 5):
    for process in processes.values():
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + timeout
    for process in processes.values():
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)
