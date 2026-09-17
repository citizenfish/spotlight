"""Levels, loaded from text: `assets/levels/level<n>.txt` is the source.

Issue #107 (The rooms, AK). A level is a building -- a chain of rooms joined
by east and west doorways with one exit -- and the file is the one place it
is authored, the way `assets/sprites/` is the one place a figure is drawn.
`scene.py` is a view of level 3 for the names the tests and the bots read.

Pure parsing: integers only, no pygame, no floats, nothing the Z80 could not
do with a table -- on the port a level is the same bytes packed, and the
tester's note *Room budget and feasibility* prices the packing.

The format, in full:

    level: 3            once, first
    name: Rescue        once
    room: <name>        starts a room; the building starts in its first
    floor: yellow|cyan  the room's floor hue; adjacent rooms never share
    map:                followed by exactly 22 rows of 32 characters
    worker: x y blood   pixels and blood points, any number
    cleg: cx cy         a cell, any number
    spotlight: cx cy power
    light: left top width height
    searchlight: radius repeat|vary      at most one
    start: x y          pixels; every room has one
    door: east|west r-r <room name>      rows inclusive, the room it leads to

Blank lines and `;` comments go anywhere. A malformed line raises
`ValueError` naming the line. On top of `Building.validate`, the loader
refuses: a room with no `start:`; a doorway whose rows are not 10-12; two
adjacent rooms sharing a floor hue; a room reached only through a room with
no worker (a silent room strands the listener -- shouts carry one doorway).
"""

from functools import lru_cache
from pathlib import Path

from spotlight.core.constants import CYAN, YELLOW

from .building import (
    DEFAULT_BUDGET, Budget, Building, Doorway, EAST, Room, Searchlight, WEST,
    palette,
)

#: Where the level files live: `assets/levels/`, two directories up from the
#: package, beside the sprites and the tiles.
LEVELS_DIR = Path(__file__).resolve().parents[2] / "assets" / "levels"

FLOORS = {"yellow": YELLOW, "cyan": CYAN}
SIDES = {"east": EAST, "west": WEST}
DOOR_ROWS = (10, 11, 12)
ROWS, COLS = 22, 32


class _RoomSpec:
    __slots__ = ("name", "floor", "rows", "workers", "clegs", "spotlights",
                 "lights", "searchlight", "start", "doors", "line")

    def __init__(self, name: str, line: int) -> None:
        self.name = name
        self.line = line
        self.floor = None
        self.rows: list[str] = []
        self.workers: list = []
        self.clegs: list = []
        self.spotlights: list = []
        self.lights: list = []
        self.searchlight = None
        self.start = None
        self.doors: list = []


BUDGET_KEYS = ("blood", "spray", "torch", "lives")


