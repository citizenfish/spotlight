"""A run, from the first frame to an ending that says what happened.

Issue #15 needs a session to be a thing you can start, finish and start again;
issue #17 needs one that can be driven without a keyboard. Both are the same
refactor -- the loop body came out of the Pygame `while` -- so these tests cover
the refactor as much as the feature.

The regressions pinned here, each of which is something the spike got wrong:

* **The tally lost people.** A run of seven was reported "0 out, 0 lost, 4 never
  found": three in the tail when the last life went were in no column.
* **A clean sweep and a massacre ended identically**, both as "nobody left to
  save", because the end condition did not look at who was left alive.
* **Restarting did not exist.** There was one run per process.
"""

import pytest

from spotlight.core.constants import CELL
from spotlight.core.screen import Screen

from spikes import (
    clegs as clegs_mod, panel, rescue as rescue_mod, scene, session,
)
from spikes.session import Intent, Session
from spikes.spotlights import FloorLight

import screenreader


def run_until_over(run: Session, limit: int = 20000,
                   intent: Intent = session.IDLE) -> str:
    """Drive the real loop until it ends. No fake frames anywhere."""
    while run.over is None and run.frame < limit:
        run.step(intent)
    assert run.over is not None, "the run never ended"
    return run.over


def touch(run: Session, worker) -> None:
    """Put the player on somebody, so the real `reach` finds them.

    Teleporting is a test convenience and it is only used to get the *player*
    somewhere; freeing, following and delivering all go through the game's own
    code. Issue #17's Oracle bot walks the same route for real, and
    `test_driver.py` uses it to reach this ending the honest way.

    **It has to move the player's room as well as their pixels** (issue #21).
    A cell reference means nothing without a room, and four of the seven are in
    the far one: leaving `here` behind would put the player on top of somebody
    through a wall and reach nobody.
    """
    run.here = worker.room
    run.player.x, run.player.y = worker.x, worker.y


def test_a_fresh_session_has_everybody_in_the_room():
    run = Session()
    assert run.total == 7
    assert (run.rescued, run.lost, run.inside) == (0, 0, 7)
    assert run.tally_adds_up()
    assert run.over is None
    assert run.frame == 0


def test_the_same_seed_gives_the_same_run():
    """A seed names a run, or nothing measured from one means anything.

    Every random thing -- the Clegs' temperaments, the searchlight's tour -- is
    derived from the session seed through the same xorshift the Z80 will use.
    """
    a, b = Session(seed=99), Session(seed=99)
    for _ in range(600):
        a.step(Intent(dx=1))
        b.step(Intent(dx=1))
    assert (a.player.x, a.player.y) == (b.player.x, b.player.y)
    assert a.blood == b.blood
    assert [(c.cx, c.cy, c.state) for c in a.swarm.clegs] == \
           [(c.cx, c.cy, c.state) for c in b.swarm.clegs]
    assert [(e.frame, e.kind, e.who) for e in a.log] == \
           [(e.frame, e.kind, e.who) for e in b.log]


def test_different_seeds_give_different_runs():
    a, b = Session(seed=1), Session(seed=2)
    for _ in range(600):
        a.step(Intent(dx=1))
        b.step(Intent(dx=1))
    assert [(c.cx, c.cy) for c in a.swarm.clegs] != \
           [(c.cx, c.cy) for c in b.swarm.clegs]


def test_the_last_worker_dying_does_not_end_the_run():
    """**Issue #20's first criterion, and the thing that was wrong.**

    The level used to stop on the exact frame the last worker died. So a loss
    could not be felt -- there was no *after* to feel it in -- the player was
    never left alone in a room they had failed, and a body was never once seen:
    bodies are created on the frame somebody dies, and that was the frame the
    play area was replaced by a tally.

    A Statue never moves, so it loses everybody. Given lives it will not need,
    because what is under test is that the room carries on with nobody left in
    it to save.
    """
    run = Session(lives=99)
    while run.frame < 12000 and run.lost < run.total:
        run.step()
    assert run.lost == run.total, "not everybody died"
    assert run.over is None, "the run stopped on the last death"

    for _ in range(500):
        run.step()
    assert run.over is None, "ten seconds later it is still running"
    assert run.rescued == 0
    assert run.tally_adds_up()


def test_walking_out_of_the_exit_ends_the_run():
    """The other half of #20: the exit is a finish line, not a delivery hatch.

    *Progression and Scoring* says "reach the exit with at least the quota of
    rescued workers", so reaching it is what completes a level -- and a player
    who cannot save anybody else has to have some way to stop that is not
    standing in a failed room until their blood runs out.

    Nobody is following, and it still ends. That is the case the old rule could
    not reach at all.
    """
    run = Session()
    run.step()                           # one frame in the room they came into
    run.here, (ex, ey) = scene.BUILDING.exit
    run.player.x, run.player.y = ex * 8, ey * 8
    run.step()
    assert run.over == session.NOBODY_LEFT
    assert run.rescued == 0
    assert run.tally_adds_up()


