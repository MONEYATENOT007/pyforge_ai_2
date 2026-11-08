"""Conservative, non-executing checks for user-visible coding requirements."""

import ast

from .static_review import CODE_FENCE, MAX_CODE_CHARS


def extract_requirements(prompt: str) -> list[dict]:
    """Return a small human-reviewable checklist for recognized prompt families."""
    text = prompt.lower()
    if "sort" in text and ("list" in text or "elements" in text):
        return [
            {"id": "sort_list", "criterion": "Sort the list", "origin": "explicit"},
            {"id": "no_builtin_sort", "criterion": "Do not call sort() or sorted()", "origin": "explicit"},
        ]
    if "tkinter" in text and ("rename" in text or "renamer" in text):
        criteria = [
            ("tkinter_ui", "Use Tkinter for the application", "explicit"),
            ("folder_select", "Let the user select a root folder", "explicit"),
            ("gui_file_preview", "Display file preview inside the GUI", "explicit"),
            ("gui_name_edit", "Edit proposed names inside the GUI", "inferred"),
            ("preview_before_apply", "Show proposed changes before renaming", "inferred"),
            ("confirmation", "Confirm before bulk rename", "inferred"),
            ("collision_guard", "Avoid silent overwrite or duplicate target names", "inferred"),
        ]
        return [{"id": key, "criterion": criterion, "origin": origin} for key, criterion, origin in criteria]
    return []


def review_requirements(prompt: str, response: str) -> dict:
    """Static evidence only. Never imports or executes generated Python."""
    checklist = extract_requirements(prompt)
    match = CODE_FENCE.search(response)
    code = (match.group(1) if match else response).strip()
    if len(code) > MAX_CODE_CHARS:
        return {"syntax": "unknown", "reason": "code exceeds static review limit", "requirements": [
            {**item, "status": "unknown", "evidence": "not inspected"} for item in checklist]}
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return {"syntax": "failed", "reason": "Python did not parse", "requirements": [
            {**item, "status": "unknown", "evidence": "source did not parse"} for item in checklist]}

    calls: set[str] = set()
    imports: set[str] = set()
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    callback_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
            for keyword in node.keywords:
                if keyword.arg == "command" and isinstance(keyword.value, ast.Name):
                    callback_roots.add(keyword.value.id)

    callback_calls: set[str] = set()
    pending = list(callback_roots)
    visited: set[str] = set()
    while pending:
        name = pending.pop()
        if name in visited or name not in functions:
            continue
        visited.add(name)
        for node in ast.walk(functions[name]):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    callback_calls.add(node.func.id)
                    if node.func.id in functions:
                        pending.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    callback_calls.add(node.func.attr)

    def assess(item: dict) -> dict:
        key = item["id"]
        status, evidence = "unknown", "Runtime behavior was not checked"
        if key == "no_builtin_sort":
            if "sorted" in calls or "sort" in calls:
                status, evidence = "failed", "AST contains a sorted() or sort() call"
            else:
                status, evidence = "static_evidence", "No sorted() or sort() call found in parsed code"
        elif key == "sort_list":
            if any(isinstance(node, ast.FunctionDef) for node in ast.walk(tree)):
                status, evidence = "unknown", "Function present; ordering and edge cases require isolated tests"
        elif key == "tkinter_ui":
            if any(name == "tkinter" or name.startswith("tkinter.") for name in imports):
                status, evidence = "static_evidence", "Tkinter import found"
        elif key == "folder_select" and "askdirectory" in calls:
            status, evidence = "static_evidence", "Folder chooser call found"
        elif key == "gui_file_preview":
            if calls & {"Listbox", "Treeview", "Text"}:
                status, evidence = "static_evidence", "GUI list/table widget constructor found; population unverified"
            elif "print" in callback_calls:
                status, evidence = "failed", "Console print() is reachable from a GUI callback; no file list/table widget found"
        elif key == "gui_name_edit":
            if calls & {"Entry", "simpledialog", "askstring"}:
                status, evidence = "static_evidence", "GUI input widget/dialog found; edit behavior unverified"
            elif "input" in callback_calls:
                status, evidence = "failed", "Console input() is reachable from a GUI callback; no GUI name entry found"
        elif key == "preview_before_apply":
            if "rename" in calls and not (calls & {"Listbox", "Treeview", "Text"}):
                status, evidence = "failed", "Rename call exists without an in-GUI preview widget"
        elif key == "confirmation":
            if calls & {"askyesno", "askokcancel", "askquestion"}:
                status, evidence = "static_evidence", "Confirmation dialog call found; control flow unverified"
            elif "rename" in calls:
                status, evidence = "failed", "Rename call found without confirmation dialog"
        elif key == "collision_guard":
            if "rename" in calls:
                status, evidence = "unknown", "Overwrite protection requires control-flow and filesystem tests"
        return {**item, "status": status, "evidence": evidence}

    return {"syntax": "static_evidence", "reason": "AST parse succeeded; code was not run",
            "requirements": [assess(item) for item in checklist]}