def parse(text: str, where: str = "<text>"
          ) -> tuple[int, str, list, Budget]:
    """The file as (level number, name, room specs, budget). Raises on any
    fault. The budget's keys are the level's (issue #115) and default to the
    constants when the file does not say."""
    number, name = None, None
    budget = dict(DEFAULT_BUDGET._asdict())
    rooms: list[_RoomSpec] = []
    lines = text.splitlines()
    i = 0

    def fail(n: int, why: str) -> ValueError:
        return ValueError(f"{where}:{n}: {why}")

    def ints(n: int, parts: list, count: int, what: str) -> list[int]:
        if len(parts) != count:
            raise fail(n, f"{what} wants {count} numbers, got {len(parts)}")
        try:
            return [int(p) for p in parts]
        except ValueError:
            raise fail(n, f"{what} is not all integers: {parts!r}") from None

    while i < len(lines):
        raw = lines[i]
        i += 1
        line = raw.split(";", 1)[0].rstrip()
        if not line.strip():
            continue
        if ":" not in line:
            raise fail(i, f"expected `key: value`, got {raw!r}")
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "level":
            number = ints(i, [value], 1, "level")[0]
            continue
        if key == "name":
            name = value
            continue
        if key in BUDGET_KEYS:
            if rooms:
                raise fail(i, f"`{key}:` is the level's, and goes before "
                              "the first `room:`")
            budget[key] = ints(i, [value], 1, key)[0]
            if budget[key] < 0:
                raise fail(i, f"{key} cannot be negative")
            continue
        if key == "room":
            if not value:
                raise fail(i, "a room needs a name")
            rooms.append(_RoomSpec(value, i))
            continue
        if not rooms:
            raise fail(i, f"`{key}:` before any `room:`")
        room = rooms[-1]
        parts = value.split()
        if key == "floor":
            if value not in FLOORS:
                raise fail(i, f"floor must be one of {sorted(FLOORS)}, got {value!r}")
            room.floor = FLOORS[value]
        elif key == "map":
            if value:
                raise fail(i, "`map:` takes its rows on the lines below")
            rows = []
            while len(rows) < ROWS:
                if i >= len(lines):
                    raise fail(i, f"the map ended after {len(rows)} rows")
                row = lines[i].rstrip("\n")
                i += 1
                if len(row) != COLS:
                    raise fail(i, f"map row {len(rows)} is {len(row)} wide, not {COLS}")
                rows.append(row)
            room.rows = rows
        elif key == "worker":
            room.workers.append(tuple(ints(i, parts, 3, "worker")))
        elif key == "cleg":
            room.clegs.append(tuple(ints(i, parts, 2, "cleg")))
        elif key == "spotlight":
            room.spotlights.append(tuple(ints(i, parts, 3, "spotlight")))
        elif key == "light":
            room.lights.append(tuple(ints(i, parts, 4, "light")))
        elif key == "searchlight":
            if len(parts) != 2 or parts[1] not in ("repeat", "vary"):
                raise fail(i, "searchlight wants `radius repeat|vary`")
            radius = ints(i, parts[:1], 1, "searchlight radius")[0]
            room.searchlight = Searchlight(radius, parts[1] == "vary")
        elif key == "start":
            room.start = tuple(ints(i, parts, 2, "start"))
        elif key == "door":
            if len(parts) < 3 or parts[0] not in SIDES or "-" not in parts[1]:
                raise fail(i, "door wants `east|west r-r <room name>`")
            lo, _, hi = parts[1].partition("-")
            lo, hi = ints(i, [lo, hi], 2, "door rows")
            room.doors.append((SIDES[parts[0]], tuple(range(lo, hi + 1)),
                               " ".join(parts[2:]), i))
        else:
            raise fail(i, f"unknown key {key!r}")
    if number is None:
        raise fail(0, "no `level:` line")
    if name is None:
        raise fail(0, "no `name:` line")
    if not rooms:
        raise fail(0, "no rooms")
    if budget["lives"] < 1:
        raise fail(0, "a level needs at least one life")
    return number, name, rooms, Budget(**budget)


def build(specs: list, where: str = "<text>") -> Building:
    """Rooms from specs, doors resolved by name, the loader's refusals."""
    index = {r.name: n for n, r in enumerate(specs)}
    if len(index) != len(specs):
        raise ValueError(f"{where}: two rooms share a name")
    rooms = []
    for spec in specs:
        if spec.floor is None:
            raise ValueError(f"{where}:{spec.line}: room {spec.name!r} has no `floor:`")
        if not spec.rows:
            raise ValueError(f"{where}:{spec.line}: room {spec.name!r} has no `map:`")
        if spec.start is None:
            raise ValueError(f"{where}:{spec.line}: room {spec.name!r} has no `start:`")
        doorways = []
        for side, rows, to_name, line in spec.doors:
            if to_name not in index:
                raise ValueError(f"{where}:{line}: door leads to unknown room {to_name!r}")
            if tuple(rows) != DOOR_ROWS:
                raise ValueError(f"{where}:{line}: a doorway's rows are {DOOR_ROWS[0]}-{DOOR_ROWS[-1]}")
            doorways.append(Doorway(side, rows, to=index[to_name]))
        rooms.append(Room(
            spec.name, spec.rows, ink=palette(spec.floor),
            workers=spec.workers, clegs=spec.clegs, spotlights=spec.spotlights,
            searchlight=spec.searchlight, lights=spec.lights,
            player_start=spec.start, doorways=doorways))
    # Adjacent rooms never share a floor hue.
    for n, spec in enumerate(specs):
        for _side, _rows, to_name, line in spec.doors:
            if specs[index[to_name]].floor == spec.floor:
                raise ValueError(f"{where}:{line}: {spec.name!r} and {to_name!r} share a floor hue")
    # A room reached only through a room with no worker strands the listener.
    for n, spec in enumerate(specs[1:], start=1):
        ways_in = [m for m, other in enumerate(specs)
                   if any(index[t] == n for _s, _r, t, _l in other.doors)]
        if ways_in and all(not specs[m].workers for m in ways_in):
            raise ValueError(f"{where}:{spec.line}: room {spec.name!r} is reached only through a room with no worker")
    building = Building(rooms)
    building.validate()
    return building


