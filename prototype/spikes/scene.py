"""A hand-built static room, for judging the look.

Not a level format and not a level editor -- just enough fixed content that the
four questions in issue #5 can be answered by looking at something.

The room is written as text because it has to be read by a person, not parsed
quickly. Legend:

    #  wall        D  door (its own hue)
    .  floor       K  key (its own hue) -- none in this room
    L  room light zone (floor, but authored as always lit)

**There is no key in this room, and no room light.**

The key went because it did nothing: doors and keys are not being built in this
spike, so it was a cyan glyph on the floor that could not be picked up and
opened nothing. The legend and the hue stay, since a key is a real thing in
[[Building Structure]] and the colour rule is worth keeping exercised, but this
room does not place one. There was one, a six-by-five block in
the top-left corner, and in play it was a rectangle of dots that never changed:
permanently lit ground with nothing to say, once room lights stopped revealing
the people standing in them. The legend and `light_zones` stay, because
`RoomLight` is still one of the four sources and is still under test -- this
room simply does not author one.
"""

from spotlight.core.constants import (
    BLACK, CYAN, GREEN, MAGENTA, WHITE, COLS,
)

from .layout import PLAY_ROWS

ROOM = (
    "################################",
    "#......#......................D#",
    "#......#.......................#",
    "#......#....########...........#",
    "#......#....#......#...........#",
    "#......#....#......#...........#",
    "#...........#......#...........#",
    "#...........###.####...........#",
    "#..............................#",
    "#####.#####....................#",
    "#..............................#",
    "#.........#####................#",
    "#..............................#",
    "#..............................#",
    "#..............................#",
    "#..........########............#",
    "#..............................#",
    "#..............................#",
    "#........................#######",
    "#..............................#",
    "#..............................#",
    "################################",
)

WALL, FLOOR, DOOR, KEY, ROOM_LIGHT = "#", ".", "D", "K", "L"

#: The way out. Where you came in, and where rescued workers have to be led.
#: It is the door: a room with a door you cannot leave by is a strange room.
EXIT = DOOR

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


def validate() -> None:
    """The room must be exactly the play area, or nothing else lines up."""
    if len(ROOM) != PLAY_ROWS:
        raise ValueError(f"room is {len(ROOM)} rows, need {PLAY_ROWS}")
    for y, row in enumerate(ROOM):
        if len(row) != COLS:
            raise ValueError(f"row {y} is {len(row)} cells, need {COLS}")
        unknown = set(row) - set(INK)
        if unknown:
            raise ValueError(f"row {y} has unknown cells: {sorted(unknown)}")


def ink_map() -> bytearray:
    """Per-cell hue for the whole play area."""
    return bytearray(INK[c] for row in ROOM for c in row)


def is_solid(cx: int, cy: int) -> bool:
    if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
        return True
    return ROOM[cy][cx] in SOLID


def cells_of(kind: str) -> list[tuple[int, int]]:
    return [(cx, cy) for cy, row in enumerate(ROOM)
            for cx, c in enumerate(row) if c == kind]


def light_zones() -> list[tuple[int, int, int, int]]:
    """The authored room lights, as (left, top, width, height) runs."""
    zones = []
    for cy, row in enumerate(ROOM):
        run_start = None
        for cx in range(COLS + 1):
            lit = cx < COLS and row[cx] == ROOM_LIGHT
            if lit and run_start is None:
                run_start = cx
            elif not lit and run_start is not None:
                zones.append((run_start, cy, cx - run_start, 1))
                run_start = None
    return zones


#: The inner room has a **one-cell doorway** in its bottom wall, at (15, 7).
#: It was sealed until spike 2 was played -- a box with a worker in it that
#: nobody could reach, because while sprites were the question nobody had tried
#: to walk in. `test_every_floor_cell_is_reachable` now makes that impossible to
#: reintroduce.
#:
#: One cell wide on purpose: it is exactly the case the corner assist in
#: `player.NUDGE` exists for, so the room is also the test of it.
INNER_DOOR = (15, 7)

#: Which entity kinds move. Movers are only drawn where a light is on them
#: this frame; the rest are fixtures the fade is allowed to remember.
MOVERS = frozenset({"worker", "cleg"})

