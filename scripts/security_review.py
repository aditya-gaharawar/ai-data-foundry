"""Actual public advisory queries and a private-value source scan, scoped to local use."""

import importlib.metadata
import json
import subprocess
from pathlib import Path

import httpx
from dotenv import dotenv_values
from operational_checks import evidence_directory, save_proof


def main():
    evidence = evidence_directory()
    npm = subprocess.run(["pnpm", "audit", "--json"], capture_output=True, text=True)
    if npm.returncode not in (0, 1):
        raise RuntimeError("npm advisory service unavailable; no clean scan is claimed.")
    npm_report = json.loads(npm.stdout)
    (evidence / "npm-audit.json").write_text(json.dumps(npm_report, indent=2))
    queries = [
        {"package": {"name": dist.metadata["Name"], "ecosystem": "PyPI"}, "version": dist.version}
        for dist in importlib.metadata.distributions()
        if dist.metadata["Name"] != "ai-data-foundry"
    ]
    # Only public dependency names/versions are sent, never code, data or credentials.
    with httpx.Client(timeout=60) as client:
        response = client.post("https://api.osv.dev/v1/querybatch", json={"queries": queries})
        response.raise_for_status()
        findings = []
        for query, result in zip(queries, response.json()["results"], strict=True):
            vulnerabilities = result.get("vulns", [])
            if vulnerabilities:
                details = []
                for item in vulnerabilities:
                    document = client.get("https://api.osv.dev/v1/vulns/" + item["id"])
                    document.raise_for_status()
                    value = document.json()
                    details.append(
                        {
                            "id": item["id"],
                            "summary": value.get("summary"),
                            "severity": value.get("database_specific", {}).get("severity", "UNRATED"),
                            "aliases": value.get("aliases", []),
                        }
                    )
                findings.append(
                    {
                        "package": query["package"]["name"],
                        "version": query["version"],
                        "vulnerabilities": details,
                    }
                )
    (evidence / "python-osv-audit.json").write_text(
        json.dumps(
            {
                "source": "OSV public dependency-version queries",
                "packages_checked": len(queries),
                "findings": findings,
            },
            indent=2,
        )
    )
    # Review the sole known unfixed optional transitive advisory narrowly. A new
    # ID/package fails this gate until investigated; do not blanket allow pickle.
    reviewed = {"GHSA-w8v5-vhqr-4h9v", "PYSEC-2026-2447"}
    unresolved = [
        item
        for finding in findings
        for item in finding["vulnerabilities"]
        if finding["package"].lower() != "diskcache" or item["id"] not in reviewed
    ]
    runtime = Path("apps/api/foundry/inference_runtime.py").read_text()
    no_cache_configuration = (
        "if llm.cache is not None:" in runtime
        and "set_cache(" not in runtime
        and "LlamaDiskCache(" not in runtime
    )
    files = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    secrets = [
        value.encode()
        for key, value in dotenv_values(".env").items()
        if value and len(value) >= 12 and any(name in key for name in ["SECRET", "PASSWORD"])
    ]
    matches = []
    for encoded in files:
        if not encoded:
            continue
        path = Path(encoded.decode())
        if path.is_file() and any(secret in path.read_bytes() for secret in secrets):
            matches.append(str(path))
    npm_counts = npm_report["metadata"]["vulnerabilities"]
    passed = not unresolved and not matches and no_cache_configuration and not any(npm_counts.values())
    report = {
        "status": "PASS" if passed else "FAIL",
        "checks": {
            "npm_advisories": npm_counts,
            "python_packages_checked": len(queries),
            "unreviewed_python_advisories": len(unresolved),
            "source_files_with_private_values": matches,
            "disk_cache_unconfigured_and_refused": no_cache_configuration,
        },
        "reviewed_residuals": [
            {
                "package": item["package"],
                "version": item["version"],
                "advisory_ids": [v["id"] for v in item["vulnerabilities"]],
                "assessment": "Optional local llama.cpp wrapper imports diskcache but no disk cache is instantiated; no cache paths or pickle data are accepted; native child refuses a configured cache. Unfixed upstream advisory remains in the installed optional dependency. Remove/replace it before production.",
            }
            for item in findings
            if item["package"].lower() == "diskcache"
        ],
        "remediated": {"cryptography": "50.0.2", "pillow": "13.0.0"},
        "identifier_classification": "The documented development S3 access-key ID is a public username, not signing key material. Actual S3 secrets, application secrets and passwords are scanned as private values.",
        "limits": "Local dependency and source review only; no independent penetration test, native binary audit, container OS scan or compliance certification. The optional diskcache advisory remains a production blocker.",
    }
    save_proof("security", report)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
