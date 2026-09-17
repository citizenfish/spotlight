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
    light: left top width height
    searchlight: radius repeat|vary      every room has one
    pace: n             frames per cell of the beam (default 6)
    mount: n            the housing's corner, 0-3 (default 0)
    start: x y          pixels; every room has one
    door: east|west r-r <room name>      rows inclusive, the room it leads to

Or, since issue #120, **a rolled interior** in place of `map:` -- an
authored shell whose walls, furniture, people and flies are drawn from the
run's seed by `roller.py` (*The light round* §2):

    roll:               a rolled interior; no map:
    segments: min max   straight solid runs, count
    length: min max     cells per run
    pieces: min max     crates, desks and cabinets, count
    band: min max       every person's route distance from the start
    away: n             no fly starts nearer the start than this
    worker: blood       one line per person: the clock only
    clegs: n            how many flies

The first room of a level has the exit, in its west wall. A block with both
`map:` and `roll:` is refused. `level(n, seed)` rolls a level for a run seed,
the same way the session derives its streams, so `--seed S --level N` names
the same rooms on the window, the driver and the gallery.

Blank lines and `;` comments go anywhere. A malformed line raises
`ValueError` naming the line. On top of `Building.validate`, the loader
refuses: a room with no `start:` or no `searchlight:`; a doorway whose rows
are not 10-12; two adjacent rooms sharing a floor hue; a room reached only
through a room with no worker (a silent room strands the listener -- shouts
carry one doorway); `torch:` and `spotlight:`, which went with the torch.
"""

from functools import lru_cache
from pathlib import Path

from spotlight.core.constants import CYAN, YELLOW

from .building import (
    DEFAULT_BUDGET, Budget, Building, Doorway, EAST, Room, Searchlight, WEST,
    palette,
)

#: The run seed a level is rolled for when none is given: the driver's
#: default, so `scene.BUILDING` is the run every baseline is taken on.
DEFAULT_SEED = 0xBEEF

#: Where the level files live: `assets/levels/`, two directories up from the
#: package, beside the sprites and the tiles.
LEVELS_DIR = Path(__file__).resolve().parents[2] / "assets" / "levels"

FLOORS = {"yellow": YELLOW, "cyan": CYAN}
SIDES = {"east": EAST, "west": WEST}
DOOR_ROWS = (10, 11, 12)
ROWS, COLS = 22, 32


ROLL_KEYS = ("segments", "length", "pieces", "band", "away", "clegs")


class _RoomSpec:
    __slots__ = ("name", "floor", "rows", "workers", "clegs",
                 "lights", "searchlight", "pace", "mount", "start", "doors",
                 "line", "roll")

    def __init__(self, name: str, line: int) -> None:
        self.name = name
        self.line = line
        self.floor = None
        self.rows: list[str] = []
        self.workers: list = []
        self.clegs: list = []
        #: None for a `map:` room; for a `roll:` room the template's keys.
        self.roll: dict | None = None
        self.lights: list = []
        self.searchlight = None
        self.pace = None
        self.mount = None
        self.start = None
        self.doors: list = []


BUDGET_KEYS = ("blood", "spray", "lives", "magnet", "wake")
#: Keys the torch took with it (issue #119). Refused, not skipped, so a
#: stale level file cannot carry a dead key for ever.
DEAD_KEYS = {"torch": "the torch went with issue #119",
             "spotlight": "the floor lamps went with the torch, issue #119"}


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
        if key in DEAD_KEYS:
            raise fail(i, f"`{key}:` is no longer a key: {DEAD_KEYS[key]}")
        if key in BUDGET_KEYS:
            if rooms:
                raise fail(i, f"`{key}:` is the level's, and goes before "
                              "the first `room:`")
            if key == "wake":
                if value not in ("on", "off"):
                    raise fail(i, "wake is `on` or `off`")
                budget[key] = value == "on"
                continue
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
            if room.roll is not None:
                raise fail(i, "a room has `map:` or `roll:`, not both")
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
        elif key == "roll":
            if value:
                raise fail(i, "`roll:` takes no value; its keys follow")
            if room.rows:
                raise fail(i, "a room has `map:` or `roll:`, not both")
            room.roll = {}
        elif key in ROLL_KEYS:
            if room.roll is None:
                raise fail(i, f"`{key}:` belongs to a `roll:` room")
            if key in ("away", "clegs"):
                room.roll[key] = ints(i, parts, 1, key)[0]
            else:
                room.roll[key] = tuple(ints(i, parts, 2, key))
        elif key == "worker":
            if room.roll is not None:
                room.workers.append(ints(i, parts, 1, "a rolled worker")[0])
            else:
                room.workers.append(tuple(ints(i, parts, 3, "worker")))
        elif key == "cleg":
            if room.roll is not None:
                raise fail(i, "a rolled room counts its flies with `clegs:`")
            room.clegs.append(tuple(ints(i, parts, 2, "cleg")))
        elif key == "light":
            room.lights.append(tuple(ints(i, parts, 4, "light")))
        elif key == "searchlight":
            if len(parts) != 2 or parts[1] not in ("repeat", "vary"):
                raise fail(i, "searchlight wants `radius repeat|vary`")
            radius = ints(i, parts[:1], 1, "searchlight radius")[0]
            room.searchlight = Searchlight(radius, parts[1] == "vary")
        elif key == "pace":
            room.pace = ints(i, parts, 1, "pace")[0]
            if not 1 <= room.pace <= 12:
                raise fail(i, f"pace is frames per cell, 1 to 12, not {room.pace}")
        elif key == "mount":
            room.mount = ints(i, parts, 1, "mount")[0]
            if not 0 <= room.mount <= 3:
                raise fail(i, f"mount is a corner, 0 to 3, not {room.mount}")
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


def build(specs: list, where: str = "<text>",
          roll_seed: int | None = None) -> Building:
    """Rooms from specs, doors resolved by name, the loader's refusals.

    `roll_seed` is the run's roll stream (issue #120); every `roll:` room is
    rolled from it in file order, each taking the stream on from the last,
    so the rooms of a level differ from one another and a seed names them
    all. A file with a `roll:` room and no seed is refused.
    """
    index = {r.name: n for n, r in enumerate(specs)}
    if len(index) != len(specs):
        raise ValueError(f"{where}: two rooms share a name")
    rooms = []
    for n, spec in enumerate(specs):
        if spec.floor is None:
            raise ValueError(f"{where}:{spec.line}: room {spec.name!r} has no `floor:`")
        if spec.roll is not None:
            if roll_seed is None:
                raise ValueError(f"{where}:{spec.line}: room {spec.name!r} rolls, "
                                 "and no seed was given to roll it from")
            spec.rows, spec.workers, spec.clegs, roll_seed = _roll(
                spec, n == 0, roll_seed, f"{where}:{spec.line}")
        if not spec.rows:
            raise ValueError(f"{where}:{spec.line}: room {spec.name!r} has no `map:`")
        if spec.start is None:
            raise ValueError(f"{where}:{spec.line}: room {spec.name!r} has no `start:`")
        if spec.searchlight is None:
            # **Every room has a searchlight** (issue #118, the user's
            # ruling): the beam is how a room is seen and the thing in it
            # to keep out of, so a room without one is not a room.
            raise ValueError(f"{where}:{spec.line}: room {spec.name!r} has no "
                             "`searchlight:`; every room has one")
        if spec.pace is not None:
            spec.searchlight.pace = spec.pace
        if spec.mount is not None:
            spec.searchlight.mount = spec.mount
        doorways = []
        for side, rows, to_name, line in spec.doors:
            if to_name not in index:
                raise ValueError(f"{where}:{line}: door leads to unknown room {to_name!r}")
            if tuple(rows) != DOOR_ROWS:
                raise ValueError(f"{where}:{line}: a doorway's rows are {DOOR_ROWS[0]}-{DOOR_ROWS[-1]}")
            doorways.append(Doorway(side, rows, to=index[to_name]))
        rooms.append(Room(
            spec.name, spec.rows, ink=palette(spec.floor),
            workers=spec.workers, clegs=spec.clegs,
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


def _roll(spec, first: bool, roll_seed: int, where: str):
    """Roll one room's interior from its template (issue #120)."""
    from . import roller
    if spec.start is None:
        raise ValueError(f"{where}: room {spec.name!r} has no `start:`")
    keys = spec.roll
    template = roller.Template(
        segments=keys.get("segments", (0, 0)), length=keys.get("length", (4, 8)),
        pieces=keys.get("pieces", (0, 0)), band=keys.get("band", (4, 30)),
        away=keys.get("away", 6), workers=spec.workers,
        clegs=keys.get("clegs", 0),
        doorways=[(side, rows) for side, rows, _to, _line in spec.doors],
        start=spec.start, exit=first, lights=spec.lights)
    rolled = roller.roll(template, roll_seed, f"{where} ({spec.name})")
    return list(rolled.rows), list(rolled.workers), list(rolled.clegs), rolled.seed


