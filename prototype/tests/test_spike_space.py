"""Personal space: a fly will not step next to another fly (issue #66).

The no-two-share-a-cell rule widened by one ring, after the tester measured
the swarm and found the one real clot was the far room's own flies held
within two cells of its door lamp. The rule is about **how flies arrive**,
so it is waived where they are arriving *at somebody*: a step onto or beside
a cell holding prey is not checked. That exemption is keyed to prey and not
to the fly's goal, and the tests here pin it both ways, because keyed to the
goal the door clot would re-form one ring out and the change would buy
nothing.
"""

from spikes import clegs as C, sources as S
from spikes.session import Session
from spikes import rescue as R
from spotlight.core.constants import COLS
from tests.test_spike_clegs import OPEN, Person, _lures


def _ready(*flies):
    """Make each fly due to step on its next tick."""
    for fly in flies:
        fly._tick = fly.step_every - 1


def _cheb(a, b):
    return max(abs(a.cx - b.cx), abs(a.cy - b.cy))


def _lure(cx, cy, kind=S.LURE_TORCH):
    return [(cx, cy, S.FAR, kind)]


# --- the rule ----------------------------------------------------------------

def test_a_fly_will_not_step_beside_another_free_fly():
    """The step the old rule allowed and the new one refuses, at its
    smallest: one fly walking east at a light, another parked two cells
    ahead of it. The cell between them is free, and it is refused."""
    walker = C.Cleg(10, 10, seed=1)
    parked = C.Cleg(12, 10, seed=2)
    swarm = C.Swarm([walker, parked])
    _ready(walker)
    swarm.tick(_lure(14, 10), (0, 0), OPEN, 64)
    assert (walker.cx, walker.cy) == (10, 10), "stepped beside a fly"

    # The control: the same step, with nobody parked ahead, is taken.
    alone = C.Cleg(10, 10, seed=1)
    _ready(alone)
    C.Swarm([alone]).tick(_lure(14, 10), (0, 0), OPEN, 64)
    assert (alone.cx, alone.cy) == (11, 10)


def test_no_two_free_flies_are_ever_adjacent_on_the_way_to_a_light():
    """The property, over a whole approach: six flies steering at one light
    that is nobody -- so nothing is exempt -- never stand next to each other
    on any frame, and still all get within reach of it. That last part is
    what says the rule spreads a swarm rather than jamming it."""
    swarm = C.Swarm([C.Cleg(18 + 2 * i, 10, seed=0xBEEF + i)
                     for i in range(6)])
    for cleg in swarm.clegs:
        cleg.notice = 30
    far = lambda c: max(abs(c.cx - 26), abs(c.cy - 14))  # noqa: E731
    started = [far(c) for c in swarm.clegs]
    for _ in range(C.STEP_EVERY * 40):
        swarm.tick(_lures((26, 14)), (0, 0), OPEN, 10 ** 9)
        free = [c for c in swarm.clegs if c.state != C.ATTACHED]
        for a in free:
            for b in free:
                if a is not b:
                    assert _cheb(a, b) >= 2, \
                        f"adjacent: {[(c.cx, c.cy) for c in free]}"
    # They queue -- a greedy step with no route round the fly ahead is what
    # the design asks for -- but the queue moves: no fly ends farther off
    # than it started, most end nearer, and one of them is on the light.
    ended = [far(c) for c in swarm.clegs]
    assert all(e <= s for e, s in zip(ended, started)), (started, ended)
    assert sum(e < s for e, s in zip(ended, started)) >= 4, (started, ended)
    assert 0 in ended


def test_a_drifting_fly_obeys_the_same_rule():
    """One rule for hunting and drifting flies alike. Two idle flies with no
    light to steer for wander for a long time in an open room and are never
    beside each other."""
    swarm = C.Swarm([C.Cleg(10, 10, seed=3), C.Cleg(12, 10, seed=4)])
    for cleg in swarm.clegs:
        cleg.state = C.SATED
        cleg._timer = 10 ** 6
    for _ in range(C.SATED_DRIFT_EVERY * 300):
        swarm.tick([], (0, 0), OPEN, 64)
        assert _cheb(*swarm.clegs) >= 2, [(c.cx, c.cy) for c in swarm.clegs]


# --- the exemption, both ways -----------------------------------------------
#
# The same geometry four times. A fly waits one cell north of a target cell;
# a second fly walks at the target from the west. Its next step is beside
# the waiting fly. Whether it is taken depends on one thing only: whether
# the target cell holds prey.

def _stage():
    walker = C.Cleg(10, 10, seed=1)
    waiting = C.Cleg(12, 9, seed=2)
    _ready(walker)
    return walker, waiting, C.Swarm([walker, waiting])


