"""Clegs: one rule, and everything that follows from it."""

from spikes import clegs as C, lighting as L, sources as S
from spikes.layout import PLAY_ROWS
from spikes.spotlights import FloorLight, Spotlights
from spotlight.core.constants import COLS

OPEN = lambda cx, cy: False          # noqa: E731 - a room with no walls


def _lures(*cells):
    """Cells as lures a Cleg can notice from anywhere."""
    return [(cx, cy, S.FAR) for cx, cy in cells]


def _run(swarm, lures, player=(20, 10), frames=1, is_solid=OPEN, blood=64):
    """`lures` may be given as plain cells; they carry full reach."""
    lures = [l if len(l) == 3 else (*l, S.FAR) for l in lures]
    for _ in range(frames):
        blood = swarm.tick(lures, player, is_solid, blood)
    return blood


# --- the one rule: only lit light attracts ---------------------------------

def test_the_personal_glow_pulls_only_from_close():
    """Standing still in the dark is a reprieve, not a hiding place."""
    glow = S.Glow()
    glow.x, glow.y = 10, 10
    assert glow.lure() == (10, 10, S.GLOW_REACH)
    assert S.GLOW_REACH < S.FAR

    # A fly with every reason to come still cannot notice you from across it.
    keen = C.Cleg(10 + S.GLOW_REACH + 2, 10, seed=0xBEEF)
    assert C.Swarm.nearest_lure(keen.cx, keen.cy, [glow.lure()],
                                keen.notice) is None
    close = C.Cleg(10 + S.GLOW_REACH - 1, 10, seed=0xBEEF)
    assert C.Swarm.nearest_lure(close.cx, close.cy, [glow.lure()],
                                close.notice) == (10, 10)


def test_a_burning_spotlight_attracts_and_a_dark_one_does_not():
    cone = S.Cone(reach=5, power=100)
    cone.x, cone.y = 10, 10
    assert cone.lure() is None, "switched off, so nothing to come to"
    cone.enabled = True
    assert cone.lure() == (10, 10, S.FAR)
    cone.power = 0
    assert cone.lure() is None, "out of power is out of bait"


def test_the_cone_lures_to_the_player_not_to_the_wedge():
    """The lamp and the blood are at the point of the cone, not in it."""
    cone = S.Cone(reach=6, power=100)
    cone.x, cone.y, cone.facing = 10, 10, S.RIGHT
    cone.enabled = True
    assert cone.lure() == (10, 10, S.FAR)
    assert (14, 10) in cone.cells(), "the wedge really is out in front"


def test_a_room_light_and_a_searchlight_both_attract():
    room = S.RoomLight(4, 4, 4, 2)
    assert room.lure() == (6, 5, S.FAR)
    beam = S.Roaming(15, 10, radius=2, mode=S.Roaming.DRIFT)
    assert beam.lure() == (15, 10, S.FAR)


def test_a_spotlight_left_burning_on_the_floor_is_bait():
    lit = FloorLight(5, 5, power=100, lit=True)
    dark = FloorLight(9, 9, power=100, lit=False)
    kit = Spotlights(S.Cone(), [lit, dark])
    assert kit.floor_lures() == [(5, 5, S.FAR)]


# --- attraction ------------------------------------------------------------

def test_switching_the_light_on_draws_the_clegs_that_can_notice_it():
    near = [C.Cleg(20 + d, 10, seed=0xBEEF + d) for d in (2, 3, 4)]
    swarm = C.Swarm(near)
    before = [max(abs(c.cx - 20), abs(c.cy - 10)) for c in swarm.clegs]
    _run(swarm, [(20, 10)], frames=C.STEP_EVERY * 3)
    after = [max(abs(c.cx - 20), abs(c.cy - 10)) for c in swarm.clegs]
    assert all(a < b for a, b in zip(after, before)), \
        f"Clegs beside the light should close: {before} -> {after}"


