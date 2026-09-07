"""The four reference bots the difficulty targets are stated against.

Issue #17. The phase-0 review states all eight phase-2 targets against Statue,
Wanderer, Listener and Oracle, so the tester needs all four to exist and to
behave like their descriptions. These tests pin the description, not the score:
the scores are what phase 2 is for and they will move.

**The bots here are a re-implementation.** The review's numbers came from bots
that were monkey-patched into the loop and not kept, so these do not reproduce
them -- the Listener clears the room in about 40 seconds where the review
measured 55-66, and the Oracle in 14 where it measured 21. Some of that is that
these walk diagonally, which a player can do too. The baselines have to be taken
again from this driver before any target is judged met or missed.
"""

import pytest

from spikes import bots, report, rescue as rescue_mod, scene, session
from spikes.session import Intent, Session

LIMIT = 12000


def play(bot, seed=1, frames=LIMIT):
    run = Session(seed=seed)
    while run.over is None and run.frame < frames:
        intent = bot.intent(run)
        assert isinstance(intent, Intent), "a bot may only press keys"
        run.step(intent)
    return run


def test_a_bot_only_presses_keys():
    """No bot may reach into the run and move anybody.

    The whole value of a bot is that the session cannot tell it from a
    keyboard. A bot that nudged the player would be measuring a game nobody can
    play.
    """
    run = Session()
    for name in bots.BOTS:
        bot = bots.make(name)
        for _ in range(120):
            assert isinstance(bot.intent(run), Intent)
            run.step(bot.intent(run))


def test_the_statue_never_moves():
    run = play(bots.make("statue"), frames=400)
    assert (run.player.x, run.player.y) == scene.PLAYER_START
    assert run.rescued == 0


def test_the_statue_can_be_run_lit_or_dark():
    """Difficulty target T3 is the same statue twice. It has to be a switch."""
    dark = play(bots.make("statue", light=False), frames=1200)
    lit = play(bots.make("statue", light=True), frames=1200)
    assert dark.tally.lit_frames == 0
    assert lit.tally.lit_frames > 0


def test_the_wanderer_moves_and_lights():
    run = play(bots.make("wanderer", seed=3), frames=1500)
    assert (run.player.x, run.player.y) != scene.PLAYER_START
    assert run.tally.lit_frames > 0


def test_the_listener_never_lights_and_still_finds_people():
    """The review's sharpest finding, reproduced: the best play is dark.

    This is not a target, it is the evidence for one. If the Listener stops
    clearing the room after phase-2 tuning, this assertion is the thing to
    revisit -- and the reason it was written down.
    """
    run = play(bots.make("listener", seed=5))
    assert run.tally.lit_frames == 0
    assert run.rescued >= 1


def test_the_listener_only_goes_where_it_has_heard_somebody():
    """It acts on the shout and on nothing else. That is the claim it tests."""
    bot = bots.make("listener")
    run = Session()
    run.calls_on = False
    for _ in range(600):
        run.step(bot.intent(run))
    assert (run.player.x, run.player.y) == scene.PLAYER_START


def test_the_listener_collects_until_there_is_nothing_left_to_hear():
    """It had a batch of three and it does not any more (issue #24).

    The batch assumed the game #20 had removed -- deliver, and the run is over
    -- so every measurement of this bot was of one that stopped at three of
    seven, and T1's band was met for the bot's reasons rather than the room's.
    Now the door hands people over and the run carries on, so collecting until
    the room falls silent is simply the behaviour.
    """
    run = play(bots.make("listener"), seed=2)
    assert run.rescued > 3, "still stopping at a batch"
    assert run.rescued + run.lost == run.total, "left somebody living behind"


def test_the_oracle_gets_everybody_out_by_walking():
    """The honest version of the all-out ending: no teleporting anywhere.

    `test_session.py` reaches the same ending by putting the player on top of
    each worker, which is a test convenience. This one walks the route, frees
    everybody and carries them to the exit through the game's own code.
    """
    run = play(bots.make("oracle", seed=11))
    assert run.over == session.ALL_OUT
    assert run.rescued == run.total
    assert run.tally_adds_up()
    assert all(w.state == rescue_mod.SAVED for w in run.rescue.workers)


