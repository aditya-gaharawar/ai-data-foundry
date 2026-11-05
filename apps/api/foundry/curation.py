"""Curation contracts and deterministic quality operators. No model inference."""

import io
import json
import re
import unicodedata
import zipfile
from collections import Counter
from typing import Literal

from jsonschema import Draft202012Validator
from pydantic import Field, FiniteFloat, model_validator
from sqlalchemy import select

from .errors import Problem
from .models import AnnotationReview, AnnotationTask, Dataset, QualityProfile
from .recipes import parse_jsonl
from .schemas import Strict
from .security import canonical, digest
from .storage import put_immutable, read_artifact

MAX_CURATION_SAMPLES = 500
MAX_CURATION_BYTES = 20 * 1024 * 1024
RESOLVED = {"ACCEPTED", "REJECTED", "ADJUDICATED", "EXCLUDED"}


class ProfileConfig(Strict):
    dedupe: Literal["none", "exact", "near"] = "exact"
    text_similarity: FiniteFloat = Field(default=0.85, ge=0.5, le=1)
    image_hamming_distance: int = Field(default=4, ge=0, le=8)
    minimum_samples: int = Field(default=1, ge=1, le=MAX_CURATION_SAMPLES)
    minimum_acceptance_ratio: FiniteFloat = Field(default=0.5, ge=0, le=1)
    max_duplicate_ratio: FiniteFloat = Field(default=0, ge=0, le=1)
    max_near_duplicate_ratio: FiniteFloat = Field(default=1, ge=0, le=1)


class QualityProfileCreate(Strict):
    name: str = Field(min_length=1, max_length=160)
    modality: Literal["text", "image"]
    config: ProfileConfig = Field(default_factory=ProfileConfig)


class DataCard(Strict):
    purpose: str = Field(min_length=1, max_length=4000)
    intended_use: str = Field(min_length=1, max_length=4000)
    limitations: str = Field(min_length=1, max_length=4000)
    content_risks: str = Field(min_length=1, max_length=4000)
    restrictions: str = Field(min_length=1, max_length=4000)


class CurationCreate(Strict):
    dataset_id: str
    profile_id: str
    name: str = Field(min_length=1, max_length=160)
    categories: list[str] = Field(min_length=1, max_length=100)
    required_reviews: Literal[1, 2] = 2
    source_version_id: str | None = None
    upload_ids: list[str] = Field(default_factory=list, max_length=100)
    data_card: DataCard | None = None

    @model_validator(mode="after")
    def validate_source(self):
        if bool(self.source_version_id) == bool(self.upload_ids):
            raise ValueError("Choose one published version or one or more completed uploads.")
        if len(set(self.upload_ids)) != len(self.upload_ids):
            raise ValueError("Upload IDs must be unique.")
        self.categories = [label.strip() for label in self.categories]
        if len(set(self.categories)) != len(self.categories) or any(
            not label or len(label) > 80 or any(ord(char) < 32 for char in label) for label in self.categories
        ):
            raise ValueError("Categories must be distinct nonempty names of at most 80 characters.")
        return self


class CardUpdate(Strict):
    expected_revision: int = Field(ge=1)
    data_card: DataCard


class FreezeCuration(Strict):
    expected_revision: int = Field(ge=1)
    approved_for_publication: Literal[True]


class TaskAssignment(Strict):
    expected_revision: int = Field(ge=1)
    user_id: str | None = None


class ReviewDecision(Strict):
    expected_revision: int = Field(ge=1)
    decision: Literal["accept", "reject"]
    annotation: dict | None = None
    note: str = Field(min_length=1, max_length=2000)


class TaskReopen(Strict):
    expected_revision: int = Field(ge=1)
    note: str = Field(min_length=1, max_length=2000)


class TextAnnotation(Strict):
    kind: Literal["category"]
    label: str = Field(min_length=1, max_length=80)


class BoundingBox(Strict):
    label: str = Field(min_length=1, max_length=80)
    x: FiniteFloat = Field(ge=0)
    y: FiniteFloat = Field(ge=0)
    width: FiniteFloat = Field(gt=0)
    height: FiniteFloat = Field(gt=0)


class ImageAnnotation(Strict):
    kind: Literal["boxes"]
    boxes: list[BoundingBox] = Field(max_length=100)


