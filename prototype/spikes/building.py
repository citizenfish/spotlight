"""A building: rooms, and the doorways between them.

**A room is a whole screen, and stepping through a doorway flicks to the next
one.** That is the Atic Atac model in *Building Structure*, and issue #21 is
where the prototype stops having one room and starts having a building.

The alternative -- one screen split by an internal wall -- was considered and
rejected in the vault, and it is worth repeating here because it looks cheaper
and is not. It is what `scene.ROOM_A` already has, in its inner box: the far
side of an on-screen wall is still on screen, so the moment the second room
exists for (your tail strung out somewhere you cannot see) never happens. Two
rooms on one screen is one room.

Everything below is written so the Pygame answer and the Spectrum answer are the
same answer:

* **A room's cells are its own.** Coordinates are local, 0..31 by 0..21, one
  byte per cell, and no room ever indexes into another one's grid.
* **The threshold is a virtual column.** Column 32 of a room with an east
  doorway *is* column 0 of the room next door, and `is_solid` says so. That one
  delegation is what makes walking through a doorway ordinary movement rather
  than a special case in the player, in the Clegs, and in the follower trail --
  none of which know a doorway exists. On the Z80 it is a compare and an index
  into a two-entry door table.
* **Light does not cross it.** Each room owns its own light field, and a source
  belongs to a room, so a field simply has nowhere to put light that is not its
  room's. Standing in a doorway you cannot see through it. That is the cost the
  vault argues for: compositing two rooms' lighting is exactly what the room
  model exists to avoid, and a threshold you cannot see past makes stepping
  through it a commitment rather than a glance.

**A doorway in a vertical wall must be at least two cells tall**, because a
person is two cells tall and one cell wide. The playtest building's connecting
doorway is three, which is an authoring kindness rather than a rule: the
movement assist nudges by up to a cell, and a door a first-timer bounces off is
the first thing this audience reads as broken. One-cell doorways stay legal and
stay used -- room A's inner box has one.
"""

from spotlight.core.constants import CELL, COLS, MAGENTA, WHITE

from .layout import PLAY_ROWS
from .rescue import NEST_BROOD

# --- the entity budget ------------------------------------------------------
#
# **A level's budget is sized for its worst plausible failure, not its opening
# state.** Issue #33, and it is the first mechanic that manufactures entities:
# until nests, everything on screen was authored and counting the authored list
# was counting the worst case. A nest makes six Clegs out of nothing, so the
# question a level has to answer is no longer "what did you draw" but "what can
# this become".
#
# **The unit is T-states, and issue #34 is what it cost to learn that.** This
# counted in *Cleg-equivalents* against a ceiling of eighteen, which is the
# figure *The 48K cycle budget* arrived at **with pixel-positioned flies** --
# and cell-aligned Clegs were taken as a decision on 2026-09-07 precisely
# because nests do not fit under it. So the valve spent #33 guarding T-states
# that had been bought back the day before: measured, it refused a spawn with
# the room at **27 to 61 per cent** of the real budget, and a Statue's six nests
# landed nine flies of the thirty-six they owe.
#
# *Nests* had already written down why the unit was the trap, in the same note
# that then used it: **"Cleg-equivalents stop being a useful currency when the
# sprite format changes."** A ceiling denominated in one entity's cost moves
# whenever that entity's sprite format moves, and it has now moved once. The
# figures below are quoted from *The 48K cycle budget* rather than re-derived,
# so there is one place to change them when the port measures a real routine.
#
# **Drawing is the whole cost.** That note prices the frame's fixed work --
# the fade, the dirty attributes, the stipple -- at 19,584 T-states and leaves
# what is below for entities. Steering is nearly free by comparison and
# amortises to under 50 T-states a fly, which is why a room nobody is looking
# at is not on this bill at all.

#: A moving 8x16 person: six cells composited with a visibility test, plus the
#: restore. The player, a waiting worker, a follower.
PERSON_COST = 2902

