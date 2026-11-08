"""Small structured event emitter. Never accepts prompt or response bodies."""

import json
import sys
from datetime import datetime, timezone


def emit(event: str, **fields: str | int | float | None) -> None:
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    print(json.dumps(record, ensure_ascii=False), file=sys.stderr)
