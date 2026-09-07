"""Can the swarm get there? The level check from issue #26.

The finding it comes from: a low wall across row 18 enclosed the near room's
bottom-right corner, and a motionless player lost 146.2 blood in the middle of
the room against **1.6 in that corner** over the same 150 seconds. The beam
reached it. The flies got closer to it than to the middle and then piled
against the wall, because they steer and slide rather than pathfind.

So the check has to run the Cleg's own rule. A flood fill asks whether a path
exists, which is the wrong question about an animal that cannot find one.
"""

import pytest

from spikes import building as B, scene, swarming
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import COLS


def flood(room):
    """What a flood fill would say: every floor cell joined to any other."""
    start = next((cx, cy) for cy in range(PLAY_ROWS) for cx in range(COLS)
                 if not room.is_solid(cx, cy))
    seen, queue = {start}, [start]
    while queue:
        cx, cy = queue.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (cx + dx, cy + dy)
            if (nb not in seen and 0 <= nb[0] < COLS and 0 <= nb[1] < PLAY_ROWS
                    and not room.is_solid(*nb)):
                seen.add(nb)
                queue.append(nb)
    return seen


def walled(rows, wall):
    """A copy of a room's map with `wall` cells filled in."""
    grid = [list(row) for row in rows]
    for cx, cy in wall:
        grid[cy][cx] = B.WALL
    return ["".join(row) for row in grid]


#: The wall that was across row 18 of the near room, with the gap the player
#: walked in through. Room A opened it as part of issue #21, so the case the
#: check exists for has to be rebuilt to be pinned. The gap's column matters
#: and that is the finding: at columns 26 to 29 a steering fly gets round it
#: and the pocket is not a pocket at all.
ROW_18_WALL = [(cx, 18) for cx in range(20, COLS - 1) if cx != 25]


def pocket_room(wall=None):
    """The near room with a wall in it, and its own swarm to be reached by."""
    return B.Room("pocket", walled(scene.ROOM_A, wall or ROW_18_WALL),
                  clegs=scene.CLEGS_A, workers=scene.WORKERS_A,
                  player_start=scene.PLAYER_START)


def test_the_playtest_building_can_be_swarmed_everywhere():
    """The check runs as level validation, so this is really pinning that the
    authored building passes it -- and that a room that did not could not be
    loaded at all."""
    scene.validate()
    for room in scene.BUILDING.rooms:
        assert swarming.unswarmable(room) == []


def test_the_corner_the_measurement_found_is_flagged():
    """Row 18's wall, put back: the pocket that was ninety-one times safer."""
    stranded = swarming.unswarmable(pocket_room())
    assert stranded, "the enclosed corner was not flagged"
    assert all(cy > 18 and cx > 25 for cx, cy in stranded), stranded


def test_a_pocket_a_flood_fill_calls_reachable_is_still_flagged():
    """The acceptance criterion, and the difference between the two questions:
    *is there a path* and *can something that cannot find one get there*.

    Every cell flagged here is a cell a flood fill joins to the rest of the
    room. The player walks in through the gap; the flies steer at it, meet the
    wall, slide along it and never come round the end.
    """
    room = pocket_room()
    stranded = set(swarming.unswarmable(room))
    assert stranded, "nothing was flagged at all"
    assert stranded <= flood(room), \
        "a flood fill agrees it is unreachable, so this proves nothing"


def test_where_the_gap_is_decides_whether_it_is_a_pocket():
    """The same wall with the same size of hole in it, four columns along, is
    not a refuge -- which is exactly why this cannot be eyeballed by whoever
    drew the room."""
    passable = [(cx, 18) for cx in range(20, COLS - 1) if cx != 28]
    assert swarming.unswarmable(pocket_room(passable)) == []


def test_the_starts_are_where_flies_actually_are():
    """A fly is somewhere the author put it, or it walked in through a door.

    Never a grid over the floor: a start placed inside a pocket would report
    the pocket as reachable because something was already standing in it.
    """
    near = scene.BUILDING[scene.NEAR]
    places = swarming.origins(near)
    for door in near.doorways:
        assert all((door.column, cy) in places for cy in door.rows)
    for cleg in near.clegs:
        assert tuple(cleg) in places
    assert len(places) == len(set(near.clegs)) + sum(
        len(d.rows) for d in near.doorways)


def test_the_check_is_not_a_flood_fill():
    """Stated as a property of the code, because it is the whole issue: this
    must never quietly become a search."""
    source = (swarming.can_reach.__doc__ or "") + (swarming.__doc__ or "")
    assert "_toward" in source
    fly_steps = swarming.can_reach.__code__.co_names
    assert "_toward" in fly_steps, "it stopped using the Cleg's own rule"


def test_a_room_the_swarm_cannot_cover_will_not_load():
    """Level validation, not a script somebody remembers to run."""
    with pytest.raises(ValueError, match="swarm cannot reach"):
        B.Building((pocket_room(),)).validate()