#: A **cell-aligned** 8x8 Cleg. Roughly half a pixel-positioned one (1,654),
#: because a cell-aligned sprite needs no pre-shift and no second byte column.
#: That halving is the whole reason nests fit.
CLEG_COST = 830

#: A body, and a nest: **nothing, because neither moves.**
#:
#: *The 48K cycle budget* is explicit -- the per-entity figures price *movement*,
#: and a body is a fixture drawn from remembered ground alongside walls and
#: keys, so on the port it belongs to the dirty-cell accounting rather than to
#: this budget. A nest is the same shape: cell-sized state with a timer.
#:
#: **How many there can be is a bound, not a count** (issue #36). This used to
#: justify itself with a receipt -- *"measured over twenty runs, four bots and
#: five seeds: never more than two"* -- and then a Wanderer drew four in one
#: room on a wider sweep. The receipt was false, but that is not the mistake
#: worth remembering: **twenty runs was not too few, any number of runs would
#: have been too few**, because a sample cannot bound a worst case. An
#: observation was written where a bound was needed.
#:
#: The bound was available all along and costs nothing to take. A body is gone
#: `rescue.GONE_FRAMES` after the death that made it, so a room holds at most
#: the deaths that fit in fifty seconds -- and a follower dies where they fall,
#: so any worker in the building can die in any room. See
#: `Building.most_fixtures`, and `worst_case`, which now maximises over how
#: many of them are dead rather than assuming one.
#:
#: **The zero is not falsified; its safety margin is.** The old comment quoted
#: an exposure of +2,496 T-states if the zero turned out wrong. At the real
#: bound it is the roster, which for the playtest building is +20,314 against a
#: peak frame already at 83% of the entity budget. So if this ever stops being
#: zero, the sum has to be re-taken rather than adjusted -- and it will be,
#: because `worst_case` reads it.
FIXTURE_COST = 0

#: What a frame has left for entities, after the fixed work. From
#: *The 48K cycle budget*: 52,416 T-states a frame, less 19,584 of fade, dirty
#: attributes and stipple.
ENTITY_CEILING = 32832


def cost(clegs: int = 0, people: int = 0, nests: int = 0, bodies: int = 0,
         fixtures: int = 0) -> int:
    """What this many of each costs to draw, in T-states.

    `nests`, `bodies` and `fixtures` are the same price and are three names for
    the caller's convenience: a nest and a body are both cell-sized state that
    does not move, and `fixtures` is for the callers that have already added
    them up.
    """
    return (clegs * CLEG_COST + people * PERSON_COST
            + (nests + bodies + fixtures) * FIXTURE_COST)

# --- the authoring legend ---------------------------------------------------
# A room is written as text because it has to be read by a person, not parsed
# quickly. It is converted once, at start-up, into the two things the game
# actually uses: a solidity test and a per-cell ink map.

WALL, FLOOR, DOOR, KEY, ROOM_LIGHT = "#", ".", "D", "K", "L"

#: A gap in a wall (issue #48). **Floor in every mechanical respect -- walkable,
#: stippled, remembered, and not solid** -- and a drawing character and nothing
#: else. It exists because a one-cell doorway drawn as plain floor is an
#: *absence*, and an absence in a dark room is indistinguishable from a room
#: that stops there; a `d` cell draws returns instead, short ticks continuing
#: each wall it touches into the opening. See `tiles.DOORWAY`.
#:
#: **Authored rather than inferred**, per *Art Direction* section 3: the author
#: knows where the doorways are, and deriving it would mean every floor cell in
#: the room asking a question that only a dozen of them can answer differently.
#: One character of level data, no runtime inference.
#:
#: Lower case because it is not a `DOOR`. A `D` is the way out of the building,
#: it is 8x16, it can be locked and it carries a key's hue; a `d` is a hole.
DOORWAY = "d"

#: Every cell kind a room may be written with. A room's palette has to name all
#: of them, because a glyph with no ink is a cell that would be drawn in
#: whatever the last one wore.
CELL_KINDS = (WALL, FLOOR, DOOR, KEY, ROOM_LIGHT, DOORWAY)

