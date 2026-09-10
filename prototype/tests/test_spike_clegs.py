"""Clegs: one rule, and everything that follows from it."""

from spikes import clegs as C, lighting as L, sources as S
from spikes.layout import PLAY_ROWS
from spikes.spotlights import FloorLight, Spotlights
from spotlight.core.constants import COLS

def OPEN(cx, cy):
    """A room with no walls **inside** it. It is still a room.

    Since issue #21 `is_solid` is the only authority on where a fly may stand,
    edges included, because the column just past a doorway is the next room's
    first column and `Room.is_solid` is what says so. A test fixture that
    answers False everywhere is a plane rather than a room, and a Cleg walks off
    it -- which is what these tests used to be asserting could not happen.
    """
    return not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS)


def _lures(*cells):
    """Cells as lures a Cleg can notice from anywhere.

    A lure is `(cx, cy, reach, kind)` since issue #22 -- the kind is what a
    bite gets billed to and takes no part in the choice.
    """
    return [(cx, cy, S.FAR, S.LURE_TORCH) for cx, cy in cells]


def _run(swarm, lures, player=(20, 10), frames=1, is_solid=OPEN, blood=64):
    """`lures` may be given as plain cells; they carry full reach."""
    lures = [l if len(l) == 4 else (*l, S.FAR, S.LURE_TORCH) for l in lures]
    for _ in range(frames):
        blood = swarm.tick(lures, player, is_solid, blood)
    return blood


# --- the one rule: only lit light attracts ---------------------------------

def test_the_personal_glow_pulls_only_from_close():
    """Standing still in the dark is a reprieve, not a hiding place."""
    glow = S.Glow()
    glow.x, glow.y = 10, 10
    assert glow.lure() == (10, 10, S.GLOW_REACH, S.LURE_GLOW)
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
    assert cone.lure() == (10, 10, S.FAR, S.LURE_TORCH)
    cone.power = 0
    assert cone.lure() is None, "out of power is out of bait"


def test_the_cone_lures_to_the_player_not_to_the_wedge():
    """The lamp and the blood are at the point of the cone, not in it."""
    cone = S.Cone(reach=6, power=100)
    cone.x, cone.y, cone.facing = 10, 10, S.RIGHT
    cone.enabled = True
    assert cone.lure() == (10, 10, S.FAR, S.LURE_TORCH)
    assert (14, 10) in cone.cells(), "the wedge really is out in front"


def test_a_room_light_and_a_searchlight_both_attract():
    room = S.RoomLight(4, 4, 4, 2)
    assert room.lure() == (6, 5, S.FAR, S.LURE_ROOM)
    beam = S.Roaming(15, 10, radius=2, mode=S.Roaming.DRIFT)
    assert beam.lure() == (15, 10, S.FAR, S.LURE_BEAM)


def test_a_spotlight_left_burning_on_the_floor_is_bait():
    lit = FloorLight(5, 5, power=100, lit=True)
    dark = FloorLight(9, 9, power=100, lit=False)
    kit = Spotlights(S.Cone(), [lit, dark])
    assert kit.floor_lures() == [(5, 5, S.FAR, S.LURE_FLOOR)]


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
    wall = lambda cx, cy: OPEN(cx, cy) or (cx == 10 and cy != 5)   # noqa: E731
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


# --- not every Cleg is the same Cleg (issue #10) ---------------------------

def _of_kind(kind, cx=20, cy=10):
    """A Cleg of a chosen temperament, for testing one behaviour at a time."""
    cleg = C.Cleg(cx, cy, seed=0xBEEF)
    cleg.kind = kind
    return cleg


def test_a_swarm_is_mostly_fodder_with_a_few_clever_ones():
    """Being cornered by a clever one should be an event, not the norm."""
    from collections import Counter
    kinds = Counter(C.Cleg(5, 5, seed=1 + i * 7919).kind for i in range(400))
    assert kinds[C.PLAIN] > kinds[C.FLANKER] > kinds[C.DODGER]
    assert kinds[C.PLAIN] >= 160, "not enough fodder"
    dodgy = kinds[C.DODGER] + kinds[C.WARY]
    assert 60 <= dodgy <= 140, f"{dodgy} of 400 dodge spray"


def test_they_do_not_all_move_in_lockstep():
    """Identical speeds are half of why the swarm moved as one body."""
    speeds = {C.Cleg(5, 5, seed=1 + i * 7919).step_every for i in range(200)}
    assert len(speeds) > 1
    assert min(speeds) >= C.STEP_EVERY
    assert max(speeds) < C.STEP_EVERY + C.STEP_SPREAD


def test_nobody_is_faster_than_the_player():
    """You must always be able to outrun them."""
    from spikes.player import SPEED
    frames_per_cell_for_the_player = 8 // SPEED
    for i in range(200):
        assert C.Cleg(5, 5, seed=1 + i * 7919).step_every > \
            frames_per_cell_for_the_player


# --- dodging ---------------------------------------------------------------

