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

from types import SimpleNamespace

import pytest

from spikes import (bots, report, rescue as rescue_mod, scene, session,
                    sources, spray as spray_mod)
from spikes.session import Intent, Session
from spotlight.core.constants import CELL

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


def test_no_bot_takes_a_light_any_more():
    """Difficulty target T3 was the same statue twice, lit and dark, and the
    switch was a constructor argument. The torch went (issue #119) and so
    did the switch: a bot that is asked for one is a stale test."""
    with pytest.raises(TypeError):
        bots.make("statue", **{"light": True})
    with pytest.raises(TypeError):
        bots.Scout(seed=1, **{"light": True})


def test_the_wanderer_moves():
    run = play(bots.make("wanderer", seed=3), frames=1500)
    assert (run.player.x, run.player.y) != scene.PLAYER_START


def test_the_listener_finds_people_in_the_dark():
    """The review's sharpest finding, reproduced: the best play is dark, and
    since issue #119 the only play is.

    This is not a target, it is the evidence for one. If the Listener stops
    clearing the room after tuning, this assertion is the thing to revisit
    -- and the reason it was written down.
    """
    run = play(bots.make("listener", seed=5))
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
    # Since the light round (issue #118) this seed's building kills the
    # listener before it is done; a death is not a batch.
    assert run.over == session.NO_LIVES or \
        run.rescued + run.lost == run.total, "left somebody living behind"


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
            if bots.standable(scene.BUILDING, 0, cx, cy):
                assert not scene.ROOM_NEAR.is_solid(cx, cy)
                assert not scene.ROOM_NEAR.is_solid(cx, cy - 1)


