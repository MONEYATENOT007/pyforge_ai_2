"""Run two local, text-only Session 02 prompt probes; never execute model code."""

import json
from pathlib import Path

from pyforge.chat.service import stream_exchange
from pyforge.chat.store import ChatStore
from pyforge.evaluation.requirements import review_requirements
from pyforge.models.ollama_client import OllamaClient

MODEL = "qwen2.5-coder:1.5b-instruct-q4_K_M"
PAIRS = (("renamer_initial", "renamer_revision"),
         ("dashboard_initial", "dashboard_revision"))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    fixture = json.loads((root / "tests" / "fixtures" / "session02_cases.json").read_text(encoding="utf-8"))
    cases = {row["case_id"]: row for row in fixture["cases"]}
    output = root / "results" / "session02-gated-probes.json"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    store = ChatStore(root / "results" / "session02-gated-probes.sqlite3")
    client = OllamaClient(MODEL, context=4096, timeout=180)
    records = []
    for initial_name, correction_name in PAIRS:
        initial, correction = cases[initial_name], cases[correction_name]
        session = store.create_session(correction_name)
        store.add_message(session, "user", initial["prompt"])
        store.add_message(session, "assistant", initial["response"], model=MODEL, profile="General")
        for _ in stream_exchange(store, client, session, correction["prompt"], "General", 4096):
            pass
        generated = store.messages(session)[-1]
        records.append({
            "case_id": correction_name,
            "model": MODEL,
            "baseline_review": review_requirements(initial["prompt"], initial["response"]),
            "gated_review": review_requirements(correction["prompt"], generated["content"],
                                                 context=[initial["prompt"]]),
            "export": json.loads(store.export_json(session)),
            "runtime_execution": "not_run_no_isolated_executor",
        })
    with output.open("x", encoding="utf-8") as stream:
        json.dump({"probe_version": "session02-gated-v1", "records": records}, stream,
                  ensure_ascii=False, indent=2)
        stream.write("\n")
    for record in records:
        failures = [item["id"] for item in record["gated_review"]["requirements"] if item["status"] == "failed"]
        print(f"{record['case_id']}: static failures={failures}; runtime not run")
    print(f"Saved full responses and provenance to {output}")


if __name__ == "__main__":
    main()