def test_a_plain_cleg_walks_straight_into_spray():
    """Which is what the spray is for."""
    cleg = _of_kind(C.PLAIN, 24, 10)
    swarm = C.Swarm([cleg])
    poison = lambda cx, cy: cx == 22        # noqa: E731 - a wall of spray
    for _ in range(C.STEP_EVERY * 6):
        swarm.tick(_lures((20, 10)), (20, 10), OPEN, 64, is_sprayed=poison)
    assert cleg.cx <= 22, "stopped short of ground it does not fear"


def test_a_dodger_will_not_step_into_spray():
    cleg = _of_kind(C.DODGER, 24, 10)
    cleg.notice = 30
    swarm = C.Swarm([cleg])
    poison = lambda cx, cy: cx == 22        # noqa: E731
    for _ in range(C.STEP_EVERY * 8):
        swarm.tick(_lures((20, 10)), (20, 10), OPEN, 64, is_sprayed=poison)
        assert not poison(cleg.cx, cleg.cy), "walked into the spray"


def test_dodging_is_not_immunity():
    """Spray it is standing on still kills it. Denial, not a force field."""
    import spikes.spray as sp
    cleg = _of_kind(C.WARY, 20, 10)
    swarm = C.Swarm([cleg])
    spray = sp.Spray(charges=1)
    spray.patches[(0, (20, 10))] = 100
    assert spray.kills(swarm.sprayable()) == [cleg]


def test_a_dodger_holds_ground_rather_than_charging_it():
    """Spray still does its job against them: area denial, not a weapon."""
    cleg = _of_kind(C.DODGER, 22, 10)
    cleg.notice = 30
    swarm = C.Swarm([cleg])
    boxed = lambda cx, cy: (cx, cy) != (22, 10)      # noqa: E731
    for _ in range(C.STEP_EVERY * 4):
        swarm.tick(_lures((20, 10)), (20, 10), OPEN, 64, is_sprayed=boxed)
    assert (cleg.cx, cleg.cy) == (22, 10), "barged out through the spray"


# --- flanking --------------------------------------------------------------

def test_a_flanker_comes_in_off_to_one_side():
    far = _of_kind(C.FLANKER, 30, 10)
    assert far.aim((20, 10)) != (20, 10), "walked straight down the middle"


def test_a_flanker_stops_swinging_wide_once_it_is_close():
    near = _of_kind(C.FLANKER, 21, 10)
    assert near.aim((20, 10)) == (20, 10)


def test_the_offset_is_never_bigger_than_the_distance_it_switches_at():
    """Or a flanker goes direct before it ever reaches the line it was taking,
    and the whole thing quietly does nothing. That was the first version."""
    for dx, dy in C.FLANK_OFFSETS:
        assert max(abs(dx), abs(dy)) <= C.FLANK_UNTIL


def test_a_plain_cleg_aims_straight_at_it():
    assert _of_kind(C.PLAIN, 30, 10).aim((20, 10)) == (20, 10)


def test_flankers_still_arrive():
    """Coming the long way round must not mean never getting there."""
    cleg = _of_kind(C.FLANKER, 27, 10)
    cleg.notice = 30
    swarm = C.Swarm([cleg])
    _run(swarm, [(20, 10)], player=(20, 10), frames=C.STEP_EVERY * 30)
    assert swarm.attachments >= 1, f"never got there: {(cleg.cx, cleg.cy)}"


def test_flankers_do_not_all_take_the_same_line():
    lines = {C.Cleg(30, 10, seed=1 + i * 7919).flank for i in range(200)}
    assert len(lines) > 4, f"only {len(lines)} approaches in use"


# --- hunger: the dark stops being a refuge (issue #10) ---------------------

def test_a_fed_cleg_is_not_keen():
    assert C.Cleg(5, 5).keenness == 0


def test_going_hungry_makes_it_notice_fainter_light():
    cleg = C.Cleg(5, 5)
    cleg.hunger = C.HUNGER_STEP * 4
    assert cleg.keenness == 4


def test_keenness_is_capped():
    cleg = C.Cleg(5, 5)
    cleg.hunger = C.HUNGER_STEP * 1000
    assert cleg.keenness == C.KEEN_MAX


def test_hunger_only_helps_with_faint_light():
    """A bright light already carries further than any Cleg can notice."""
    faint = [(20, 10, 2, S.LURE_GLOW)]
    bright = [(20, 10, S.FAR, S.LURE_TORCH)]
    assert C.Swarm.nearest_lure(28, 10, faint, within=30) is None
    assert C.Swarm.nearest_lure(28, 10, faint, within=30, keenness=8) == (20, 10)
    # The bright one was already noticed, and stays noticed. No change.
    assert C.Swarm.nearest_lure(28, 10, bright, within=30) == (20, 10)


def test_a_cleg_cannot_notice_past_its_own_range_however_hungry():
    """Hunger sharpens the senses; it does not grant omniscience."""
    assert C.Swarm.nearest_lure(28, 10, [(20, 10, 2, S.LURE_GLOW)], within=4,
                                keenness=99) is None