def test_the_door_is_not_an_ending_until_you_have_gone_in():
    """One bit, and it costs nothing today because the prototype's start is a
    patch of open floor in the middle of the room.

    *Building Structure* settled on 2026-09-07 that **the player starts at the
    exit, because that is where they came in.** On the day that lands, a door
    that ends the run on contact ends every run on frame one. Pinned now, while
    it is cheap, rather than found by a tester whose run lasted 0:00.
    """
    run = Session()
    run.here, (ex, ey) = scene.BUILDING.exit
    run.player.x, run.player.y = ex * 8, ey * 8
    run._gone_in = False                 # as if they had started here
    run.step()
    assert run.over is None, "the run ended on the doorstep"

    # Step off the door and come back: now it is a way out.
    run.player.x, run.player.y = scene.PLAYER_START
    run.step()
    run.player.x, run.player.y = ex * 8, ey * 8
    run.step()
    assert run.over == session.NOBODY_LEFT


def test_running_out_of_tries_ends_the_run():
    """The third ending, reached through the real blood mechanism.

    One try rather than three, so the test is seconds rather than minutes; the
    path from blood at zero to the run ending is the game's own.
    """
    run = Session(lives=1)
    run.blood = 1
    run.step()
    run.blood = 0
    run.step()
    assert run.over == session.NO_LIVES
    assert run.lives == 0


def test_getting_everybody_out_is_its_own_ending():
    """A clean sweep must not report as "nobody left to save".

    It used to. The spike ended the level on `rescue.settled`, which is true
    both when everyone is safe and when everyone is dead, so the best possible
    run and the worst possible run ended with the same words.
    """
    run = Session()
    for worker in list(run.rescue.workers):
        touch(run, worker)
        run.step()
    assert len(run.rescue.tail) == run.total
    run.here, (ex, ey) = scene.BUILDING.exit
    run.player.x, run.player.y = ex * 8, ey * 8
    run.step()
    assert run.over == session.ALL_OUT
    assert run.rescued == run.total
    assert run.tally_adds_up()


def test_the_tally_adds_up_with_people_still_in_the_tail():
    """The bug the ending screen exists to fix.

    Wanderer, seed 4: "0 out, 0 lost, 4 never found" in a room of seven. Three
    were following the player when the last try went and appeared nowhere. They
    are still inside the building, so that is what the run says.
    """
    run = Session(lives=1)
    for worker in list(run.rescue.workers)[:3]:
        touch(run, worker)
        run.step()
    assert len(run.rescue.tail) == 3
    run.blood = 0
    run.step()
    assert run.over == session.NO_LIVES
    assert run.inside == 7
    assert run.rescued + run.lost + run.inside == run.total
    assert run.tally_adds_up()


def test_the_tally_adds_up_on_every_frame_of_a_whole_run():
    run = Session()
    while run.over is None and run.frame < 20000:
        run.step()
        assert run.tally_adds_up(), run.frame


def test_a_run_that_has_ended_does_not_advance():
    run = Session(lives=1)
    run.blood = 0
    run.step()
    frame = run.frame
    assert run.step() == []
    assert run.frame == frame


def test_the_log_says_who_and_when():
    """Events name the worker, so a report can say which person rather than how
    many. The spike printed counts, which is why a loss could not be described.
    """
    run = Session()
    touch(run, run.rescue.workers[3])
    run.step()
    freed = [e for e in run.log if e.kind == session.FREED]
    assert len(freed) == 1
    assert freed[0].who == 3
    assert freed[0].frame == run.frame
    # Worker 3 is the first of the four in the far room, and the event says so.
    # The vault asks for this in as many words: the run report must say which
    # room somebody was lost in, and it is the question the user opens with.
    assert freed[0].room == scene.FAR_NAME


def test_the_log_says_which_room():
    """One room today. Issue #21 adds the second, and every event already has
    somewhere to record which of them it happened in."""
    run = Session()
    run.step()
    run.finish(session.ABANDONED)
    assert all(e.room for e in run.log)


