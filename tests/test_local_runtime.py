import importlib.util
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("local_runtime", Path("scripts/local_runtime.py"))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def test_lock_rejects_another_process_and_releases_after_owner_exits(tmp_path):
    with runtime.supervisor_lock(tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; from pathlib import Path; sys.path.insert(0, 'scripts'); from local_runtime import supervisor_lock;\nwith supervisor_lock(Path(sys.argv[1])): pass",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "already starting or running" in result.stderr
    with runtime.supervisor_lock(tmp_path):
        pass


def test_shutdown_escalates_and_reaps_unresponsive_child():
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print("ready", flush=True); time.sleep(60)',
        ],
        stdout=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        assert process.stdout.readline() == b"ready\n"
        runtime.stop_processes({"test": process}, timeout=0.05)
        assert process.returncode == -9
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()


def test_process_identity_rejects_corrupt_stale_and_unrelated_pids(tmp_path):
    local = tmp_path / ".local"
    local.mkdir()
    pid_file = local / "worker.pid"
    for value in ["invalid", "0", "1", "999999999", str(os.getpid())]:
        pid_file.write_text(value)
        assert not runtime.verify_process(tmp_path, "worker", "foundry.worker")


def test_occupied_port_prevents_startup():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        with pytest.raises(RuntimeError, match="already in use"):
            runtime.check_ports((listener.getsockname()[1],))
