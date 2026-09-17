"""The playtest building's room A as it was drawn by hand, for the tests
that need a fixed geometry.

Room A rolled from the light round on (issue #121): its walls are the seed's
now, and the vault's *The Playtest Building* is the record. Three things in
the suite are about a *particular* shape -- the inner box and its one-cell
doorway, the slide along the box's floor, the pocket a wall across row 18
made -- and they take it from here rather than from `scene`, which is a view
of whatever Level 3 rolled for the default seed.
"""

from spikes import building as B

#: The map, byte for byte as `level3.txt` carried it from 2026-09-07 to the
#: light round: the inner box with its one-cell door at (15, 7), the wall
#: turned on its side at column 24, the pipe run at row 15, and the east
#: doorway at rows 10-12.
ROOM_A = (
    "################################",
    "#......#.......................#",
    "#......#.......................#",
    "#......#....########...........#",
    "#......#....#......#...........#",
    "#......#....#......#...........#",
    "#...........#......#...........#",
    "#...........###d####...........#",
    "#..............................#",
    "#####.#####....................#",
    "D..............................d",
    "D.........xx[]x................d",
    "#..............................d",
    "#..............................#",
    "#..............................#",
    "#..........========............#",
    "#..............................#",
    "#.......................|......#",
    "#.......................|......#",
    "#.......................|......#",
    "#.......................|......#",
    "################################",
)
WORKERS_A = ((141, 128, 90), (115, 34, 40), (232, 152, 30))
CLEGS_A = ((2, 3), (29, 8), (6, 20))
PLAYER_START = (140, 72)
INNER_DOOR = (15, 7)


def room_a(doorways=True) -> B.Room:
    """Room A as a `Room`, with or without its east doorway."""
    rows = ROOM_A
    if not doorways:
        rows = tuple(row[:-1] + "#" if row.endswith("d") else row for row in ROOM_A)
    return B.Room("the main room", rows, ink=B.palette(6),
                  workers=WORKERS_A, clegs=CLEGS_A,
                  searchlight=B.Searchlight(3, False),
                  player_start=PLAYER_START,
                  doorways=(B.Doorway(B.EAST, (10, 11, 12), 1),) if doorways else ())