def load(path, seed: int | None = None) -> Building:
    """A building from a level file, rolled for a run `seed` where it rolls.

    The seed is the run's, as `--seed` gives it; the roll stream is derived
    from it and the file's level number exactly as `Session` derives its
    own (`seeds.roll_seed`), so a rolled room is the same on the window,
    the driver and the gallery for one seed.
    """
    from . import seeds
    path = Path(path)
    number, name, specs, budget = parse(path.read_text(), str(path))
    roll = None if seed is None else seeds.roll_seed(seed, number)
    building = build(specs, str(path), roll_seed=roll)
    building.level = number
    building.title = name
    building.budget = budget
    building.seed = seed
    return building


#: Level 4 and on (issue #121, ruling 7): Level 3's templates re-rolled with
#: every clock `CLOCK_STEP` points shorter a level down to `CLOCK_FLOOR`
#: (44 s); from the first level at the floor, one more fly a level in the far
#: room up to `MOST_FLIES` in the building; every beam varies from
#: `VARY_FROM`. The roll is the progression as well as the variety.
LAST_FILE = 3
CLOCK_STEP, CLOCK_FLOOR = 3, 22
VARY_FROM = 5
MOST_FLIES = 9


def level(n: int, seed: int = DEFAULT_SEED) -> Building:
    """Level `n` for run `seed`, loaded once per pair. On the Z80 the
    template is a pointer into ROM and the roll happens at level start."""
    return _level(n, seed)