def test_a_light_across_the_room_recruits_nobody():
    """A Cleg is not omniscient, and a swarm that all reacts at once is a clump."""
    far = C.Cleg(2, 2, seed=0xBEEF)
    swarm = C.Swarm([far])
    assert far.notice < 25
    _run(swarm, [(30, 20)], frames=C.STEP_EVERY * 4)
    assert far.goal is None, "noticed a light right across the room"


def test_each_cleg_notices_at_its_own_range():
    """So they peel off toward a light at different moments."""
    ranges = {C.Cleg(5, 5, seed=0xBEEF + i * 977).notice for i in range(40)}
    assert len(ranges) > 3, f"the swarm shares one range: {ranges}"
    assert min(ranges) >= C.NOTICE_MIN and max(ranges) <= C.NOTICE_MAX


def test_they_keep_coming_after_the_light_goes_out():
    """A one-second flash is a decision whose cost arrives later."""
    cleg = C.Cleg(26, 10, seed=0xBEEF)
    swarm = C.Swarm([cleg])
    _run(swarm, [(20, 10)], frames=C.STEP_EVERY)     # a glimpse
    assert cleg.goal == (20, 10)
    before = cleg.cx
    _run(swarm, [], frames=C.STEP_EVERY * 3)         # and it is dark again
    assert cleg.cx < before, "gave up the moment the light went out"
    assert cleg.goal == (20, 10), "forgot where it saw the light"


def test_arriving_at_an_empty_spot_ends_the_errand():
    cleg = C.Cleg(21, 10, seed=0xBEEF)
    swarm = C.Swarm([cleg])
    _run(swarm, [(20, 10)], frames=C.STEP_EVERY)
    _run(swarm, [], frames=C.STEP_EVERY * 3)
    assert (cleg.cx, cleg.cy) == (20, 10)
    assert cleg.goal is None, "still heading somewhere it already is"


def test_switching_it_off_makes_them_lose_interest():
    """With nothing lit above a glow, the swarm blunders instead of hunting."""
    swarm = C.Swarm([C.Cleg(2, 2)])
    _run(swarm, [], frames=C.DRIFT_EVERY * 40)
    cleg = swarm.clegs[0]
    assert cleg.state == C.HUNTING, "still hungry, just with nothing to aim at"
    # Drifting is aimless: over many steps it should not have marched anywhere.
    assert max(abs(cleg.cx - 2), abs(cleg.cy - 2)) < 20


def test_they_go_to_the_nearest_light_not_always_to_the_player():
    """Baiting: a burning light closer than you takes the swarm instead."""
    swarm = C.Swarm([C.Cleg(4, 4)])
    _run(swarm, [(20, 10), (2, 2)], player=(20, 10), frames=C.STEP_EVERY * 3)
    cleg = swarm.clegs[0]
    assert (cleg.cx, cleg.cy) != (4, 4)
    assert max(abs(cleg.cx - 2), abs(cleg.cy - 2)) < 2, "should head for the bait"


def test_nearest_lure_compares_squared_distance():
    assert C.Swarm.nearest_lure(0, 0, _lures((10, 0), (0, 3))) == (0, 3)
    assert C.Swarm.nearest_lure(5, 5, []) is None


# --- attach, drain, drop off ------------------------------------------------

def test_an_attached_cleg_drains_a_set_amount_and_then_leaves():
    swarm = C.Swarm([C.Cleg(20, 10)])
    blood = _run(swarm, [(20, 10)], frames=1)
    cleg = swarm.clegs[0]
    assert cleg.state == C.ATTACHED

    blood = _run(swarm, [(20, 10)], frames=C.DRAIN_EVERY * C.DRAIN_TOTAL,
                 blood=blood)
    assert blood == 64 - C.DRAIN_TOTAL, "took exactly its fixed amount"
    assert cleg.state == C.SATED, "and left of its own accord"