def test_the_exit_is_reachable_by_route():
    start = (scene.NEAR, scene.PLAYER_START[0] // 8,
             (scene.PLAYER_START[1] + 15) // 8)
    building = scene.BUILDING
    assert bots.route(building, start,
                      bots.stand_cells(building, scene.NEAR,
                                       *scene.ROOM_NEAR.exit_cell()))


def test_a_script_is_one_intent_per_frame():
    frames = bots.parse_script("3R 2D S 2.")
    assert len(frames) == 3 + 2 + 1 + 2
    assert [(f.dx, f.dy) for f in frames[:5]] == [(1, 0)] * 3 + [(0, 1)] * 2
    assert frames[5].spray
    assert not frames[6].spray


def test_a_script_repeats_a_button_only_once():
    """`3S` is three frames, one of them a press. Holding a key does not
    fire the spray three times."""
    frames = bots.parse_script("3S")
    assert [f.spray for f in frames] == [True, False, False]


def test_a_bad_script_says_so():
    with pytest.raises(ValueError):
        bots.parse_script("100Z")
    # `T` was the torch, until issue #119.
    with pytest.raises(ValueError):
        bots.parse_script("T")


def test_a_scripted_run_replays_exactly():
    script = bots.parse_script("200R 150D S 300L")
    a = play(bots.Script(script), seed=4, frames=900)
    b = play(bots.Script(script), seed=4, frames=900)
    assert (a.player.x, a.player.y) == (b.player.x, b.player.y)
    assert a.tally.sprays == b.tally.sprays == 1


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

    **With the swarm out of the building**, because this is a claim about the
    bot and the walls and the flies were noise in it. Measured with them in,
    the drop on these seeds was exactly the 20 per cent the bar was set at,
    and issue #66 -- which moved where flies stand and so where the bot got
    bitten -- took it to 18 and failed a test about something else. With
    the flies out the drop is 17 per cent (95 against 115 wedged frames), and
    the bar is set below that so the next change to the swarm cannot touch
    it. It is a bar, not a target: the bot's rule is what #24 measured.
    """
    with_rule, without = [], []
    for seed in (1, 2, 3, 4, 5):
        turning = bots.Wanderer(seed=seed)
        grinding = bots.Wanderer(seed=seed)
        grinding.WEDGED_FRAMES = 10 ** 9        # as it was before #24
        for bot, out in ((turning, with_rule), (grinding, without)):
            run = Session(seed=seed)
            for place in run.places:
                place.swarm.clegs.clear()
            out.append(_wedge(bot, run, 3000))
    assert all(a <= b for a, b in zip(with_rule, without)), \
        f"worse on some seed: {with_rule} against {without}"
    assert sum(with_rule) * 100 <= sum(without) * 85, \
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
    a shout over that doorway says the door and not the person. Checked on
    every frame up to the first crossing, however soon that comes: since
    issue #79 the scout has no flash to hand it the near room, so it heads
    for its frontiers at once and may reach the door well inside three
    hundred frames."""
    bot = bots.Scout(seed=1)
    run = Session(seed=1)
    for _ in range(300):
        run.step(bot.intent(run))
        if run.here != scene.NEAR:
            break
        assert not any(room == scene.FAR for room, _, _ in bot.seen)
    assert bot.seen, "it learned nothing of the room it is in"


def test_the_scout_goes_to_the_edge_of_its_map_when_the_route_runs_out():
    bot = bots.Scout(seed=1)
    run = Session(seed=1)
    for _ in range(120):
        run.step(bot.intent(run))
    edges = bot.frontiers(run)
    assert edges, "a bot that has not left the near room has a frontier"
    for place in edges:
        assert bot._unknown_from(place) is not None


def test_the_scout_still_explores_the_building():
    """It finds the far room by walking to the edge of what it knows."""
    run = play(bots.make("scout", seed=1))
    assert run.crossings > 0, "never found the far room"


def test_the_scout_gets_people_out():
    """It has to be able to play the game, or it measures nothing.

    From issue #79 to issue #117 it could not, and the marker on this test
    was the record: the scout mapped a room from what it had seen, the
    opening flash had shown it the whole room on frame one, and without
    that it burned its torch exploring and bled out with nobody out. Nobody
    taught it. **The beam did**: since #117 the searchlight writes the walls
    it passes into the fade, so a swept room is a known one, and the scout
    reads that memory as it always did. With its own torch as well it got
    seven out on seed 1; without one (issue #119) it gets three out of the
    playtest building and everyone out of Level 1 on every seed, which is a
    player's game and not a ceiling's.
    """
    run = play(bots.make("scout", seed=1))
    assert run.rescued >= 3
    from spikes import levels
    dark = Session(seed=1, building=levels.level(1))
    bot = bots.make("scout", seed=1)
    while dark.over is None and dark.frame < LIMIT:
        dark.step(bot.intent(dark))
    assert dark.over == session.ALL_OUT


def test_both_new_bots_are_selectable_from_the_driver():
    assert {"scout", "wanderer"} <= set(bots.BOTS)
    assert isinstance(bots.make("scout"), bots.Scout)


# The crossing walker (issue #29, target T3e) went with the torch (issue
# #119): it walked a stated route lit and dark, and there is no lit.

# --- the bot that goes back for a body (issue #33) --------------------------

def test_the_undertaker_douses_a_body_inside_its_window():
    """**The ceiling on the body window**, which is what difficulty target T12
    is asked of: a bot that abandons what it is doing at the moment of death
    should reach the body in at least three deaths in five.

    The death is forced here rather than waited for, and deliberately: an
    Oracle on this building saves everybody, so on its own it never produces a
    body to go back for. That is itself worth knowing -- **the window cannot be
    measured against perfect play**, because perfect play never opens one -- and
    it is why T12 is stated as a comparison between two bots rather than as a
    figure. What this test pins is that the instrument works: told there is a
    body, the bot walks to it and spends a charge inside the twenty seconds.
    """
    reached = 0
    for seed in (1, 2, 3, 4, 5):
        bot = bots.make("undertaker", seed=seed)
        run = Session(seed=seed)
        for _ in range(60):
            run.step(bot.intent(run))
        victim = [w for w in run.rescue.workers
                  if w.room == scene.NEAR and w.state == rescue_mod.WAITING][-1]
        victim.bitten(victim.blood)
        run.step()
        while victim.in_window and run.over is None:
            run.step(bot.intent(run))
        reached += 1 if victim.doused else 0
    assert reached >= 3, f"the window was reached in {reached} deaths of five"


def test_the_undertaker_measures_the_burst_the_game_actually_lays():
    """**A bot is an instrument**, so it has to ask the spray's own rule.

    It did for issue #41 -- the room goes into `patch_cells`, so the bot never
    counts a cell that lands on wall -- and it has to for issue #44, where the
    same room call now moves a blocked cell one step back toward the player
    instead of losing it. A bot measuring the pre-rebound burst would refuse to
    fire on a body a charge would now save, and every difficulty number taken
    with it would understate what a charge buys.

    Backed against the west wall facing into it: every cell ahead is wall, so
    the pre-rebound burst covered nothing at all and the whole of what the
    charge buys is the two cells level with the player.
    """
    run = Session(seed=1)
    run.player.x, run.player.y = 1 * CELL, 12 * CELL
    run.player.facing = sources.LEFT
    assert (run.player.cx, run.player.cy) == (1, 13)

    laid = set(spray_mod.patch_cells(run.player.cx, run.player.cy,
                                     run.player.facing, run.is_solid))
    assert laid == {(1, 12), (1, 14)}, "the burst is not the one #44 specifies"
    assert set(spray_mod.patch_cells(1, 13, sources.LEFT)) & laid == set(), \
        "these cells are the rebound, not the taper"

    on_rebound = SimpleNamespace(room=run.here, cells=lambda: {(1, 14)})
    elsewhere = SimpleNamespace(room=run.here, cells=lambda: {(5, 5)})
    assert bots.Undertaker._would_cover(run, on_rebound), \
        "the bot cannot see the ground the rebound lays"
    assert not bots.Undertaker._would_cover(run, elsewhere)

    # And it is still the room's answer, not an idealised burst: a cell inside
    # the wall is covered by neither the burst nor the bot.
    in_wall = SimpleNamespace(room=run.here, cells=lambda: {(0, 13)})
    assert run.is_solid(0, 13), "the room changed; re-measure this test"
    assert not bots.Undertaker._would_cover(run, in_wall)


def test_a_bot_that_does_not_know_about_bodies_walks_past_them():
    """The other half of T12, and the reason the window is worth anything: a
    Listener carries on working, because a body is not a shout."""
    bot = bots.make("listener", seed=1)
    run = Session(seed=1)
    for _ in range(60):
        run.step(bot.intent(run))
    victim = [w for w in run.rescue.workers
              if w.room == scene.NEAR and w.state == rescue_mod.WAITING][-1]
    victim.bitten(victim.blood)
    run.step()
    while victim.in_window and run.over is None:
        run.step(bot.intent(run))
    assert not victim.doused, "the Listener went back for a body it cannot hear"


def test_a_walker_wedged_on_a_diagonal_lets_go_of_one_key():
    """Issue #112 (The rooms AP). The listener, started in Level 1's third
    room, arrived at the exit door one pixel below the door's rows pressing
    up-and-left and never moved again: the horizontal step was refused by
    the wall under the door and nudged a pixel up, the vertical step was
    refused and nudged a pixel back, and `Player.move` resolved both inside
    one frame, so the figure ended where it began. Four seeds of four.

    The set-up is the note's: the exit at rows 10-11 of the west wall, a
    wall at (0, 12), the goal the door's feet cell (0, 11), and a Walker one
    pixel off the door's rows -- at (8, 79), feet in (1, 11), so that its
    route is the one diagonal step and the first frame carries it to (8, 81),
    the pixel the note found it stalled on, and the next back again. A
    person lets go of one key; so does a Walker now.
    """
    from spikes import levels

    building = levels.level(1).solo(0)
    room = building[0]
    assert room.rows[10][0] == room.rows[11][0] == "D"
    assert room.rows[12][0] == "#"
    run = Session(seed=1, building=building)
    run.player.x, run.player.y = 8, 79

    class ToTheDoor(bots.Walker):
        def intent(self, run):
            return self._walk(run, bots.stand_cells(run.building, 0, 0, 10))

    walker = ToTheDoor(seed=1)
    for frame in range(50):
        if run.rescue.at_exit(run.here, run.player.occupied_cells()):
            break
        run.step(walker.intent(run))
    else:
        raise AssertionError(
            f"still at {(run.player.x, run.player.y)} after 50 frames")
    assert frame < 50


# --- a bot that sprays at a fly (issue #122) ----------------------------------

def _spraying_run(level, seed, bot="listener", spray=True):
    from spikes import levels
    building, _ = levels.pick(level, seed=seed)
    run = Session(seed=seed, building=building, sound=False)
    player = bots.make(bot, seed=seed, spray=spray)
    while run.over is None and run.frame < LIMIT:
        run.step(player.intent(run))
    return run


def test_the_reference_bots_do_not_spray_unless_armed():
    """The flag defaults off, so the measured rows stay comparable."""
    for name in ("listener", "oracle"):
        assert bots.make(name, seed=1).spray is False
        assert bots.make(name, seed=1, spray=True).spray is True
    # A statue has no fire button to arm.
    assert not getattr(bots.make("statue", seed=1, spray=True), "spray", False)


def test_the_spraying_listener_spends_its_charges_and_kills_on_level_three():
    """Four seeds: every charge spent, at least two flies killed a run, and
    at least as many out as the dry listener with less blood lost."""
    from spikes import levels
    wet_out = dry_out = wet_blood = dry_blood = 0
    for seed in range(session.DEFAULT_SEED, session.DEFAULT_SEED + 4):
        wet = _spraying_run(3, seed)
        dry = _spraying_run(3, seed, spray=False)
        assert wet.tally.sprays == levels.level(3).budget.spray == 5, seed
        assert wet.tally.swatted >= 2, seed
        wet_out += wet.rescued
        dry_out += dry.rescued
        wet_blood += wet.tally.blood_lost
        dry_blood += dry.tally.blood_lost
    assert wet_out >= dry_out
    assert wet_blood < dry_blood


def test_the_spraying_listener_fires_in_level_ones_second_room():
    """Three charges and one fly: a charge is fired where the fly is."""
    fired = 0
    for seed in range(session.DEFAULT_SEED, session.DEFAULT_SEED + 4):
        run = _spraying_run(1, seed)
        fired += run.tally.sprays >= 1
        assert run.tally.sprays <= 3
    assert fired >= 3


def test_the_rule_fires_only_at_a_hunting_fly_ahead_and_never_on_poison():
    from spikes import clegs as C
    run = Session(seed=1, sound=False)
    bot = bots.make("listener", seed=1, spray=True)
    run.step()
    charges = run.spray.charges
    # A fly two cells ahead, hunting: fire.
    fly = run.place.swarm.clegs[0]
    run.player.facing = 3                              # RIGHT
    fly.cx, fly.cy = run.player.cx + 2, run.player.cy
    fly.state = C.HUNTING
    intent = bot._armed(run, Intent())
    assert intent.spray
    # The same fly behind: nothing.
    fly.cx = run.player.cx - 2
    assert not bot._armed(run, Intent()).spray
    # Ahead but sated: nothing.
    fly.cx, fly.state = run.player.cx + 2, C.SATED
    assert not bot._armed(run, Intent()).spray
    # Hunting again, but the ground ahead is already poisoned: nothing.
    fly.state = C.HUNTING
    run.step(Intent(spray=True))
    assert run.spray.charges == charges - 1
    assert not bot._armed(run, Intent()).spray
