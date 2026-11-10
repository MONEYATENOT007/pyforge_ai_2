import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from pyforge.cli import main
from pyforge.training.curation import prepare_dataset


TASKS = Path(__file__).resolve().parents[1] / "pyforge/evaluation/tasks.json"


def examples() -> list[dict]:
    base = {
        "task_type": "explanation", "source": "owner-authored synthetic fixture",
        "license": "owner_authorized", "reviewed_by": "test-reviewer",
        "reviewed_at": "2026-11-10T12:00:00+05:30", "review_status": "approved",
        "verification_status": "human_reviewed",
    }
    return [
        {**base, "id": "a", "family_id": "family-a", "task_type": "code",
         "prompt": "Implement add_one(x).", "response": "def add_one(x): return x + 1",
         "split": "train", "verification_status": "isolated_test_passed",
         "verification_reference": "synthetic-test-report-a"},
        {**base, "id": "b", "family_id": "family-b", "prompt": "Explain Python slices.",
         "response": "A slice selects a range.", "split": "validation"},
        {**base, "id": "c", "family_id": "family-c", "prompt": "Explain Python generators.",
         "response": "They yield values lazily.", "split": "held_out"},
    ]


class TrainingCurationTests(unittest.TestCase):
    def test_prepares_reviewed_splits_without_exporting_held_out_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "candidates.json"
            source.write_text(json.dumps(examples()), encoding="utf-8")
            output = root / "prepared"
            manifest = prepare_dataset(source, TASKS, output)
            self.assertEqual(manifest["counts"], {"train": 1, "validation": 1, "held_out": 1})
            self.assertEqual(manifest["source_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            train = json.loads((output / "train.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(train["messages"][1]["content"], examples()[0]["response"])
            self.assertEqual(train["provenance"]["verification_reference"], "synthetic-test-report-a")
            self.assertNotIn("Explain Python generators.", "".join(
                file.read_text(encoding="utf-8") for file in output.iterdir()
            ))
            self.assertEqual(len(manifest["held_out_prompt_sha256"]), 1)
            self.assertEqual(json.loads((output / "manifest.json").read_text(encoding="utf-8"))["files_sha256"],
                             manifest["files_sha256"])
            with self.assertRaises(FileExistsError):
                prepare_dataset(source, TASKS, output)

    def test_rejects_unreviewed_code_and_missing_rights_before_output(self):
        for edit in (
            {"review_status": "candidate"},
            {"license": "unknown"},
            {"verification_status": "human_reviewed"},
            {"verification_reference": ""},
            {"reviewed_at": "2026-11-10T12:00:00"},
        ):
            with self.subTest(edit=edit), tempfile.TemporaryDirectory() as temp:
                rows = examples()
                rows[0].update(edit)
                source = Path(temp) / "candidates.json"
                source.write_text(json.dumps(rows), encoding="utf-8")
                output = Path(temp) / "prepared"
                with self.assertRaises(ValueError):
                    prepare_dataset(source, TASKS, output)
                self.assertFalse(output.exists())

    def test_rejects_prompt_and_family_leakage(self):
        task_prompt = json.loads(TASKS.read_text(encoding="utf-8"))[0]["prompt"]
        for edit in (
            {"prompt": "  IMPLEMENT  add_one(x).  "},
            {"family_id": "family-a"},
            {"prompt": task_prompt},
        ):
            with self.subTest(edit=edit), tempfile.TemporaryDirectory() as temp:
                rows = examples()
                rows[1].update(edit)
                source = Path(temp) / "candidates.json"
                source.write_text(json.dumps(rows), encoding="utf-8")
                output = Path(temp) / "prepared"
                with self.assertRaises(ValueError):
                    prepare_dataset(source, TASKS, output)
                self.assertFalse(output.exists())

    def test_cli_requires_all_splits(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "candidates.json"
            source.write_text(json.dumps(examples()[:2]), encoding="utf-8")
            output = Path(temp) / "prepared"
            self.assertEqual(main(["curate-data", "--input", str(source), "--output", str(output)]), 2)
            self.assertFalse(output.exists())

    def test_cli_writes_manifest_from_explicit_reviewed_file(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "candidates.json"
            source.write_text(json.dumps(examples()), encoding="utf-8")
            output = Path(temp) / "prepared"
            self.assertEqual(main(["curate-data", "--input", str(source), "--output", str(output)]), 0)
            self.assertEqual(json.loads((output / "manifest.json").read_text(encoding="utf-8"))["counts"],
                             {"train": 1, "validation": 1, "held_out": 1})
