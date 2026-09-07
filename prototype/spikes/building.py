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

from spotlight.core.constants import CELL, COLS, CYAN, MAGENTA, WHITE

from .layout import PLAY_ROWS

# --- the authoring legend ---------------------------------------------------
# A room is written as text because it has to be read by a person, not parsed
# quickly. It is converted once, at start-up, into the two things the game
# actually uses: a solidity test and a per-cell ink map.

WALL, FLOOR, DOOR, KEY, ROOM_LIGHT = "#", ".", "D", "K", "L"

#: What hue each kind of cell wears. Light decides how bright; this decides
#: which colour. Both are per-cell and single-valued, so no clash.
INK = {
    WALL: WHITE,
    FLOOR: WHITE,
    ROOM_LIGHT: WHITE,
    DOOR: MAGENTA,
    KEY: CYAN,
}

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

    def __init__(self, name: str, rows, *, workers=(), clegs=(),
                 spotlights=(), searchlight: Searchlight | None = None,
                 player_start: tuple[int, int] | None = None,
                 doorways=()) -> None:
        self.name = name
        self.rows = tuple(rows)
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
            unknown = set(row) - set(INK)
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
        """Per-cell hue for the whole play area."""
        return bytearray(INK[c] for row in self.rows for c in row)

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
