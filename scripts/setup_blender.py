"""Use an installed pinned Blender or verify/extract its official Linux x64 runtime."""

import argparse
import hashlib
import platform
import subprocess
import tarfile
from pathlib import Path

import httpx

VERSION = "4.3.2"
NAME = f"blender-{VERSION}-linux-x64"
SHA256 = "4da1c956673c0485e63054e563ee69198cc8f80d8157dd7592dffc8a6a5592e6"


def version_matches(executable):
    try:
        result = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0 and result.stdout.splitlines()[0] == "Blender " + VERSION
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    executable = Path("/usr/bin/blender")
    if not version_matches(executable):
        if platform.system() != "Linux" or platform.machine() != "x86_64":
            raise SystemExit(
                "This optional installer is pinned to Linux x86_64. Configure another verified 4.3.2 runtime explicitly."
            )
        folder = root / ".local/runtimes"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        executable = folder / NAME / "blender"
        if not version_matches(executable):
            archive = folder / (NAME + ".tar.xz")
            try:
                with httpx.stream(
                    "GET",
                    f"https://download.blender.org/release/Blender4.3/{NAME}.tar.xz",
                    timeout=180,
                    follow_redirects=True,
                ) as response:
                    response.raise_for_status()
                    hasher = hashlib.sha256()
                    with archive.open("wb") as stream:
                        for chunk in response.iter_bytes():
                            hasher.update(chunk)
                            stream.write(chunk)
                if hasher.hexdigest() != SHA256:
                    raise SystemExit("Official Blender runtime checksum mismatch; refusing extraction.")
                with tarfile.open(archive) as bundle:
                    if any(not member.name.startswith(NAME + "/") for member in bundle.getmembers()):
                        raise SystemExit("Runtime archive has unexpected paths.")
                    bundle.extractall(folder, filter="data")
            finally:
                archive.unlink(missing_ok=True)
    if not version_matches(executable):
        raise SystemExit(
            "Pinned Blender cannot start. Install the required system graphics libraries before enabling rendering."
        )
    if args.env_output:
        args.env_output.parent.mkdir(parents=True, exist_ok=True)
        args.env_output.write_text(f"BLENDER_EXECUTABLE={executable}\n")
        args.env_output.chmod(0o600)
    print("Verified Blender " + VERSION + ": " + str(executable))


if __name__ == "__main__":
    main()
