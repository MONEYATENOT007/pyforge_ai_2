"""Conservative AST checks. Candidate code is parsed, never imported or run."""

import ast
import re

from .static_review import MAX_CODE_CHARS, extract_python_code

CHECKER_VERSION = "session02-static-v2"


def _effective_prompt(prompt: str, context: list[str] | None) -> str:
    prompts = [*(context or []), prompt]
    anchors = ("task manager", "performance window", "make me an app", "bulk file renamer",
               "file renamer", "code to sort", "sort a list")
    current = prompt.lower()
    if not any(anchor in current for anchor in anchors) and not re.search(
        r"\b(?:above code|previous response|earlier code|your code|that code|fix|debug|traceback|nameerror|not use pyqt|just use tkinter|doesn't|doesnt|still broken)\b",
        current,
    ):
        return prompt
    start = next((i for i in range(len(prompts) - 1, -1, -1)
                  if any(anchor in prompts[i].lower() for anchor in anchors)), len(prompts) - 1)
    return "\n".join(prompts[start:])


def extract_requirements(prompt: str, context: list[str] | None = None) -> list[dict]:
    """Small, explicit checklist for known prompt families, including correction turns."""
    text = _effective_prompt(prompt, context).lower()
    if ("task manager" in text or "performance window" in text or "performance dashboard" in text or
            ("gpu" in text and "cpu" in text and "ram" in text and
             ("graph" in text or "monitor" in text))):
        criteria = [
            ("tkinter_only", "Use Tkinter and exclude PyQt when requested", "explicit"),
            ("cpu_metric", "Show CPU utilization from a CPU source", "explicit"),
            ("ram_metric", "Show RAM utilization from a memory source", "explicit"),
            ("gpu_metric", "Use a GPU source or report unavailable", "explicit"),
            ("live_graphs", "Render historical live usage graphs", "explicit"),
            ("nonblocking_updates", "Keep periodic GUI updates non-blocking", "inferred"),
            ("unresolved_references", "Resolve names used by the application", "inferred"),
            ("invalid_literal_conversion", "Avoid known invalid literal conversions", "inferred"),
        ]
    elif ("renam" in text and ("tkinter" in text or "preview" in text)):
        criteria = [
            ("tkinter_ui", "Use Tkinter for the application", "explicit"),
            ("folder_select", "Let the user select a root folder", "explicit"),
            ("gui_file_preview", "Populate an in-GUI file preview", "explicit"),
            ("gui_name_edit", "Edit proposed names inside the GUI", "inferred"),
            ("preview_before_apply", "Show proposed changes before renaming", "inferred"),
            ("confirmation", "Confirm before bulk rename", "inferred"),
            ("collision_guard", "Avoid silent overwrite or duplicate target names", "inferred"),
        ]
    elif "sort" in text and ("list" in text or "elements" in text):
        criteria = [
            ("sort_list", "Sort the list", "explicit"),
            ("no_builtin_sort", "Do not call sort() or sorted()", "explicit"),
        ]
    else:
        criteria = []
    return [{"id": key, "criterion": criterion, "origin": origin} for key, criterion, origin in criteria]


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _reachable_callbacks(tree: ast.AST) -> set[str]:
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    roots = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg == "command" and isinstance(keyword.value, ast.Name):
                roots.add(keyword.value.id)
    pending = list(roots)
    visited = set()
    calls = set()
    while pending:
        name = pending.pop()
        if name in visited or name not in functions:
            continue
        visited.add(name)
        for node in ast.walk(functions[name]):
            if isinstance(node, ast.Call):
                called = _call_name(node)
                calls.add(called)
                if called in functions:
                    pending.append(called)
    return calls