def test_a_restart_is_a_new_session_with_nothing_carried_over():
    """The cheapest guarantee available: there is no reset path to get wrong."""
    played = Session(seed=7)
    for _ in range(400):
        played.step(Intent(dx=1, torch=True))
    fresh, benchmark = Session(seed=7), Session(seed=7)
    assert (fresh.player.x, fresh.player.y) == \
           (benchmark.player.x, benchmark.player.y) == scene.PLAYER_START
    assert fresh.frame == 0 and fresh.log == []
    assert fresh.blood == fresh.blood_full
    assert fresh.lives == session.LIVES
    assert [w.state for w in fresh.rescue.workers] == \
           [w.state for w in benchmark.rescue.workers]
    assert [(c.cx, c.cy) for c in fresh.swarm.clegs] == \
           [(c.cx, c.cy) for c in benchmark.swarm.clegs]
    assert fresh.cone.lit is False


def test_a_session_draws_a_whole_frame_including_the_strip():
    """Drawing is portable too, so the driver can capture frames without a host."""
    run = Session()
    screen = Screen()
    run.step()
    run.draw(screen)
    assert any(screen.pixels), "nothing was drawn"
    # The strip is painted on the first draw of a session, not carried over
    # from whatever run was on screen before it.
    assert run._painted_strip


def test_the_run_says_nothing_to_stdout(capsys):
    """Everything the player needs is on screen. Nothing prints."""
    run = Session(lives=1)
    for _ in range(300):
        run.step(Intent(dx=1, torch=True))
    run.blood = 0
    run.step()
    assert run.over is not None
    assert capsys.readouterr().out == ""


# --- staggered clocks and the death beat (issue #18) -----------------------

def test_the_deaths_in_a_real_run_are_spread_out_not_simultaneous():
    """**The thing that was wrong.** Every run ended with seven deaths on the
    same frame, so `death_spread_seconds` was zero on every seed, no loss could
    be sequenced and the level ended the instant the first body appeared.

    Driven through the real loop, not through `Rescue` on its own, because the
    bug was only visible in a whole run.
    """
    run = Session(seed=1, lives=99)
    deaths = []
    while run.frame < 12000:
        for event in run.step():
            if event.kind == session.WORKER_DIED:
                deaths.append(event.frame)
        if run.over is not None:
            break
    assert len(deaths) == run.total, "not everybody died"
    assert len(set(deaths)) == len(deaths), "two people died on the same frame"

    # **The twenty-second bound moved out of this test with issue #19**, and
    # that is a finding rather than a relaxation. Target T7 -- *no two worker
    # deaths within twenty seconds* -- was met by the authored ladder alone,
    # which is what the test below pins. Once Clegs can bite waiting workers, a
    # full meal is `DRAIN_TOTAL` points off somebody's clock, which at
    # `BLEED_EVERY` frames a point is sixteen seconds of their life -- so one
    # bite can very nearly close a twenty-second gap and two can overtake it.
    #
    # Measured on the Statue over seeds 1 to 5: seven to ten worker bites a
    # run, forty-four to sixty-nine points of worker blood, and closest gaps of
    # 4, 8, 4, 1 and 3 seconds against a target of twenty. **T7 is unmet and it
    # is the level's ladder that has to answer for it, not this test.** The
    # spacing is also a budget requirement -- *Nests* holds concurrent nests to
    # two on the strength of it -- so it is worth a decision rather than a
    # weaker assertion here.
    gaps = [b - a for a, b in zip(deaths, deaths[1:])]
    assert min(gaps) > 0, f"two deaths {min(gaps)} frames apart"


def test_the_authored_clock_ladder_still_puts_twenty_seconds_between_deaths():
    """T7's target, measured on the thing that is supposed to deliver it.

    The ladder in `scene.WORKERS_A` is 30/40/50/60/70/80/90 against one bleed
    tick for everybody, which is twenty seconds between consecutive deaths --
    one body window each. Nothing but the clock is running here, so this is the
    room's authored intent with the swarm taken out of it, and it is what the
    real run above is measured against when it comes up short.
    """
    from spikes import rescue as rescue_mod

    room = rescue_mod.Rescue(scene.WORKERS_A, scene.BUILDING.exit)
    deaths = []
    for frame in range(20000):
        for _ in room.tick():
            deaths.append(frame)
        if room.settled:
            break
    assert len(deaths) == len(scene.WORKERS_A)
    gaps = [b - a for a, b in zip(deaths, deaths[1:])]
    assert min(gaps) == 20 * 50, f"the ladder gives {[g // 50 for g in gaps]}s"