def test_a_fly_steps_beside_another_to_reach_the_player():
    """The player is prey, lit or not. The ring around them is not fenced
    off by the fly already waiting in it."""
    walker, waiting, swarm = _stage()
    swarm.tick(_lure(12, 10, S.LURE_GLOW), (12, 10), OPEN, 64)
    assert (walker.cx, walker.cy) == (11, 10)


def test_a_fly_steps_beside_another_to_reach_a_lit_worker():
    """A worker a lit light is on is prey on the same terms."""
    walker, waiting, swarm = _stage()
    swarm.tick(_lure(12, 10), (0, 0), OPEN, 64, prey=[Person(12, 10)])
    assert (walker.cx, walker.cy) == (11, 10)


def test_a_fly_will_not_step_beside_another_to_reach_a_worker_in_the_dark():
    """The same worker, unlit, is not in the prey list and is nobody. The
    exemption reads the prey list and nothing else."""
    walker, waiting, swarm = _stage()
    swarm.tick(_lure(12, 10), (0, 0), OPEN, 64, prey=[])
    assert (walker.cx, walker.cy) == (10, 10)


def test_a_fly_will_not_step_beside_another_in_the_ring_round_a_room_light():
    """**The trap**: keyed to the fly's goal, the ring round the far room's
    lamp would be exempt and the door clot would re-form one ring out. The
    walker's goal is a room light. It has no prey, and the step is refused.
    """
    walker, waiting, swarm = _stage()
    swarm.tick(_lure(12, 10, S.LURE_ROOM), (0, 0), OPEN, 64)
    assert walker.goal == (12, 10) and walker.goal_source == S.LURE_ROOM
    assert (walker.cx, walker.cy) == (10, 10)


def test_the_exemption_is_the_prey_cell_and_its_ring_and_no_further():
    """One ring, not two. A step two cells from the player is checked as
    anywhere else, so the spread the rule buys is not lost in a wider halo."""
    walker = C.Cleg(9, 10, seed=1)
    waiting = C.Cleg(11, 9, seed=2)
    swarm = C.Swarm([walker, waiting])
    _ready(walker)
    swarm.tick(_lure(12, 10, S.LURE_GLOW), (12, 10), OPEN, 64)
    assert (walker.cx, walker.cy) == (9, 10)


def test_they_can_still_pack_the_ring_round_the_player():
    """What the exemption gives back: the last ring round a lit person can
    still fill up, one fly a cell, so a burst dropped on your own doorstep
    can still take several. Eight flies from eight sides all arrive."""
    ring = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            if (dx, dy) != (0, 0)]
    swarm = C.Swarm([C.Cleg(15 + 3 * dx, 10 + 3 * dy, seed=5 + i)
                     for i, (dx, dy) in enumerate(ring)])
    for cleg in swarm.clegs:
        cleg.notice = 30
    most = 0
    for _ in range(C.STEP_EVERY * 12):
        swarm.tick(_lure(15, 10, S.LURE_GLOW), (15, 10), OPEN, 10 ** 9)
        most = max(most, len(swarm.attached()))
    assert most == 8


# --- what the rule does not touch --------------------------------------------

def test_an_in_place_step_is_never_refused_by_this_rule():
    """The idle twitch (issue #61) is a step into the fly's own cell, which is
    not a step. A fly already beside another -- put there, not stepped there
    -- must not have its null heading refused, or it re-rolls a heading it
    would never have rolled and the log moves for a reason nobody meant."""
    twitcher = C.Cleg(10, 10, seed=1)
    neighbour = C.Cleg(11, 10, seed=2)
    twitcher.heading = (0, 0)
    twitcher._run = 5
    twitcher._tick = C.DRIFT_EVERY - 1
    neighbour._tick = 0
    before = (twitcher._seed, twitcher.wing)
    C.Swarm([twitcher, neighbour]).tick([], (0, 0), OPEN, 64)
    assert (twitcher.cx, twitcher.cy) == (10, 10)
    assert twitcher.heading == (0, 0), "the null heading was re-rolled"
    assert twitcher._run == 4
    assert twitcher._seed == before[0], "a random number was spent"
    assert twitcher.wing != before[1], "the twitch did not flip the wing"


def test_an_attached_fly_does_not_block():
    """Attached flies are not in the taken set and stay out of it. One
    feeding on a worker in the dark is nobody's neighbour."""
    victim = Person(12, 9, blood=99)
    walker = C.Cleg(10, 10, seed=1)
    feeding = C.Cleg(12, 9, seed=2)
    swarm = C.Swarm([walker, feeding])
    swarm.tick(_lure(12, 9), (0, 0), OPEN, 64, prey=[victim])
    assert feeding.state == C.ATTACHED
    _ready(walker)
    swarm.tick(_lure(14, 10), (0, 0), OPEN, 64, prey=[])
    assert (walker.cx, walker.cy) == (11, 10)


