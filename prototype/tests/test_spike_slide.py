"""A Cleg blocked by a wall slides along it (issue #85).

The user stood at the start cell under the magnet and lived; a fly sat in
the box above the start with the player's cell as its goal, straight through
the box's floor, and never arrived. The greedy step had nothing to try once
the wanted axis was refused and the other axis's delta was zero.
"""

from spikes import clegs as C, scene, session as S
from spikes.session import Intent, Session
from spotlight.core.constants import CELL

START = (18, 10)


def _room():
    # The hand-drawn room A (issue #121): the slide is about its box.
    from playtest import room_a
    return room_a()


def _walk(fly: C.Cleg, goal, frames: int = 400, avoid=None) -> list:
    """Step one fly toward a fixed goal through the near room's walls."""
    path = []
    for _ in range(frames):
        fly._toward(*goal, _room().is_solid, avoid)
        path.append((fly.cx, fly.cy))
        if (fly.cx, fly.cy) == goal:
            break
    return path


def test_the_box_above_the_start_and_the_wall_below_it_are_walls():
    room = _room()
    assert room.is_solid(18, 7) and not room.is_solid(15, 7), "the box's floor and mouth"
    assert room.is_solid(18, 15) and not room.is_solid(19, 15), "the wall under the start"
    assert not room.is_solid(*START)


def test_a_fly_in_the_box_reaches_the_player_straight_below_it():
    fly = C.Cleg(18, 6, seed=5)
    path = _walk(fly, START)
    assert path[-1] == START, f"never arrived: {path[-8:]}"
    assert (15, 7) in path, "it did not leave by the box's mouth"


def test_a_fly_under_the_wall_reaches_the_player_straight_above_it():
    fly = C.Cleg(18, 16, seed=5)
    path = _walk(fly, START)
    assert path[-1] == START, f"never arrived: {path[-8:]}"


def test_no_slide_starts_with_an_open_line_and_the_step_is_the_old_one():
    fly = C.Cleg(10, 10, seed=5)
    fly._toward(18, 10, _room().is_solid)
    assert (fly.cx, fly.cy) == (11, 10) and fly.slide == (0, 0)
    fly._toward(18, 13, _room().is_solid)
    assert (fly.cx, fly.cy) == (12, 10) and fly.slide == (0, 0), \
        "the longer axis first, as before"


def test_a_slide_does_not_step_back_to_where_it_was_stuck():
    """Held while the wanted axis is closed; the other axis is not tried
    before it, or the two cells trade places for ever."""
    fly = C.Cleg(18, 6, seed=5)
    path = _walk(fly, START, frames=3)
    assert len(set(path)) == len(path), f"it oscillated: {path}"
    assert path == [(17, 6), (16, 6), (15, 6)], "not a slide along the box's floor"


def test_the_slide_is_dropped_when_the_wanted_axis_opens():
    fly = C.Cleg(18, 6, seed=5)
    _walk(fly, START, frames=3)
    assert fly.slide != (0, 0), "no slide was started against the wall"
    while (fly.cx, fly.cy) != (15, 6):
        fly._toward(*START, _room().is_solid)
    fly._toward(*START, _room().is_solid)
    assert (fly.cx, fly.cy) == (15, 7) and fly.slide == (0, 0)


def test_a_refused_slide_flips_once_and_a_dead_end_stands():
    # A one-cell pocket: everything but the cell itself is solid.
    solid = lambda cx, cy: (cx, cy) != (5, 5)
    fly = C.Cleg(5, 5, seed=5)
    fly._toward(5, 9, solid)
    assert (fly.cx, fly.cy) == (5, 5)
    assert fly.slide != (0, 0), "it did not even try to slide"
    # A wall to the left only: the slide, signed by the coin, flips if refused.
    solid = lambda cx, cy: cy == 6 or cx < 5
    fly = C.Cleg(5, 5, seed=5)
    fly._toward(5, 9, solid)
    assert (fly.cx, fly.cy) == (6, 5)


def test_the_statue_at_the_start_is_found_under_the_magnet():
    """The user's report, as a run: stand at the start cell, do nothing. Every
    hunting fly in the room that the magnet aims at the player arrives
    within a few seconds, none sits six cells off with the player as its
    goal for the length of a magnet."""
    run = Session(seed=0xBEEF)
    stuck = 0
    for _ in range(3000):
        run.step(Intent())
        if run.magnet:
            for fly in run.place.swarm.clegs:
                if fly.state == C.HUNTING and fly.goal == START \
                        and (fly.cx, fly.cy) in ((18, 6), (18, 16)):
                    stuck += 1
    assert stuck < 60, f"a fly sat at the wall for {stuck} magnet frames"
