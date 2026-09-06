"""A hand-built static room, for judging the look.

Not a level format and not a level editor -- just enough fixed content that the
four questions in issue #5 can be answered by looking at something.

The room is written as text because it has to be read by a person, not parsed
quickly. Legend:

    #  wall        D  door (its own hue)
    .  floor       K  key (its own hue)
    L  room light zone (floor, but authored as always lit)
"""

from spotlight.core.constants import (
    BLACK, CYAN, GREEN, MAGENTA, WHITE, COLS,
)

from .layout import PLAY_ROWS

ROOM = (
    "################################",
    "#LLLLLL#......................D#",
    "#LLLLLL#.......................#",
    "#LLLLLL#....########...........#",
    "#LLLLLL#....#......#...........#",
    "#LLLLLL#....#......#...........#",
    "#...........#......#...........#",
    "#...........########...........#",
    "#..............................#",
    "#####.#####....................#",
    "#..............................#",
    "#.........#####................#",
    "#..............................#",
    "#....K.........................#",
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


#: Entities, at deliberately awkward pixel offsets so they straddle cells.
#: (sprite name, x, y) in pixels.
ENTITIES = (
    ("worker", 14 * 8 + 3, 4 * 8 + 2),      # inside the inner room, dark
    ("worker", 3 * 8 + 4, 2 * 8),           # in the room light, fully lit
    ("cleg", 12 * 8 + 5, 6 * 8 + 3),        # hard against a wall
    ("cleg", 20 * 8 + 2, 12 * 8 + 6),       # open floor
    ("body", 7 * 8 + 2, 17 * 8 + 4),
    ("nest", 27 * 8 + 5, 19 * 8 + 1),
)

#: Where the player starts: on the edge of the room light, so the very first
#: thing on screen is a figure straddling a light boundary.
PLAYER_START = (6 * 8 + 4, 5 * 8)
