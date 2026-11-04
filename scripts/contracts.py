"""Freeze OpenAPI and generate Python model contracts without external generators."""

import json
import keyword
import re
import subprocess
import sys
from pathlib import Path

from foundry.api import app

root = Path(__file__).resolve().parents[1]
schema = app.openapi()


def typename(name):
    return re.sub(r"\W", "_", name)


def annotation(spec):
    if "$ref" in spec:
        return typename(spec["$ref"].split("/")[-1])
    if "anyOf" in spec:
        return " | ".join(dict.fromkeys(annotation(part) for part in spec["anyOf"]))
    if "enum" in spec:
        return "Literal[" + ", ".join(repr(value) for value in spec["enum"]) + "]"
    kind = spec.get("type")
    if kind == "array":
        return "list[" + annotation(spec.get("items", {})) + "]"
    return {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "null": "None",
        "object": "dict[str, Any]",
    }.get(kind, "Any")


code = [
    '"""Generated from packages/contracts/openapi.json. Do not edit."""',
    "",
    "from __future__ import annotations",
    "",
    "from typing import Any, Literal",
    "",
    "from pydantic import BaseModel, ConfigDict, Field",
    "",
]
names = []
for name, spec in schema["components"]["schemas"].items():
    if spec.get("type") != "object":
        continue
    name = typename(name)
    names.append(name)
    code += [
        f"class {name}(BaseModel):",
        "    model_config = ConfigDict(populate_by_name=True, extra='ignore')",
    ]
    required = spec.get("required", [])
    for field, definition in spec.get("properties", {}).items():
        safe = (
            field + "_"
            if keyword.iskeyword(field) or hasattr(__import__("pydantic").BaseModel, field)
            else field
        )
        typ = annotation(definition)
        if field not in required and "None" not in typ:
            typ += " | None"
        default = "..." if field in required else "None"
        code.append(f"    {safe}: {typ} = Field({default}, alias={field!r})")
    code.append("")
code += [f"{name}.model_rebuild()" for name in names]
python_code = subprocess.run(
    [sys.executable, "-m", "ruff", "format", "--stdin-filename", "models.py", "-"],
    input="\n".join(code) + "\n",
    text=True,
    capture_output=True,
    check=True,
).stdout
outputs = {
    root / "packages/contracts/openapi.json": json.dumps(schema, indent=2, sort_keys=True) + "\n",
    root / "packages/sdk-python/datafoundry/models.py": python_code,
}
for path, value in outputs.items():
    if "--check" in sys.argv:
        if not path.exists() or path.read_text() != value:
            raise SystemExit(f"Contract drift: regenerate {path.relative_to(root)}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
print(f"OpenAPI {schema['openapi']}: {len(schema['paths'])} paths; {len(names)} generated Python models.")
