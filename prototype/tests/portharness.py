"""Assemble the port, run it on a Z80, and read the screen back as bytes.

One helper so every port test measures the same way, and so that the thing the
port is compared *against* is the prototype itself rather than a second opinion
about what the picture should be.

**Why a simulator and not an emulator** (ruled 2026-10-04, *The port begins*):
`skoolkit.simulator.Simulator` is headless, pip-installed into this venv, hands
back the 6,912 bytes the real display file holds, and counts T-states exactly --
a lone `ld a,5` advances the counter by seven. So the frame budget stops being an
estimate in a vault note and becomes an assertion, and the port's screen can be
compared with `core.screen.Screen` cell for cell.

The register file is a list of thirty, addressed by index and not by name;
`PC` and `T` are the two this needs and they are not documented anywhere but
here and the vault note.
"""

import os
import pathlib
import shutil
import subprocess

import pytest

from spikes import bitmaps_gen, floor as floor_mod, sprites, tiles
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import CELL, COLS, ROWS, SCREEN_H, SCREEN_W
from spotlight.core.screen import Screen, attr_byte

simulator = pytest.importorskip("skoolkit.simulator",
                                reason="pip install skoolkit")

#: `Simulator.registers` is a plain list; these are the two indices this uses.
PC, T = 24, 25

SCREEN_AT = 0x4000
ATTRS_AT = 0x5800
ORIGIN = 0x8000

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "spectrum" / "src"
BUILD = ROOT / "spectrum" / "build"

#: What `main.asm` draws the play area in, and what the reference must use: the
#: light field is the next slice, so a room is drawn lit or there is nothing to
#: compare. Bright white on black.
PLAY_ATTR = attr_byte(ink=7, paper=0, bright=True)

#: Where `main.asm` stands the player, in cells. Kept here so one edit moves
#: both the port and its reference, which is the whole point of the comparison.
PLAYER_CX, PLAYER_CY = 5, 12

#: The shape `tools/rooms.py` emitted into `rooms.asm`.
SHELL = "dogleg"


def sjasmplus() -> str:
    """Where the assembler is, found once.

    `SJASMPLUS` overrides, as it does in `spectrum/Makefile`, then the PATH,
    then the place `spectrum/README.md` says to put it. **Resolved in one place
    and used by every caller** -- the first cut of this searched in `assemble`
    and hardcoded the path in `symbol`, so a machine with sjasmplus anywhere
    else would have assembled happily and then failed looking for symbols.
    """
    if _tool:
        return _tool[0]
    for candidate in (os.environ.get("SJASMPLUS"), "sjasmplus",
                      str(pathlib.Path.home() / ".local/bin/sjasmplus")):
        if not candidate:
            continue
        found = shutil.which(candidate)
        if found:
            _tool.append(found)
            return found
    pytest.skip("sjasmplus not installed; see spectrum/README.md")


_tool: list[str] = []


def assemble() -> bytes:
    """sjasmplus over `spectrum/src/main.asm`, returning the raw binary.

    Skips rather than fails when the assembler is absent: a developer without
    the Z80 toolchain still gets the prototype's whole suite, and CI that wants
    the port tested installs it. The invocation is the one in
    `spectrum/Makefile` and nowhere else.
    """
    BUILD.mkdir(parents=True, exist_ok=True)
    done = subprocess.run([sjasmplus(), "--sym=main.sym", "main.asm"], cwd=SRC,
                          capture_output=True, text=True)
    if done.returncode:
        pytest.fail(f"sjasmplus refused main.asm:\n{done.stdout}\n{done.stderr}")
    return (BUILD / "spotlight.bin").read_bytes()


def run(label: str, blob: bytes, limit: int = 200_000):
    """Call one routine by name and come back with the machine and its cost.

    `label` is resolved out of sjasmplus's own symbol listing rather than
    guessed, so the test cannot drift from the source as the code moves.
    """
    memory = [0] * 65536
    memory[ORIGIN:ORIGIN + len(blob)] = list(blob)
    # A `ret` to land on: the routine returns to an address holding `halt`,
    # which stops the run without needing an instruction budget guessed right.
    memory[0x7000] = 0x76                       # halt
    machine = simulator.Simulator(memory)
    machine.registers[12] = 0x7FFE              # SP, clear of the code
    memory[0x7FFE] = 0x00
    memory[0x7FFF] = 0x70                       # return address $7000
    machine.registers[PC] = symbol(label)
    machine.registers[T] = 0
    for _ in range(limit):
        machine.run()
        if machine.registers[PC] == 0x7000:
            break
    else:
        pytest.fail(f"{label} did not return inside {limit} instructions")
    return machine, machine.registers[T]


_symbols: dict[str, int] = {}


def symbol(name: str) -> int:
    """An address out of the assembler's export list."""
    if not _symbols:
        listing = SRC / "main.sym"
        if not listing.exists():
            assemble()
        for line in listing.read_text().splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[1].strip().startswith("EQU"):
                value = parts[1].strip().removeprefix("EQU").strip()
                try:
                    _symbols[parts[0].strip()] = int(value.lstrip("$"), 16)
                except ValueError:
                    continue
    if name not in _symbols:
        raise KeyError(f"{name} is not in main.sym: "
                       f"{sorted(_symbols)[:10]}...")
    return _symbols[name]


# --- the reference, built out of the prototype -------------------------------

def shell_rows() -> tuple[str, ...]:
    from spikes import levels
    text = (ROOT / "assets" / "levels" / "ladder.txt").read_text()
    return levels.parse(text)[4][SHELL]


def reference() -> Screen:
    """The same room and the same player, drawn by the prototype's own code.

    Not a second implementation: `tiles.blit`, `floor`'s table and
    `sprites.draw` are the functions the game draws with, so if the port and
    this disagree the port is wrong.
    """
    rows = shell_rows()

    def solid(cx: int, cy: int) -> bool:
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return True                 # off the room counts as wall
        from spikes import building as B
        return rows[cy][cx] == B.WALL

    screen = Screen()
    screen.clear(attr_byte(ink=7, paper=0))
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            if solid(cx, cy):
                art = tiles.WALL_LIT[tiles.mask_at(solid, cx, cy)]
            else:
                art = floor_mod.FLOOR_LIT[(cy & 3) * 4 + (cx & 3)]
            tiles.blit(screen, cx, cy, art)
            screen.set_attr(cx, cy, PLAY_ATTR)
    sprites.draw(screen, bitmaps_gen.PLAYER_N,
                 PLAYER_CX * CELL, PLAYER_CY * CELL)
    return screen


def display_file(screen: Screen) -> bytearray:
    """The prototype's one-byte-a-pixel buffer as the 6,144 bytes the ULA reads.

    The display file's shape, which is the only place this conversion lives:
    for pixel row y and byte column x,
        address = ((y & $C0) << 5) | ((y & 7) << 8) | ((y & $38) << 2) | x
    """
    out = bytearray(6144)
    for y in range(SCREEN_H):
        base = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
        row = y * SCREEN_W
        for byte in range(SCREEN_W // 8):
            bits = 0
            for bit in range(8):
                if screen.pixels[row + byte * 8 + bit]:
                    bits |= 0x80 >> bit
            out[base + byte] = bits
    return out


def play_area(blob) -> bytes:
    """Only the rows the play area owns: the strip is not this slice's."""
    keep = bytearray()
    for y in range(PLAY_ROWS * CELL):
        base = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
        keep += bytes(blob[base:base + SCREEN_W // 8])
    return bytes(keep)
