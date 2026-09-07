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

from spotlight.core.screen import Screen

from spikes import scene, session
from spikes.session import Intent, Session


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
    """
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


def test_standing_still_ends_with_nobody_left_to_save():
    """The Statue's ending: everybody bleeds out and the run says so."""
    run = Session()
    assert run_until_over(run) == session.NOBODY_LEFT
    assert run.rescued == 0
    assert run.lost == run.total
    assert run.tally_adds_up()


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
    ex, ey = scene.exit_cell()
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
    assert freed[0].room == scene.ROOM_NAME


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