def test_hunger_builds_while_hunting_and_resets_on_feeding():
    cleg = C.Cleg(20, 10, seed=0xBEEF)
    swarm = C.Swarm([cleg])
    _run(swarm, [], player=(0, 0), frames=300)
    assert cleg.hunger >= 300

    _run(swarm, [], player=(cleg.cx, cleg.cy), frames=1)
    assert cleg.state == C.ATTACHED
    _run(swarm, [], player=(cleg.cx, cleg.cy),
         frames=C.DRAIN_EVERY * C.DRAIN_TOTAL)
    assert cleg.state == C.SATED
    assert cleg.hunger == 0, "still straining to find you on a full stomach"


def test_standing_still_in_the_dark_gets_you_found_eventually():
    """The whole point: hiding is a breather, not a strategy."""
    far = C.Cleg(5, 5, seed=0xBEEF)
    far.notice = 20
    swarm = C.Swarm([far])
    glow = S.Glow(); glow.x, glow.y = 14, 10
    for _ in range(50 * 90):
        swarm.tick([glow.lure()], (14, 10), OPEN, 10 ** 9)
    assert swarm.attachments >= 1, "hid for a minute and a half undisturbed"


# --- wandering, rather than diffusing --------------------------------------

def test_a_wandering_cleg_holds_its_heading_for_a_run():
    cleg = C.Cleg(16, 11, seed=0xBEEF)
    swarm = C.Swarm([cleg])
    seen = []
    last = (cleg.cx, cleg.cy)
    for _ in range(C.DRIFT_EVERY * 6):
        swarm.tick([], (0, 0), OPEN, 64)
        if (cleg.cx, cleg.cy) != last:
            seen.append((cleg.cx - last[0], cleg.cy - last[1]))
            last = (cleg.cx, cleg.cy)
    assert seen, "never moved"
    assert len(set(seen)) < len(seen), "re-rolled its heading every single step"


def test_a_wandering_cleg_actually_goes_somewhere():
    """An unbiased step-by-step walk barely leaves where it started, which is
    what left parts of the room permanently empty."""
    reach = []
    for i in range(20):
        cleg = C.Cleg(16, 11, seed=1 + i * 7919)
        swarm = C.Swarm([cleg])
        _run(swarm, [], player=(0, 0), frames=C.DRIFT_EVERY * 40)
        reach.append(max(abs(cleg.cx - 16), abs(cleg.cy - 11)))
    assert sum(reach) / len(reach) > 5, f"average displacement {sum(reach)/20:.1f}"


def test_wandering_still_respects_walls():
    cleg = C.Cleg(16, 11, seed=0xBEEF)
    swarm = C.Swarm([cleg])
    wall = lambda cx, cy: OPEN(cx, cy) or cx > 18       # noqa: E731
    for _ in range(C.DRIFT_EVERY * 60):
        swarm.tick([], (0, 0), wall, 64)
        assert not wall(cleg.cx, cleg.cy)


def test_no_two_clegs_stand_on_the_same_cell():
    """They steer for the same light by the same rule, so without elbow room
    they converge on one square and stack -- one Cleg drawn six times."""
    swarm = C.Swarm([C.Cleg(20 + i, 10, seed=0xBEEF + i) for i in range(6)])
    for cleg in swarm.clegs:
        cleg.notice = 30
    for _ in range(C.STEP_EVERY * 20):
        swarm.tick(_lures((26, 10)), (0, 0), OPEN, 10 ** 9)
        loose = [(c.cx, c.cy) for c in swarm.clegs if c.state != C.ATTACHED]
        assert len(loose) == len(set(loose)), f"two on one cell: {loose}"


def test_they_can_still_all_reach_the_player():
    """The player's cell is the exception: several can feed at once, and an
    arriving one must not be blocked by the ones already there."""
    swarm = C.Swarm([C.Cleg(20, 10) for _ in range(4)])
    _run(swarm, [(20, 10)], player=(20, 10), frames=1)
    assert len(swarm.attached()) == 4


# --- dying must not empty the room (issue #27) -----------------------------

def test_detaching_never_removes_a_cleg_from_the_swarm():
    """The bug: the session's death branch deleted every attached fly.

    A lit Statue on seed 3 went from six Clegs to three across two deaths and
    finished the run with a try in hand, so **dying made the game easier**.
    Whatever else `detach` does, the swarm it returns is the swarm it was given.
    """
    swarm = C.Swarm([C.Cleg(20, 10, seed=0xBEEF + i) for i in range(4)])
    _run(swarm, [(20, 10)], player=(20, 10), frames=1)
    assert len(swarm.attached()) == 4
    assert swarm.detach(OPEN) == 4
    assert len(swarm.clegs) == 4
    assert swarm.attached() == []