def validate_annotation(annotation: dict | None, payload: dict, modality: str, categories: list[str]) -> dict:
    from pydantic import ValidationError

    try:
        if modality == "text":
            value = TextAnnotation.model_validate(annotation)
            if value.label not in categories:
                raise ValueError("Choose a category from this curation's vocabulary.")
            return value.model_dump()
        value = ImageAnnotation.model_validate(annotation)
        image = payload["image"]
        for box in value.boxes:
            if (
                box.label not in categories
                or box.x + box.width > image["width"]
                or box.y + box.height > image["height"]
            ):
                raise ValueError("Every box must use a known category and fit inside the decoded image.")
        # Consensus is independent of the order in which the same boxes were drawn.
        return {"kind": "boxes", "boxes": sorted((box.model_dump() for box in value.boxes), key=canonical)}
    except (ValidationError, ValueError, KeyError, TypeError):
        raise Problem(
            422,
            "INVALID_ANNOTATION",
            "Use a known text category or finite positive pixel boxes within the decoded image bounds.",
        ) from None


def text_shingles(payload: dict) -> set[str]:
    text = " ".join(value for key, value in sorted(payload.items()) if isinstance(value, str))
    if len(text) > 10000:
        raise Problem(
            422, "CURATION_TEXT_LIMIT", "Curation supports at most 10,000 text characters per sample."
        )
    words = re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold())
    return {" ".join(words[index : index + 3]) for index in range(max(1, len(words) - 2))}


def duplicate_analysis(samples: list[dict], modality: str, config: dict) -> dict:
    """Stable, input-order representatives. Near matches are lexical/perceptual, never semantic."""
    profile = ProfileConfig.model_validate(config)
    representatives, exact, near = [], {}, {}
    seen = {}
    fingerprints = []
    for index, sample in enumerate(samples):
        payload = sample["payload"]
        key = payload["image"]["artifact"]["sha256"] if modality == "image" else digest(canonical(payload))
        fingerprint = int(payload["image"]["dhash"], 16) if modality == "image" else text_shingles(payload)
        fingerprints.append(fingerprint)
        if key in seen:
            exact[index] = seen[key]
            continue
        seen[key] = index
        for previous in representatives:
            if modality == "image":
                similar = (fingerprint ^ fingerprints[previous]).bit_count() <= profile.image_hamming_distance
            else:
                other = fingerprints[previous]
                similar = (
                    len(fingerprint & other) / max(1, len(fingerprint | other)) >= profile.text_similarity
                )
            if similar:
                near[index] = previous
                break
        if index not in near:
            representatives.append(index)
    excluded = {}
    if profile.dedupe in {"exact", "near"}:
        excluded.update(
            {
                str(index): {"reason": "exact_duplicate", "representative": other}
                for index, other in exact.items()
            }
        )
    if profile.dedupe == "near":
        excluded.update(
            {
                str(index): {"reason": "near_duplicate", "representative": other}
                for index, other in near.items()
            }
        )
    return {
        "total": len(samples),
        "exact_duplicates": len(exact),
        "near_duplicates": len(near),
        "excluded": excluded,
        "retained": len(samples) - len(excluded),
        "algorithm": "sha256 + token-trigram-jaccard/1"
        if modality == "text"
        else "normalized-png-sha256 + dhash64/1",
        "config": profile.model_dump(),
    }


def source_samples(curation) -> list[dict]:
    return parse_jsonl(read_artifact(curation.source_artifact))


def task_reviews(db, task) -> list:
    return list(
        db.scalars(
            select(AnnotationReview)
            .where(
                AnnotationReview.task_id == task.id, AnnotationReview.organization_id == task.organization_id
            )
            .order_by(AnnotationReview.task_revision)
        )
    )


def latest_votes(reviews: list, round_number: int) -> list:
    latest = {}
    for review in reviews:
        if review.round == round_number and review.decision in {"accept", "reject"}:
            latest[review.user_id] = review
    return list(latest.values())


