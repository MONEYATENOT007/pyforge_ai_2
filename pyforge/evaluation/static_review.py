"""Non-executing checks for benchmark output. No generated code is imported or run."""

import ast
import json
from pathlib import Path
import re


# Names explicitly requested by the fixed prompt set. This is a narrow check,
# not a correctness oracle: a function can exist and still be wrong.
REQUIRED_NAMES = {
    "core_sum_even": ("sum_even",),
    "core_unique_order": ("unique_in_order",),
    "core_chunk": ("chunks",),
    "core_flatten": ("flatten_once",),
    "core_counter": ("Counter",),
    "core_lru": ("LRUCache",),
    "edge_parse_int": ("parse_positive_int",),
    "edge_median": ("median",),
    "edge_safe_divide": ("safe_divide",),
    "edge_slug": ("slugify_ascii",),
    "debug_mutable_default": ("append_item",),
    "debug_unbound_local": ("choose",),
    "refactor_duplicate": ("upper_name", "lower_name"),
    "refactor_branch": ("status",),
    "automation_atomic_text": ("atomic_write_text",),
}

CODE_FENCE = re.compile(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", re.IGNORECASE | re.DOTALL)
MAX_CODE_CHARS = 100_000


def review_output(task_id: str, output: str) -> dict:
    if not isinstance(output, str):
        return {"task_id": task_id, "code_found": False, "ast_parse_ok": False, "reason": "missing text"}
    match = CODE_FENCE.search(output)
    code = match.group(1) if match else output
    code = code.strip()
    if not code:
        return {"task_id": task_id, "code_found": False, "ast_parse_ok": False, "reason": "empty code"}
    if len(code) > MAX_CODE_CHARS:
        return {"task_id": task_id, "code_found": True, "ast_parse_ok": False, "reason": "code exceeds static review limit"}
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError) as exc:
        return {"task_id": task_id, "code_found": True, "ast_parse_ok": False, "reason": type(exc).__name__}
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    required = REQUIRED_NAMES.get(task_id, ())
    missing = sorted(set(required) - names)
    return {"task_id": task_id, "code_found": True, "ast_parse_ok": True, "required_names": list(required), "missing_names": missing, "note": "AST parsing and name presence do not establish runtime correctness"}


def review_file(results: Path, output: Path, valid_task_ids: set[str]) -> tuple[int, int, int]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing review: {output}")
    rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = set()
    for row in rows:
        task_id = row.get("task_id") if isinstance(row, dict) else None
        if task_id not in valid_task_ids or task_id in seen:
            raise ValueError(f"Unknown or duplicate task id in results: {task_id}")
        seen.add(task_id)
    reviews = [review_output(row["task_id"], row.get("raw_output")) for row in rows]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        for review in reviews:
            stream.write(json.dumps(review, ensure_ascii=False) + "\n")
    parsed = sum(bool(item["ast_parse_ok"]) for item in reviews)
    missing = sum(bool(item.get("missing_names")) for item in reviews)
    return len(reviews), parsed, missing