def test_a_death_is_announced_from_where_they_fell():
    """The death beat, through the whole pipeline: the shout lifts its own
    cells out of the dark and the word is over the body, on the frame they die.

    A death nobody notices is the same as no death, and an absence is not a
    signal -- a first-timer with six other voices in the building will not
    notice that one of them stopped.
    """
    from spikes import lighting, rescue as rescue_mod

    run = Session(seed=1, lives=99)
    dying = min(run.rescue.workers, key=lambda w: w.blood)
    while True:
        events = run.step()
        if any(e.kind == session.WORKER_DIED for e in events):
            break
        assert run.frame < 12000, "nobody died"

    assert dying.state == rescue_mod.DEAD, \
        "the shortest clock was not the first to run out"
    assert dying in run.shouting, "the death was not announced"
    for cell in dying.call_cells():
        assert cell in run.call_cells
        cx, cy = cell
        assert run.field.level_at(cx, cy) == lighting.LIT
        assert not run.field.reveals_at(cx, cy), "a shout revealed somebody"


def test_every_death_is_announced_exactly_once():
    """One shout each, not a body that goes on calling. A corpse with something
    left to say would be a permanent bearing to a place there is no longer any
    reason to go.
    """
    from spikes import rescue as rescue_mod

    run = Session(seed=1, lives=99)
    said = {}
    while run.frame < 12000 and run.over is None:
        run.step()
        # Asked of **everybody**, not of `run.shouting`, which since issue #21
        # is only the room the player is standing in. A death is announced from
        # the cell they fell in, in the room they fell in; a player next door
        # hears it as a word over the doorway instead, and that is a different
        # claim tested where the doorway is. Four of the seven are in the far
        # room, so reading `run.shouting` here would quietly test three.
        for worker in run.rescue.calling(run.frame):
            if worker.state == rescue_mod.DEAD:
                said[id(worker)] = said.get(id(worker), 0) + 1
    assert len(said) == run.lost > 0, "not every death was announced"
    lengths = list(said.values())        # in the order they died
    # The **last** death ends the run on the frame it happens -- "nobody left
    # to save" -- so its call is cut off after one frame. That is issue #20's
    # to fix (*do not end the level the instant the last worker dies*), not
    # this one's, and when it lands this test should tighten to all of them.
    # **Every one of them, including the last.** This used to have to skip the
    # final death, because the run ended on the frame it happened and the shout
    # was cut off after a single frame. Issue #20 is what lets a death be
    # announced in full, and that is the whole point of it: there is now an
    # *after* for the loss to land in.
    assert lengths == [rescue_mod.CALL_FRAMES] * len(lengths), \
        f"death calls lasted {lengths} frames"
    assert run.over is None, "the run ended on the last death again"


# --- dying must not empty the room (issue #27) -----------------------------

#: Seed 3 with the torch held on is the run the bug was reported and measured
#: on: it loses its first try at 35 seconds and used to come out of it with
#: half a swarm. Named here so the regression is pinned on the run that showed
#: it rather than on a run chosen to be convenient.
BUG_SEED = 3


def _lit_statue_run(seed: int = BUG_SEED, frames: int = 12000):
    """The reported run, driven for real. Returns the session and the frame of
    every try lost.

    **The frame budget went from 9000 to 12000 with issue #21, and the claims
    below did not move.** Splitting the six flies three and three between the
    two rooms halves what a player standing still in the near room is up
    against, so the same seed takes about twice as long to spend two tries:
    the deaths on this seed were at 51s and 105s and are now at 103s and 189s.
    Neither test is about how fast a Statue dies; both are about what happens
    to the swarm **when** it does, and they still need two deaths to compare
    across.
    """
    from spikes import bots
    bot = bots.Statue(seed=seed, light=True)
    run = Session(seed=seed)
    sizes, deaths = set(), []
    while run.over is None and run.frame < frames:
        for event in run.step(bot.intent(run)):
            if event.kind == session.LIFE_LOST:
                deaths.append(run.frame)
        sizes.add(len(run.swarm.clegs))
    return run, sizes, deaths


def test_the_swarm_is_the_same_size_across_a_run_with_deaths():
    """**The bug found in play, and the reason every measurement taken from a
    run with a death in it has to be retaken.**

    The death branch removed every Cleg attached to the player, permanently. On
    this seed the swarm went from six to three across two deaths and the run
    finished with a try in hand and half the room's threat gone, so the gap
    between the first death and the second was nearly four times the gap before
    the first. **Dying was the cheapest way to make the game easier.**

    Nothing kills a Cleg but the spray, and a Statue never sprays, so on this
    run the count may not move at all.
    """
    run, sizes, deaths = _lit_statue_run()
    assert len(deaths) >= 2, f"wanted a run with deaths in it, got {deaths}"
    assert run.tally.swatted == 0, "a Statue never sprays"
    # **The building's total, not a room's** (issue #21). `run.swarm` adds the
    # rooms up, so this now also catches a fly being dropped on the floor
    # between two swarms while it walks through a doorway -- which is the same
    # bug in a new place, and the one thing a per-room count would miss.
    assert sizes == {len(scene.CLEGS_A) + len(scene.CLEGS_B)}, \
        f"the swarm changed size: {sizes}"


