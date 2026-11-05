"""Pinned procedural perception scenes; no uploaded scripts or arbitrary assets."""

import json
import os
import signal
import subprocess
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from typing import Literal

from PIL import Image
from pydantic import Field

from .config import settings
from .errors import Problem
from .media import prepare_image
from .schemas import Strict
from .security import digest
from .storage import put_immutable


class SimulationConfig(Strict):
    engine: Literal["blender.procedural@1", "isaac.sim", "isaac.lab"] = "blender.procedural@1"
    object_type: Literal["cube", "sphere"] = "cube"
    count: int = Field(default=1, ge=1, le=5)
    frames_per_scene: int = Field(default=1, ge=1, le=3)
    resolution: Literal[64, 128, 256] = 128
    fps: int = Field(default=10, ge=1, le=30)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    render_samples: int = Field(default=4, ge=1, le=16)


@lru_cache(maxsize=1)
def blender_state():
    try:
        result = subprocess.run(
            [settings().blender_executable, "--version"], capture_output=True, text=True, timeout=5
        )
        version = result.stdout.splitlines()[0]
        ready = result.returncode == 0 and version == "Blender " + settings().blender_version
        return {
            "state": "READY" if ready else "BLOCKED_EXTERNAL",
            "version": version,
            "reason": "CPU Cycles, original primitives, RGB and object-index masks."
            if ready
            else "Install the pinned Blender version before dispatch.",
        }
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return {
            "state": "BLOCKED_EXTERNAL",
            "version": None,
            "reason": "The pinned headless Blender runtime is unavailable.",
        }


def require_simulator(config):
    if config["engine"] != "blender.procedural@1":
        raise Problem(
            409,
            "BLOCKED_EXTERNAL",
            "Isaac requires an operator-validated release/driver matrix and an NVIDIA RTX GPU with RT cores. H100/A100/H200 cannot satisfy rendering requirements; no compatible pool is configured.",
        )
    state = blender_state()
    if state["state"] != "READY":
        raise Problem(409, "BLOCKED_EXTERNAL", state["reason"])


def render_scene(config, organization_id, heartbeat, cancelled):
    require_simulator(config)
    script = Path(__file__).with_name("blender_runtime.py").resolve()
    with tempfile.TemporaryDirectory(prefix="foundry-blender-") as directory:
        base = Path(directory)
        request = base / "request.json"
        request.write_text(json.dumps(config))
        with (base / "render.log").open("wb") as log:
            process = subprocess.Popen(
                [
                    settings().blender_executable,
                    "--background",
                    "--factory-startup",
                    "--disable-autoexec",
                    "--threads",
                    "2",
                    "--python",
                    str(script),
                    "--",
                    str(request),
                    str(base),
                ],
                stdout=log,
                stderr=log,
                start_new_session=True,
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "LANG": "C.UTF-8",
                    "OMP_NUM_THREADS": "2",
                    "OPENBLAS_NUM_THREADS": "2",
                },
            )
            started = time.monotonic()
            try:
                while process.poll() is None:
                    heartbeat()
                    if cancelled():
                        raise Problem(409, "CANCELLED", "Scene rendering cancelled before publication.")
                    if time.monotonic() - started > 180:
                        raise Problem(
                            422, "SIMULATION_TIMEOUT", "The bounded CPU render exceeded three minutes."
                        )
                    time.sleep(0.25)
                if process.returncode != 0 or not (base / "frames.json").exists():
                    raise Problem(
                        422,
                        "SIMULATION_FAILED",
                        "The pinned Blender runtime failed; no synthetic success or version was created.",
                    )
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
        frames = json.loads((base / "frames.json").read_text())
        samples = []
        for frame in frames:
            rgb = (base / frame.pop("rgb_file")).read_bytes()
            mask_path = base / frame.pop("mask_file")
            mask = Image.open(mask_path).convert("L")
            bounds = mask.getbbox()
            if not bounds or mask.size != (config["resolution"], config["resolution"]):
                raise Problem(
                    422,
                    "SIMULATION_ALIGNMENT_FAILED",
                    "Rendered mask and image must be aligned and contain a visible object.",
                )
            x, y, right, bottom = bounds
            media = prepare_image(rgb, "image/png", organization_id)
            scene = put_immutable(
                organization_id, (base / frame.pop("scene_file")).read_bytes(), "model/gltf-binary"
            )
            sample = {
                "payload": {
                    "image": media,
                    "simulation": {
                        **frame,
                        "mask_artifact": put_immutable(organization_id, mask_path.read_bytes(), "image/png"),
                        "scene_artifact": scene,
                        "engine": "blender.procedural@1",
                        "engine_version": settings().blender_version,
                        "label_coordinates": "top-left pixel x/y/width/height; visible object-index mask",
                        "physics": "scripted primitive motion; no robot dynamics or real-world accuracy claim",
                    },
                },
                "annotation": {
                    "kind": "boxes",
                    "boxes": [
                        {
                            "label": config["object_type"],
                            "x": x,
                            "y": y,
                            "width": right - x,
                            "height": bottom - y,
                        }
                    ],
                },
                "review_status": "SIMULATION_DERIVED",
            }
            samples.append(sample)
        return {
            "samples": samples,
            "metadata": {
                "engine": "blender.procedural@1",
                "version": settings().blender_version,
                "script_sha256": digest(script.read_bytes()),
                "seed": config["seed"],
                "frames": len(samples),
                "duration_ms": round((time.monotonic() - started) * 1000),
                "sensor_types": ["rgb", "object_index_mask"],
                "units": "meters, seconds, radians",
            },
        }


def register(app):
    from fastapi import Request, Response

    from .api import DB, Auth, get
    from .models import Version
    from .recipes import parse_jsonl
    from .storage import read_artifact

    @app.get("/v1/simulations/capabilities", tags=["Simulation"])
    def simulation_capabilities(p: Auth):
        p.require("datasets:read")
        return {
            "items": [
                {
                    "engine": "blender.procedural@1",
                    **blender_state(),
                    "sensors": ["rgb", "object_index_mask"],
                    "max_frames": 15,
                },
                {
                    "engine": "isaac.sim",
                    "state": "BLOCKED_EXTERNAL",
                    "reason": "No validated RTX/RT-core runtime, driver and release matrix is configured; H100/A100/H200 are not renderer-compatible.",
                },
                {
                    "engine": "isaac.lab",
                    "state": "BLOCKED_EXTERNAL",
                    "reason": "Requires a configured, version-compatible Isaac Sim/Isaac Lab worker. No robotics episode is fabricated.",
                },
            ]
        }

    @app.get("/v1/versions/{version_id}/samples/{sample_id}/artifacts/{kind}", tags=["Simulation"])
    def simulation_artifact(version_id: str, sample_id: str, kind: str, request: Request, p: Auth, db: DB):
        p.require("datasets:read")
        version = get(db, Version, version_id, p.organization_id)
        sample = next(
            (
                row
                for row in parse_jsonl(read_artifact(version.manifest["data_artifact"]))
                if row["sample_id"] == sample_id
            ),
            None,
        )
        if not sample or kind not in {"mask", "scene"} or "simulation" not in sample["payload"]:
            raise Problem(404, "NOT_FOUND", "Simulation artifact not found.")
        artifact = sample["payload"]["simulation"][kind + "_artifact"]
        data = read_artifact(artifact)
        return Response(
            data,
            media_type=artifact["content_type"],
            headers={
                "X-Content-SHA256": digest(data),
                "Content-Disposition": f'inline; filename="{sample_id}.{"glb" if kind == "scene" else "png"}"',
            },
        )