def test_the_oracle_is_the_ceiling():
    """Faster than the bot that has to wait to be told where people are.

    The two bots are comparable again. While the Listener stopped at a batch of
    three it was not doing the same job -- ten seconds with three of seven is a
    shorter job, not a faster bot -- and the comparison had to be rigged with a
    batch of seven to mean anything. Issues #28 and #24 between them removed
    both halves of that: the door hands people over and the run carries on, so
    the Listener collects everybody it can hear.

    What it shows is the thing worth knowing: this bot finds the far room **by
    ear**, from a call drawn over a doorway, and it still takes far longer than
    a bot that was simply told where everybody was.
    """
    oracle = play(bots.make("oracle", seed=6))
    listener = play(bots.make("listener", seed=6))
    assert oracle.rescued == oracle.total
    assert oracle.rescued >= listener.rescued
    assert oracle.seconds < listener.seconds


def test_the_listener_finds_the_far_room_by_ear():
    """Target T10, and it is a test of the shouts-through-a-doorway rule as
    much as of the geometry: this bot acts on nothing but what it is told, and
    the only thing the far room ever tells it is a word over a gap in the east
    wall. Take the rule away and it never leaves the near room."""
    for seed in (1, 2, 3, 4, 5):
        run = play(bots.make("listener", seed=seed), seed=seed)
        assert run.crossings > 0, f"seed {seed}: never found the door"
        first = next(e for e in run.log if e.kind == session.CROSSED)
        assert first.seconds <= 60, f"seed {seed}: took {first.seconds}s"


@pytest.mark.parametrize("name", sorted(bots.BOTS))
def test_every_bot_is_reproducible(name):
    a = play(bots.make(name, seed=8), frames=1500)
    b = play(bots.make(name, seed=8), frames=1500)
    assert (a.player.x, a.player.y) == (b.player.x, b.player.y)
    assert [(e.frame, e.kind, e.who) for e in a.log] == \
           [(e.frame, e.kind, e.who) for e in b.log]


def test_a_bot_that_gets_stuck_gets_itself_unstuck():
    """The room can stop a figure dead -- the phase-0 review found a case where
    a 16-tall sprite at an unaligned y clips a wall with its head. A bot that
    could not notice would stand there and report the room as impossible."""
    bot = bots.make("oracle", seed=2)
    run = Session(seed=2)
    positions = set()
    for _ in range(2000):
        run.step(bot.intent(run))
        positions.add((run.player.x, run.player.y))
    assert len(positions) > 100


def test_routes_keep_the_head_out_of_the_ceiling():
    """A person is two cells tall, so a route that only checks the feet walks
    them into a lintel."""
    for cx in range(32):
        for cy in range(22):
            if bots.standable(0, cx, cy):
                assert not scene.ROOM_NEAR.is_solid(cx, cy)
                assert not scene.ROOM_NEAR.is_solid(cx, cy - 1)