#: The hues that mean a **thing** rather than a **place**, so they are the same
#: in every room of the building (issue #47, *Art Direction* section 2).
#:
#: * WHITE is solid. A wall is the one thing you must never walk into, so it
#:   keeps the one constant hue and the floor carries which room you are in.
#: * MAGENTA is a door -- and **a key takes the hue of the door it opens**, so
#:   the key is magenta here rather than the cyan it used to be. *Building
#:   Structure* already says a door's colour says which key; tying the two
#:   together is what that sentence implied, and it frees cyan to mean the
#:   spray and nothing else. Cyan meaning two things was the collision that
#:   forced this.
#:
#: BLUE appears nowhere in this table and nowhere in a room's, deliberately:
#: non-bright blue on black is the least legible pair the machine sells, and
#: this game is played in the dark.
#: A doorway is WHITE for the same reason a wall is: what it draws is the ends
#: of the walls either side of it, and those are white in every room of every
#: building. It is the one non-solid cell that takes a solid cell's hue, and it
#: takes it because of what is drawn there rather than because of what it is --
#: you can walk through it, and *Art Direction*'s per-room colour table says
#: WHITE in both rooms.
CONSTANT_INK = {
    WALL: WHITE,
    DOOR: MAGENTA,
    KEY: MAGENTA,
    DOORWAY: WHITE,
}


def palette(floor: int) -> dict:
    """A room's ink table: the building's constant hues, plus its own floor.

    One ink byte per cell kind, authored beside the room's map, because colour
    is how a player tells one room from another -- the loudest complaint any
    tester has made about this game is that they could not hold the building's
    geography, and a global ink map cannot answer it.

    **The room light zone takes the floor's hue** and not one of its own: it is
    floor that happens to be lit, and giving it a hue would make the emergency
    lighting a different *place* rather than the same place lit.

    Cheap on the Z80 as well as here: five bytes per room in ROM, and an
    attribute byte costs exactly the same whatever colour it holds, so the
    per-frame cost of a palette is nothing at all.
    """
    return dict(CONSTANT_INK, **{FLOOR: floor, ROOM_LIGHT: floor})


#: What a room gets when it authors no palette of its own: the all-white
#: scheme the whole game wore before issue #47. Nothing the player ever sees
#: uses it -- both rooms in `scene` author their own -- and it exists so that
#: a scratch room built by a test or a tool need not invent a colour scheme to
#: ask a question about walls.
DEFAULT_INK = palette(WHITE)

SOLID = frozenset({WALL})

#: The way out of the building. It is drawn as a door because a room with a
#: door you cannot leave by is a strange room.
EXIT = DOOR

#: Which side of a room a doorway is in. Only the two vertical walls are needed
#: by the playtest building; a doorway in a horizontal wall is the *easier*
#: case (a person is one cell wide, so one cell across fits) and is left until
#: a room wants one.
EAST, WEST = 0, 1

#: How wide a person is, in pixels. Used only to decide when a figure has
#: cleared a threshold entirely.
PERSON_WIDTH = 8


