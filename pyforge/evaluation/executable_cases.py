"""Select reviewed, narrowly scoped checks for a chat response."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

_PYTHON_BLOCK = re.compile(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", re.IGNORECASE | re.DOTALL)
_SORT_NAMES = ("sort_numbers", "bubble_sort", "sort_list", "sort_array", "sort_values", "sort")


@dataclass(frozen=True)
class ExecutableCase:
    code: str
    tests: str
    label: str
    contract: str


def prepare_sort_case(response: str) -> ExecutableCase | None:
    """Find one self-contained Python block with a recognized sorting function.

    This checks only a returned ascending list. It does not infer the user's
    full requirements or promise correctness beyond its five reviewed cases.
    """
    blocks = _PYTHON_BLOCK.findall(response)
    if len(blocks) == 1:
        code = blocks[0].strip()
    elif not blocks and response.lstrip().startswith(("def ", "import ", "from ")):
        code = response.strip()
    else:
        return None
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    name = next((name for name in _SORT_NAMES if name in functions), None)
    if name is None:
        return None
    args = functions[name].args
    if len(args.posonlyargs) + len(args.args) != 1 or args.vararg or args.kwarg or args.kwonlyargs:
        return None
    tests = f'''target = globals()[{name!r}]
for source, expected in [
    ([], []), ([4], [4]), ([3, 1, 2], [1, 2, 3]),
    ([2, 2, 1], [1, 2, 2]), ([-2, 5, 0, -2], [-2, -2, 0, 5]),
]:
    actual = target(list(source))
    assert actual == expected, f"{{source!r}} returned {{actual!r}}; expected {{expected!r}}"
'''
    return ExecutableCase(code, tests, "Ascending list sort: 5 cases",
                          f"Calls {name}(values) and expects a returned ascending list; "
                          "checks empty, singleton, ordinary, duplicate and negative inputs.")
