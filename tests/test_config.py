import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pyforge.config import load_storage


class StorageConfigTests(unittest.TestCase):
    def test_example_is_unconfigured_and_does_not_create_roots(self):
        with patch.dict(os.environ, {"PYFORGE_FAST_ROOT": "", "PYFORGE_BULK_ROOT": "", "PYFORGE_WORKSPACE_ROOT": ""}):
            config = load_storage("config/storage.example.json")
        self.assertIsNone(config.fast_root)
        self.assertIsNone(config.bulk_root)
        self.assertIsNone(config.workspace_root)

    def test_environment_overrides_file(self):
        with tempfile.TemporaryDirectory() as temp:
            config_file = Path(temp) / "storage.json"
            config_file.write_text(json.dumps({"fast_root": str(Path(temp) / "from_file")}), encoding="utf-8")
            target = Path(temp) / "from_env"
            with patch.dict(os.environ, {"PYFORGE_FAST_ROOT": str(target)}):
                config = load_storage(config_file)
            self.assertEqual(config.fast_root, target)
            self.assertFalse(target.exists())

    def test_invalid_type_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            config_file = Path(temp) / "storage.json"
            config_file.write_text('{"bulk_root": 42}', encoding="utf-8")
            with patch.dict(os.environ, {"PYFORGE_BULK_ROOT": ""}):
                with self.assertRaises(ValueError):
                    load_storage(config_file)
