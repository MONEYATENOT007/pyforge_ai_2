"""Validate reviewed examples and emit split training data without running code."""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from pyforge.evaluation.runner import load_tasks


MAX_SOURCE_BYTES = 10_000_000
SPLITS = {"train", "validation", "held_out"}
TASK_TYPES = {"code", "explanation"}


def _fingerprint(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return hashlib.sha256(re.sub(r"\s+", " ", normalized).strip().encode("utf-8")).hexdigest()


def _required_text(row: dict, key: str, number: int) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"example {number}: {key} must be nonempty text")
    return value.strip() if key not in {"prompt", "response"} else value


def _validated_rows(rows: object, evaluation_prompts: set[str]) -> list[dict]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("candidate file must contain a nonempty JSON list")
    seen_ids: set[str] = set()
    seen_prompts: set[str] = set()
    family_splits: dict[str, str] = {}
    validated = []
    for number, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"example {number}: expected an object")
        item = {key: _required_text(row, key, number) for key in (
            "id", "family_id", "task_type", "prompt", "response", "source",
            "license", "reviewed_by", "reviewed_at", "review_status",
            "verification_status", "split",
        )}
        if item["id"] in seen_ids:
            raise ValueError(f"duplicate example id: {item['id']}")
        seen_ids.add(item["id"])
        if item["task_type"] not in TASK_TYPES:
            raise ValueError(f"example {number}: unsupported task_type")
        if item["split"] not in SPLITS:
            raise ValueError(f"example {number}: unsupported split")
        if item["review_status"] != "approved":
            raise ValueError(f"example {number}: human approval is required")
        if item["license"].casefold() in {"unknown", "unverified", "none"}:
            raise ValueError(f"example {number}: usage rights must be identified")
        try:
            reviewed_at = datetime.fromisoformat(item["reviewed_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"example {number}: reviewed_at must be an ISO 8601 timestamp") from exc
        if reviewed_at.tzinfo is None:
            raise ValueError(f"example {number}: reviewed_at needs a timezone")
        if item["task_type"] == "code" and item["verification_status"] != "isolated_test_passed":
            raise ValueError(f"example {number}: code requires an isolated passing test")
        if item["task_type"] == "explanation" and item["verification_status"] not in {"human_reviewed", "isolated_test_passed"}:
            raise ValueError(f"example {number}: explanation requires recorded review")
        if item["verification_status"] == "isolated_test_passed":
            item["verification_reference"] = _required_text(row, "verification_reference", number)
        prompt_hash = _fingerprint(item["prompt"])
        if prompt_hash in seen_prompts:
            raise ValueError(f"example {number}: duplicate prompt")
        seen_prompts.add(prompt_hash)
        if item["split"] != "held_out" and prompt_hash in evaluation_prompts:
            raise ValueError(f"example {number}: prompt overlaps the evaluation task bank")
        previous = family_splits.setdefault(item["family_id"], item["split"])
        if previous != item["split"]:
            raise ValueError(f"example {number}: family_id crosses data splits")
        item["prompt_sha256"] = prompt_hash
        validated.append(item)
    return validated


def prepare_dataset(source: Path, evaluation_tasks: Path, output_dir: Path) -> dict:
    """Write new train/validation JSONL and a manifest; held-out text stays in source."""
    if output_dir.exists():
        raise FileExistsError(f"Refusing to replace existing dataset: {output_dir}")
    if source.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("candidate file exceeds 10 MB review limit")
    source_bytes = source.read_bytes()
    task_bytes = evaluation_tasks.read_bytes()
    tasks = load_tasks(evaluation_tasks)
    evaluation_prompts = {_fingerprint(task["prompt"]) for task in tasks}
    rows = _validated_rows(json.loads(source_bytes), evaluation_prompts)
    counts = Counter(row["split"] for row in rows)
    if any(counts[split] == 0 for split in SPLITS):
        raise ValueError("train, validation, and held_out each need an approved example")
    payloads = {}
    for split in ("train", "validation"):
        records = []
        for row in rows:
            if row["split"] == split:
                records.append({
                    "id": row["id"], "family_id": row["family_id"],
                    "messages": [{"role": "user", "content": row["prompt"]},
                                 {"role": "assistant", "content": row["response"]}],
                    "provenance": {key: row[key] for key in (
                        "source", "license", "reviewed_by", "reviewed_at",
                        "verification_status",
                    )},
                })
                if "verification_reference" in row:
                    records[-1]["provenance"]["verification_reference"] = row["verification_reference"]
        payloads[split + ".jsonl"] = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records).encode("utf-8")
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "evaluation_tasks_sha256": hashlib.sha256(task_bytes).hexdigest(),
        "counts": {split: counts[split] for split in ("train", "validation", "held_out")},
        "families": {split: len({row["family_id"] for row in rows if row["split"] == split}) for split in ("train", "validation", "held_out")},
        "files_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()},
        "held_out_prompt_sha256": [row["prompt_sha256"] for row in rows if row["split"] == "held_out"],
        "review_note": "Human approval and verification fields were checked; source claims were not independently verified by this command.",
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir()
    for name, data in payloads.items():
        (output_dir / name).write_bytes(data)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