def _widgets_and_writes(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    widget_names = set()
    widget_types = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or _call_name(value) not in {"Listbox", "Treeview", "Text", "Entry"}:
            continue
        widget_types.add(_call_name(value))
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                widget_names.add(target.id)
            elif isinstance(target, ast.Attribute):
                widget_names.add(target.attr)
    writes = set()
    reads = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        receiver = node.func.value
        receiver_name = receiver.id if isinstance(receiver, ast.Name) else receiver.attr if isinstance(receiver, ast.Attribute) else ""
        if receiver_name in widget_names:
            if node.func.attr in {"insert", "set", "item"}:
                writes.add(receiver_name)
            if node.func.attr in {"get", "selection", "curselection"}:
                reads.add(receiver_name)
    return widget_types, writes, reads


def _unresolved_special_names(tree: ast.AST) -> list[str]:
    bound = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            bound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            bound.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            bound.update(target.id for target in node.targets if isinstance(target, ast.Name))
    watched = {"matplotlib", "QTimer"}
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    return sorted((used & watched) - bound)


def review_requirements(prompt: str, response: str, *, context: list[str] | None = None) -> dict:
    """Return static evidence and failures; never report runtime verification."""
    checklist = extract_requirements(prompt, context)
    code = extract_python_code(response).strip()
    if len(code) > MAX_CODE_CHARS:
        return {"checker_version": CHECKER_VERSION, "syntax": "unknown", "reason": "code exceeds static review limit",
                "requirements": [{**item, "status": "unknown", "evidence": "not inspected"} for item in checklist]}
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return {"checker_version": CHECKER_VERSION, "syntax": "failed", "reason": "Python did not parse",
                "requirements": [{**item, "status": "unknown", "evidence": "source did not parse"} for item in checklist]}

    nodes = list(ast.walk(tree))
    call_nodes = [node for node in nodes if isinstance(node, ast.Call)]
    calls = {_call_name(node) for node in call_nodes}
    imports = [alias.name for node in nodes if isinstance(node, ast.Import) for alias in node.names]
    imports += [node.module for node in nodes if isinstance(node, ast.ImportFrom) and node.module]
    has_tk = any(name == "tkinter" or name.startswith("tkinter.") for name in imports)
    has_qt = any(name.startswith(("PyQt", "PySide")) for name in imports)
    callbacks = _reachable_callbacks(tree)
    widgets, writes, reads = _widgets_and_writes(tree)
    unresolved = _unresolved_special_names(tree)
    literal_errors = []
    for scope in [node for node in nodes if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        assignments = {}
        for node in ast.walk(scope):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments.setdefault(target.id, set()).add(
                            node.value.value if isinstance(node.value, ast.Constant) else None
                        )
        for node in ast.walk(scope):
            if not isinstance(node, ast.Call) or _call_name(node) != "float" or not node.args:
                continue
            argument = node.args[0]
            values = {argument.value} if isinstance(argument, ast.Constant) else (
                assignments.get(argument.id, set()) if isinstance(argument, ast.Name) else set()
            )
            if values and all(isinstance(value, str) and value.endswith("%") for value in values):
                literal_errors.append(node)
    blocking_cpu = [node for node in call_nodes if _call_name(node) == "cpu_percent" and
                    any(keyword.arg == "interval" and isinstance(keyword.value, ast.Constant) and
                        isinstance(keyword.value.value, (int, float)) and keyword.value.value > 0
                        for keyword in node.keywords)]
    gpu_cpu_source = any(
        isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and _call_name(node.value) == "cpu_percent"
        and any(isinstance(target, ast.Name) and "gpu" in target.id.lower() for target in node.targets)
        for node in nodes
    )
    folder_rename = "askdirectory" in callbacks and "rename" in callbacks
    graph_draw = bool(calls & {"plot", "create_line"})
    graph_history = bool(calls & {"append", "extend"})
    model_claims = response.replace(code, "")
    tkinter_only = bool(re.search(r"(tkinter\s+only|just\s+use\s+tkinter|not\s+use\s+pyqt|only\s+tkinter)", _effective_prompt(prompt, context), re.I))

    def assess(item: dict) -> dict:
        key = item["id"]
        status, evidence = "unknown", "Runtime behavior was not checked"
        if key == "no_builtin_sort":
            status, evidence = ("failed", "sorted() or sort() call found") if calls & {"sort", "sorted"} else (
                "static_evidence", "No sorted() or sort() call found in parsed code")
        elif key == "tkinter_ui":
            if has_qt and tkinter_only:
                status, evidence = "failed", "PyQt/PySide import violates the Tkinter-only instruction"
            elif has_tk:
                status, evidence = "static_evidence", "Tkinter import found; GUI behavior unverified"
        elif key == "folder_select" and "askdirectory" in calls:
            status, evidence = "static_evidence", "Folder chooser call found"
        elif key == "gui_file_preview":
            if "print" in callbacks and not writes:
                status, evidence = "failed", "Callback prints file names; no GUI preview population found"
            elif widgets & {"Listbox", "Treeview", "Text"} and not writes:
                status, evidence = "failed", "Preview widget is constructed but never populated"
            elif writes and widgets & {"Listbox", "Treeview", "Text"}:
                status, evidence = "static_evidence", "Widget write found; displayed values remain unverified"
        elif key == "gui_name_edit":
            if "input" in callbacks:
                status, evidence = "failed", "Console input() is reachable from a GUI callback"
            elif reads and widgets & {"Entry", "Text"}:
                status, evidence = "static_evidence", "GUI input read found; edit behavior unverified"
        elif key == "preview_before_apply":
            if folder_rename:
                status, evidence = "failed", "Folder-selection callback reaches rename before a separate apply step"
            elif "rename" in calls and not writes:
                status, evidence = "failed", "Rename call found without GUI preview population"
        elif key == "confirmation":
            if calls & {"askyesno", "askokcancel", "askquestion"}:
                status, evidence = "static_evidence", "Confirmation dialog call found; control flow unverified"
            elif "rename" in calls:
                status, evidence = "failed", "Rename call found without confirmation dialog"
        elif key == "collision_guard" and "rename" in calls:
            status, evidence = "unknown", "Collision safety needs data-flow and disposable-file tests"
        elif key == "tkinter_only":
            if has_qt and tkinter_only:
                status, evidence = "failed", "PyQt/PySide import violates the current Tkinter-only instruction"
            elif has_tk and not has_qt:
                status, evidence = "static_evidence", "Tkinter import found and no PyQt/PySide import found"
        elif key == "cpu_metric" and "cpu_percent" in calls:
            status, evidence = "static_evidence", "CPU source call found; values unverified"
        elif key == "ram_metric" and "virtual_memory" in calls:
            status, evidence = "static_evidence", "Memory source call found; values unverified"
        elif key == "gpu_metric":
            if gpu_cpu_source:
                status, evidence = "failed", "GPU variable is assigned from psutil.cpu_percent()"
            elif calls & {"nvmlDeviceGetUtilizationRates", "nvidia_smi", "query_gpu"}:
                status, evidence = "static_evidence", "GPU-specific source call found; values unverified"
        elif key == "live_graphs":
            if not graph_draw:
                status, evidence = "failed", "No graph drawing call found"
            elif "clear" in calls and not graph_history:
                status, evidence = "failed", "Graph is cleared and redrawn without historical samples"
            elif graph_history:
                status, evidence = "static_evidence", "Historical sample append and graph drawing found; live behavior unverified"
        elif key == "nonblocking_updates":
            if blocking_cpu:
                status, evidence = "failed", "Positive cpu_percent(interval=...) blocks a GUI update"
            elif calls & {"after", "start"}:
                status, evidence = "unknown", "Timer call found; callback scheduling requires further review"
        elif key == "unresolved_references" and unresolved:
            status, evidence = "failed", "Unbound reference(s): " + ", ".join(unresolved)
        elif key == "invalid_literal_conversion" and literal_errors:
            status, evidence = "failed", "float() receives a percent-suffixed string literal"
        result = {**item, "status": status, "evidence": evidence}
        if status == "failed" and (
            (key == "gui_file_preview" and "preview" in model_claims.lower()) or
            (key == "tkinter_only" and "tkinter" in model_claims.lower())
        ):
            result["claim_conflict"] = True
        return result

    return {"checker_version": CHECKER_VERSION, "syntax": "static_evidence",
            "reason": "AST parse succeeded; no code was run",
            "requirements": [assess(item) for item in checklist]}