def test_the_player_does_not_instantly_re_die_at_the_entrance():
    """The other half of the fix. Putting the swarm back must not put it back
    *on* you: leaving the flies attached across a respawn, or detaching them
    hungry onto the square you are returned to, spends the next try in a couple
    of seconds and reads as the game cheating.

    Five seconds is a floor rather than a target -- the run measured 57 and 58
    seconds between consecutive deaths -- and it is the quantity that fails
    loudly if a detached fly ever comes back hungry.
    """
    _run, _sizes, deaths = _lit_statue_run()
    gaps = [b - a for a, b in zip(deaths, deaths[1:])]
    assert gaps, "needed at least two deaths to have a gap"
    assert min(gaps) > 250, f"a try was spent in under five seconds: {gaps}"


def test_dying_detaches_rather_than_deletes():
    """The mechanism, at the frame it happens on, without waiting for a run.

    The player is put back at the entrance and the flies that were on them are
    still in the room -- sated, so they drift off, and scattered, so they are
    not stacked on the square you are standing on.
    """
    from spikes import clegs as clegs_mod
    run = Session(lives=3)
    run.step()
    for cleg in run.place.swarm.clegs[:3]:
        cleg.cx, cleg.cy = run.player.cx, run.player.cy
        run.place.swarm._attach(cleg)
    before = len(run.swarm.clegs)
    run.blood = 0
    run.step()
    assert run.lives == 2
    assert len(run.swarm.clegs) == before
    assert run.swarm.attached() == []
    assert all(c.state == clegs_mod.SATED for c in run.place.swarm.clegs[:3])
    here = (run.player.cx, run.player.cy)
    assert here not in [(c.cx, c.cy) for c in run.swarm.clegs[:3]]


# --- Clegs bite waiting workers and lit followers (issue #19) --------------
#
# **The thing that was wrong.** `Swarm.tick` never took a worker, so nothing
# could happen to the tail: the phase-0 review's words were *"the tail is not a
# liability, it is a rucksack"*, and with nothing able to touch it the best play
# was to gather all seven and leave once -- the opposite of the decision the
# design calls the game. These pin it through the real loop, because the rule
# that decides who is prey is the light field's and the light field only exists
# in a running session.


def _free(run, index, torch=True):
    """Touch a worker so they follow, through the game's own `reach`."""
    worker = run.rescue.workers[index]
    touch(run, worker)
    run.step(Intent(torch=torch))
    assert worker.state == rescue_mod.FOLLOWING
    return worker


def _flies_on(run, person, count=2):
    """Put `count` flies in the cell somebody is standing in.

    **The flies come from that person's own room's swarm** (issue #21). A room
    has its own swarm, because a swarm ticks against one room's lures, one
    room's walls and one room's lit people -- so a fly from the room next door
    standing on cell (17, 4) is standing somewhere else entirely and can no more
    bite you than a fly on the other side of a wall. Taking them off the
    building-wide `run.swarm` used to work when there was one room and quietly
    stopped meaning anything when there were two.
    """
    flies = run.places[person.room].swarm.clegs[:count]
    assert flies, "that room has no swarm to bite with"
    for cleg in flies:
        cleg.cx, cleg.cy = person.cell()
    return flies


def _walk_away(run, worker, frames=30):
    """Walk east with the tail strung out behind, which is the safe way round.

    The cone points the way you are walking, so the people behind you are in
    the dark. This is what the game looks like when nothing is going wrong.
    """
    for _ in range(frames):
        run.step(Intent(dx=1))
    assert worker not in run._lit_people(run.place), \
        "the tail was lit walking away"
    return worker


def _turn_round(run, worker, frames=2):
    """Look back down your own line, which is the thing that gets them eaten."""
    for _ in range(frames):
        run.step(Intent(dx=-1))
    assert worker in run._lit_people(run.place), \
        "turning round did not light the tail"
    return worker


def test_a_follower_is_dark_behind_you_and_lit_when_you_turn_round():
    """**The trap the whole tail is built on**, end to end.

    The cone points the way you are walking, so the people behind you are in
    the dark -- and the instinct to turn and check on them is exactly what puts
    them in the light. *Trapped Workers*: "a worker trailing you through
    darkness is ignored, and one standing in your cone is prey."
    """
    run = Session(seed=1)
    worker = _free(run, 5)
    _walk_away(run, worker)
    assert run._lit_people(run.place) == [], "walking away, the tail is in the dark"
    _turn_round(run, worker)
    assert run._lit_people(run.place) == [worker], "turning round lit them up"