def test_detached_clegs_scatter_rather_than_stack():
    """They were all riding the same cell, and no two Clegs may share one --
    six in one square is not a swarm, it is one Cleg drawn six times.

    They land as close to where you fell as the room allows, so the place you
    died is a knot of flies rather than a clean slate.
    """
    swarm = C.Swarm([C.Cleg(20, 10, seed=0xBEEF + i) for i in range(6)])
    _run(swarm, [(20, 10)], player=(20, 10), frames=1)
    swarm.detach(OPEN)
    where = [(c.cx, c.cy) for c in swarm.clegs]
    assert len(set(where)) == len(where), f"stacked: {where}"
    assert (20, 10) not in where, "nobody stays on the square you fell on"
    for cx, cy in where:
        assert max(abs(cx - 20), abs(cy - 10)) <= 2, "scattered, not teleported"


def test_a_detached_cleg_never_lands_in_a_wall_and_is_never_lost():
    """Boxed in on every side, it stays where it is. Inconvenient is fine;
    deleted is the bug."""
    boxed = lambda cx, cy: (cx, cy) != (20, 10)      # noqa: E731
    swarm = C.Swarm([C.Cleg(20, 10, seed=0xBEEF + i) for i in range(3)])
    _run(swarm, [(20, 10)], player=(20, 10), frames=1, is_solid=boxed)
    swarm.detach(boxed)
    assert len(swarm.clegs) == 3
    assert all((c.cx, c.cy) == (20, 10) for c in swarm.clegs)


def test_a_cleg_that_was_drinking_when_you_bled_out_has_had_its_meal():
    """The second decision in issue #27, and it is the one that keeps the
    respawn survivable.

    A part-fed fly does **not** carry its progress into your next life. It has
    had the whole blood budget off you, so it is sated: off, uninterested, and
    drifting briskly away for ten seconds. Detaching them hungry instead
    reproduces exactly the leak the design already names -- a fed fly that sits
    on the cell it fed from, notices the glow it is standing in, and bites again
    for ever -- on top of a player who has just been handed a fresh eight pips
    and cannot yet have moved.
    """
    swarm = C.Swarm([C.Cleg(20, 10)])
    cleg = swarm.clegs[0]
    _run(swarm, [(20, 10)], player=(20, 10), frames=C.DRAIN_EVERY * 3 + 1)
    assert cleg.state == C.ATTACHED and 0 < cleg.taken < C.DRAIN_TOTAL
    swarm.detach(OPEN)
    assert cleg.state == C.SATED
    assert cleg._timer == C.SATED_FRAMES
    assert cleg.hunger == 0, "fed, so not straining to find you"
    assert cleg.goal is None


def test_detaching_nobody_is_not_an_error():
    swarm = C.Swarm([C.Cleg(2, 2), C.Cleg(9, 9)])
    assert swarm.detach(OPEN) == 0
    assert len(swarm.clegs) == 2


# --- every bite is billed to the lure that caused it (issue #22) ------------

def _lure(cell, kind, reach=None):
    return (cell[0], cell[1], S.FAR if reach is None else reach, kind)


def test_a_cleg_records_the_source_it_acquired_at_acquisition():
    cleg = C.Cleg(20, 4, seed=0xBEEF)
    cleg.notice = 30
    swarm = C.Swarm([cleg])
    assert cleg.goal_source == S.LURE_NONE, "nothing has lured it yet"
    swarm.tick([_lure((20, 10), S.LURE_BEAM)], (0, 0), OPEN, 64)
    assert cleg.goal == (20, 10)
    assert cleg.goal_source == S.LURE_BEAM


def test_the_source_survives_the_fly_changing_its_mind():
    """**The whole point of the hook**, and the thing that is easy to build the
    wrong way.

    A Cleg that crossed the room for the searchlight and then found the player
    in the dark is the beam's kill. A hunting fly re-takes its goal on every
    frame it can notice a light, and one cell from the player the nearest light
    it can notice is nearly always the player's own glow -- so billing the
    latest acquisition would put almost every bite in the game on the glow and
    measure a coincidence rather than the game.
    """
    cleg = C.Cleg(20, 4, seed=0xBEEF)
    cleg.notice = 30
    swarm = C.Swarm([cleg])
    swarm.tick([_lure((20, 20), S.LURE_BEAM)], (0, 0), OPEN, 64)
    assert cleg.goal_source == S.LURE_BEAM

    # Now the player's glow is much the nearer light. It changes where the fly
    # is going; it does not change what brought it.
    for _ in range(C.STEP_EVERY * 8):
        swarm.tick([_lure((20, 20), S.LURE_BEAM),
                    _lure((20, 5), S.LURE_GLOW, reach=S.GLOW_REACH + 12)],
                   (20, 5), OPEN, 64)
    assert cleg.goal_source == S.LURE_BEAM, "the glow only closed the gap"
    assert cleg.state == C.ATTACHED
    assert swarm.bites_by_source[S.LURE_BEAM] == 1
    assert swarm.bites_by_source[S.LURE_GLOW] == 0


