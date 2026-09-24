"""
chatddx's own tools: each file stands alone, git can name it by its blob, and
each function takes what its tool declares, by name, order, requirement, type
and default.
"""

import ast
import inspect
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from chatddx.repo.inventories import ParsedInventory
from chatddx.runtime import tools
from chatddx.runtime.implementation import blob_of, implementation

FILES = sorted(Path(tools.__file__).parent.glob("*.py"))


def imported(path: Path) -> list[str]:
    """What a file imports, a relative import by its leading dots."""
    names: list[str] = []

    for node in ast.walk(ast.parse(path.read_text())):
        match node:
            case ast.Import(names=aliases):
                names += [alias.name for alias in aliases]
            case ast.ImportFrom(module=module, level=level):
                names.append("." * level + (module or ""))
            case _:
                pass

    return names


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_a_tool_file_imports_nothing_else_of_chatddx_s(path: Path):
    assert [n for n in imported(path) if n.startswith(("chatddx", "."))] == []


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.name)
def test_a_tool_file_s_blob_is_the_one_git_gives_it(path: Path):
    git = subprocess.run(
        ["git", "hash-object", str(path)], capture_output=True, text=True, check=True
    )

    assert blob_of(path.read_bytes()) == git.stdout.strip()


def test_each_tool_takes_what_it_declares(test_inventory: ParsedInventory):
    for trail, details in test_inventory.tool.values():
        if details.implementation is None:
            continue

        function = implementation(details.implementation.entry_point).function
        parameters = inspect.signature(function).parameters
        schema: dict[str, Any] = trail.parameters
        declared: dict[str, Any] = schema.get("properties", {})
        required: set[str] = set(schema.get("required", []))

        assert list(parameters) == list(declared), trail.name

        for name, parameter in parameters.items():
            annotated = TypeAdapter(parameter.annotation).json_schema()
            default = declared[name].get("default", inspect.Parameter.empty)

            assert (parameter.default is inspect.Parameter.empty) == (
                name in required
            ), f"{trail.name}.{name}"
            assert annotated.get("type") == declared[name].get("type"), name
            assert parameter.default == default, f"{trail.name}.{name}"
