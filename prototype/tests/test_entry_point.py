"""``python -m spotlight`` has to start the game, not the walking skeleton.

Issue #14. A tester is handed one command. Before this, the obvious command ran
``core.game`` -- a blob of light in an empty grid -- and the game itself was
reachable only as ``python -m spikes.spike1``. Somebody following the README
played the wrong program and would have reported on a dot.

These tests pin the delegation rather than the window: opening a real window
here would be slow and would tell us nothing the display tests do not.
"""

import spotlight.__main__ as entry
from spikes import spike1


def test_entry_point_runs_the_game(monkeypatch):
    """The command a tester is given reaches the playable spike."""
    calls = []
    monkeypatch.setattr(spike1, "main", lambda argv=None: calls.append(argv) or 0)

    assert entry.main([]) == 0
    assert calls == [[]]


def test_scale_is_passed_through(monkeypatch):
    """--scale N still sets the window size; it is forwarded, not reinvented."""
    calls = []
    monkeypatch.setattr(spike1, "main", lambda argv=None: calls.append(argv) or 0)

    entry.main(["--scale", "4"])
    assert calls == [["--scale", "4"]]


def test_entry_point_does_not_reach_the_skeleton():
    """The skeleton is still tested, but nothing routes a player to it."""
    source = entry.__file__
    with open(source) as handle:
        text = handle.read()
    assert "core.game" not in text.replace("``core.game``", "")
    assert "Game()" not in text
