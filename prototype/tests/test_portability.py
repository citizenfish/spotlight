"""The core must stay host-independent, or the port gets much harder."""

import ast
import pathlib

CORE = pathlib.Path(__file__).resolve().parents[1] / "spotlight" / "core"
FORBIDDEN = {"pygame", "numpy"}


def _imported_modules(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_core_imports_no_host_libraries():
    offenders = {}
    for path in CORE.rglob("*.py"):
        bad = _imported_modules(path) & FORBIDDEN
        if bad:
            offenders[path.name] = sorted(bad)
    assert not offenders, f"core must not import host libraries: {offenders}"


def test_core_uses_no_float_literals():
    """Floats do not exist on a Z80. Catch them before they spread."""
    offenders = []
    for path in CORE.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, f"float literals in core: {offenders}"
