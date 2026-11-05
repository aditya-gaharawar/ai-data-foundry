"""Download a pinned Apache-2.0 local test model; never contact an inference service."""

import hashlib
import json
from pathlib import Path

import httpx

MODEL = "bartowski/SmolLM2-135M-Instruct-GGUF"
REVISION = "09816acd5d99df7be770d85ea30822623dab342c"
FILENAME = "SmolLM2-135M-Instruct-Q4_K_M.gguf"
SHA256 = "2e8040ceae7815abe0dcb3540b9995eaa1fa0d2ca9e797d0a635ae4433c68c2d"
SOURCE = "HuggingFaceTB/SmolLM2-135M-Instruct"
SOURCE_REVISION = "12fd25f77366fa6b3b4b768ec3050bf629380bac"


def main():
    try:
        __import__("llama_cpp")
    except (ImportError, RuntimeError, OSError):
        raise SystemExit("Install the supported local-model runtime before enabling model weights.") from None
    root = Path(__file__).resolve().parents[1]
    target = root / ".local/models"
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    model = target / FILENAME
    with httpx.Client(timeout=180, follow_redirects=True) as client:
        card = client.get(f"https://huggingface.co/api/models/{SOURCE}/revision/{SOURCE_REVISION}")
        card.raise_for_status()
        if card.json().get("cardData", {}).get("license") != "apache-2.0":
            raise SystemExit("The pinned source no longer provides the expected Apache-2.0 license metadata.")
        if not model.exists():
            partial = model.with_suffix(".part")
            try:
                with client.stream(
                    "GET", f"https://huggingface.co/{MODEL}/resolve/{REVISION}/{FILENAME}"
                ) as response:
                    response.raise_for_status()
                    with partial.open("wb") as out:
                        for chunk in response.iter_bytes():
                            out.write(chunk)
                partial.replace(model)
            finally:
                partial.unlink(missing_ok=True)
    if hashlib.sha256(model.read_bytes()).hexdigest() != SHA256:
        raise SystemExit("Model checksum mismatch; the model is not enabled.")
    manifest = {
        "model_ref": "smollm2-135m-instruct-q4_k_m",
        "path": str(model.relative_to(root)),
        "sha256": SHA256,
        "bytes": model.stat().st_size,
        "license": "Apache-2.0",
        "source": SOURCE,
        "source_revision": SOURCE_REVISION,
        "quantization_repository": MODEL,
        "quantization_revision": REVISION,
        "terms_url": f"https://huggingface.co/{SOURCE}/tree/{SOURCE_REVISION}",
        "usage": "Local synthetic test inference; structured validity is not factual accuracy",
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    model.chmod(0o600)
    (target / "manifest.json").chmod(0o600)
    print(
        "Pinned Apache-2.0 model downloaded and SHA-256 verified; application consent is required before use."
    )


if __name__ == "__main__":
    main()
