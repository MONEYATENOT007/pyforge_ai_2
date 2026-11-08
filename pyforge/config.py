"""Small dependency-free configuration loader; never creates directories."""

from dataclasses import dataclass
import json
import os
from pathlib import Path


@dataclass(frozen=True)
class StorageConfig:
    fast_root: Path | None = None
    bulk_root: Path | None = None
    workspace_root: Path | None = None


def load_storage(path: str | Path | None = None) -> StorageConfig:
    source = Path(path) if path else Path("config/storage.json")
    raw = json.loads(source.read_text(encoding="utf-8")) if source.is_file() else {}
    if not isinstance(raw, dict):
        raise ValueError("storage config must be a JSON object")

    def setting(key: str, env: str) -> Path | None:
        value = os.environ.get(env) or raw.get(key)
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError(f"{key} must be a path string or null")
        return Path(value).expanduser().absolute()

    return StorageConfig(
        setting("fast_root", "PYFORGE_FAST_ROOT"),
        setting("bulk_root", "PYFORGE_BULK_ROOT"),
        setting("workspace_root", "PYFORGE_WORKSPACE_ROOT"),
    )