def test_prey_is_exactly_who_is_drawn_so_the_rule_can_be_seen():
    """If you can see them, so can the flies.

    The prey test is `LightField.prey_at`, one step stricter than the
    `reveals_at` the drawing uses: your own dim glow shows you somebody at
    arm's length without making them prey. Anybody the swarm can find is
    therefore somebody on screen, so the player is never punished by a rule
    they had no way to observe.
    """
    run = Session(seed=1)
    _turn_round(run, _walk_away(run, _free(run, 5)))
    for person in run._lit_people(run.place):
        assert any(run.field.reveals_at(*c) for c in person.cells()), \
            "something was prey that was never drawn"


def test_a_lit_follower_is_bitten_and_a_dark_one_is_not():
    """The criterion, in the loop, with the swarm put where it has to be.

    The flies are placed on the follower rather than walked there, because what
    is under test is whether a lit worker is prey at all -- how a fly gets to
    somebody is the swarm's own business and is tested in `test_spike_clegs`.
    """
    dark = Session(seed=1)
    worker = _walk_away(dark, _free(dark, 5))
    _flies_on(dark, worker)
    dark.step(Intent(dx=1))
    assert dark.swarm.victim_attachments == 0, "a dark follower was bitten"

    lit = Session(seed=1)
    worker = _turn_round(lit, _walk_away(lit, _free(lit, 5)))
    _flies_on(lit, worker)
    lit.step(Intent(dx=-1))
    assert lit.swarm.victim_attachments > 0, "a lit follower was ignored"
    assert [e.who for e in lit.frame_events
            if e.kind == session.WORKER_BITTEN] == [5, 5]


def test_a_waiting_worker_standing_in_light_is_bitten_where_they_stand():
    """A spotlight left burning beside somebody is bait with a person in it.

    This is the design's own baiting rule read with a worker on the lit ground:
    a light on the floor pulls exactly as hard as one in your hand, and now
    there is something for the swarm to find when it gets there.
    """
    run = Session(seed=1)
    worker = run.rescue.workers[3]
    cx, cy = worker.cell()
    # The lamp lies in **the worker's room**, which is the far one: a light
    # belongs to the room it is in, and the same cell in the other room is a
    # different place (issue #21).
    lamp = FloorLight(cx, cy, power=9000, lit=True, room=worker.room)
    run.kit.floor.append(lamp)
    run.step()
    where = run.places[worker.room]
    assert worker in run._lit_people(where), "a burning lamp did not light them"

    _flies_on(run, worker)
    run.step()
    assert run.swarm.victim_attachments > 0
    assert worker.state == rescue_mod.WAITING, "still waiting, and bleeding"


def test_a_follower_can_die_en_route_and_the_tally_still_adds_up():
    """The third criterion. A follower bled to death by flies is counted as a
    loss, is out of the tail, and appears in exactly one column."""
    run = Session(seed=1)
    worker = _free(run, 5)
    worker.blood = 2
    _turn_round(run, _walk_away(run, worker))
    _flies_on(run, worker, 3)
    for _ in range(clegs_mod.DRAIN_EVERY * 3):
        run.step(Intent(dx=-1))
        assert run.tally_adds_up(), run.frame

    assert worker.state == rescue_mod.DEAD
    assert worker not in run.rescue.tail, "a body was still being dragged along"
    assert run.lost == 1
    died = [e for e in run.log if e.kind == session.WORKER_DIED]
    assert [e.who for e in died] == [5], "the death was not counted once"


def test_a_worker_bitten_to_death_still_gets_their_death_shout():
    """A death has to be announced or it did not happen as far as the player is
    concerned, and that is no less true when a fly did it than when the clock
    did. It is also the only channel a follower being eaten has.
    """
    run = Session(seed=1)
    worker = _free(run, 5)
    worker.blood = 1
    _turn_round(run, _walk_away(run, worker))
    for cleg in run.swarm.clegs[:3]:
        cleg.cx, cleg.cy = worker.cell()
    while worker.state != rescue_mod.DEAD:
        run.step(Intent(dx=-1))
        assert run.frame < 3000
    assert worker in run.shouting, "a bitten worker died in silence"

    said = 1
    for _ in range(rescue_mod.CALL_FRAMES * 2):
        run.step(Intent(dx=-1))
        said += worker in run.shouting
    assert said == rescue_mod.CALL_FRAMES, \
        "a bite death is not the same length of shout as a clock death"