def test_a_brood_hatches_into_the_ring_round_its_nest_as_before():
    """Placement is not a step and is not governed. A crowded nest scatters
    its brood into the cells around it in `SCATTER` order, which puts
    hatchlings beside each other, exactly as it did before this rule."""
    run = Session(seed=1, lives=99)
    nest = run.rescue.workers[0]
    nest.blood = 1
    for _ in range(R.BLEED_EVERY + R.BODY_FRAMES + 1):
        nest.tick()
    assert nest.nesting
    at = nest.cell()
    place = run.places[nest.room]
    for fly in place.swarm.clegs:
        fly.cx, fly.cy = at            # the nest's own cell is crowded
    was = len(place.swarm.clegs)
    for _ in range(3):
        assert run._hatch(nest)
    born = place.swarm.clegs[was:]
    expected = [(at[0] + dx, at[1] + dy) for dx, dy in C.SCATTER[:3]]
    assert [(f.cx, f.cy) for f in born] == expected
    assert _cheb(born[0], born[2]) == 1, "the staging no longer stages"


# --- through a doorway ---------------------------------------------------------

def test_a_fly_will_not_step_through_a_doorway_beside_a_fly_next_door():
    """**The thing the first cut of this rule got wrong**, staged as it was
    found. The far room's lamp is one cell in from its doorway and holds a
    far-room fly on the landing at (0, 11). A main-room fly steering at the
    door lure from (30, 12) wants (31, 12), the doorway cell, which is one
    cell from that fly -- the far room's (0, 11) is the main room's (32, 11).
    Checked against its own room's flies only, it stepped, and on to the
    threshold beside the sitter, and four flies ended up touching at the
    lamp: the #65 leak one ring out. The session answers through the
    doorway with the same rule and the same translation, and it waits at
    the mouth of the doorway instead.

    The far-room fly is parked -- never due to step -- so the staging holds
    for the whole run, and the real building, lures and steps are used.
    """
    from spikes import scene
    from tests.test_spike_doorway import DOOR_ROW, _put_flies

    run = Session(seed=1)
    sitter = _put_flies(run, scene.FAR, [(0, DOOR_ROW)])[0]
    crosser = _put_flies(run, scene.NEAR, [(COLS - 2, DOOR_ROW + 1)])[0]
    for fly in run.places[scene.FAR].swarm.clegs:
        fly.step_every = 10 ** 6            # parked
        fly.still = -10 ** 9                # and never bored of it (issue #93)
    _ready(crosser)
    held = 0
    for _ in range(200):
        run.step()
        assert (sitter.cx, sitter.cy) == (0, DOOR_ROW), "the staging moved"
        # The staging holds: the crosser wants the door and is standing at
        # its mouth, which is exactly when it used to step.
        if crosser.goal == (COLS, DOOR_ROW) and crosser.cx == COLS - 2:
            held += 1
        for place in run.places:
            for fly in place.swarm.clegs:
                if fly is sitter or fly.state == C.ATTACHED:
                    continue
                # Everything in one coordinate system: the far room's grid
                # starts at the near room's column COLS.
                fx = fly.cx + (COLS if place.index == scene.FAR else 0)
                assert max(abs(fx - COLS), abs(fly.cy - DOOR_ROW)) >= 2, \
                    f"beside the far-room fly at frame {run.frame}: " \
                    f"room {place.index} ({fly.cx}, {fly.cy})"
    assert held > 0, "the staging never held the crosser at the doorway"


def test_a_fly_steps_through_a_doorway_beside_another_to_reach_the_player():
    """The exemption, across the wall. The player stands on the far room's
    landing; a far-room fly waits one cell in, beside them. A main-room fly
    stepping onto the threshold next to that fly is arriving at the player
    and is not refused; the same step two rows further from the player is.
    Keyed to prey exactly as at home."""
    from spikes import scene
    from tests.test_spike_doorway import at_door

    run = at_door(Session(seed=1), room=scene.FAR)
    run.step()
    assert run.here == scene.FAR
    px, py = run.player.cx, run.player.cy
    assert px == 0, "the staging should stand the player on the landing"
    up = 1        # the check is geometry on cells; no wall is consulted
    waiting = run.places[scene.FAR].swarm.clegs[0]
    from_near = run._held_beyond(run.places[scene.NEAR])

    waiting.cx, waiting.cy = 1, py + up           # beside the player
    assert not from_near(COLS, py), "onto the player is never refused"
    assert not from_near(COLS, py + up), "beside the player: arriving"

    waiting.cx, waiting.cy = 1, py + 2 * up       # two rows off the player
    assert from_near(COLS, py + 2 * up), "not arriving: refused"
    assert not from_near(COLS, py + up), "still beside the player: arriving"
