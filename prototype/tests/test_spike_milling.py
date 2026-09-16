"""A Cleg with nothing to chase keeps moving (issue #93).

The far room's flies were half as lively as the near room's and stood for
seconds at a time: a null heading ran for up to twelve seconds, a heading
into brick was wasted, and every fly that reached the door light stood on
it. Three rules, pinned one at a time.
"""

from spikes import clegs as C, scene, session as S, sources
from spikes.session import Intent, Session

OPEN = lambda cx, cy: not (0 <= cx < 32 and 0 <= cy < 22)      # a bare room


def _drift(fly, frames, is_solid=OPEN):
    for _ in range(frames):
        fly._drift(is_solid)


def test_a_null_heading_is_one_twitch_and_not_a_run():
    """Roll until a (0, 0) comes up; its run is one, and the next drift rolls
    again rather than standing through the run the roll gave it."""
    fly = C.Cleg(10, 10, seed=3)
    nulls = 0
    for _ in range(400):
        fly._run = 0                       # force a roll every drift
        fly._drift(OPEN)
        if fly.heading == (0, 0):
            nulls += 1
            assert fly._run == 0, "a null heading was given a run"
    assert nulls > 20, "the coin never came up null, so nothing was tested"


def test_a_drifting_fly_turned_by_a_wall_walks_along_it():
    """In a corner, most rolls are brick; a fly there used to stand. Now a
    refused heading is turned a quarter and taken. Count the frames it
    moves on out of a hundred forced rolls, against the old rule's."""
    corner = lambda cx, cy: cx < 5 or cy < 5 or cx > 30 or cy > 20
    moves = 0
    fly = C.Cleg(5, 5, seed=11)
    for _ in range(100):
        fly._run = 0
        fly._drift(corner)
        moves += (fly.cx, fly.cy) != (5, 5)
        fly.cx, fly.cy = 5, 5             # back in the corner every time
    # From (5, 5) with walls left and above, five of the eight headings are
    # brick and one is null; the old rule moved on about two rolls in eight,
    # the turn moves on every non-null roll.
    assert moves >= 60, moves


def test_a_fly_stuck_with_a_goal_gets_bored_and_wanders_then_looks_again():
    """Standing on a room light it has reached: two seconds, then it drops
    the goal, ignores the light for three, and takes it up again."""
    swarm = C.Swarm([C.Cleg(10, 10, seed=5)])
    fly = swarm.clegs[0]
    lure = [(10, 10, 20, sources.LURE_ROOM)]           # a light where it stands
    is_solid = OPEN
    for _ in range(C.STUCK_FRAMES - 1):
        swarm.tick(lure, None, is_solid, 0)
    # It stands on the light: the goal is taken up and cleared by arrival
    # every frame, and the source says which light it was.
    assert fly.goal_source == sources.LURE_ROOM and fly.bored == 0
    swarm.tick(lure, None, is_solid, 0)
    assert fly.goal is None and fly.bored == C.MILL_FRAMES, "not bored on the frame"
    assert fly.goal_source == sources.LURE_NONE
    moved = False
    for _ in range(C.MILL_FRAMES):
        swarm.tick(lure, None, is_solid, 0)
        assert fly.goal is None, "it noticed the light while bored"
        moved = moved or (fly.cx, fly.cy) != (10, 10)
    assert moved, "it never wandered"
    assert fly.bored == 0
    for _ in range(40):
        swarm.tick(lure, None, is_solid, 0)
        if fly.goal_source == sources.LURE_ROOM:
            break
    assert fly.goal_source == sources.LURE_ROOM, "it did not take the light up again"


def test_a_fly_queued_at_the_player_under_the_magnet_is_never_bored():
    swarm = C.Swarm([C.Cleg(10, 10, seed=5)])
    fly = swarm.clegs[0]
    wall = lambda cx, cy: OPEN(cx, cy) or (cx, cy) == (11, 10)   # the way is shut
    for _ in range(C.STUCK_FRAMES * 3):
        swarm.tick([], None, wall, 0, magnet=(14, 10))
    assert fly.goal == (14, 10) and fly.bored == 0


def test_the_far_rooms_swarm_no_longer_stands_on_its_door_light():
    """The measurement the ruling was made on, as a floor: over a listener's
    two minutes the far room's flies spend under a tenth of their frames
    standing three seconds or more, where it was a fifth."""
    from spikes import bots
    run = Session(seed=0xBEEF)
    bot = bots.make("listener", seed=0xBEEF)
    far = run.places[scene.FAR]
    still, long, frames = {}, 0, 0
    while run.over is None and run.frame < 6000:
        run.step(bot.intent(run))
        for fly in far.swarm.clegs:
            k, pos = id(fly), (fly.cx, fly.cy)
            still[k] = still.get(k, (pos, 0))
            still[k] = (pos, still[k][1] + 1) if still[k][0] == pos else (pos, 0)
            frames += 1
            long += still[k][1] >= 150
    assert frames, "the far room had no flies"
    assert long * 10 < frames, f"{long} of {frames} fly-frames standing three seconds or more"
