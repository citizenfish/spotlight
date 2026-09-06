"""The core must stay host-independent, or the port gets much harder."""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = ROOT / "spotlight" / "core"
SPIKES = ROOT / "spikes"
FORBIDDEN = {"pygame", "numpy"}


def _portable_sources():
    """Everything that has to survive the port to Z80.

    That is all of core/, plus the spikes' logic modules. Anything named
    spike* is exempt: the entry points (spike1.py ...) and the host drivers
    beside them (spike_buzz.py) are the throwaway Pygame layer, the equivalent
    of frontend/, and the port replaces them wholesale.

    The split is worth keeping honest. The buzz, for instance, is two files on
    purpose: deciding how loud it should be is portable and integer, and making
    the noise is not.
    """
    yield from CORE.rglob("*.py")
    if SPIKES.is_dir():
        yield from (p for p in SPIKES.rglob("*.py")
                    if not p.name.startswith("spike"))


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
    for path in _portable_sources():
        bad = _imported_modules(path) & FORBIDDEN
        if bad:
            offenders[path.name] = sorted(bad)
    assert not offenders, f"portable code must not import host libraries: {offenders}"


def test_core_uses_no_float_literals():
    """Floats do not exist on a Z80. Catch them before they spread."""
    offenders = []
    for path in _portable_sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, f"float literals in portable code: {offenders}"