def test_a_sated_cleg_eventually_gets_hungry_again():
    swarm = C.Swarm([C.Cleg(20, 10)])
    _run(swarm, [(20, 10)],
         frames=1 + C.DRAIN_EVERY * C.DRAIN_TOTAL + C.SATED_FRAMES + 1)
    assert swarm.clegs[0].state in (C.HUNTING, C.ATTACHED)


def test_several_attach_at_once_and_drain_in_parallel():
    """A swarm arriving together is far worse than one Cleg arriving four times."""
    swarm = C.Swarm([C.Cleg(20, 10) for _ in range(4)])
    blood = _run(swarm, [(20, 10)], frames=1)
    assert len(swarm.attached()) == 4

    blood = _run(swarm, [(20, 10)], frames=C.DRAIN_EVERY, blood=blood)
    assert swarm.drained == 4, "four bites in the same frame, not one"
    assert blood == 64 - 4


def test_blood_never_goes_below_zero():
    swarm = C.Swarm([C.Cleg(20, 10) for _ in range(3)])
    blood = _run(swarm, [(20, 10)], frames=400, blood=2)
    assert blood == 0


# --- what the player cannot do ---------------------------------------------

def test_spray_cannot_reach_a_cleg_that_has_already_attached():
    """Once it is on you the damage is decided. There is no panic button."""
    on_you, loose = C.Cleg(20, 10), C.Cleg(21, 10)
    swarm = C.Swarm([on_you, loose])
    _run(swarm, [(20, 10)], frames=1)
    assert on_you.state == C.ATTACHED
    assert swarm.sprayable() == [loose]


def test_killing_removes_only_the_clegs_given():
    a, b, c = C.Cleg(1, 1), C.Cleg(2, 2), C.Cleg(3, 3)
    swarm = C.Swarm([a, b, c])
    assert swarm.kill([b]) == 1
    assert swarm.clegs == [a, c]


# --- movement, and the absence of pathfinding -------------------------------

def test_a_cleg_slides_along_a_wall_rather_than_pressing_into_it():
    wall = lambda cx, cy: cx == 10 and cy != 5      # noqa: E731 - a gap at y=5
    cleg = C.Cleg(8, 8)
    cleg.notice = 30            # this is about walls, not about eyesight
    swarm = C.Swarm([cleg])
    _run(swarm, [(20, 8)], frames=C.STEP_EVERY * 4, is_solid=wall)
    assert not wall(cleg.cx, cleg.cy), "walked into the wall"
    assert (cleg.cx, cleg.cy) != (8, 8), "gave up instead of sliding"


def test_a_cleg_never_leaves_the_room():
    swarm = C.Swarm([C.Cleg(0, 0)])
    for target in ((-5, -5), (99, 99), (0, 99), (99, 0)):
        _run(swarm, [target], frames=C.STEP_EVERY * 40)
        for c in swarm.clegs:
            assert 0 <= c.cx < COLS and 0 <= c.cy < PLAY_ROWS


def test_there_is_no_route_finding_anywhere_in_the_module():
    """A fly that solved mazes would be a different and costlier animal."""
    import pathlib
    src = pathlib.Path(C.__file__).read_text().lower()
    for banned in ("heapq", "deque", "astar", "a_star", "dijkstra", "bfs",
                   "frontier", "visited"):
        assert banned not in src, f"{banned} has no business in here"


# --- what the buzz is told --------------------------------------------------

def test_nearest_distance_ignores_a_cleg_already_on_you():
    on_you, far = C.Cleg(20, 10), C.Cleg(26, 10)
    swarm = C.Swarm([on_you, far])
    _run(swarm, [(20, 10)], frames=1)
    assert on_you.state == C.ATTACHED
    assert swarm.nearest_distance(20, 10) == 6, "the one on you is not a warning"


def test_nearest_distance_is_none_with_nothing_left():
    assert C.Swarm([]).nearest_distance(5, 5) is None