def load(path) -> Building:
    """A building from a level file."""
    path = Path(path)
    number, name, specs, budget = parse(path.read_text(), str(path))
    building = build(specs, str(path))
    building.level = number
    building.title = name
    building.budget = budget
    return building


@lru_cache(maxsize=None)
def level(n: int) -> Building:
    """Level `n`, loaded once. On the Z80 this is a pointer into ROM."""
    return load(LEVELS_DIR / f"level{n}.txt")


def levels() -> list[int]:
    """The level numbers that exist, in order."""
    return sorted(int(p.stem[5:]) for p in LEVELS_DIR.glob("level*.txt"))


# --- the flags -----------------------------------------------------------------

#: The level every command plays when none is asked for (issue #109). Three,
#: so that nothing measured moves: Level 3 is the playtest building, and the
#: sixteen baseline hashes are its.
DEFAULT_LEVEL = 3

LEVEL_FLAG, ROOM_FLAG, SOLO_FLAG = "--level", "--room", "--solo"


def pick(level: int = DEFAULT_LEVEL, room: int | None = None,
         solo: bool = False):
    """The building `--level` names and the room to start in, or a `ValueError`
    that says what is wrong in one line.

    `room` starts the player in that room of the building at its own start
    -- the building as a whole, doorways and all. With `solo`, the room is
    played on its own (`Building.solo`): one room, its doorways bricked up,
    and no `room` means the level's start room. Returns `(building, start)`
    where `start` is None for the building's own start room.
    """
    if level not in levels():
        have = ", ".join(str(n) for n in levels()) or "none"
        raise ValueError(f"there is no level {level}; the levels are {have}")
    building = globals()["level"](level)
    if room is None:
        if not solo:
            return building, None
        room = building.start[0]
    if not 0 <= room < len(building):
        raise ValueError(f"level {level} has {len(building)} rooms, "
                         f"0 to {len(building) - 1}; there is no room {room}")
    if solo:
        return building.solo(room), None
    return building, room


def add_flags(parser) -> None:
    """`--level`, `--room` and `--solo` on an argparse parser."""
    parser.add_argument(LEVEL_FLAG, type=int, default=DEFAULT_LEVEL,
                        help=f"which level to play (default {DEFAULT_LEVEL})")
    parser.add_argument(ROOM_FLAG, type=int, default=None,
                        help="start in this room of the level, at its own "
                             "start (default the level's start room)")
    parser.add_argument(SOLO_FLAG, action="store_true",
                        help="play the room on its own: doorways bricked up "
                             "and the west one made the way out")


def from_argv(argv: list[str]) -> tuple[int, int | None, bool]:
    """The same three, from a bare argv (the window parses its own)."""
    def after(flag):
        try:
            return int(argv[argv.index(flag) + 1])
        except (IndexError, ValueError):
            raise ValueError(f"{flag} needs a number") from None
    level = after(LEVEL_FLAG) if LEVEL_FLAG in argv else DEFAULT_LEVEL
    room = after(ROOM_FLAG) if ROOM_FLAG in argv else None
    return level, room, SOLO_FLAG in argv


def picked(argv: list[str]):
    """`pick`, from a bare argv."""
    return pick(*from_argv(argv))
