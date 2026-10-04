"""A room's solidity bitmap is generated, like every other table (issue #153).

The same rule and the same reason as `test_bitmaps_tool.py`: the shell is
authored as a grid of `#` and `.` in `assets/levels/`, the Z80 reads 88 bytes,
and the only thing that can keep those two honest is regenerating one from the
other and comparing. A shell edited without regenerating fails here.

And one claim the bitmaps tool cannot make: **the bits the port reads say the
same thing as `Room.is_wall`**, cell for cell, which is what makes the picture
comparison in `test_port_room.py` a test of the drawing rather than of the data.
"""

import pathlib
import subprocess
import sys

import pytest

from spikes import building as B, levels
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import COLS

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "rooms.py"
TABLE = ROOT / "spectrum" / "src" / "rooms.asm"
LEVEL = ROOT / "assets" / "levels" / "ladder.txt"
SHELL = "dogleg"


def test_the_committed_table_regenerates_byte_for_byte(tmp_path):
    out = tmp_path / "rooms.asm"
    done = subprocess.run(
        [sys.executable, str(TOOL), str(LEVEL.relative_to(ROOT)), SHELL,
         "--asm", str(out)], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert out.read_text() == TABLE.read_text(), \
        "spectrum/src/rooms.asm is stale; regenerate it"


def _packed_from_table() -> list[list[int]]:
    """The bytes as the port will read them, parsed back out of the asm."""
    rows = []
    for line in TABLE.read_text().splitlines():
        line = line.strip()
        if line.startswith("DEFB"):
            operand = line.removeprefix("DEFB").split(";")[0]
            rows.append([int(b.strip().lstrip("$"), 16)
                         for b in operand.split(",")])
    return rows


def test_the_bits_say_what_the_prototype_says():
    """Bit 7 is the leftmost cell, a set bit is solid, and the two machines
    agree on every one of the 704 cells."""
    packed = _packed_from_table()
    assert len(packed) == PLAY_ROWS, len(packed)
    shapes = levels.parse(LEVEL.read_text())[4]
    art = shapes[SHELL]
    for cy, row in enumerate(packed):
        assert len(row) == COLS // 8
        for cx in range(COLS):
            bit = bool(row[cx // 8] & (0x80 >> (cx % 8)))
            assert bit == (art[cy][cx] == B.WALL), (cx, cy)


def test_a_shape_that_is_not_there_is_refused_by_name():
    done = subprocess.run(
        [sys.executable, str(TOOL), str(LEVEL.relative_to(ROOT)), "nosuch",
         "--asm", "/dev/null"], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode != 0
    assert "nosuch" in done.stderr and SHELL in done.stderr