def evaluate_curation(db, curation) -> tuple[dict, list[dict], list[dict]]:
    target = db.scalar(
        select(Dataset).where(
            Dataset.id == curation.dataset_id, Dataset.organization_id == curation.organization_id
        )
    )
    profile = db.scalar(
        select(QualityProfile).where(
            QualityProfile.id == curation.profile_id,
            QualityProfile.organization_id == curation.organization_id,
        )
    )
    config = ProfileConfig.model_validate(profile.config)
    samples = source_samples(curation)
    tasks = db.scalars(
        select(AnnotationTask)
        .where(
            AnnotationTask.curation_id == curation.id,
            AnnotationTask.organization_id == curation.organization_id,
        )
        .order_by(AnnotationTask.sample_index)
    ).all()
    reviews = db.scalars(
        select(AnnotationReview)
        .join(AnnotationTask, AnnotationReview.task_id == AnnotationTask.id)
        .where(
            AnnotationTask.curation_id == curation.id,
            AnnotationReview.organization_id == curation.organization_id,
        )
        .order_by(AnnotationReview.created_at, AnnotationReview.id)
    ).all()
    selected, history = [], []
    invalid_labels = 0
    validator = Draft202012Validator(target.sample_schema)
    for task in tasks:
        if task.accepted:
            sample = samples[task.sample_index]
            try:
                annotation = validate_annotation(
                    task.annotation, sample["payload"], target.modality, curation.categories
                )
            except Problem:
                invalid_labels += 1
                continue
            selected.append(
                {
                    **sample,
                    "sample_id": "smp_" + digest(task.id)[:32],
                    "annotation": annotation,
                    "review_status": task.status,
                    "annotation_task_id": task.id,
                }
            )
    for review in reviews:
        history.append(
            {
                "id": review.id,
                "task_id": review.task_id,
                "user_id": review.user_id,
                "api_key_id": review.api_key_id,
                "decision": review.decision,
                "annotation": review.annotation,
                "note": review.note,
                "round": review.round,
                "task_revision": review.task_revision,
                "created_at": review.created_at.isoformat(),
            }
        )
    pending = sum(task.status not in RESOLVED for task in tasks)
    invalid = sum(not validator.is_valid(sample["payload"]) for sample in selected)
    dupes = duplicate_analysis(selected, target.modality, profile.config)
    total = len(tasks)
    eligible = sum(task.status != "EXCLUDED" for task in tasks)
    acceptance = len(selected) / max(eligible, 1)
    card_ok = all(str(curation.data_card.get(key, "")).strip() for key in DataCard.model_fields)
    reasons = []
    from .policies import check_publication_policy, pii_transform

    try:
        governance = check_publication_policy(db, target, "curate")
        if (
            curation.dedupe_report.get("governance_policy_sha256", governance["sha256"])
            != governance["sha256"]
        ):
            reasons.append("Governance changed after intake. Create a curation under the current policy.")
        transformed, _ = pii_transform(
            [sample["payload"] for sample in selected], governance["definition"]["pii_mode"]
        )
        if transformed != [sample["payload"] for sample in selected]:
            reasons.append("Redaction would change reviewed data. Review a new curation after redaction.")
    except Problem as error:
        reasons.append(error.message)
    if pending or len(tasks) != len(samples):
        reasons.append("All nonduplicate tasks need completed independent reviews or adjudication.")
    if len(selected) < config.minimum_samples:
        reasons.append("Accepted sample count is below the quality profile minimum.")
    if acceptance < config.minimum_acceptance_ratio:
        reasons.append("Acceptance ratio is below the quality profile minimum.")
    if invalid or invalid_labels:
        reasons.append("Accepted payloads and annotations must all be valid.")
    if dupes["exact_duplicates"] / max(1, len(selected)) > config.max_duplicate_ratio:
        reasons.append("Remaining exact duplication exceeds the quality profile maximum.")
    if dupes["near_duplicates"] / max(1, len(selected)) > config.max_near_duplicate_ratio:
        reasons.append("Remaining near duplication exceeds the quality profile maximum.")
    if not card_ok:
        reasons.append("Complete every data card field before publication approval.")
    if target.policy.get("allowed_training_use") is not True or target.archived:
        reasons.append("The dataset must be active with declared source-use rights.")
    current_votes = [latest_votes([r for r in reviews if r.task_id == task.id], task.round) for task in tasks]
    paired = [votes for votes in current_votes if len(votes) == 2]
    agreements = sum(
        canonical((v[0].decision, v[0].annotation)) == canonical((v[1].decision, v[1].annotation))
        for v in paired
    )
    report = {
        "passed": not reasons,
        "reasons": reasons,
        "total": total,
        "eligible": eligible,
        "accepted": len(selected),
        "rejected": sum(task.accepted is False and task.status != "EXCLUDED" for task in tasks),
        "excluded": total - eligible,
        "pending": pending,
        "valid": len(selected) - invalid,
        "invalid": invalid,
        "invalid_annotations": invalid_labels,
        "acceptance_ratio": acceptance,
        "review_coverage": (eligible - pending) / max(1, eligible),
        "required_reviews": curation.required_reviews,
        "duplicates": dupes["exact_duplicates"],
        "duplicate_ratio": dupes["exact_duplicates"] / max(1, len(selected)),
        "near_duplicates": dupes["near_duplicates"],
        "source_deduplication": curation.dedupe_report,
        "status_counts": dict(Counter(task.status for task in tasks)),
        "agreement": {
            "paired_tasks": len(paired),
            "agreed": agreements,
            "ratio": agreements / len(paired) if paired else None,
        },
        "checks": [
            "json_schema",
            "annotation_bounds_and_vocabulary",
            "exact_deduplication",
            "near_deduplication",
            "independent_human_reviews",
            "data_card",
            "source_rights",
        ],
        "limitations": [
            "Human agreement does not establish ground-truth accuracy.",
            "Near duplicates use lexical shingles or perceptual dHash, not semantic equivalence.",
            "No PII, factuality, contamination or automated label model checks.",
        ],
    }
    return report, selected, history


