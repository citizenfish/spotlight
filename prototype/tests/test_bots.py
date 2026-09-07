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

from spikes import bots, rescue as rescue_mod, scene, session
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


def test_the_listener_leaves_in_batches():
    bot = bots.make("listener")
    run = play(bot, seed=2)
    assert run.rescued >= bot.batch


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
    """Faster than the bot that has to wait to be told where people are."""
    oracle = play(bots.make("oracle", seed=6))
    listener = play(bots.make("listener", seed=6))
    assert oracle.seconds < listener.seconds


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
            if bots.standable(cx, cy):
                assert not scene.is_solid(cx, cy)
                assert not scene.is_solid(cx, cy - 1)


def test_the_exit_is_reachable_by_route():
    start = (scene.PLAYER_START[0] // 8, (scene.PLAYER_START[1] + 15) // 8)
    assert bots.route(start, bots.stand_cells(*scene.exit_cell()))


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