def test_a_fly_that_arrived_and_then_blundered_onto_you_is_still_billed():
    """It walked across the room for the beam, got where it was going, found
    nothing there and stumbled onto a dark player. That is the beam's kill and
    not nobody's."""
    cleg = C.Cleg(20, 10, seed=0xBEEF)
    cleg.goal, cleg.goal_source = None, S.LURE_BEAM
    swarm = C.Swarm([cleg])
    swarm.tick([], (20, 10), OPEN, 64)
    assert cleg.state == C.ATTACHED
    assert swarm.bites_by_source[S.LURE_BEAM] == 1


def test_a_new_journey_takes_a_new_source():
    """The source moves when the fly sets off again from a standing start.

    Rejected alternative, recorded because it is the obvious other answer:
    keeping the first lure since the last meal for ever. That bills a fly to
    something it walked to, arrived at and left forty cells and twenty seconds
    ago, which is not the journey that killed anybody.
    """
    cleg = C.Cleg(20, 10, seed=0xBEEF)
    cleg.notice = 30
    cleg.goal, cleg.goal_source = None, S.LURE_BEAM
    swarm = C.Swarm([cleg])
    swarm.tick([_lure((24, 10), S.LURE_TORCH)], (0, 0), OPEN, 64)
    assert cleg.goal_source == S.LURE_TORCH


def test_feeding_closes_the_account():
    swarm = C.Swarm([C.Cleg(20, 10, seed=0xBEEF)])
    cleg = swarm.clegs[0]
    _run(swarm, [(20, 10)], player=(20, 10),
         frames=C.DRAIN_EVERY * C.DRAIN_TOTAL + 2)
    assert cleg.state == C.SATED
    assert cleg.goal_source == S.LURE_NONE, "a meal closes the account"


def test_blood_and_bites_add_up_to_what_was_taken():
    """The buckets are the whole of it: nothing is drained off the books."""
    swarm = C.Swarm([C.Cleg(20 + i, 10, seed=0xBEEF + i) for i in range(4)])
    for cleg in swarm.clegs:
        cleg.notice = 30
    blood = 10 ** 6
    start = blood
    for _ in range(C.STEP_EVERY * 60):
        blood = swarm.tick(_lures((20, 10)), (20, 10), OPEN, blood)
    assert sum(swarm.blood_by_source) == start - blood
    assert sum(swarm.bites_by_source) == swarm.attachments


def test_the_billing_is_never_read_back_by_the_swarm():
    """A record, not an input. A Cleg that knew which lure had paid best would
    be a different and much more expensive animal.

    Scrambling the field every frame changes nothing about where anybody goes,
    which is what makes the hook safe to measure with.
    """
    def play(scramble):
        swarm = C.Swarm([C.Cleg(20 + i, 6 + i, seed=0xBEEF + i)
                         for i in range(6)])
        for cleg in swarm.clegs:
            cleg.notice = 12
        blood, where = 10 ** 6, []
        for frame in range(C.STEP_EVERY * 80):
            blood = swarm.tick(_lures((20, 10)), (20, 10), OPEN, blood)
            if scramble:
                for i, cleg in enumerate(swarm.clegs):
                    cleg.goal_source = (frame + i) % S.LURE_KINDS
            where.append([(c.cx, c.cy, c.state) for c in swarm.clegs])
        return blood, where

    assert play(False) == play(True)


# --- the hunger cap is not the dial it was thought to be (issue #25) --------

def test_halving_the_hunger_cap_changes_no_measured_number():
    """**The falsified prediction, pinned so it cannot be re-derived.**

    Issue #25 cut `KEEN_MAX` from twelve to six, predicting the dark
    thirty-second cost would fall from 33.2 to 18-20. Measured on five seeds it
    did not move by a single point, and neither did anything else. This drives
    the real loop at both caps on three seeds and asserts they are identical --
    the blood, the bites, and the frame of every one of them.

    Two reasons, and both are worth having in front of whoever reaches for this
    constant next. **Arithmetically** the cap is out of reach inside the window:
    six cells of keenness needs six times `HUNGER_STEP`, which is the whole
    thirty seconds. **Mechanically** the extra cells almost never decide
    anything even over three minutes, because the searchlight is lit, mobile and
    noticeable from anywhere, so it wins the nearest-lure comparison before the
    glow's extra reach is ever the deciding term. Measured: between a cap of six
    and a cap of twelve, the lure a fly picks differs on 0 to 35 cleg-frames in
    a three-minute run, and never on a frame it steps on.
    """
    from spikes import bots, session as session_mod

    def play(cap, seed):
        was, C.KEEN_MAX = C.KEEN_MAX, cap
        try:
            bot = bots.Statue(seed=seed, light=False)
            run = session_mod.Session(seed=seed, lives=99)
            while run.over is None and run.frame < 30 * 50:
                run.step(bot.intent(run))
            return (run.tally.blood_lost, run.tally.attachments,
                    [(e.frame, e.kind, e.count) for e in run.log])
        finally:
            C.KEEN_MAX = was

    for seed in (1, 2, 3):
        assert play(6, seed) == play(12, seed), f"seed {seed}"


