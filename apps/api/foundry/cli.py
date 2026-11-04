import json
import os
from pathlib import Path

import httpx
import typer
from datafoundry import DataFoundry

app = typer.Typer(help="Workspace-local AI Data Foundry CLI")
datasets = typer.Typer()
runs = typer.Typer()
recipes = typer.Typer()
curations = typer.Typer(help="Curation sessions and quality profiles")
annotations = typer.Typer(help="Human review queue and decisions")
app.add_typer(datasets, name="datasets")
app.add_typer(runs, name="runs")
app.add_typer(recipes, name="recipes")
app.add_typer(curations, name="curations")
app.add_typer(annotations, name="annotations")


def client():
    key = os.environ.get("FOUNDRY_API_KEY")
    if not key:
        raise typer.BadParameter("Set FOUNDRY_API_KEY to a scoped key from your workspace.")
    return DataFoundry(api_key=key, base_url=os.environ.get("FOUNDRY_API_URL", "http://localhost:8000"))


@app.command()
def doctor():
    response = httpx.get(
        os.environ.get("FOUNDRY_API_URL", "http://localhost:8000") + "/v1/health/ready", timeout=10
    )
    typer.echo(json.dumps(response.json(), indent=2))
    if response.is_error:
        raise typer.Exit(1)


@app.command()
def auth():
    with client() as api:
        typer.echo(json.dumps(api.request("GET", "/v1/me"), indent=2))


@datasets.command("list")
def list_datasets():
    with client() as api:
        for value in api.datasets.list():
            typer.echo(f"{value.id}\t{value.name}")


@datasets.command("create")
def create_dataset(name: str, project: str, permit_training: bool = False):
    with client() as api:
        result = api.datasets.create(
            name=name,
            project_id=project,
            policy={
                "origin": "local",
                "allowed_training_use": permit_training,
                "license": "user-declared-local",
            },
        )
        typer.echo(result.model_dump_json())


@datasets.command("upload")
def upload_dataset(dataset_id: str, path: Path):
    with client() as api:
        typer.echo(json.dumps(api.datasets.upload(dataset_id, path)))


@datasets.command("export")
def export_dataset(version_id: str, output: Path, format: str = "jsonl"):
    with client() as api:
        typer.echo(str(api.datasets.download(version_id, output, format=format)))


@recipes.command("validate")
def validate_recipe(path: Path):
    with client() as api:
        typer.echo(json.dumps(api.recipes.validate(json.loads(path.read_text()))))


@recipes.command("create")
def create_recipe(path: Path, project: str):
    with client() as api:
        typer.echo(
            api.recipes.create(project_id=project, definition=json.loads(path.read_text())).model_dump_json()
        )


@runs.command("submit")
def submit_run(dataset: str, revision: str, budget: float = 1):
    with client() as api:
        typer.echo(
            api.runs.create(
                dataset_id=dataset, recipe_revision_id=revision, max_budget_usd=budget
            ).model_dump_json()
        )


@runs.command("watch")
def watch_run(run_id: str):
    with client() as api:
        result = api.runs.wait(run_id)
        typer.echo(result.model_dump_json())
        if result.status != "SUCCEEDED":
            raise typer.Exit(1)


@runs.command("cancel")
def cancel_run(run_id: str):
    with client() as api:
        typer.echo(json.dumps(api.runs.cancel(run_id)))


@curations.command("list")
def list_curations():
    with client() as api:
        for value in api.curations.list():
            typer.echo(value.model_dump_json())


@curations.command("get")
def get_curation(curation_id: str):
    with client() as api:
        typer.echo(api.curations.get(curation_id).model_dump_json())


@curations.command("profiles")
def list_profiles():
    with client() as api:
        for profile in api.quality_profiles.list():
            typer.echo(profile.model_dump_json())


@curations.command("create-profile")
def create_profile(path: Path):
    with client() as api:
        typer.echo(api.quality_profiles.create(**json.loads(path.read_text())).model_dump_json())


@curations.command("create")
def create_curation(path: Path):
    with client() as api:
        typer.echo(api.curations.create(**json.loads(path.read_text())).model_dump_json())


@curations.command("data-card")
def update_card(curation_id: str, revision: int, path: Path):
    with client() as api:
        typer.echo(
            api.curations.update_card(
                curation_id, expected_revision=revision, data_card=json.loads(path.read_text())
            ).model_dump_json()
        )


@curations.command("freeze")
def freeze_curation(curation_id: str, revision: int, approve_publication: bool = False):
    if not approve_publication:
        raise typer.BadParameter("Review the data card and quality report, then use --approve-publication.")
    with client() as api:
        typer.echo(
            api.curations.freeze(
                curation_id, expected_revision=revision, approved_for_publication=True
            ).model_dump_json()
        )


@annotations.command("list")
def list_annotations(curation_id: str | None = None):
    with client() as api:
        for task in api.annotations.list(curation_id=curation_id):
            typer.echo(task.model_dump_json())


@annotations.command("get")
def get_annotation(task_id: str):
    with client() as api:
        typer.echo(api.annotations.get(task_id).model_dump_json())


@annotations.command("decision")
def review_annotation(task_id: str, path: Path):
    with client() as api:
        typer.echo(api.annotations.review(task_id, **json.loads(path.read_text())).model_dump_json())


@annotations.command("assign")
def assign_annotation(task_id: str, revision: int, user_id: str):
    with client() as api:
        typer.echo(
            api.annotations.assign(task_id, expected_revision=revision, user_id=user_id).model_dump_json()
        )


@annotations.command("adjudicate")
def adjudicate_annotation(task_id: str, path: Path):
    with client() as api:
        typer.echo(api.annotations.adjudicate(task_id, **json.loads(path.read_text())).model_dump_json())


@annotations.command("reopen")
def reopen_annotation(task_id: str, revision: int, note: str):
    with client() as api:
        typer.echo(api.annotations.reopen(task_id, expected_revision=revision, note=note).model_dump_json())