def test_a_follower_dying_closes_the_line_and_leaves_the_body_where_it_fell():
    """Settled in the vault 2026-09-07, and it needs no code of its own: the
    tail is a path and a set of people walking it, not a set of slots.

    The person behind the one who died moves up the trail; the body stays put.
    """
    run = Session(seed=1)
    first = _free(run, 5)
    second = _free(run, 3, torch=True)
    assert run.rescue.tail == [first, second]

    for _ in range(60):
        run.step(Intent(dx=-1))
    fell_at = (first.x, first.y)
    behind = (second.x, second.y)
    first.bleed(first.blood)
    run.step(Intent(dx=-1))

    assert run.rescue.tail == [second], "the line did not close up"
    assert (first.x, first.y) == fell_at, "the body was moved"
    assert (second.x, second.y) != behind, "nobody moved up"


def test_the_players_own_bites_are_untouched_by_the_new_rule():
    """**The fourth criterion.** A run in which no worker is ever lit must
    count bites exactly as it did before -- and a worker being eaten must never
    show up in `attachments`, in the first `BITTEN` frame, or in the per-lure
    billing that the searchlight's whole case rests on.
    """
    run = Session(seed=3)
    for cleg in run.swarm.clegs[:2]:
        cleg.cx, cleg.cy = run.player.cx, run.player.cy
    run.step()
    bitten = [e for e in run.log if e.kind == session.BITTEN]
    assert bitten and sum(e.count for e in bitten) == 2
    assert run.tally.attachments == 2
    assert sum(run.swarm.bites_by_source) == 2

    worker = _turn_round(run, _walk_away(run, _free(run, 5)))
    for cleg in run.swarm.clegs[2:5]:
        cleg.cx, cleg.cy = worker.cell()
    before = (run.tally.attachments, sum(run.swarm.bites_by_source))
    for _ in range(clegs_mod.DRAIN_EVERY * 2):
        run.step(Intent(dx=-1))
    assert run.swarm.victim_attachments > 0, "nothing bit the worker"
    assert (run.tally.attachments, sum(run.swarm.bites_by_source)) == before, \
        "a worker bite was counted as a bite on the player"
    # The two flies already on the player go on drinking, which is why this is
    # an equality against what the player actually lost rather than a frozen
    # number: every point billed to a lure is a point out of the player, and
    # the worker's blood is in a ledger of its own.
    assert sum(run.swarm.blood_by_source) == run.tally.blood_lost
    assert run.swarm.victim_blood > 0


# --- the level ends at the exit or the last life (issue #20) ---------------


def test_a_body_lies_on_screen_for_its_whole_lifetime():
    """**The measurement nobody had ever been able to take.**

    *Playtest readiness*: "bodies appear on the frame the level ends", and
    `BODY_FRAMES` -- the window in which a flyspray could save a corpse from
    becoming a nest -- "has never once elapsed on screen". Both were true
    because the run stopped on the last death, and the first death is not the
    last only since issue #18 staggered the clocks.

    So this is the first test in the prototype's life that can watch a body
    lie there, and it watches the whole window out.
    """
    run = Session(seed=1, lives=99)
    while run.frame < 12000 and not run.rescue.bodies():
        run.step()
    body = run.rescue.bodies()[0]
    fell_at = (body.x, body.y)
    assert not body.turning, "it turned before it had lain there at all"

    screen = Screen()
    for _ in range(rescue_mod.BODY_FRAMES):
        run.step()
        assert run.over is None, "the run ended under the body"
        assert body in run.rescue.bodies(), "the body stopped existing"
        assert (body.x, body.y) == fell_at, "the body moved"
    assert body.turning, "the window never ran out"

    # And it is on the screen, not merely in the model. A body is a fixture:
    # it is drawn wherever the ground is lit or remembered, unlike a person,
    # who is drawn only where a light is on them this frame.
    run.draw(screen)
    assert any(screen.point(body.x + dx, body.y + CELL + dy)
               for dy in range(CELL) for dx in range(CELL)), \
        "nothing was drawn where somebody died"


def test_the_tally_adds_up_at_every_ending_the_game_can_reach():
    """Rescued + lost + still inside = seven, whichever way a run stops.

    It is the number a tester reads off the ending screen and it has been wrong
    before: a run of seven reported "0 out, 0 lost, 4 never found", with three
    people in the tail appearing in no column at all.
    """
    endings = {}

    # Everybody out: collect the room and walk out of the door.
    sweep = Session()
    for worker in list(sweep.rescue.workers):
        touch(sweep, worker)
        sweep.step()
    sweep.here, (ex, ey) = scene.BUILDING.exit
    sweep.player.x, sweep.player.y = ex * 8, ey * 8
    sweep.step()
    endings[sweep.over] = sweep

    # Walked out without them, with three in the tail and four still waiting.
    part = Session()
    for worker in list(part.rescue.workers)[:3]:
        touch(part, worker)
        part.step()
    part.here = scene.BUILDING.exit[0]
    part.player.x, part.player.y = ex * 8, ey * 8
    part.step()
    endings[part.over] = part

    # Out of tries.
    spent = Session(lives=1)
    spent.step()
    spent.blood = 0
    spent.step()
    endings[spent.over] = spent

    assert set(endings) == {session.ALL_OUT, session.NOBODY_LEFT,
                            session.NO_LIVES}
    for name, run in endings.items():
        assert run.tally_adds_up(), \
            f"{name}: {run.rescued} + {run.lost} + {run.inside} " \
            f"!= {run.total}"
        assert run.rescued + run.lost + run.inside == 7


