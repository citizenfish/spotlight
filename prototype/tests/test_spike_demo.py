"""The demo loop (issue #89), driven headless through a whole cycle."""

import pygame

from spikes import spike1, spike_demo
from spotlight.core.screen import Screen


def _demo(runs=2, seed=1, bot="oracle"):
    shell = spike1.Shell(Screen(), seed=seed)
    return spike_demo.Demo(shell, bot=bot, runs=runs, title_seconds=1,
                           ending_seconds=1)


def test_the_title_is_pressed_for_you_after_the_wait():
    demo = _demo()
    for _ in range(spike_demo.FRAME_RATE - 1):
        demo.frame()
    assert demo.shell.state == spike1.TITLE
    demo.frame()
    assert demo.shell.state == spike1.PLAY
    assert demo.shell.run is not None and demo.shell.run.seed == 1
    assert demo.bot is not None and demo.played == 1


def test_the_bot_plays_the_run_through_the_shells_own_keys():
    demo = _demo()
    for _ in range(spike_demo.FRAME_RATE):
        demo.frame()
    run = demo.shell.run
    for _ in range(300):
        demo.frame()
    # Three hundred, and the one the press frame stepped on the way in.
    assert run.frame == 301, "the shell did not step every frame"
    assert run.player.x != run.building.start[1][0] \
        or run.player.y != run.building.start[1][1], "the bot never moved"


def test_an_ending_is_followed_by_a_fresh_run_on_the_next_seed():
    demo = _demo(runs=2, seed=1)
    for _ in range(spike_demo.FRAME_RATE):
        demo.frame()
    first = demo.shell.run
    frames = 0
    while demo.shell.state != spike1.ENDED and frames < 20000:
        demo.frame()
        frames += 1
    assert demo.shell.state == spike1.ENDED, "the oracle's run never ended"
    for _ in range(spike_demo.FRAME_RATE):
        demo.frame()
    assert demo.shell.state == spike1.PLAY
    assert demo.shell.run is not first and demo.shell.run.seed == 2
    assert demo.played == 2 and demo.done


def test_a_finished_loop_presses_nothing_more():
    demo = _demo(runs=1, seed=3)
    for _ in range(spike_demo.FRAME_RATE):
        demo.frame()
    assert demo.done
    while demo.shell.state != spike1.ENDED:
        demo.frame()
    for _ in range(3 * spike_demo.FRAME_RATE):
        demo.frame()
    assert demo.shell.state == spike1.ENDED, "it started a run it was not asked for"


def test_for_ever_means_for_ever():
    demo = _demo(runs=0)
    assert demo.forever and not demo.done
    for _ in range(spike_demo.FRAME_RATE):
        demo.frame()
    assert not demo.done


def test_the_shell_takes_a_seed_and_a_player_gets_the_default():
    from spikes import session
    assert spike1.Shell(Screen()).seed == session.DEFAULT_SEED
    shell = spike1.Shell(Screen(), seed=11)
    shell.key(pygame.K_s)
    assert shell.run.seed == 11
