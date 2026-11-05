"""Trusted, minimal CPU inference child. No database or provider credentials are inherited."""

import json
import sys
from pathlib import Path


def main():
    from jsonschema import Draft202012Validator
    from llama_cpp import Llama

    request = json.loads(Path(sys.argv[1]).read_text())
    schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "minLength": 1, "maxLength": 512},
            "response": {"type": "string", "minLength": 1, "maxLength": 512},
        },
        "required": ["prompt", "response"],
        "additionalProperties": False,
    }
    llm = Llama(
        model_path=request["model_path"],
        n_ctx=2048,
        n_threads=2,
        n_gpu_layers=0,
        chat_format="chatml",
        verbose=False,
        seed=request["seed"],
    )
    # The optional wrapper depends on diskcache, which has an unfixed pickle
    # advisory. Never configure/read a disk cache or accept cache paths.
    if llm.cache is not None:
        raise RuntimeError("Disk-backed or user-supplied model caches are forbidden.")
    samples = []
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for index in range(request["count"]):
        result = llm.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "Write one short synthetic instruction example. Return JSON with prompt and response strings. Avoid personal information. "
                    + request["instructions"],
                },
                {"role": "user", "content": f"Produce example {index + 1}; keep both strings short."},
            ],
            response_format={"type": "json_object", "schema": schema},
            max_tokens=request["max_output_tokens"],
            temperature=0.2,
        )
        value = json.loads(result["choices"][0]["message"]["content"])
        Draft202012Validator(schema).validate(value)
        samples.append(value)
        for key in usage:
            usage[key] += result["usage"][key]
    Path(sys.argv[2]).write_text(json.dumps({"samples": samples, "usage": usage}))


if __name__ == "__main__":
    main()