#: Entities, at deliberately awkward pixel offsets so they straddle cells.
#: (sprite name, x, y) in pixels.
#: Fixed scenery. **Empty on purpose.** A body and a nest were placed here while
#: sprites were the question in spike 1, and they stayed long after they meant
#: anything -- two objects on screen that could not be reached, sprayed or
#: rescued. Bodies come from workers who bleed out now, and nests are not built.
#: The list stays because the drawing code and its tests are about the *kinds*
#: of thing a room holds, not about these two.
ENTITIES = ()

#: Trapped workers, as (x, y) in pixels. **These are the reason to want light.**
#:
#: Spike 2 had nothing to look for, which made its own question unanswerable:
#: you cannot judge whether switching the light on is worth it when there is
#: nothing you need to see. Finding these is the objective -- no tail, no quota,
#: no blood clocks, none of which spike 2 is building. Reaching one is enough.
#:
#: They are people, so they are only drawn where a light is on them, and the
#: opening flash does not show them. You are given the shape of the room and
#: not who is in it, which is exactly the bargain: the layout is free and the
#: people cost you light, and light costs you blood.
#:
#: Spread into corners the player has to commit to, and one behind the inner
#: room's single doorway.
#:
#: **None of them near the exit.** One was two cells from the door, which is not
#: a rescue -- there is no journey, no decision about when to leave, and nothing
#: the clock can bite on. A worker's distance from the way out is the size of the
#: bet you take by going to fetch them.
WORKERS = (
    (14 * 8 + 3, 4 * 8 + 2),        # inside the inner room, through one door
    (3 * 8 + 4, 2 * 8),             # top left
    (9 * 8 + 2, 4 * 8),             # north, behind the inner room
    (2 * 8 + 3, 19 * 8),            # bottom left
    (29 * 8, 19 * 8),               # bottom right, behind the low wall
    (17 * 8 + 5, 16 * 8),           # open floor, easy
    (7 * 8 + 2, 11 * 8),            # mid left
)

#: What the exit sign says, and it is always on.
EXIT_SIGN = "EXIT"


def exit_sign_cells() -> list[tuple[int, int]]:
    """Where the sign hangs: alongside the door, on the same row.

    **Lit whatever else is,** because that is what an emergency exit sign does --
    it has its own battery and it is the one thing in a failing building you can
    count on seeing. It is also the only fixed thing in the room that tells the
    player where they are going, and a way out you cannot find is not a way out.

    Beside rather than above: the door is in the top wall, and above it is the
    wall itself.
    """
    ex, ey = exit_cell()
    left = max(0, min(COLS - len(EXIT_SIGN), ex - len(EXIT_SIGN)))
    return [(left + i, ey) for i in range(len(EXIT_SIGN))]


def exit_cell() -> tuple[int, int]:
    """The one cell that counts as out. Reaching it with a tail saves them."""
    doors = cells_of(EXIT)
    if not doors:
        raise ValueError("the room has no way out")
    return doors[0]


#: Where the swarm starts, in cells. Clegs live on the cell grid -- they have
#: no need of pixel placement, and putting them there would cost the Z80 a
#: shift-and-mask per fly per frame for no gain.
#:
#: Spread wide and none of them near the player, so a swarm has to travel and
#: you hear it coming long before it arrives.
CLEGS = ((11, 6), (26, 14), (2, 3), (29, 8), (6, 20), (24, 19))

#: Spotlight pickups lying about the building, as (cx, cy, power). Powers vary
#: deliberately -- picking one up is a commitment, and a weak one is a trap.
SPOTLIGHTS = (
    (4, 16, 900),
    (26, 3, 400),
    (16, 20, 1500),
    (2, 10, 150),
)

#: Where the player starts. Open floor with room to move in every direction, at
#: an x offset that is not a multiple of 8 so the figure straddles two cell
#: columns from the very first frame.
#:
#: Two things the first attempt got wrong: the whole 8x16 box has to clear the
#: walls rather than just the cell the coordinates land in -- the first choice
#: put the player's shoulder inside a wall and they could not move at all -- and
#: the start should have room in every direction, not be tucked under a wall.
PLAYER_START = (17 * 8 + 4, 9 * 8)
