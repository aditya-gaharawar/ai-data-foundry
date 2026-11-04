import copy
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import definition
from datafoundry import verify_webhook
from foundry.errors import Problem
from foundry.recipes import compile_recipe, generate_text, parse_jsonl, quality_report
from foundry.security import canonical, digest, read_token, signed_token, webhook_signature
from jsonschema import Draft202012Validator


def test_generator_is_reproducible_and_correct():
    first, repeated = generate_text(100, 42), generate_text(100, 42)
    assert first == repeated
    assert first != generate_text(100, 43)
    assert len(set(digest(canonical(row)) for row in first)) == 100
    for row in first:
        numbers = row["prompt"].split("What is ")[1].removesuffix("?").split(" + ")
        assert int(row["response"]) == sum(map(int, numbers))


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda value: value["edges"].append({"from": "publish", "to": "source"}), "RECIPE_CYCLE"),
        (lambda value: value["nodes"][0]["config"].update(engine="unapproved.api"), "INVALID_NODE_CONFIG"),
        (lambda value: value["edges"][0].update(to="absent"), "INVALID_RECIPE"),
        (
            lambda value: value["nodes"][0].update(resource_requirements={"gpu": "H100"}),
            "CAPABILITY_UNAVAILABLE",
        ),
        (lambda value: value["nodes"][1].update(type="simulate"), "UNSUPPORTED_PIPELINE"),
    ],
)
def test_recipe_rejects_unsupported_or_malformed_work(mutation, code):
    value = copy.deepcopy(definition())
    mutation(value)
    with pytest.raises(Problem) as error:
        compile_recipe(value)
    assert error.value.code == code


def test_quality_gate_reports_denominators_and_blocks_bad_data():
    schema = {
        "type": "object",
        "required": ["prompt", "response"],
        "properties": {"prompt": {"type": "string"}, "response": {"type": "string"}},
    }
    row = {"prompt": "hello", "response": "world"}
    report = quality_report([row, row, {"prompt": 4}], schema, {})
    assert not report["passed"]
    assert (report["total"], report["invalid"], report["duplicates"]) == (3, 1, 1)


@pytest.mark.parametrize("payload", [b"", b"[]\n", b"not json", b"\xff"])
def test_jsonl_parser_rejects_invalid_sources(payload):
    with pytest.raises(Problem):
        parse_jsonl(payload)


def test_signed_grants_and_webhook_tampering():
    value = signed_token({"org": "org-a", "exp": int(time.time()) + 60})
    assert read_token(value)["org"] == "org-a"
    with pytest.raises(Problem):
        read_token(value + "x")
    with pytest.raises(Problem):
        read_token(signed_token({"exp": int(time.time()) - 10}))
    raw = canonical({"event_id": "evt_123456789", "data": {"ok": True}})
    timestamp = str(int(time.time()))
    signature = webhook_signature("test-secret", timestamp, raw)
    assert verify_webhook("test-secret", raw, timestamp, signature)["data"]["ok"]
    with pytest.raises(ValueError):
        verify_webhook("test-secret", raw + b" ", timestamp, signature)
    with pytest.raises(ValueError):
        verify_webhook("test-secret", raw, str(int(time.time()) - 600), signature)


def test_contracts_and_generated_clients_are_current():
    subprocess.run([sys.executable, "scripts/contracts.py", "--check"], check=True, capture_output=True)
    schema = json.loads(Path("packages/contracts/openapi.json").read_text())
    assert schema["openapi"].startswith("3.1")
    assert "bearerAuth" in schema["components"]["securitySchemes"]
    assert schema["paths"]["/v1/runs"]["post"]["responses"]["202"]
    Draft202012Validator.check_schema(json.loads(Path("contracts/recipe.schema.json").read_text()))