def test_the_exit_is_reachable_by_route():
    start = (scene.NEAR, scene.PLAYER_START[0] // 8,
             (scene.PLAYER_START[1] + 15) // 8)
    assert bots.route(start, bots.stand_cells(scene.NEAR,
                                              *scene.ROOM_NEAR.exit_cell()))


def test_a_script_is_one_intent_per_frame():
    frames = bots.parse_script("3R 2D T S 2.")
    assert len(frames) == 3 + 2 + 1 + 1 + 2
    assert [(f.dx, f.dy) for f in frames[:5]] == [(1, 0)] * 3 + [(0, 1)] * 2
    assert frames[5].torch and not frames[5].spray
    assert frames[6].spray


def test_a_script_repeats_a_button_only_once():
    """`3T` is three frames, one of them a press. Holding a key does not
    toggle a torch three times."""
    frames = bots.parse_script("3T")
    assert [f.torch for f in frames] == [True, False, False]


def test_a_bad_script_says_so():
    with pytest.raises(ValueError):
        bots.parse_script("100Z")


def test_a_scripted_run_replays_exactly():
    script = bots.parse_script("200R 150D T 300L")
    a = play(bots.Script(script), seed=4, frames=900)
    b = play(bots.Script(script), seed=4, frames=900)
    assert (a.player.x, a.player.y) == (b.player.x, b.player.y)
    assert a.tally.lit_frames == b.tally.lit_frames > 0


# --- the Wanderer stops grinding into walls (issue #24) --------------------

def _wedge(bot, run, frames):
    """Play, counting the frames it pressed a direction and did not move."""
    blocked = pressing = 0
    for _ in range(frames):
        intent = bot.intent(run)
        before = (run.here, run.player.x, run.player.y)
        run.step(intent)
        if intent.dx or intent.dy:
            pressing += 1
            blocked += before == (run.here, run.player.x, run.player.y)
    return 100 * blocked // max(1, pressing)


def test_the_wanderer_turns_when_it_has_stopped_moving():
    """It held a direction into a wall for up to fourteen seconds.

    No first-timer does that, so T4 and T5 were measured against a bot
    handicapped in a way no person is -- a floor beneath the floor.
    """
    bot = bots.Wanderer(seed=3)
    run = Session(seed=3)
    for _ in range(bots.Wanderer.WEDGED_FRAMES * 4):
        run.step(Intent())              # it presses, the run ignores it
        bot.intent(run)
    assert bot._wedged < bots.Wanderer.WEDGED_FRAMES, "it never gave up"


def test_the_wanderer_wastes_fewer_frames_than_it_used_to():
    """Measured, not asserted in the abstract: the same walk with the rule
    switched off wedges materially more.

    Across the five seeds rather than seed by seed, because a random walk that
    never happened to wedge cannot be improved -- seed 4 is one, and asserting
    per seed would be asserting that every walk meets a wall.
    """
    with_rule, without = [], []
    for seed in (1, 2, 3, 4, 5):
        turning = bots.Wanderer(seed=seed)
        grinding = bots.Wanderer(seed=seed)
        grinding.WEDGED_FRAMES = 10 ** 9        # as it was before #24
        with_rule.append(_wedge(turning, Session(seed=seed), 3000))
        without.append(_wedge(grinding, Session(seed=seed), 3000))
    assert all(a <= b for a, b in zip(with_rule, without)), \
        f"worse on some seed: {with_rule} against {without}"
    assert sum(with_rule) * 10 <= sum(without) * 8, \
        f"not a material drop: {with_rule} against {without}"


# --- the Scout (issue #24) -------------------------------------------------

def test_the_scout_knows_nothing_it_has_not_seen():
    """Including where the walls are. That is the whole difference from the
    Listener, which routes by BFS over the true geometry and so walks through
    walls it has never seen to reach a shout it has just heard."""
    bot = bots.Scout(seed=1)
    run = Session(seed=1)
    room, (ex, ey) = scene.BUILDING.exit
    assert bot.seen == set(), "it knew something before it looked"
    assert not bot._passable(room, ex, ey + 1), "it knew where the door was"

    run.step()                       # the light is cast at the end of a frame
    bot.intent(run)
    assert bot.seen, "it saw nothing at all"
    assert all(room == run.here for room, _, _ in bot.seen), \
        "it can see into a room it is not in"


def test_the_scout_does_not_know_the_room_it_has_not_been_in():
    """The far room is unknown ground until it walks through the doorway, and
    a shout over that doorway says the door and not the person."""
    bot = bots.Scout(seed=1)
    run = Session(seed=1)
    for _ in range(300):
        run.step(bot.intent(run))
    assert run.here == scene.NEAR
    assert not any(room == scene.FAR for room, _, _ in bot.seen)


def test_the_scout_goes_to_the_edge_of_its_map_when_the_route_runs_out():
    bot = bots.Scout(seed=1)
    run = Session(seed=1)
    for _ in range(120):
        run.step(bot.intent(run))
    edges = bot.frontiers(run)
    assert edges, "a bot that has not left the near room has a frontier"
    for place in edges:
        assert bot._unknown_from(place) is not None


def test_the_scouts_torch_follows_its_route_and_can_be_turned_off():
    """Its light policy is a consequence of where it is going, not a flag set
    from outside -- which is what makes the T2 pair mean anything."""
    lit = bots.Scout(seed=1, light=True)
    run = Session(seed=1)
    burning = set()
    for _ in range(1500):
        run.step(lit.intent(run))
        burning.add((lit.exploring, run.cone.enabled))
    assert (True, True) in burning, "it explored in the dark"

    dark = bots.Scout(seed=1, light=False)
    control = Session(seed=1)
    for _ in range(1500):
        control.step(dark.intent(control))
    assert control.tally.lit_frames == 0, "the control lit up"


def test_the_scout_puts_the_torch_out_on_ground_it_already_knows():
    """The bug this policy had: every branch but one built its intent with the
    Walker's default -- *press the torch and leave it on* -- so the bot burned
    all twenty seconds of a spotlight walking a room it had already mapped, and
    T2 would have measured a torch nothing was routing by.
    """
    bot = bots.Scout(seed=1, light=True)
    run = Session(seed=1)
    known = 0
    for _ in range(2500):
        run.step(bot.intent(run))
        if not bot.exploring and run.frame > 200:
            known += 1
            assert not run.cone.lit, \
                "the torch is burning on ground it does not need to see"
    assert known > 500, "it never walked anywhere it already knew"


def test_the_dark_scout_is_the_same_bot_with_no_torch():
    """A fair control: same routing, same targets, same rules about what it
    knows. The only difference is that it cannot extend its map with light."""
    lit, dark = bots.Scout(seed=2, light=True), bots.Scout(seed=2, light=False)
    assert type(lit)._walk is type(dark)._walk
    assert lit._passable.__func__ is dark._passable.__func__
    run = Session(seed=2)
    for _ in range(200):
        run.step(dark.intent(run))
    assert dark.seen, "the dark scout learns nothing at all"


def test_the_scout_gets_people_out():
    """It has to be able to play the game, or it measures nothing."""
    run = play(bots.make("scout", seed=1))
    assert run.rescued >= 5
    assert run.crossings > 0, "never found the far room"


def test_both_new_bots_are_selectable_from_the_driver():
    assert {"scout", "wanderer"} <= set(bots.BOTS)
    assert isinstance(bots.make("scout", light=False), bots.Scout)


# --- the crossing walker (issue #29, target T3e) ---------------------------

def _cross(seed=1, light=False, frames=4000):
    bot = bots.Crosser(seed=seed, light=light)
    run = Session(seed=seed)
    while run.over is None and run.frame < frames:
        run.step(bot.intent(run))
    return bot, run


def test_the_crossing_walker_walks_its_route_over_and_over():
    """The bargain is a race, and every other bot is standing still."""
    bot, run = _cross()
    assert len(bot.crossings) > 5, "it never got there and back"
    ends = {tuple(c["to"]) for c in bot.crossings}
    assert ends == set(bots.Crosser.ROUTE), "it wandered off its route"
    for crossing in bot.crossings:
        assert crossing["from"] != crossing["to"]


def test_a_crossing_is_about_five_seconds_and_cannot_saturate():
    """Bounded on purpose: blood over a whole run saturates at 191.8 of 192,
    which is why no whole-run measure can see the bargain."""
    bot, _ = _cross()
    seconds = bot.summary()["all"]["crossing_frames"] / 50
    assert 3 <= seconds <= 7, seconds


def test_the_route_is_stated_in_the_run_report():
    """A figure nobody can reproduce is not a measurement."""
    bot, run = _cross()
    lines = report.human(run, bot="crosser", measured=bot.summary())
    stated = [l for l in lines if "route was" in l]
    assert stated, "the report does not say where it walked"
    for _room, cx, cy in bots.Crosser.ROUTE:
        assert f"{cx},{cy}" in stated[0]


def test_both_of_t3es_figures_are_reported():
    """Extra bites per crossing, and the share of crossings with a fly on you
    before the far end. Per crossing rather than per run, which is what stops
    them being a quotient of two long totals."""
    bot, _ = _cross(light=True)
    summary = bot.summary()
    for part in ("all", "lit", "dark"):
        assert {"crossings", "bites_per_crossing_tenths",
                "bitten_before_arrival_percent"} <= set(summary[part])
    assert summary["all"]["crossings"] == \
        summary["lit"]["crossings"] + summary["dark"]["crossings"]


def test_lit_and_dark_crossings_are_split_within_one_run():
    """A torch is twenty seconds and a crossing is four, so a bot asked to hold
    the light on spends the first few crossings lit and the rest of the run
    dark. Averaging those together reports neither."""
    bot, run = _cross(light=True)
    assert bot.summary()["lit"]["crossings"], "no crossing was lit at all"
    assert bot.summary()["dark"]["crossings"], "the torch outlived the run"
    dark, _ = _cross(light=False)
    assert dark.summary()["lit"]["crossings"] == 0


def test_the_same_route_is_comparable_lit_and_dark():
    """Same seed, same room, same swarm, same walk. Only the light differs."""
    lit, _ = _cross(seed=3, light=True)
    dark, _ = _cross(seed=3, light=False)
    assert lit.summary()["route"] == dark.summary()["route"]
    assert abs(lit.summary()["all"]["crossings"]
               - dark.summary()["all"]["crossings"]) <= 2


def test_the_crossing_walker_is_selectable_from_the_driver():
    assert "crosser" in bots.BOTS
    assert isinstance(bots.make("crosser", light=True), bots.Crosser)