# --- a lit person is prey, and the player is not the only person (issue #19) -
#
# **The thing that was wrong.** `Swarm.tick` never saw a worker at all, so a
# follower in the light was in no danger, the tail was a rucksack rather than a
# liability, and the choice the whole design rests on -- turn to check your line
# and you expose it -- did not exist in the build. These pin the mechanism; the
# session tests pin it happening in a real run.


class Person:
    """The smallest thing a Cleg can feed on, for testing the swarm alone.

    `Worker` is the real one. This exists so that the swarm's side of the
    contract is stated in one place and tested without dragging the clock, the
    tail and the exit in with it. Anything with `cells`, `cell`, `bitten` and
    `alive` is prey.
    """

    def __init__(self, cx, cy, blood=8):
        self.cx, self.cy = cx, cy
        self.blood = blood
        self.hits = 0

    def cells(self):
        return {(self.cx, self.cy)}

    def cell(self):
        return self.cx, self.cy

    @property
    def alive(self):
        return self.blood > 0

    def bitten(self, amount=1):
        self.blood = max(0, self.blood - amount)
        self.hits += amount
        return self.blood == 0


def test_a_cleg_that_reaches_a_lit_person_attaches_to_them():
    """The mechanism, at its smallest. A fly steered onto somebody who is not
    the player lands on them and starts drinking."""
    victim = Person(12, 10)
    cleg = C.Cleg(12, 10, seed=1)
    swarm = C.Swarm([cleg])
    swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert cleg.state == C.ATTACHED
    assert cleg.victim is victim
    assert swarm.bitten == [victim]
    assert swarm.victim_attachments == 1


def test_a_person_in_the_dark_is_not_prey_at_all():
    """**The asymmetry is the mechanic.** The session decides who is lit, so
    "in the dark" is simply not being in the prey list -- and a fly standing on
    somebody it cannot see walks over them."""
    victim = Person(12, 10)
    cleg = C.Cleg(12, 10, seed=1)
    swarm = C.Swarm([cleg])
    swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[])
    assert cleg.state == C.HUNTING
    assert cleg.victim is None
    assert victim.blood == 8


def test_a_bite_costs_a_worker_the_same_as_it_costs_the_player():
    """DRAIN_TOTAL points at one every DRAIN_EVERY frames, then it leaves.

    Same numbers, different pocket: a point of a worker's blood is
    `rescue.BLEED_EVERY` frames of their life, so a full meal is a real bite
    out of the clock rather than a scratch.
    """
    victim = Person(12, 10, blood=99)
    swarm = C.Swarm([C.Cleg(12, 10, seed=1)])
    for _ in range(C.DRAIN_EVERY * C.DRAIN_TOTAL + 2):
        swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert victim.hits == C.DRAIN_TOTAL
    assert swarm.clegs[0].state == C.SATED, "a fed fly leaves"
    assert swarm.clegs[0].victim is None
    assert swarm.victim_blood == C.DRAIN_TOTAL


def test_a_worker_can_be_drunk_to_death():
    """Which is the whole point: a lit follower can be killed on the way out."""
    victim = Person(12, 10, blood=3)
    swarm = C.Swarm([C.Cleg(12, 10, seed=1)])
    for _ in range(C.DRAIN_EVERY * 4):
        swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert not victim.alive
    assert swarm.victim_blood == 3, "it cannot take more than they had"


def test_a_fly_whose_host_dies_goes_back_to_hunting_rather_than_sated():
    """It has not had a meal, so it does not get a meal's ten seconds off.

    The opposite choice is defensible for the *player* -- `detach` sates them,
    because a fly on a dying player has had the whole blood budget -- and it is
    wrong here for exactly that reason: a fly on a worker has taken at most
    eight points off a clock that was already running out. Sating it would hand
    the player a reprieve in exchange for a death.
    """
    victim = Person(12, 10, blood=1)
    cleg = C.Cleg(12, 10, seed=1)
    swarm = C.Swarm([cleg])
    for _ in range(C.DRAIN_EVERY + 1):
        swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert not victim.alive
    assert cleg.state == C.HUNTING and cleg.victim is None


def test_an_attached_fly_rides_the_person_it_is_on():
    """Running does not help a worker either. It is on them, and it is drawn on
    them rather than at the spot where it landed."""
    victim = Person(12, 10, blood=99)
    cleg = C.Cleg(12, 10, seed=1)
    swarm = C.Swarm([cleg])
    swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert cleg.state == C.ATTACHED
    victim.cx, victim.cy = 20, 4
    swarm.tick([], (30, 20), OPEN, 64, prey=[victim])
    assert (cleg.cx, cleg.cy) == (20, 4)


