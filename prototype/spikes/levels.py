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
    building: The Hollins Hotel      what the building is called (issue #126)
    people: 90 80 70 ...             the roster, one clock a person (issue #143);
                                     the shape deals them out to rooms
    room: <name>        starts a room; the building starts in its first
    map:                followed by exactly 22 rows of 32 characters
    worker: x y blood   pixels and blood points, any number
    cleg: cx cy         a cell, any number
    light: left top width height
    searchlight: radius repeat|vary      every room has one
    pace: n             frames per cell of the beam (default 6)
    start: x y          pixels; every room has one
    at: col row         where the room sits in the building's plan (issue #134),
                        and since #145 the room's floor hue too: `(col+row) & 1`
    fade: n             wall-memory rate divisor, 1 (3 s) or 2 (6 s); level's own
    door: east|west r-r <room name>      rows inclusive, the room it leads to
    door: north|south c-c <room name>    columns inclusive, for the room above
                                         or below on the plan (issue #139)

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
    shell: <name>       one or more; which authored shells this room may be

And, since issue #132, **the walls are authored too**. A shell is a named
grid declared before the first `room:`, and a `roll:` room names the shells
it may be built from; the roll picks one and the contents still roll inside
it. A room with no `shell:` gets the plain rectangle, as every room did
before, so an unconverted template keeps loading.

    shape: <name>       starts a shell; followed by 22 rows of 32
    ####...####         walls, floor and doorways only -- no furniture, no
    ...                 light, no person, no fly: those are the roll's

A shell holds at most **two** internal structures, each a bay (a wall from
one border stopping short of the opposite one), a division (a wall border to
border with a gap of two or three) or a chamber (a rectangle with a door in
each of two opposite walls). A chamber with **one** door is not authored: no
room here is enterable only one way.

That is a design rule and not a safety one, and the difference is worth
keeping straight. The figure it was ruled on -- 17 unfair rooms in 256 -- was
measured when the *chambers themselves rolled*, at a random size and position;
an authored one-doored chamber strands nothing, on its bare walls or on 256
rolled seeds. `tests/test_spike_shells.py` pins that so nobody reads a
fairness reason into it later. What does the safety work is
`swarming.strands_a_shell`, which gates every shell whatever shape it is, and
since issue #144 `roller.blocks_a_landing` beside it -- a wall may reach the
border, and a doorway is three cells wide so a tail files through it, and a
wall standing in the gap's own lane satisfies both rules while being the one
thing `DOORWAY_CELLS = 3` exists to prevent. **A wall runs across the axis the
room's doorways are not on:** a division between an east and a west doorway,
and rows 6 to 15 only when the doorways are north and south.

**A shape may be declared and named by nobody.** The gate checks every shape a
level declares, which is why `parse` hands them back, so a shell can be
authored and proved a slice before the room that uses it exists.

The first room of a level has the exit, in its west wall. A block with both
`map:` and `roll:` is refused. `level(n, seed)` rolls a level for a run seed,
the same way the session derives its streams, so `--seed S --level N` names
the same rooms on the window, the driver and the gallery.

Blank lines and `;` comments go anywhere. A malformed line raises
`ValueError` naming the line. On top of `Building.validate`, the loader
refuses: a room with no `start:` or no `searchlight:`; a doorway that is not
three rows running together clear of the corners (they left the middle of the
wall in #135); two adjacent rooms sharing a floor hue; a room reached only
through a room with no worker (a silent room strands the listener -- shouts
carry one doorway); a plan that is half authored, has two rooms in one place,
holds more rooms than it can draw, or has an east door that does not lead east
(#134); `torch:`, `spotlight:` and `mount:`, which are gone.
"""

from functools import lru_cache
from pathlib import Path

from spotlight.core.constants import CYAN, YELLOW

from .building import (
    DEFAULT_BUDGET, DOORWAY_CELLS, PLAN_COLS, PLAN_MOST, PLAN_ROWS,
    VERTICAL_SIDES, Budget, Building, Doorway, EAST, NORTH, Room, Searchlight,
    SIDE_NAMES, SOUTH, WEST, palette,
)

#: The run seed a level is rolled for when none is given: the driver's
#: default, so `scene.BUILDING` is the run every baseline is taken on.
DEFAULT_SEED = 0xBEEF

#: Where the level files live: `assets/levels/`, two directories up from the
#: package, beside the sprites and the tiles.
LEVELS_DIR = Path(__file__).resolve().parents[2] / "assets" / "levels"

#: The two floor hues, by name. Kept for the message the dead `floor:` key
#: gives and for anything building a room by hand.
FLOORS = {"yellow": YELLOW, "cyan": CYAN}


def hue_at(col: int, row: int) -> int:
    """A room's floor hue, from where it stands on the plan (issue #145).

    `(col + row) & 1` -- a chequerboard, and **adjacent rooms therefore never
    share a hue, for ever, with no check and nothing to author.** Two hues over
    a grid sounds impossible and is not: a grid graph is bipartite, so parity
    two-colours any building the plan can hold. All three shipped files obeyed
    it by hand already, which is how it was found.

    It saves a byte a room on the Z80 and a loader refusal here, and it gives
    the player something for nothing: **every doorway you cross flips the
    colour**, so the floor under your feet says whether you are an odd or an
    even number of doors from the way out. A player cannot count that on a
    hand-authored building because a hand-authored building need not be
    consistent; this one is, by construction.
    """
    return CYAN if (col + row) & 1 else YELLOW
SIDES = {"east": EAST, "west": WEST, "north": NORTH, "south": SOUTH}
DOOR_ROWS = (10, 11, 12)
ROWS, COLS = 22, 32


ROLL_KEYS = ("segments", "length", "pieces", "band", "away", "clegs")


class _RoomSpec:
    __slots__ = ("name", "floor", "rows", "workers", "clegs",
                 "lights", "searchlight", "pace", "start", "doors",
                 "line", "roll", "shells", "at")

    def __init__(self, name: str, line: int) -> None:
        self.name = name
        self.line = line
        #: The room's ink, filled in by `build` from where the room stands on
        #: the plan (issue #145). Not authored: `floor:` is a dead key.
        self.floor = None
        self.rows: list[str] = []
        self.workers: list = []
        self.clegs: list = []
        #: None for a `map:` room; for a `roll:` room the template's keys.
        self.roll: dict | None = None
        #: The names of the shells this room may be built from (issue #132),
        #: in the order the file lists them. Empty is the plain rectangle.
        self.shells: list[str] = []
        self.lights: list = []
        self.searchlight = None
        self.pace = None
        self.start = None
        #: Where the room sits in the building's plan (issue #134).
        self.at = None
        self.doors: list = []


BUDGET_KEYS = ("blood", "spray", "lives", "magnet", "wake", "fade")
#: Keys the torch took with it (issue #119). Refused, not skipped, so a
#: stale level file cannot carry a dead key for ever.
DEAD_KEYS = {"torch": "the torch went with issue #119",
             "spotlight": "the floor lamps went with the torch, issue #119",
             "mount": "the housing's corner rolls with the beam since #137",
             "floor": "a room's hue is `(col + row) & 1` of its `at:` since "
                      "issue #145; two ways to say it is how they drift"}


def parse(text: str, where: str = "<text>"
          ) -> tuple[int, str, list, Budget, dict]:
    """The file as (level number, name, room specs, budget, shapes). Raises on
    any fault. The budget's keys are the level's (issue #115) and default to the
    constants when the file does not say. The building's name (issue #126)
    rides on the budget's `building` field.

    **`shapes` is every `shape:` the file declares, used or not** (issue #144).
    A room's own shells come resolved on its spec, so this was thrown away --
    and a shape no room named was therefore invisible to everything, the gate
    included. That is the state BU's new shells are authored in: declared, so
    the gate checks them, and named by nobody until the levels are re-authored.
    """
    number, name = None, None
    building_name = None
    budget = dict(DEFAULT_BUDGET._asdict())
    #: The level's authored shells by name (issue #132), in declaration order.
    shapes: dict[str, tuple] = {}
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
        if key == "building":
            if rooms:
                raise fail(i, "`building:` is the level's, and goes before "
                              "the first `room:`")
            if not value or len(value) > BIG_WIDTH:
                raise fail(i, f"a building's name is 1 to {BIG_WIDTH} characters")
            building_name = value
            continue
        if key in DEAD_KEYS:
            raise fail(i, f"`{key}:` is no longer a key: {DEAD_KEYS[key]}")
        if key == "people":
            # **The roster is the building's** (issue #143): one clock a person,
            # dealt to rooms by the shape rather than authored room by room.
            if rooms:
                raise fail(i, "`people:` is the level's, and goes before the "
                              "first `room:`")
            words = value.split()
            clocks = ints(i, words, len(words), "people")
            if not clocks:
                raise fail(i, "`people:` wants at least one clock")
            for blood in clocks:
                if blood <= 0:
                    raise fail(i, f"a person cannot start on {blood} blood")
            budget["people"] = tuple(clocks)
            continue
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
        if key == "shape":
            # An authored shell (issue #132). Declared before the first
            # `room:`, because a shell is the level's vocabulary rather than
            # one room's property -- two rooms may be built from the same one.
            if rooms:
                raise fail(i, "`shape:` is the level's, and goes before the "
                              "first `room:`")
            if not value:
                raise fail(i, "a shape needs a name")
            if value in shapes:
                raise fail(i, f"there are two shapes called {value!r}")
            rows = []
            while len(rows) < ROWS:
                if i >= len(lines):
                    raise fail(i, f"shape {value!r} ended after {len(rows)} rows")
                row = lines[i].rstrip("\n")
                i += 1
                if len(row) != COLS:
                    raise fail(i, f"shape {value!r} row {len(rows)} is "
                                  f"{len(row)} wide, not {COLS}")
                rows.append(row)
            shapes[value] = tuple(rows)
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
        if key == "map":
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
        elif key == "shell":
            if room.roll is None:
                raise fail(i, "`shell:` belongs to a `roll:` room")
            if value not in shapes:
                raise fail(i, f"no shape called {value!r}; "
                              f"the level declares {sorted(shapes) or 'none'}")
            if any(named == value for named, _rows in room.shells):
                raise fail(i, f"{room.name!r} names shell {value!r} twice")
            # Resolved here rather than carried as a name, so `parse` keeps
            # its four-value shape and a spec is self-contained.
            room.shells.append((value, shapes[value]))
        elif key in ROLL_KEYS:
            if room.roll is None:
                raise fail(i, f"`{key}:` belongs to a `roll:` room")
            if key in ("away", "clegs"):
                room.roll[key] = ints(i, parts, 1, key)[0]
            else:
                room.roll[key] = tuple(ints(i, parts, 2, key))
        elif key == "worker":
            if room.roll is not None:
                raise fail(i, "a rolled room does not author its own people "
                              "since issue #143; the building's `people:` line "
                              "names the roster and the shape deals it out")
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
        elif key == "at":
            col, row = ints(i, parts, 2, "at")
            if not (0 <= col < PLAN_COLS
                    and 0 <= row < PLAN_ROWS):
                raise fail(i, f"at {col} {row} is off the plan, which is "
                              f"{PLAN_COLS} across and "
                              f"{PLAN_ROWS} down")
            room.at = (col, row)
        elif key == "start":
            room.start = tuple(ints(i, parts, 2, "start"))
        elif key == "door":
            if len(parts) < 3 or parts[0] not in SIDES or "-" not in parts[1]:
                raise fail(i, "door wants `east|west|north|south a-b "
                              "<room name>`; east and west take rows, north "
                              "and south take columns")
            side = SIDES[parts[0]]
            lo, _, hi = parts[1].partition("-")
            vertical = side in VERTICAL_SIDES
            what = "rows" if vertical else "columns"
            lo, hi = ints(i, [lo, hi], 2, f"door {what}")
            span = tuple(range(lo, hi + 1))
            # **Checked here, where the line is read, and not in `build`**
            # (issue #139). It used to be checked after the room had been
            # rolled, and a rolled room cuts its doorways into the shell -- so
            # a doorway at columns 30-32 crashed the roller with an index error
            # before the loader got to say what was wrong with it.
            along = ROWS if vertical else COLS
            if len(span) != DOORWAY_CELLS:
                raise fail(i, f"a doorway is {DOORWAY_CELLS} {what}, "
                              f"not {len(span)}")
            if span[0] < 1 or span[-1] > along - 2:
                raise fail(i, f"a doorway at {what} {span[0]}-{span[-1]} runs "
                              f"into the corner; 1 to {along - 2} is the wall")
            room.doors.append((side, span, " ".join(parts[2:]), i))
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
    if budget["fade"] not in (1, 2):
        raise fail(0, f"fade is a rate divisor, 1 or 2, not {budget['fade']}; "
                      "1 is the three-second wall memory and 2 is six")
    if building_name is not None:
        budget["building"] = building_name
    return number, name, rooms, Budget(**budget), shapes


def deal(specs: list, roster, seed: int, where: str = "<text>") -> list:
    """Which room each of the building's people is in, and on which clock.

    Issue #143. Returns a list of clock lists, one a room, in room order.

    **The order is a rule and not a convenience**, because the loader refuses a
    room reached only through a room with nobody in it -- a shout carries exactly
    one doorway, so a silent room on a path strands a listening player. With more
    rooms than people, something has to decide which rooms are empty, and it has
    to be the rooms that cannot strand anybody:

    1. **Every room that is not a dead end is given somebody first.** A room with
       more than one doorway is on a path between two others by definition.
    2. **Then the dead ends, in a rolled order**, until the roster runs out. Two
       empty rooms in a nine-room building are therefore always leaves.
    3. **Then whatever is left**, round the rooms from a rolled start.

    **Which dead end is empty rolls with the seed, and must.** A player who can
    learn that the north spur is always empty has learned the level rather than
    the building, and the whole point of the roll is that they cannot.

    **Clocks go shortest-nearest-the-exit.** Once the rooms are settled the
    roster is sorted and dealt against the rooms in order of how many doorways
    they are from the way out, so a deeper room holds a longer clock and nobody
    is asked to cross a building on the shortest fuse in it. Ties go to the
    lower room index, so a seed names a building.
    """
    from . import roller
    rooms = len(specs)
    clocks = sorted(roster)
    if len(clocks) < 1:
        raise ValueError(f"{where}: a building needs at least one person")

    ways = [len(spec.doors) for spec in specs]
    leaves = [i for i in range(rooms) if ways[i] <= 1]
    inner = [i for i in range(rooms) if ways[i] > 1]
    if len(clocks) < len(inner):
        raise ValueError(
            f"{where}: {len(clocks)} people cannot fill {len(inner)} rooms that "
            f"are not dead ends, and a room with nobody in it on a path between "
            f"two who are strands a listening player")

    dice = roller._Dice(seed)
    order = list(inner)
    # The dead ends in a rolled order: a shuffle drawn from the stream, so which
    # spur goes empty is the seed's.
    pool = list(leaves)
    while pool:
        order.append(pool.pop(dice.draw(len(pool))))

    counts = [0] * rooms
    for n, room in enumerate(order):
        if n < len(clocks):
            counts[room] = 1
    left = len(clocks) - sum(counts)
    at = dice.draw(rooms) if left else 0
    for n in range(left):
        counts[order[(at + n) % rooms]] += 1

    # Depth from the way out, over the doorway graph. The exit is in the first
    # room, which is where a building starts.
    depth = [None] * rooms
    depth[0], queue = 0, [0]
    index = {spec.name: i for i, spec in enumerate(specs)}
    while queue:
        here = queue.pop(0)
        for _side, _span, to_name, _line in specs[here].doors:
            # A door to a room that does not exist is `build`'s to refuse, by
            # name and by line; the deal runs before that and must not turn it
            # into a KeyError from in here.
            to = index.get(to_name)
            if to is not None and depth[to] is None:
                depth[to] = depth[here] + 1
                queue.append(to)
    for i in range(rooms):
        if depth[i] is None:
            depth[i] = rooms          # unreachable; `validate` will say so

    slots = []
    for i in range(rooms):
        slots += [i] * counts[i]
    slots.sort(key=lambda i: (depth[i], i))
    out = [[] for _ in range(rooms)]
    for blood, room in zip(clocks, slots):
        out[room].append(blood)
    return out


def build(specs: list, where: str = "<text>",
          roll_seed: int | None = None, people=(),
          people_seed: int | None = None) -> Building:
    """Rooms from specs, doors resolved by name, the loader's refusals.

    `roll_seed` is the run's roll stream (issue #120); every `roll:` room is
    rolled from it in file order, each taking the stream on from the last,
    so the rooms of a level differ from one another and a seed names them
    all. A file with a `roll:` room and no seed is refused.

    `people` is the building's roster (issue #143), which `deal` hands out to
    the rooms before anything is rolled -- a rolled room takes the clocks it
    is dealt and puts them where the roll says. `people_seed` is that deal's
    own stream; a `build` called with only a roll seed (the tests, the shell
    gate) takes it from `seeds.PEOPLE_TAG` off the roll seed, so one seed is
    always enough to name a building.
    """
    index = {r.name: n for n, r in enumerate(specs)}
    if len(index) != len(specs):
        raise ValueError(f"{where}: two rooms share a name")
    # **The roster is dealt before the rooms are built**, because a rolled room
    # is handed clocks rather than authoring them, and the deal needs the shape
    # of the whole building -- which rooms are dead ends -- to know which rooms
    # may be left empty.
    rolled = [spec for spec in specs if spec.roll is not None]
    if people:
        if not rolled:
            raise ValueError(
                f"{where}: `people:` is a roster for the roll to deal out, and "
                f"no room in this building rolls; an authored room says where "
                f"its people stand with `worker: x y blood`")
        if len(rolled) != len(specs):
            missing = next(s for s in specs if s.roll is None)
            raise ValueError(
                f"{where}:{missing.line}: room {missing.name!r} does not roll, "
                f"and the building has a `people:` roster; a building's people "
                f"are all dealt or all authored")
        if people_seed is None:
            from . import seeds
            people_seed = seeds.stream(roll_seed or 1, seeds.PEOPLE_TAG)
        floor = clock_floor(len(specs))
        hands = deal(specs, [max(floor, blood) for blood in people],
                     people_seed, where)
        for spec, clocks in zip(specs, hands):
            spec.workers = clocks
    elif rolled:
        raise ValueError(
            f"{where}: {len(rolled)} of this building's rooms roll, and a rolled "
            f"room takes its people from the building's `people:` line")
    rooms = []
    for n, spec in enumerate(specs):
        # **The hue is derived and not authored** (issue #145): the parity of the
        # room's place on the plan, or of its index when the building has no
        # plan, which for a chain is the same alternation a row always had.
        spec.floor = hue_at(*(spec.at if spec.at is not None else (n, 0)))
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
        doorways = []
        for side, rows, to_name, line in spec.doors:
            if to_name not in index:
                raise ValueError(f"{where}:{line}: door leads to unknown room {to_name!r}")
            # **A doorway may be anywhere in a wall, and in any of the four**
            # (issues #135 and #139). It was pinned to rows 10-12 of the two
            # vertical walls -- the exact middle -- in every room of every
            # level, so a player had never once had to remember which way out
            # of a room. Its shape is checked in `parse`, which runs before
            # anything is rolled; what is left for here is the room it leads to.
            doorways.append(Doorway(side, rows, to=index[to_name]))
        rooms.append(Room(
            spec.name, spec.rows, ink=palette(spec.floor),
            workers=spec.workers, clegs=spec.clegs,
            searchlight=spec.searchlight, lights=spec.lights,
            player_start=spec.start, doorways=doorways, at=spec.at))
    # **Adjacent rooms never share a floor hue, and since issue #145 that is a
    # theorem rather than a check** -- a grid graph is bipartite and the hue is
    # the parity of the position, so no authored building the plan can hold can
    # break it. The check is kept because a building assembled by hand in a test
    # has no plan and takes the parity of the room index, and nothing then stops
    # a doorway joining rooms 0 and 2. That is the only shape this can still
    # fire on, and it says so.
    for n, spec in enumerate(specs):
        for _side, _rows, to_name, line in spec.doors:
            if specs[index[to_name]].floor == spec.floor:
                raise ValueError(
                    f"{where}:{line}: {spec.name!r} and {to_name!r} share a floor "
                    f"hue; a building with no `at:` takes each room's hue from "
                    f"its index, and these two are an even number apart")
    # **The plan's grid, which the loader has never checked** (issue #134).
    # Either every room says where it is or none does: a half-authored grid
    # would draw some rooms on top of each other, and until now a building of
    # four rooms drew off the left edge of the screen in silence.
    placed = [spec for spec in specs if spec.at is not None]
    if placed and len(placed) != len(specs):
        missing = next(s for s in specs if s.at is None)
        raise ValueError(f"{where}:{missing.line}: room {missing.name!r} has no "
                         "`at:` and some rooms have one; a building's plan is "
                         "either authored or it is not")
    if placed:
        seen = {}
        for spec in specs:
            if spec.at in seen:
                raise ValueError(
                    f"{where}:{spec.line}: {spec.name!r} and {seen[spec.at]!r} "
                    f"are both at {spec.at[0]} {spec.at[1]}")
            seen[spec.at] = spec.name
        if len(specs) > PLAN_MOST:
            raise ValueError(
                f"{where}: {len(specs)} rooms, and a building's plan holds "
                f"{PLAN_MOST} -- {PLAN_COLS} across and {PLAN_ROWS} down")
        # **East leads east.** A doorway is authored twice, once on each side,
        # and nothing has ever checked that the two agree with the shape of the
        # building. With the plan drawn on a grid a lie here is visible, so it
        # is worth refusing: the plan would show a door into the room next to
        # it and the door would put the player somewhere else.
        for spec in specs:
            col, row = spec.at
            for side, _rows, to_name, line in spec.doors:
                want = {EAST: (col + 1, row), WEST: (col - 1, row),
                        NORTH: (col, row - 1), SOUTH: (col, row + 1)}[side]
                got = specs[index[to_name]].at
                if got != want:
                    way = SIDE_NAMES[side]
                    raise ValueError(
                        f"{where}:{line}: {spec.name!r} is at {col} {row} and "
                        f"its {way} door leads to {to_name!r} at "
                        f"{got[0]} {got[1]}, which is not {way} of it")
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
        start=spec.start, exit=first, lights=spec.lights,
        shells=[rows for _name, rows in spec.shells])
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
    number, name, specs, budget, _shapes = parse(path.read_text(), str(path))
    roll = None if seed is None else seeds.roll_seed(seed, number)
    building = build(specs, str(path), roll_seed=roll, people=budget.people,
                     people_seed=(None if seed is None
                                  else seeds.people_seed(seed, number)))
    building.level = number
    building.title = name
    building.name = budget.building
    building.budget = budget
    building.seed = seed
    return building


#: What the buildings past the last file are called (issue #126): Level 3
#: re-rolled is a different building each time, and it says so. Cycled.
BEYOND_NAMES = (
    "Blackwell Mill", "Cutter's Yard", "The Vane Institute",
    "Ashgrove Sanatorium", "The Old Assize", "Parade Picture House",
    "The Kessler Works", "St Jude's Infirmary", "The Granary",
    "Lowry's Printworks",
)

#: The widest a building's name can be, in characters: the screen.
BIG_WIDTH = 32


#: Level 4 and on (issue #121, ruling 7): Level 3's templates re-rolled with
#: every clock `CLOCK_STEP` points shorter a level down to `CLOCK_FLOOR`
#: (44 s); from the first level at the floor, one more fly a level in the far
#: room up to `MOST_FLIES` in the building; every beam varies from
#: `VARY_FROM`. The roll is the progression as well as the variety.
LAST_FILE = 3
CLOCK_STEP, CLOCK_FLOOR = 3, 22

#: How much the clock floor grows per room past three (issue #143): seven blood,
#: which is fourteen seconds at `rescue.BLEED_EVERY`. A bigger building is a
#: longer tour, and the floor has to grow with it or everybody on the floor clock
#: is dead before a player can reach them.
#:
#: **It scales with the building and not with a room's depth**, and that is
#: measured rather than assumed: the oracle spends 34.1, 32.8 and 33.7 seconds a
#: person at depths nought, one and two, over 144 people. It sweeps
#: deepest-first and walks everybody out together, so the carry falls exactly as
#: the reach rises and depth costs a perfect player nothing. What grows is the
#: whole tour.
#:
#: Seven is a starting value with one measured anchor, and the round's last
#: slice gates it: the oracle has to get everybody out of the largest building
#: with every clock at the floor.
CLOCK_PER_ROOM = 7


def clock_floor(rooms: int) -> int:
    """The shortest clock a building of `rooms` rooms may hand anybody.

    22 blood at three rooms, which is 44 seconds, and 64 at nine, which is 128.
    (The issue that asked for this glossed nine rooms as 86 seconds; 86 is the
    six-room figure. The formula and its 44-second anchor agree, and the gloss
    was the slip.)
    """
    return CLOCK_FLOOR + CLOCK_PER_ROOM * max(0, rooms - 3)
VARY_FROM = 5
MOST_FLIES = 9

#: **The ladder, one new thing a level** (issue #146, rulings 6 to 8). It
#: revises three rows of the previous round's ruling 9, which was taken three
#: days earlier and is superseded rather than forgotten: six-second wall memory
#: now runs to Level 6 rather than Level 3, `pace: 5` arrives at Level 8 rather
#: than 4, and `spray: 4` at Level 10 rather than 4.
#:
#: The reason the earlier position changed is that ruling 9 was taken when Level
#: 4 gained nothing structural, and it now gains a **ring**. Halving the wall
#: memory on the level that introduces a topology makes the topology
#: unlearnable, and Level 4 was already the steepest single step in the game --
#: it moved four dials at once while Levels 6 to 9 were nearly flat. Spreading
#: them out addresses both with one move, and **Level 4 is expected to get
#: easier**.
#:
#:     level  rooms  what is new                doors   flies  spray  pace  fade
#:     4      4      a fourth room and a ring   centre  6      5      6     2
#:     5      4      doorways leave the middle  off     6      5      6     2
#:     6      5      one room with one way out  off     6      5      6     2
#:     7      5      the wall memory halves     off     7      5      6     1
#:     8      7      a second loop, two junctions off    8      5      6     1
#:     9      9      two more rooms; a dead end can be empty
#:                                              off     9      5      6     1
#:     10     9      spray 5 to 4, and the beam quickens
#:                                              off     9      4      5     1
#:     13     9      spray 4 to 3               off     9      3      5     1
#:     14+    9      the clock, to the floor    off     9      3      5     1
#:
#: **`pace: 5` is at Level 10 and not Level 8** (ruled 2026-09-30), which revises
#: ruling 8 a second time -- it went from Level 4 to Level 8 in the issue and from
#: Level 8 to Level 10 here, and both times for a measured reason.
#:
#: At Level 8 **perfect play could not finish the level**: the oracle cleared six
#: seeds of eight, and on the worst it freed all seven people and then lost all
#: three lives to twenty-seven bites. What made that visible was fixing the
#: transposed magnet cell (`Session._magnet_cell`): before it, a magnetised fly in
#: a room reached north or south walked at the wrong wall and never crossed, so the
#: magnet did not work in any of this round's new shapes. With it working, Level 8
#: was two rooms, the eighth fly *and* the quicker beam at one level-up -- three
#: things, which is exactly the fault the round was raised to fix about Level 4.
#:
#: Moving it to 10 clears every level from 1 to 9 on all eight seeds **and leaves
#: no row of the ladder moving more than two dials**, which the issue's own table
#: did not manage. Level 9 at `PACE_FROM = 9` also cleared; 10 was taken because it
#: is the arrangement that obeys "one new thing a level" best.
#:
#: `magnet:` is refused outright: measured, it is not monotonic (55 of 56 saved
#: at five seconds, **42** at ten, 55 at twenty), so a ladder up it walks a
#: curve that is not one.
PACE_FROM, LATE_PACE = 10, 5
#: The spray steps down at these levels, one charge each, to `LATE_SPRAY`.
SPRAY_FROM, SPRAY_AGAIN, LATE_SPRAY = 10, 13, 3
DOORS_OFF_CENTRE = 5
#: Where the six-second wall memory ends: the levels that teach hold the room in
#: mind for twice as long, and that now runs to the end of Level 6.
FADE_HALVES_AT = 7
#: Where the clock starts tightening. Everything before it is a new *shape* or a
#: new dial; the clock is what is left once the building has stopped growing.
CLOCK_FROM = 14

#: The nine-room building Levels 4 and up are cut from (issue #146). Not a
#: level: `levels()` globs `level*.txt` and this is not one, so nothing loads it
#: by number.
LADDER_FILE = "ladder.txt"

#: How many of the ladder's rooms are switched on, by level. The chain is
#: 4, 4, 5, 5, 7, 9 -- and **eight is skipped deliberately**: seven is the last
#: size at which every room holds somebody, so eight buys one empty leaf for
#: nothing.
LADDER_ROOMS = {4: 4, 5: 4, 6: 5, 7: 5, 8: 7}
MOST_ROOMS = 9

#: The building's fly count by level, as a **total** and never a per-room
#: number. Six until the building stops being a teaching shape, then one more a
#: level to `MOST_FLIES`.
FLIES_AT = {7: 7, 8: 8}


def ladder_rooms(n: int) -> int:
    """How many of the ladder's nine rooms Level `n` switches on."""
    return LADDER_ROOMS.get(n, MOST_ROOMS)


def ladder_flies(n: int) -> int:
    """The building's whole swarm at Level `n`."""
    return FLIES_AT.get(n, 6 if n < 7 else MOST_FLIES)

#: Where a doorway sits once it stops sitting in the middle. Cycled by level,
#: so a level number names a building: the same rows every run of Level 6.
#: Clear of the corners, three rows, running together -- which is what
#: `build` refuses anything else for.
#: **None of them is the middle**, or the ladder would hand a level back the
#: room it had just stopped teaching: a five-band cycle that included 10-12
#: put Level 9's doorways back in the centre.
DOOR_BANDS = ((5, 6, 7), (15, 16, 17), (7, 8, 9), (13, 14, 15),
              (4, 5, 6), (16, 17, 18))


def _shifted(rows, n: int):
    """The rows a doorway takes on level `n`, once they leave the middle."""
    return DOOR_BANDS[(n - DOORS_OFF_CENTRE) % len(DOOR_BANDS)]


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
    """Level `n` past the last file: the ladder cut to size, dials turned.

    Issue #146. It used to be Level 3 re-rolled with the clock cut, which was
    the whole of the progression once the fly count topped out -- and Level 3 is
    a three-room column, so no amount of dial-turning could ever have produced a
    ring. The ladder is its own authored building of nine rooms
    (`ladder.txt`), and a level takes **the first `ladder_rooms(n)` of them**:
    four for the ring, five with the first dead end, seven for two loops and a
    spur, nine for two loops and three spurs.

    Cutting rooms means cutting the doorways that led to them, which is the whole
    mechanism: the file authors every edge of the nine-room shape and a level
    keeps the ones with both ends switched on. Nothing about the shape is
    computed -- it is authored once and sliced.

    **Levels 1 to 3 are not on this ladder**, and they are not supersets of one
    another either: a row, a corner and a column, three teaching shapes that
    each meet one axis with the rest of the game held still. The superset chain
    starts here.
    """
    from . import seeds
    path = LEVELS_DIR / LADDER_FILE
    _number, name, specs, budget, _shapes = parse(path.read_text(), str(path))
    if len(specs) != MOST_ROOMS:
        raise ValueError(f"{path}: the ladder authors {len(specs)} rooms, "
                         f"and the biggest building is {MOST_ROOMS}")
    for spec in specs:
        if spec.roll is None:
            raise ValueError(f"{path}: every room of the ladder must roll, "
                             f"and {spec.name!r} does not")

    # **The rooms that are on**, and then the doorways whose far end is also on.
    live = ladder_rooms(n)
    specs = specs[:live]
    on = {spec.name for spec in specs}
    for spec in specs:
        spec.doors = [d for d in spec.doors if d[2] in on]

    # The clock holds until the building has stopped growing and every dial has
    # arrived; from `CLOCK_FROM` it tightens `CLOCK_STEP` a level to the floor,
    # which is the building's own and rose with the rooms (issue #143).
    floor = clock_floor(len(specs))
    cut = CLOCK_STEP * max(0, n - CLOCK_FROM + 1)
    roster = tuple(max(floor, blood - cut) for blood in budget.people)

    for spec in specs:
        # **A spur keeps `repeat`** (ruling 12): the one room you cannot go
        # round is the one room whose light you can learn to time. Everything
        # else varies once the player has met the ring.
        if n >= VARY_FROM and len(spec.doors) > 1:
            spec.searchlight.vary = True
        if n >= PACE_FROM:
            spec.searchlight.pace = LATE_PACE
        # Doorways stop sitting at the exact middle of the wall (#135, ruling
        # 8), from Level 5 rather than Level 4 (#146). Which band they move to is
        # the level's and not a roll: the same level number gives the same
        # building, and a doorway that moved per seed would be a room you cannot
        # learn at all.
        if n >= DOORS_OFF_CENTRE:
            spec.doors = [(side, _shifted(span, n), to, line)
                          for side, span, to, line in spec.doors]

    # **The swarm is a building total** and never a per-room number (ruling 12),
    # so it is dealt here rather than authored: evenly over the live rooms with
    # the remainder to the deepest, which are the rooms a player reaches last.
    flies = ladder_flies(n)
    for i, spec in enumerate(specs):
        spec.roll["clegs"] = flies // live + (1 if i >= live - flies % live else 0)

    budget = budget._replace(
        people=roster,
        # Six seconds of wall memory is for the levels that teach, and that now
        # runs to the end of Level 6 rather than Level 3 (#146 revising #137's
        # ruling 9): halving it on the level that introduces a topology makes
        # the topology unlearnable.
        fade=2 if n < FADE_HALVES_AT else 1,
        # The spray walks down once the building has stopped growing: five, then
        # four at Level 10, then three at 13.
        spray=max(LATE_SPRAY, budget.spray - (1 if n >= SPRAY_FROM else 0)
                  - (1 if n >= SPRAY_AGAIN else 0)))
    building = build(specs, f"{path} as level {n}",
                     roll_seed=seeds.roll_seed(seed, n), people=roster,
                     people_seed=seeds.people_seed(seed, n))
    building.level = n
    building.title = name
    building.name = BEYOND_NAMES[(n - LAST_FILE - 1) % len(BEYOND_NAMES)]
    building.budget = budget._replace(building=building.name)
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