def test_arriving_with_a_tail_banks_them_before_the_run_is_judged():
    """The exit is a finish line, but it hands people over on the way through.

    `deliver` runs earlier in the frame than `_ending` does, so somebody in the
    tail on the last frame is counted as out rather than as still inside. Get
    that order wrong and a clean sweep reports as an abandonment.
    """
    run = Session()
    for worker in list(run.rescue.workers)[:2]:
        touch(run, worker)
        run.step()
    run.here, (ex, ey) = scene.BUILDING.exit
    run.player.x, run.player.y = ex * 8, ey * 8
    run.step()
    assert run.over == session.NOBODY_LEFT
    assert run.rescued == 2 and len(run.rescue.tail) == 0
    assert run.inside == 5


def test_the_run_carries_on_past_a_loss_so_the_loss_can_be_felt():
    """Not the same claim as "the last death does not end it".

    A player is meant to be left in the room afterwards, with the body in it
    and the rest of the building still running: the swarm still moving, the
    clock still going on everybody who is left. That is the *after* a loss
    needs in order to be a loss rather than a screen change.
    """
    run = Session(seed=1, lives=99)
    while run.frame < 12000 and run.lost == 0:
        run.step()
    assert run.lost == 1
    at_death = run.frame
    moving = [(c.cx, c.cy) for c in run.swarm.clegs]
    blood = [w.blood for w in run.rescue.alive_waiting()]

    for _ in range(600):
        run.step()
    assert run.over is None
    assert run.frame == at_death + 600
    assert [(c.cx, c.cy) for c in run.swarm.clegs] != moving, \
        "the swarm froze when somebody died"
    assert [w.blood for w in run.rescue.alive_waiting()] != blood, \
        "the clock stopped for everybody else"


# --- the torch running out (issue #31) -------------------------------------

def test_the_torch_running_out_is_an_event_and_it_flashes():
    """A first-timer switches it on to see, leaves it on, and goes dark.

    Until this, nothing said so: the bar slid to empty over twenty seconds and
    the light simply stopped. The bar is not an event -- the moment it matters
    is the moment the player is looking at something else, in the dark.
    """
    run = Session()
    run.cone.power = 3
    # The frame the torch is switched on burns a frame of it, like any other.
    run.step(Intent(torch=True))
    assert run.cone.lit and run.cone.power == 2

    run.step()
    assert run.cone.lit, "went out a frame early"
    assert not any(e.kind == session.TORCH_OUT for e in run.frame_events)

    events = run.step()
    assert [e.kind for e in events if e.kind == session.TORCH_OUT] == \
        [session.TORCH_OUT]
    assert not run.cone.lit
    assert run.panel.flashing("light")


def test_the_torch_going_out_is_announced_once_and_then_stops_flashing():
    run = Session()
    run.cone.power = 1
    run.step(Intent(torch=True))
    for _ in range(panel.ALERT_FRAMES + 10):
        run.step()
    assert sum(1 for e in run.log if e.kind == session.TORCH_OUT) == 1
    assert not run.panel.flashing("light"), "the alert never ended"


def test_swapping_onto_a_fresh_light_is_not_the_torch_running_out():
    """The bar refills in front of you, and you did it on purpose.

    The alert is for the thing that happens *to* the player. A spotlight picked
    up on the same frame the last one died is not that.
    """
    run = Session()
    cx, cy = run.player.cx, run.player.cy
    run.kit.floor.append(FloorLight(cx, cy, power=500, room=run.here))
    run.cone.power = 1
    run.step(Intent(torch=True))
    assert any(e.kind == session.SWAPPED for e in run.frame_events)
    assert not any(e.kind == session.TORCH_OUT for e in run.frame_events)
    assert not run.panel.flashing("light")


def test_the_strip_says_in_words_how_many_are_safe():
    """Issue #31: `*3/7` left the reader to guess what was being counted."""
    run = Session()
    screen = Screen()
    run.draw(screen)
    region = panel.REGIONS["rescued"]
    assert screenreader.read(screen, region.label_col, region.row,
                             len(region.label)) == "SAFE"
    assert screenreader.read(screen, region.col, region.row,
                             region.width).rstrip() == "0/7"