def test_the_player_is_prey_lit_or_not_and_everybody_else_is_not():
    """Contact is contact for the player -- their own glow is a light they
    cannot switch off -- and darkness is what protects the people behind them.
    Both rules, in one test, because they are one rule read twice."""
    victim = Person(12, 10)
    swarm = C.Swarm([C.Cleg(12, 10, seed=1), C.Cleg(20, 20, seed=2)])
    swarm.tick([], (20, 20), OPEN, 64, prey=[])
    assert swarm.clegs[1].state == C.ATTACHED, "the player is always prey"
    assert swarm.clegs[0].state == C.HUNTING, "the worker is in the dark"


def test_a_worker_bite_moves_none_of_the_player_counters():
    """**The player being bitten is unchanged**, and it is the criterion most
    easily broken by accident. Every phase-2 baseline is stated in
    `attachments`, in the frame of the first `BITTEN` event, and in the
    per-lure billing from issue #22 -- so a worker being eaten must not appear
    in any of them. Worker blood is a different currency: a point is two
    seconds of somebody's life, not a pip of eight.
    """
    victim = Person(12, 10, blood=99)
    swarm = C.Swarm([C.Cleg(12, 10, seed=1)])
    for _ in range(C.DRAIN_EVERY * 3):
        swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert victim.hits > 0, "the test is worthless if nothing was bitten"
    assert swarm.attachments == 0
    assert swarm.drained == 0
    assert sum(swarm.bites_by_source) == 0
    assert sum(swarm.blood_by_source) == 0
    assert swarm.on_player() == []


def test_the_players_blood_is_untouched_by_a_fly_on_a_worker():
    victim = Person(12, 10, blood=99)
    swarm = C.Swarm([C.Cleg(12, 10, seed=1)])
    blood = 64
    for _ in range(C.DRAIN_EVERY * 3):
        blood = swarm.tick(_lures((12, 10)), (30, 20), OPEN, blood,
                           prey=[victim])
    assert blood == 64


def test_bleeding_out_does_not_shake_the_flies_off_your_followers():
    """`detach` is about the player's death and only the player's death.

    Scattering a fly that is riding a follower would teleport it across the
    room to the cell you fell on, which is not where it was.
    """
    victim = Person(12, 10, blood=99)
    on_worker = C.Cleg(12, 10, seed=1)
    on_player = C.Cleg(30, 20, seed=2)
    swarm = C.Swarm([on_worker, on_player])
    swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert on_worker.state == on_player.state == C.ATTACHED

    assert swarm.detach(OPEN) == 1, "only the one on the player comes off"
    assert on_worker.state == C.ATTACHED and on_worker.victim is victim
    assert on_player.state == C.SATED


def test_the_spray_does_not_reach_a_fly_that_has_already_landed_on_anybody():
    """The rule is *landed*, not *landed on you*: once it is on, the damage is
    decided and the whole defensive game happened before contact."""
    victim = Person(12, 10, blood=99)
    cleg = C.Cleg(12, 10, seed=1)
    swarm = C.Swarm([cleg])
    swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert cleg.state == C.ATTACHED
    assert swarm.sprayable() == []


def test_several_flies_can_feed_on_one_worker_at_once():
    """As they can on the player. A swarm that reaches somebody is far worse
    than one Cleg arriving four times."""
    victim = Person(12, 10, blood=99)
    swarm = C.Swarm([C.Cleg(12, 9, seed=1), C.Cleg(12, 11, seed=2),
                     C.Cleg(11, 10, seed=3)])
    for _ in range(40):
        swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert len(swarm.attached()) >= 2, \
        [c.state for c in swarm.clegs]


def test_the_prey_map_is_built_once_and_covers_the_whole_figure():
    """A person is 8x16, so they straddle two or three cells and a fly landing
    on any of them has landed on them. It is a map rather than a search because
    a Cleg must never acquire one."""
    class Tall(Person):
        def cells(self):
            return {(self.cx, self.cy), (self.cx, self.cy - 1)}

    victim = Tall(12, 10)
    assert C.Swarm.prey_cells([victim]) == {(12, 10): victim, (12, 9): victim}


# --- the sonar counts a fly on somebody who is not you (issue #32) ----------
#
# The sonar is the only channel the dark has. A Cleg is not merely hard to see
# in darkness, it is not drawn at all -- so once a fly has landed on the
# follower two paces behind you there is nothing to see, and the only other
# channel is the death shout, which arrives too late to be a warning.

def test_the_sonar_counts_a_fly_feeding_on_a_worker():
    """A fast rattle behind you means something is on somebody behind you."""
    victim = Person(12, 10, blood=99)
    cleg = C.Cleg(12, 10, seed=1)
    swarm = C.Swarm([cleg])
    swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert cleg.state == C.ATTACHED and cleg.victim is victim
    assert swarm.nearest_distance(30, 20) == 18, "it is still worth hearing"


def test_the_sonar_still_ignores_a_fly_feeding_on_you():
    """Your blood is already saying it; a click that repeats it is noise."""
    victim = Person(12, 10, blood=99)
    on_worker = C.Cleg(12, 10, seed=1)
    on_player = C.Cleg(30, 20, seed=2)
    swarm = C.Swarm([on_worker, on_player])
    swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert on_worker.state == on_player.state == C.ATTACHED
    assert swarm.nearest_distance(30, 20) == 18, \
        "the near one is on you, so the far one is the news"