def frozen_input(curation, target) -> tuple[list[dict], dict]:
    if curation.state != "FROZEN" or not curation.snapshot or curation.dataset_id != target.id:
        raise Problem(409, "CURATION_NOT_FROZEN", "Use an approved frozen curation for this dataset.")
    snapshot = json.loads(read_artifact(curation.snapshot))
    if not snapshot["quality"]["passed"] or snapshot["policy"].get("allowed_training_use") is not True:
        raise Problem(409, "CURATION_GATE_FAILED", "Frozen quality and rights evidence must pass.")
    for sample in snapshot["samples"]:
        validate_annotation(sample["annotation"], sample["payload"], target.modality, snapshot["categories"])
        if not Draft202012Validator(target.sample_schema).is_valid(sample["payload"]):
            raise Problem(
                422, "CURATION_SCHEMA_CHANGED", "The current dataset schema rejects a frozen sample."
            )
        if target.modality == "image":
            read_artifact(sample["payload"]["image"]["artifact"])
    return snapshot["samples"], snapshot


def image_exports(organization_id: str, samples: list[dict], categories: list[str], data_card: dict) -> dict:
    """Validated pixel COCO and normalized YOLO bundles, with identical real image bytes."""
    images, annotations, yolo = [], [], {}
    media = {}
    for index, sample in enumerate(samples, start=1):
        image = sample["payload"]["image"]
        annotation = validate_annotation(sample["annotation"], sample["payload"], "image", categories)
        filename = f"images/{sample['sample_id']}.png"
        media[filename] = read_artifact(image["artifact"])
        images.append(
            {"id": index, "file_name": filename, "width": image["width"], "height": image["height"]}
        )
        rows = []
        for box in annotation["boxes"]:
            category = categories.index(box["label"])
            annotations.append(
                {
                    "id": len(annotations) + 1,
                    "image_id": index,
                    "category_id": category + 1,
                    "bbox": [box["x"], box["y"], box["width"], box["height"]],
                    "area": box["width"] * box["height"],
                    "iscrowd": 0,
                }
            )
            rows.append(
                f"{category} {(box['x'] + box['width'] / 2) / image['width']:.12g} {(box['y'] + box['height'] / 2) / image['height']:.12g} {box['width'] / image['width']:.12g} {box['height'] / image['height']:.12g}"
            )
        yolo[f"labels/{sample['sample_id']}.txt"] = ("\n".join(rows) + ("\n" if rows else "")).encode()
    coco = {
        "images": images,
        "annotations": annotations,
        "categories": [{"id": index + 1, "name": name} for index, name in enumerate(categories)],
    }
    bundles = {
        "coco": {**media, "annotations.json": canonical(coco), "data-card.json": canonical(data_card)},
        "yolo": {
            **media,
            **yolo,
            "data.yaml": canonical({"path": ".", "train": "images", "names": categories}),
            "data-card.json": canonical(data_card),
        },
    }
    result = {}
    for kind, files in bundles.items():
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, raw)
        result[kind] = put_immutable(organization_id, output.getvalue(), "application/zip")
    return result
