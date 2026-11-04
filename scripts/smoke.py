"""Run the real core integration scenario, including signed webhook and SDK/CLI."""

import subprocess
import sys

subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_integration.py::test_complete_sdk_export_webhook_and_cli",
    ],
    check=True,
)