def test_the_sonar_follows_a_fly_onto_the_host_that_walks_off():
    """`_ride` keeps the fly on its host, so the distance is the host's."""
    victim = Person(12, 10, blood=99)
    swarm = C.Swarm([C.Cleg(12, 10, seed=1)])
    swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    victim.cx, victim.cy = 26, 20
    swarm.tick([], (30, 20), OPEN, 64, prey=[victim])
    assert swarm.nearest_distance(30, 20) == 4, "it went where they went"


def test_the_sonar_is_unchanged_when_nothing_is_attached_to_anybody():
    """The click rate for an ordinary run does not move."""
    swarm = C.Swarm([C.Cleg(12, 10, seed=1), C.Cleg(26, 4, seed=2)])
    assert swarm.nearest_distance(30, 20) == 16, "the nearer of the two"


# --- the wingbeat is the fly's speed (issue #49) ----------------------------
#
# The only animated thing in the play area, and the rule it is built to is a
# port decision wearing an art decision's clothes: **the frame flips when the
# Cleg steps a cell, never on the frame counter.** Alternating on
# `session.frame` is 25Hz, which is a strobe rather than a wingbeat, and it
# dirties every fly's cell every other frame whether or not the fly moved --
# about 15,000 T-states a frame animating flies that are standing still,
# against 32,832 for all entities.

def test_a_cleg_that_does_not_step_holds_its_frame():
    """**The whole of the cost argument, as a test.**

    A fly with nothing to go to stands still, and a fly standing still must not
    be redrawn. If this ever fails, the swarm has started costing a redraw a
    frame each for nothing.
    """
    # A cell the room will not let it out of. A hunting fly with nothing to go
    # to still wanders, which is the *other* half of the rule: it flaps when it
    # wanders, because it moved. What must cost nothing is the fly that does
    # not move, so the fixture is one that cannot.
    def boxed(cx, cy):
        return (cx, cy) != (10, 10)

    cleg = C.Cleg(10, 10, seed=0xBEEF)
    swarm = C.Swarm([cleg])
    was = cleg.wing
    for _ in range(50):
        swarm.tick(_lures((30, 10)), (30, 20), boxed, 64)
    assert (cleg.cx, cleg.cy) == (10, 10), "it moved, so this asks nothing"
    assert cleg.wing == was, "a fly standing still is flapping"


def test_a_cleg_that_steps_alternates_its_frame():
    """A fly walking towards a light beats its wings once per cell.

    So the swarm visibly quickens as it closes, on the same channel the sonar
    is already using -- and it costs nothing, because a fly that stepped is
    being erased and redrawn anyway.
    """
    cleg = C.Cleg(10, 10, seed=0xBEEF)
    swarm = C.Swarm([cleg])
    frames, where = [cleg.wing], (cleg.cx, cleg.cy)
    steps = 0
    for _ in range(200):
        swarm.tick(_lures((30, 10)), (30, 10), OPEN, 64)
        if (cleg.cx, cleg.cy) != where:
            steps += 1
            where = (cleg.cx, cleg.cy)
            frames.append(cleg.wing)
    assert steps >= 4, "the fly never set off, so this asks nothing"
    assert all(a != b for a, b in zip(frames, frames[1:])), \
        f"the wingbeat did not alternate with the steps: {frames}"


def test_a_cleg_sitting_on_somebody_is_still():
    """**A fly that is feeding is not flying**, which is also correct.

    An attached Cleg is carried by its victim -- `Swarm.tick` writes its cell
    directly rather than stepping it -- so it keeps whatever frame it landed
    in, however far the person it is riding walks.
    """
    victim = Person(12, 10, blood=99)
    cleg = C.Cleg(12, 10, seed=1)
    swarm = C.Swarm([cleg])
    swarm.tick(_lures((12, 10)), (30, 20), OPEN, 64, prey=[victim])
    assert cleg.state == C.ATTACHED
    landed = cleg.wing
    for step in range(10):
        victim.cx = 12 + step
        swarm.tick([], (30, 20), OPEN, 64, prey=[victim])
    assert cleg.cx == victim.cx, "the fly did not ride its host"
    assert cleg.wing == landed, "a fly on somebody is beating its wings"


def test_the_wingbeat_is_one_bit_and_indexes_the_frame_table():
    """One bit per fly, and the drawing is a table lookup rather than a branch.

    Stated as a test because it is the thing that makes the animation free on
    the Z80: an eight-bit `wing` would be a byte per fly and a comparison per
    draw, and neither is needed.
    """
    cleg = C.Cleg(10, 10, seed=0xBEEF)
    swarm = C.Swarm([cleg])
    for _ in range(120):
        swarm.tick(_lures((30, 10)), (30, 10), OPEN, 64)
        assert cleg.wing in (0, 1)
