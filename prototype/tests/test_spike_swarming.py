"""Can the swarm get there? The level check from issue #26.

The finding it comes from: a low wall across row 18 enclosed the near room's
bottom-right corner, and a motionless player lost 146.2 blood in the middle of
the room against **1.6 in that corner** over the same 150 seconds. The beam
reached it. The flies got closer to it than to the middle and then piled
against the wall, because they steer and slide rather than pathfind.

So the check has to run the Cleg's own rule. A flood fill asks whether a path
exists, which is the wrong question about an animal that cannot find one.

**Issue #131 took the original case away and the check is still needed.** The
piling-against-the-wall the measurement saw was a limit cycle in `_toward`:
the slide was dropped the moment the longest axis changed, so a fly beside a
long wall oscillated and never came round the end. A fly that follows a wall
to its end reaches row 18's corner, so that room passes now, and the test
which used to assert it was flagged asserts the reverse and says why.

What survives is the argument, not the example. `hook_room` below is a shape
the fixed fly still cannot enter and a flood fill still calls connected --
found by measuring the candidates after #131 rather than by reasoning about
them -- and it is the class of mistake the bare-shell gate exists to catch.
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
    """The hand-drawn room A with a wall in it, and its own swarm to be
    reached by. Room A rolls now (issue #121); the copy is `playtest.py`'s."""
    import playtest
    return B.Room("pocket", walled(playtest.ROOM_A, wall or ROW_18_WALL),
                  clegs=playtest.CLEGS_A, workers=playtest.WORKERS_A,
                  player_start=playtest.PLAYER_START)


def test_the_playtest_building_can_be_swarmed_everywhere():
    """The check runs as level validation, so this is really pinning that the
    authored building passes it -- and that a room that did not could not be
    loaded at all."""
    scene.validate()
    for room in scene.BUILDING.rooms:
        assert swarming.unswarmable(room) == []


#: A pocket that survives a fly which **does** follow a wall to its end: a
#: division down column 14, a bay along row 10 to the east border, and a lip
#: along row 17 that closes the dogleg. The wedge north-east of the bay is
#: joined to the rest of the room -- a flood fill walks into it -- and a
#: greedy stepper cannot, because reaching it means going *west* past the
#: division first, which is away from the target on both axes.
#:
#: Found by measurement after issue #131, not invented: the shapes that used
#: to strand a fly (one wall with a gap, a spiral, two walls with opposed
#: gaps) are all reachable now, and this is the class that is not. It is
#: also exactly the authoring mistake the bare-shell gate exists to catch --
#: three walls, which no shell is allowed anyway.
HOOK_WALL = ([(cx, 10) for cx in range(14, COLS - 1)]
             + [(14, cy) for cy in range(10, 18)]
             + [(cx, 17) for cx in range(14, 24)])


def hook_room():
    """A bare shell with `HOOK_WALL` in it and one east doorway to come in by."""
    rows = [[B.WALL] * COLS]
    rows += [[B.WALL] + [B.FLOOR] * (COLS - 2) + [B.WALL]
             for _ in range(PLAY_ROWS - 2)]
    rows.append([B.WALL] * COLS)
    for cx, cy in HOOK_WALL:
        rows[cy][cx] = B.WALL
    door_rows = (10, 11, 12)
    for cy in door_rows:
        rows[cy][COLS - 1] = B.DOORWAY
    return B.Room("hook", ("".join(r) for r in rows), player_start=(24, 96),
                  doorways=(B.Doorway(B.EAST, door_rows, 0),))


def test_the_corner_the_measurement_found_is_reachable_since_the_slide_was_held():
    """Row 18's wall, put back -- and **the pocket is not a pocket any more.**

    This test asserted the opposite until issue #131, and the reversal is the
    point. The #26 measurement found flies that *"got closer to the corner
    than to the middle and then piled against the wall"*, and piling against
    a wall is precisely the limit cycle #131 removed: the slide used to be
    dropped the moment the longest axis changed, so a fly beside a long wall
    ping-ponged in a band that never contained the gap. A fly that follows a
    wall to its end walks round this one.

    So the corner that was ninety-one times safer is ordinary floor now, and
    it was a bug in the animal rather than a fact about the room. The check
    below is still worth having -- `hook_room` is a shape the fixed fly still
    cannot enter -- but the room this module was named for passes it.
    """
    assert swarming.unswarmable(pocket_room()) == []
    # And so does the same wall with its gap four columns along, which used to
    # be the contrast case: where the gap is no longer decides anything.
    passable = [(cx, 18) for cx in range(20, COLS - 1) if cx != 28]
    assert swarming.unswarmable(pocket_room(passable)) == []


def test_a_pocket_a_flood_fill_calls_reachable_is_still_flagged():
    """The acceptance criterion, and the difference between the two questions:
    *is there a path* and *can something that cannot find one get there*.

    Every cell flagged here is a cell a flood fill joins to the rest of the
    room. The fly comes in through the east doorway, steers at the wedge,
    meets the bay, follows it to its end -- and the lip along row 17 puts the
    end back where it started.
    """
    room = hook_room()
    stranded = set(swarming.unswarmable(room))
    assert stranded, "nothing was flagged at all"
    assert stranded <= flood(room), \
        "a flood fill agrees it is unreachable, so this proves nothing"


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
        B.Building((hook_room(),)).validate()