def test_an_attached_cleg_rides_along_when_you_run():
    """It is on you. Walking away does not leave it draining you from afar."""
    swarm = C.Swarm([C.Cleg(20, 10)])
    _run(swarm, [(20, 10)], player=(20, 10), frames=1)
    cleg = swarm.clegs[0]
    assert cleg.state == C.ATTACHED

    _run(swarm, [(28, 18)], player=(28, 18), frames=1)
    assert (cleg.cx, cleg.cy) == (28, 18), "left behind, still draining"


def test_running_does_not_shake_one_off():
    swarm = C.Swarm([C.Cleg(20, 10)])
    blood = _run(swarm, [(20, 10)], frames=1)
    for step in range(C.DRAIN_EVERY * 2):
        blood = _run(swarm, [(20 + step, 10)], player=(20 + step, 10),
                     frames=1, blood=blood)
    assert blood < 64, "running should not have saved any blood"


# --- the dark hides you; it does not armour you ----------------------------

def test_walking_into_a_cleg_in_the_dark_gets_you_bitten():
    """Contact is contact. It does not have to see you to land on you."""
    swarm = C.Swarm([C.Cleg(20, 10)])
    _run(swarm, [], player=(20, 10), frames=1)
    assert len(swarm.attached()) == 1


def test_nothing_crosses_the_room_for_you_in_the_dark():
    """What the dark buys is not being looked for."""
    far = C.Cleg(2, 2, seed=0xBEEF)
    swarm = C.Swarm([far])
    glow = S.Glow(); glow.x, glow.y = 20, 10
    for _ in range(C.STEP_EVERY * 20):
        swarm.tick([glow.lure()], (20, 10), OPEN, 64)
    assert far.goal is None, "came looking from right across the room"
    assert max(abs(far.cx - 20), abs(far.cy - 10)) > 10


def test_standing_still_is_a_reprieve_and_not_a_hiding_place():
    """Something that blunders close will find you. Keep moving."""
    near = C.Cleg(20 + S.GLOW_REACH - 1, 10, seed=0xBEEF)
    swarm = C.Swarm([near])
    glow = S.Glow(); glow.x, glow.y = 20, 10
    blood = 64
    for _ in range(C.STEP_EVERY * 6):
        blood = swarm.tick([glow.lure()], (20, 10), OPEN, blood)
    assert (near.cx, near.cy) == (20, 10), "never found you at arm's length"
    assert blood < 64, "found you and did nothing"


def test_one_already_attached_keeps_drinking_when_the_light_goes_out():
    """Switching off does not undo a bite. The damage was decided on contact."""
    swarm = C.Swarm([C.Cleg(20, 10)])
    blood = _run(swarm, [(20, 10)], frames=1)
    assert len(swarm.attached()) == 1
    blood = _run(swarm, [], frames=C.DRAIN_EVERY * 2, blood=blood,
)
    assert blood < 64


def test_a_fed_cleg_leaves_rather_than_parking_on_you():
    """One fly draining a whole budget on its own is a leak, not a swarm."""
    cleg = C.Cleg(20, 10, seed=0xBEEF)
    swarm = C.Swarm([cleg])
    _run(swarm, [], player=(20, 10), frames=1)
    assert cleg.state == C.ATTACHED
    _run(swarm, [], player=(20, 10),
         frames=C.DRAIN_EVERY * C.DRAIN_TOTAL + C.SATED_FRAMES)
    assert max(abs(cleg.cx - 20), abs(cleg.cy - 10)) > 2, \
        "still sitting on the cell it fed from"


def test_a_fed_cleg_moves_off_faster_than_an_idle_one():
    assert C.SATED_DRIFT_EVERY < C.DRIFT_EVERY


def test_an_idle_cleg_mills_about_rather_than_crossing_the_room():
    """Otherwise the floor becomes randomly scattered mines and moving costs
    more blood than standing still, which is exactly backwards."""
    cleg = C.Cleg(16, 11, seed=0xBEEF)
    swarm = C.Swarm([cleg])
    _run(swarm, [], player=(0, 0), frames=50 * 20)      # twenty seconds
    assert max(abs(cleg.cx - 16), abs(cleg.cy - 11)) < 12