class Doorway:
    """A gap in one of a room's vertical walls, and the room beyond it.

    `rows` are the cell rows the gap occupies, in **both** rooms: the vault
    puts the doorway at the same rows on each side, so the world is continuous
    and only the view jumps.
    """

    __slots__ = ("side", "rows", "to")

    def __init__(self, side: int, rows, to: int) -> None:
        self.side = side
        self.rows = tuple(rows)
        #: Index of the room on the other side, within the same `Building`.
        self.to = to

    @property
    def column(self) -> int:
        """The column, in this room, that the gap is cut through."""
        return COLS - 1 if self.side == EAST else 0

    @property
    def beyond(self) -> int:
        """The virtual column just past the threshold. Not in this room."""
        return COLS if self.side == EAST else -1

    @property
    def landing(self) -> int:
        """The column, in the room beyond, that `beyond` corresponds to."""
        return 0 if self.side == EAST else COLS - 1

    @property
    def middle(self) -> int:
        """The row a word written over this doorway sits on."""
        return self.rows[len(self.rows) // 2]

    def cells(self) -> list[tuple[int, int]]:
        """The gap, in this room's coordinates."""
        return [(self.column, cy) for cy in self.rows]

    def __repr__(self) -> str:
        side = "east" if self.side == EAST else "west"
        return f"Doorway({side}, rows {self.rows[0]}-{self.rows[-1]}, to {self.to})"


class Searchlight:
    """What a room authors about its roaming light, or `None` for none at all.

    Mode and radius are per light, not per game -- *Light and Darkness* is
    explicit that a building may escalate across its rooms. Room B authors no
    searchlight at all, which is the first time any room has said no.
    """

    __slots__ = ("radius", "vary")

    def __init__(self, radius: int = 3, vary: bool = False) -> None:
        self.radius = radius
        self.vary = vary


class Room:
    """One screen: walls, doorways, and the entities authored into it.

    The data is authored, never rolled. A room is designed.
    """

    def __init__(self, name: str, rows, *, ink=None, workers=(), clegs=(),
                 spotlights=(), searchlight: Searchlight | None = None,
                 player_start: tuple[int, int] | None = None,
                 doorways=()) -> None:
        self.name = name
        self.rows = tuple(rows)
        #: **The room owns its palette** (issue #47). It used to be one global
        #: map from cell kind to ink, which meant every room in the building
        #: was the same colour and nothing on screen said which one you were
        #: standing in. See `palette`.
        self.ink = dict(ink if ink is not None else DEFAULT_INK)
        #: (x, y, blood) in pixels and blood points, local to this room.
        self.workers = tuple(tuple(w) for w in workers)
        #: (cx, cy). Clegs live on the cell grid; pixel placement would cost
        #: the Z80 a shift and a mask per fly per frame for no gain.
        self.clegs = tuple(tuple(c) for c in clegs)
        #: (cx, cy, power).
        self.spotlights = tuple(tuple(s) for s in spotlights)
        self.searchlight = searchlight
        self.player_start = player_start
        self.doorways = tuple(doorways)
        #: Set by `Building`. A room does not exist on its own -- it needs to
        #: know what is on the other side of its doorways.
        self.building: "Building | None" = None
        self.index = 0

    def __repr__(self) -> str:
        return f"Room({self.name!r})"

    # --- shape --------------------------------------------------------------

    def validate(self) -> None:
        """The room must be exactly the play area, or nothing else lines up."""
        if len(self.rows) != PLAY_ROWS:
            raise ValueError(
                f"{self.name}: {len(self.rows)} rows, need {PLAY_ROWS}")
        for y, row in enumerate(self.rows):
            if len(row) != COLS:
                raise ValueError(
                    f"{self.name}: row {y} is {len(row)} cells, need {COLS}")
            unknown = set(row) - set(self.ink)
            if unknown:
                raise ValueError(
                    f"{self.name}: row {y} has unknown cells: {sorted(unknown)}")
        for i, worker in enumerate(self.workers):
            # Position and blood are authored on the same line so they cannot
            # drift apart, and the shape is checked because a two-element row
            # would silently fall back to the default clock for everybody --
            # the exact bug issue #18 exists to remove.
            if len(worker) != 3:
                raise ValueError(
                    f"{self.name}: worker {i} is {worker}, need (x, y, blood)")
            if worker[2] <= 0:
                raise ValueError(f"{self.name}: worker {i} starts dead")
        for door in self.doorways:
            if len(door.rows) < 2:
                # A person is two cells tall and one wide, so a doorway in a
                # *vertical* wall needs two rows or nobody fits. The rule was
                # written for horizontal walls, which is the only case the
                # prototype had, and it does not carry over unchanged.
                raise ValueError(
                    f"{self.name}: doorway {door} is {len(door.rows)} cells "
                    f"tall; a vertical wall needs at least two")
            for cy in door.rows:
                if self.rows[cy][door.column] in SOLID:
                    raise ValueError(
                        f"{self.name}: doorway {door} is walled up at row {cy}")

    def is_solid(self, cx: int, cy: int) -> bool:
        """Can nothing stand here?

        **This is the only authority on what is walkable**, and it is what the
        player, the Clegs and the bots all consult -- so making the column just
        past a doorway answer for the room next door is the whole of the
        crossing mechanism. Nothing else in the game knows a doorway exists.
        """
        if not 0 <= cy < PLAY_ROWS:
            return True
        if 0 <= cx < COLS:
            return self.rows[cy][cx] in SOLID
        beyond = self.across(cx, cy)
        if beyond is None:
            return True
        room, ncx, ncy = beyond
        return room.rows[ncy][ncx] in SOLID

    # --- what a cell is made of, for drawing only ---------------------------
    #
    # Neither of these is an authority on anything a player can do. `is_solid`
    # is, and it stays the only one -- see its docstring. These two answer a
    # *drawing* question, about this room's own grid, and the difference
    # matters at exactly one place: the column past a doorway. `is_solid`
    # delegates it to the room next door, because walking through is ordinary
    # movement; the tile mask must not, because **off the room counts as
    # wall**, which is what makes the outer wall show one face -- inward -- and
    # nothing get drawn against the screen edge. A mask that reached across a
    # threshold would also cost the Z80 a door-table lookup per wall cell per
    # frame, to change what a handful of cells at the very edge of the screen
    # look like.

    def is_wall(self, cx: int, cy: int) -> bool:
        """Is this cell solid **in this room's own grid**? Drawing only."""
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return True
        return self.rows[cy][cx] in SOLID

    def is_doorway(self, cx: int, cy: int) -> bool:
        """Is this cell an authored gap in a wall? Drawing only."""
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return False
        return self.rows[cy][cx] == DOORWAY

    def across(self, cx: int, cy: int) -> "tuple[Room, int, int] | None":
        """What is at (cx, cy) when it is past one of this room's walls.

        Returns the room next door and the same point in *its* coordinates, or
        None if there is no doorway there -- which is nearly always, because a
        doorway is three rows out of twenty-two.
        """
        if self.building is None:
            return None
        for door in self.doorways:
            if cx == door.beyond and cy in door.rows:
                return self.building.rooms[door.to], door.landing, cy
        return None

    def doorway_to(self, other: int) -> Doorway | None:
        for door in self.doorways:
            if door.to == other:
                return door
        return None

    # --- contents -----------------------------------------------------------

    def ink_map(self) -> bytearray:
        """Per-cell hue for the whole play area, from **this room's** palette.

        One byte per cell, and it is the only thing that chooses a cell's
        colour: light chooses the brightness, contents choose the hue, and
        neither ever consults the other. That is what keeps attribute clash
        impossible while the two rooms wear different schemes.
        """
        return bytearray(self.ink[c] for row in self.rows for c in row)

    def solid_map(self) -> bytes:
        """One byte per cell, 1 where a wall is. Built on request, not held.

        For the repaint counter (issue #46), which has to split the cells that
        changed light level into walls and floor and cannot afford a method
        call per cell to do it. Nothing in the game asks for this, so nothing
        in the game builds it -- it is made once by a run that is measuring
        itself and by no other.

        It goes through `is_solid` rather than reading `rows` a second time,
        because `is_solid` is the only authority on what is walkable and a
        second definition of a wall is a second thing to keep in step.
        """
        return bytes(1 if self.is_solid(cx, cy) else 0
                     for cy in range(PLAY_ROWS) for cx in range(COLS))

    def cells_of(self, kind: str) -> list[tuple[int, int]]:
        return [(cx, cy) for cy, row in enumerate(self.rows)
                for cx, c in enumerate(row) if c == kind]

    def light_zones(self) -> list[tuple[int, int, int, int]]:
        """The authored room lights, as (left, top, width, height) rectangles.

        Runs on a row are joined, and **rows are merged downward when they line
        up**, so a block of `L` cells is one light rather than one per row.
        That matters more than it looks: a room light is a lure as well as an
        illumination, and three stacked one-row zones would put three lures a
        cell apart, which is not what the author drew. Room B's light over the
        doorway home is the first block-shaped one any room has authored.
        """
        zones: list[list[int]] = []
        for cy, row in enumerate(self.rows):
            run_start = None
            for cx in range(COLS + 1):
                lit = cx < COLS and row[cx] == ROOM_LIGHT
                if lit and run_start is None:
                    run_start = cx
                elif not lit and run_start is not None:
                    width = cx - run_start
                    grown = next(
                        (z for z in zones
                         if z[0] == run_start and z[2] == width
                         and z[1] + z[3] == cy), None)
                    if grown is not None:
                        grown[3] += 1
                    else:
                        zones.append([run_start, cy, width, 1])
                    run_start = None
        return [tuple(z) for z in zones]

    @property
    def has_exit(self) -> bool:
        return bool(self.cells_of(EXIT))

    def exit_cell(self) -> tuple[int, int]:
        """The one cell that counts as out. Reaching it with a tail saves them.

        Where a door is more than one cell tall, this is the top of it; the
        others are still walkable and still `EXIT` ink, and touching any part of
        the doorway puts the top cell inside the figure's box, so which one is
        named makes no difference to the player.
        """
        doors = self.cells_of(EXIT)
        if not doors:
            raise ValueError(f"{self.name} has no way out")
        return doors[0]

    def exit_facing(self) -> tuple[int, int]:
        """Which way is out, as a direction to walk in.

        The exit delivers on touch and **leaving is pushing through it** (issue
        #28), so the door needs an outside: a wall it is set into, and a
        direction that carries you out of it rather than along it.

        That is exactly why it **cannot sit in a corner**. A cell in the top-left
        is in two walls at once and there is no answer to "which way is out",
        so this refuses rather than picking one. A door that is in no wall at
        all is refused for the same reason -- it is a hole in the floor, and
        walking off it in any direction just puts you back in the room.
        """
        ex, ey = self.exit_cell()
        walls = [(-1, 0)] * (ex == 0) + [(1, 0)] * (ex == COLS - 1) \
            + [(0, -1)] * (ey == 0) + [(0, 1)] * (ey == PLAY_ROWS - 1)
        if len(walls) != 1:
            raise ValueError(
                f"{self.name}: the way out at {(ex, ey)} is "
                + ("in a corner" if walls else "not in a wall")
                + ", so there is no direction that leads out of it")
        return walls[0]

    def exit_sign_cells(self, word: str) -> list[tuple[int, int]]:
        """Where the sign hangs: alongside the door, on the same row.

        **Lit whatever else is,** because that is what an emergency exit sign
        does -- it has its own battery, and it is the one thing in a failing
        building you can count on seeing. It is also the only fixed thing in a
        room that tells the player where they are going, and a way out you
        cannot find is not a way out.

        Beside rather than above: the exit used to be a door in the top wall,
        where above it is masonry. It is now in the **west** wall (issue #21),
        where beside means to the east -- into the room rather than into the
        bricks. So the side is chosen from where the door is rather than
        assumed, which is what a second room forced.
        """
        if not self.has_exit:
            return []
        ex, ey = self.exit_cell()
        if ex <= len(word):
            left = ex + 1                      # a door in the west wall
        else:
            left = max(0, min(COLS - len(word), ex - len(word)))
        return [(left + i, ey) for i in range(len(word))]


class Building:
    """Rooms, and what is on the other side of each doorway.

    A building rather than a level: entities cross doorways, so the population
    ceiling and the tally are the building's and not any one room's. See
    *The Playtest Building* -- "a room is a view, not a container".
    """

    def __init__(self, rooms) -> None:
        self.rooms = list(rooms)
        for i, room in enumerate(self.rooms):
            room.building = self
            room.index = i

    def __len__(self) -> int:
        return len(self.rooms)

    def __getitem__(self, index: int) -> Room:
        return self.rooms[index]

    def validate(self) -> None:
        for room in self.rooms:
            room.validate()
        for room in self.rooms:
            for door in room.doorways:
                back = self.rooms[door.to].doorway_to(room.index)
                if back is None:
                    raise ValueError(
                        f"{room.name}: {door} has no door back again")
                if back.rows != door.rows:
                    # The world is continuous and only the view jumps, which is
                    # only true if the two sides line up. A doorway that landed
                    # you somewhere else would teleport a tail.
                    raise ValueError(
                        f"{room.name}: {door} does not line up with {back}")
        # **Can the swarm get everywhere the player can?** Last, because it
        # needs the doorways to line up first -- a fly reaches part of a room
        # by walking in through one. See `swarming`: floor the player can reach
        # and the Clegs cannot is a permanent refuge in a dark game, and it is
        # invisible to whoever drew the room. It is a level property and not
        # something the searchlight can guarantee.
        from . import swarming
        for room in self.rooms:
            stranded = swarming.unswarmable(room)
            if stranded:
                raise ValueError(
                    f"{room.name}: the swarm cannot reach "
                    f"{len(stranded)} floor cells, starting at {stranded[0]}")

    # --- the entity budget --------------------------------------------------

    @property
    def population(self) -> int:
        """Every Cleg the building starts with. All of them can be in one room."""
        return sum(len(room.clegs) for room in self.rooms)

    @property
    def roster(self) -> int:
        """How many people this building has in it to lose."""
        return sum(len(room.workers) for room in self.rooms)

    @property
    def largest_tail(self) -> int:
        """The most people who can be walking behind the player at once.

        Everybody but the one whose death made the nest. A tail is a set of
        *living* workers, and the worst plausible failure has a nest in it, so
        one of them is on the floor rather than in the line.
        """
        return max(0, self.roster - 1)

    @property
    def most_fixtures(self) -> int:
        """The most bodies and nests one room can be holding at once.

        **A bound, and that is the point of it** (issue #36). A body is gone
        `rescue.GONE_FRAMES` after the death that made it, so a room holds at
        most the deaths that fit into fifty seconds -- and since a follower dies
        where they fall, any worker in the building can die in any room. In the
        worst case that is the whole roster, and no measurement is needed or
        would help: a sample cannot bound a worst case, which is the lesson the
        receipt this replaced was bought with.

        The prototype's measured peak is four in one room over 105 runs, which
        this bound comfortably contains. That is what a bound is for.
        """
        return self.roster

    @property
    def most_lamps(self) -> int:
        """The most dropped spotlights one room can be holding at once.

        **The whole building's**, not a room's, because a spotlight moves: a
        swap leaves the one you were carrying where you stand, so every light
        in the building can end up on one room's floor.

        A dropped spotlight is a fixture -- it stays put, the fade may remember
        it, and since issue #49 it is drawn on the floor like a key. It is
        counted here because **the day `FIXTURE_COST` stops being zero, these
        move with it** rather than waiting for somebody to remember that the
        room has lamps in it. Today it changes no number at all.
        """
        return sum(len(room.spotlights) for room in self.rooms)

    def worst_case(self) -> int:
        """What this building can come to in one room, in T-states.

        **The worst plausible failure, not the opening state**: the swarm the
        level authored, one nest's full brood, the player, and whatever mixture
        of dead and following the roster can be in.

        **Dead and following are the same people**, so the two cannot both be at
        their maximum -- every fixture on the floor is a person not in the line.
        This maximises over the split rather than assuming it, which matters
        only if `FIXTURE_COST` ever stops being zero: today the worst is one
        death, because a body is free and a follower is not, and the sum lands
        in the same place the hand-written version did. **The day the zero
        moves, this moves with it** rather than needing somebody to remember.

        At least one is dead, because a level with no nest in it is not the
        failure this is sizing for.

        **The room's authored spotlights are counted as fixtures too** (issue
        #49). They are free today, because a fixture is priced at zero, and
        that is exactly the reason to count them now: the arithmetic has to
        find them the day the zero moves.

        **This counts the building's whole swarm**, where the runtime valve
        counts a room's -- see `Session._load`. Clegs cross doorways and go to
        light, so a room's authored population is not its worst case and a level
        author cannot be told that it is. The valve is asked whether a frame can
        be drawn *now*; this is asked whether the level can ever ask for one
        that cannot.
        """
        flies = self.population + NEST_BROOD
        lamps = self.most_lamps
        return max(cost(clegs=flies, people=1 + self.roster - dead,
                        fixtures=min(dead, self.most_fixtures) + lamps)
                   for dead in range(1, max(1, self.roster) + 1))

    @property
    def over_budget(self) -> int:
        """T-states by which the worst plausible failure beats the ceiling.

        **Counted here and refused nowhere**, per *Nests*: *"the valve, which is
        now the budget's only guarantee"*. A level over the ceiling is a level
        whose nests the valve will hold up; it is not a level that cannot be
        drawn, because holding the spawn is what stops the drawing ever being
        asked for.

        **The playtest building is inside it**, with about five per cent spare,
        and the reading that said otherwise was issue #34: the ceiling was the
        pixel-positioned one. `test_held_constants.py` pins the arithmetic both
        ways round, because a number that was wrong once in this direction is
        worth being able to see is right now.
        """
        return max(0, self.worst_case() - ENTITY_CEILING)

    def index_of(self, name: str) -> int:
        for i, room in enumerate(self.rooms):
            if room.name == name:
                return i
        raise KeyError(name)

    @property
    def start(self) -> tuple[int, tuple[int, int]]:
        """Which room the player starts in, and where in it."""
        for i, room in enumerate(self.rooms):
            if room.player_start is not None:
                return i, room.player_start
        raise ValueError("no room in this building starts the player")

    @property
    def exit(self) -> tuple[int, tuple[int, int]]:
        """The one way out of the whole building."""
        for i, room in enumerate(self.rooms):
            if room.has_exit:
                return i, room.exit_cell()
        raise ValueError("this building has no way out")

    @property
    def exit_facing(self) -> tuple[int, int]:
        """The direction you have to keep walking in to leave (issue #28)."""
        for room in self.rooms:
            if room.has_exit:
                return room.exit_facing()
        raise ValueError("this building has no way out")

    # --- crossing -----------------------------------------------------------

    def step_across(self, index: int, cx: int, cy: int):
        """Where a *cell-placed* entity that stepped past a wall ends up.

        Returns `(room index, cx, cy)` or None. Clegs move a cell at a time and
        are stopped by `Room.is_solid`, so the only way to be here at all is to
        have walked through a doorway.
        """
        beyond = self.rooms[index].across(cx, cy)
        if beyond is None:
            return None
        room, ncx, ncy = beyond
        return room.index, ncx, ncy

    def cross(self, index: int, x: int, y: int, width: int = PERSON_WIDTH):
        """Where a *pixel-placed* figure that walked off a room's edge ends up.

        Returns `(room index, x)` or None. **The transition happens when the
        figure has cleared the threshold entirely**, not when it first touches
        it, which is what keeps the walk continuous: at x=255 you straddle room
        A's last column and room B's first, and at x=256 you are wholly in room
        B's first column, which is x=0 there. Nothing jumps but the view.
        """
        room = self.rooms[index]
        if x >= COLS * CELL:
            side, moved = EAST, x - COLS * CELL
        elif x + width <= 0:
            side, moved = WEST, x + COLS * CELL
        else:
            return None
        rows = range(y // CELL, (y + 2 * CELL - 1) // CELL + 1)
        for door in room.doorways:
            if door.side == side and any(cy in door.rows for cy in rows):
                return door.to, moved
        return None
