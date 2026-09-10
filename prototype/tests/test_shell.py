"""Title, play, ending, again -- the shape of a session in the window.

Issue #15. The shell is the state machine `main` used to be, pulled out so it
can be tested by pressing keys at it rather than by opening a window and
waiting. Everything here runs headless: `conftest.py` forces the dummy SDL
drivers, and nothing in the shell touches a surface.
"""

import pygame
import pytest

from spotlight.core.screen import Screen

from spikes import session, spike1
from screenreader import rows


@pytest.fixture
def shell():
    return spike1.Shell(Screen())


def test_the_title_is_what_a_player_sees_first(shell):
    """The window used to open straight into the opening flash."""
    assert shell.state == spike1.TITLE
    assert shell.run is None
    text = rows(shell.screen)
    assert any("ARROW KEYS" in line for line in text)


def test_the_title_waits_for_a_key(shell):
    """Frames pass and nothing starts until somebody presses something."""
    for _ in range(50):
        shell.frame(dx=1)
    assert shell.state == spike1.TITLE
    assert shell.run is None


def test_any_key_starts_the_game(shell):
    assert shell.key(pygame.K_j) is True
    assert shell.state == spike1.PLAY
    assert shell.run is not None and shell.run.frame == 0


def test_escape_quits_from_anywhere(shell):
    assert shell.key(pygame.K_ESCAPE) is False
    shell.key(pygame.K_SPACE)
    assert shell.key(pygame.K_ESCAPE) is False


def test_playing_advances_the_run(shell):
    shell.key(pygame.K_SPACE)
    for _ in range(30):
        shell.frame(dx=1)
    assert shell.run.frame == 30


def test_the_torch_and_the_spray_are_edge_triggered(shell):
    """Holding a key down must not strobe the torch or empty the can."""
    shell.key(pygame.K_SPACE)          # start
    shell.key(pygame.K_t)
    shell.frame()
    assert shell.run.cone.enabled is True
    for _ in range(20):
        shell.frame()
    assert shell.run.cone.enabled is True


def _out_of_the_pause(shell):
    """Run out whatever pause the last frame asked for (issue #52).

    An ending stops the clock for a second before the ending screen replaces
    the play frame -- a beat on the frame it happened, which is what the pause
    is for. The frames are the shell's: `run.step` is not called during them,
    so nothing about the run moves. See `Shell.frame`.
    """
    held = shell.held
    for _ in range(held):
        shell.frame()
    return held


def test_an_ending_replaces_the_play_screen(shell):
    shell.key(pygame.K_SPACE)
    shell.run.lives = 1
    shell.run.blood = 0
    shell.frame()
    assert _out_of_the_pause(shell) == 50
    assert shell.state == spike1.ENDED
    text = rows(shell.screen)
    assert session.ENDING_TEXT[session.NO_LIVES][0] in text
    assert any(line.startswith("GOT OUT") for line in text)


def test_space_from_the_ending_starts_a_clean_run(shell):
    """A fresh run, not a rewound one.

    The run before it had a worker freed, a torch burning and a quarter of its
    blood gone; none of that may survive, and the cheapest way to guarantee it
    is that the object does not.
    """
    shell.key(pygame.K_SPACE)
    first = shell.run
    first.player.x, first.player.y = first.rescue.workers[0].x, \
        first.rescue.workers[0].y
    shell.key(pygame.K_t)
    shell.frame()
    assert first.rescue.tail and first.cone.enabled
    first.lives = 1
    first.blood = 0
    shell.frame()
    _out_of_the_pause(shell)
    assert shell.state == spike1.ENDED

    shell.key(pygame.K_SPACE)
    assert shell.state == spike1.PLAY
    assert shell.run is not first
    assert shell.run.frame == 0
    assert shell.run.rescue.tail == []
    assert shell.run.cone.enabled is False
    assert shell.run.blood == shell.run.blood_full
    assert shell.run.lives == session.LIVES
    assert shell.run.log == []


def test_other_keys_do_not_restart_from_the_ending(shell):
    """The ending names one key, so only that key does it."""
    shell.key(pygame.K_SPACE)
    shell.run.lives = 1
    shell.run.blood = 0
    shell.frame()
    _out_of_the_pause(shell)
    shell.key(pygame.K_j)
    assert shell.state == spike1.ENDED


def test_a_whole_session_prints_nothing(capsys):
    """Start to finish with no debug key touched: stdout stays empty."""
    shell = spike1.Shell(Screen())
    shell.key(pygame.K_SPACE)
    shell.run.lives = 1
    for _ in range(100):
        shell.frame(dx=1)
    shell.run.blood = 0
    shell.frame()
    shell.key(pygame.K_SPACE)
    for _ in range(20):
        shell.frame(dy=1)
    assert capsys.readouterr().out == ""
