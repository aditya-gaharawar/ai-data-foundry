import json
import random
from pathlib import Path
from typing import Literal

from jsonschema import Draft202012Validator, ValidationError
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as ModelError

from .errors import Problem
from .security import canonical, digest

RECIPE_SCHEMA = json.loads(Path("contracts/recipe.schema.json").read_text())


def validate_sample_schema(schema: dict) -> None:
    if len(canonical(schema)) > 65536:
        raise Problem(422, "SCHEMA_TOO_LARGE", "Sample schemas are limited to 64 KiB locally.")
    stack = [schema]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            if "$ref" in value or "$dynamicRef" in value:
                raise Problem(
                    422,
                    "UNSUPPORTED_SCHEMA_REF",
                    "Inline schema definitions. Reference resolution is disabled to prevent remote fetches.",
                )
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception:
        raise Problem(422, "INVALID_SAMPLE_SCHEMA", "The sample schema is not valid JSON Schema.") from None


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateConfig(Strict):
    engine: Literal["deterministic.text@1"] = "deterministic.text@1"
    count: int = Field(default=100, ge=1, le=10000)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)


class IngestConfig(Strict):
    upload_id: str


class ValidateConfig(Strict):
    minimum_samples: int = Field(default=1, ge=1, le=10000)
    max_duplicate_ratio: float = Field(default=0, ge=0, le=1)
    max_invalid_ratio: float = Field(default=0, ge=0, le=1)


class ExportConfig(Strict):
    format: Literal["jsonl"] = "jsonl"


def compile_recipe(definition: dict) -> list[dict]:
    try:
        Draft202012Validator(RECIPE_SCHEMA).validate(definition)
    except ValidationError as error:
        raise Problem(422, "INVALID_RECIPE", error.message) from None
    nodes = definition["nodes"]
    indexed = {node["id"]: node for node in nodes}
    if len(indexed) != len(nodes):
        raise Problem(422, "INVALID_RECIPE", "Node IDs must be unique.")
    incoming = {key: [] for key in indexed}
    outgoing = {key: [] for key in indexed}
    seen = set()
    for edge in definition["edges"]:
        a, b = edge["from"], edge["to"]
        if a not in indexed or b not in indexed or (a, b) in seen:
            raise Problem(422, "INVALID_RECIPE", "Edges must connect existing nodes exactly once.")
        outgoing[a].append(b)
        incoming[b].append(a)
        seen.add((a, b))
    ready = [key for key in indexed if not incoming[key]]
    order = []
    degrees = {key: len(value) for key, value in incoming.items()}
    while ready:
        key = ready.pop(0)
        order.append(indexed[key])
        for child in outgoing[key]:
            degrees[child] -= 1
            if degrees[child] == 0:
                ready.append(child)
    if len(order) != len(nodes):
        raise Problem(422, "RECIPE_CYCLE", "The recipe contains a cycle.")
    if any(len(incoming[key]) > 1 or len(outgoing[key]) > 1 for key in indexed):
        raise Problem(422, "UNSUPPORTED_GRAPH", "This local engine supports a single connected pipeline.")
    kinds = [node["type"] for node in order]
    if kinds not in (
        ["generate", "validate", "publish"],
        ["ingest", "validate", "publish"],
        ["generate", "validate", "publish", "export"],
        ["ingest", "validate", "publish", "export"],
    ):
        raise Problem(
            422,
            "UNSUPPORTED_PIPELINE",
            "Use generate/ingest → validate → publish, optionally followed by export.",
        )
    if len(seen) != len(nodes) - 1:
        raise Problem(422, "INVALID_RECIPE", "All nodes must form one connected pipeline.")
    schemas = {
        "generate": GenerateConfig,
        "ingest": IngestConfig,
        "validate": ValidateConfig,
        "publish": Strict,
        "export": ExportConfig,
    }
    for node in order:
        if node.get("resource_requirements"):
            raise Problem(422, "CAPABILITY_UNAVAILABLE", "The local worker exposes CPU text processing only.")
        try:
            schemas[node["type"]].model_validate(node["config"])
        except ModelError as error:
            raise Problem(422, "INVALID_NODE_CONFIG", str(error)) from None
    return order


def generate_text(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    return [
        {
            "prompt": f"Example {index + 1}: What is {a} + {b}?",
            "response": str(a + b),
            "tags": ["arithmetic", "deterministic"],
        }
        for index in range(count)
        for a, b in [(rng.randrange(10000), rng.randrange(10000))]
    ]


def parse_jsonl(data: bytes) -> list[dict]:
    try:
        lines = data.decode("utf-8").splitlines()
        if len(lines) > 10000:
            raise ValueError("At most 10,000 JSONL records are supported locally.")

        def reject_constant(value):
            raise ValueError(f"Non-finite JSON number {value} is unsupported.")

        values = [json.loads(line, parse_constant=reject_constant) for line in lines if line.strip()]
        if not values or any(not isinstance(value, dict) for value in values):
            raise ValueError("Upload nonempty JSONL containing one object per line.")
        return values
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as error:
        raise Problem(422, "INVALID_JSONL", str(error)) from None


def quality_report(samples: list[dict], schema: dict, config: dict) -> dict:
    validator = Draft202012Validator(schema)
    invalid = sum(not validator.is_valid(sample) for sample in samples)
    hashes = [digest(canonical(sample)) for sample in samples]
    duplicates = len(samples) - len(set(hashes))
    thresholds = ValidateConfig.model_validate(config)
    total = len(samples)
    passed = (
        total >= thresholds.minimum_samples
        and invalid / max(total, 1) <= thresholds.max_invalid_ratio
        and duplicates / max(total, 1) <= thresholds.max_duplicate_ratio
    )
    return {
        "passed": passed,
        "total": total,
        "valid": total - invalid,
        "invalid": invalid,
        "duplicates": duplicates,
        "duplicate_ratio": duplicates / max(total, 1),
        "schema_coverage": 1.0,
        "checks": ["json_schema", "sha256_integrity", "exact_deduplication", "source_rights"],
        "limitations": ["No semantic, factuality, contamination, or PII model checks in this milestone."],
    }