@lru_cache(maxsize=None)
def _level(n: int, seed: int) -> Building:
    if n <= LAST_FILE:
        return load(LEVELS_DIR / f"level{n}.txt", seed)
    return _beyond(n, seed)


def _beyond(n: int, seed: int) -> Building:
    """Level `n` past the last file: the last file's shells, tightened."""
    from . import seeds
    path = LEVELS_DIR / f"level{LAST_FILE}.txt"
    number, name, specs, budget = parse(path.read_text(), str(path))
    above = n - LAST_FILE
    for spec in specs:
        if spec.roll is None:
            raise ValueError(f"{path}: level {n} needs every room of level "
                             f"{LAST_FILE} to roll, and {spec.name!r} does not")
    # The first level at the floor: where the level's shortest clock, cut
    # `CLOCK_STEP` a level, first reaches it.
    shortest = min(b for spec in specs for b in spec.workers)
    floor_level = LAST_FILE + max(0, -(-(shortest - CLOCK_FLOOR) // CLOCK_STEP))
    for spec in specs:
        spec.workers = [max(CLOCK_FLOOR, blood - CLOCK_STEP * above)
                        for blood in spec.workers]
        if n >= VARY_FROM:
            spec.searchlight.vary = True
    extra = max(0, n - floor_level)
    have = sum(spec.roll.get("clegs", 0) for spec in specs)
    specs[-1].roll["clegs"] = specs[-1].roll.get("clegs", 0) + \
        min(extra, max(0, MOST_FLIES - have))
    building = build(specs, f"{path} as level {n}",
                     roll_seed=seeds.roll_seed(seed, n))
    building.level = n
    building.title = name
    building.budget = budget
    building.seed = seed
    return building


def levels() -> list[int]:
    """The level numbers that exist, in order."""
    return sorted(int(p.stem[5:]) for p in LEVELS_DIR.glob("level*.txt"))


# --- the flags -----------------------------------------------------------------

#: The level every command plays when none is asked for: one, since issue
#: #123 -- the game starts at the start. It was three through the rooms
#: round (issue #109) so that nothing measured moved; the sixteen baseline
#: hashes are Level 3's and the driver's re-baseline command says
#: `--level 3`. `scene.py` stays a view of Level 3 (`SCENE_LEVEL`), the
#: playtest building every test of the rules is written against.
DEFAULT_LEVEL = 1
SCENE_LEVEL = 3

LEVEL_FLAG, ROOM_FLAG, SOLO_FLAG = "--level", "--room", "--solo"


def pick(level: int = DEFAULT_LEVEL, room: int | None = None,
         solo: bool = False, seed: int = DEFAULT_SEED):
    """The building `--level` names and the room to start in, or a `ValueError`
    that says what is wrong in one line.

    `room` starts the player in that room of the building at its own start
    -- the building as a whole, doorways and all. With `solo`, the room is
    played on its own (`Building.solo`): one room, its doorways bricked up,
    and no `room` means the level's start room. Returns `(building, start)`
    where `start` is None for the building's own start room.
    """
    if level < 1 or (level <= LAST_FILE and level not in levels()):
        have = ", ".join(str(n) for n in levels()) or "none"
        raise ValueError(f"there is no level {level}; the levels are {have}"
                         f" and every level after {LAST_FILE} is level "
                         f"{LAST_FILE} again, tightened")
    building = globals()["level"](level, seed)
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


def picked(argv: list[str], seed: int = DEFAULT_SEED):
    """`pick`, from a bare argv."""
    return pick(*from_argv(argv), seed=seed)
