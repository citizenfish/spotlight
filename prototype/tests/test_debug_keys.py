"""The developer keys must be unreachable by accident.

Issue #16. The spike bound sixteen letters, and `F` reveals the whole room and
everybody in it and holds it there. A tester who presses a key to find out what
it does could silently destroy the thing we are asking them about and would
never know they had -- and the phase-0 review found this the third most likely
thing to bite a stranger, after not knowing how to start it and not knowing what
the keys are.

The fix is not a warning. It is that the keys do nothing: with the flag off the
`Debug` object is never built, so there is nothing for a stray key to reach.

The test that matters is the exhaustive one below: every letter and digit is
pressed, and the run has to come out identical to one where nothing was pressed
at all. A per-key list would have missed whichever key somebody adds next.
"""

import pygame
import pytest

from spotlight.core.screen import Screen

from spikes import spike1

#: Everything a fidgeting tester might press that is not one of the three
#: controls. `T` and `SPACE` are the controls and are tested separately; `ESC`
#: quits from everywhere and is not a game action.
IDLE_KEYS = [getattr(pygame, f"K_{c}") for c in "abcdefghijklmnopqrsuvwxyz"]
IDLE_KEYS += [getattr(pygame, f"K_{d}") for d in "0123456789"]


def snapshot(run):
    """Everything a debug key can reach. If none of this moved, none of them did."""
    return (
        run.opening.held, run.opening.enabled,
        run.glow.enabled, run.roaming.enabled,
        run.roaming.vary, run.roaming.radius, run.roaming.inset,
        run.roaming.step_every, run.roaming.memory, run.roaming.mode,
        run.calls_on, run.field.light_hue, run.field.hue_memory,
        bytes(run.field.charge), dict(run.panel.values),
        (run.player.x, run.player.y), run.blood, run.lives,
        [(c.cx, c.cy, c.state) for c in run.swarm.clegs],
    )


def started(debug=False):
    shell = spike1.Shell(Screen(), debug=debug)
    shell.key(pygame.K_j)          # any key starts it
    for _ in range(40):
        shell.frame(dx=1)
    return shell


def test_without_the_flag_there_is_no_debug_object():
    shell = started()
    assert shell.debug is None


@pytest.mark.parametrize("key", IDLE_KEYS)
def test_without_the_flag_every_other_key_is_inert(key):
    shell = started()
    before = snapshot(shell.run)
    shell.key(key)
    assert snapshot(shell.run) == before, pygame.key.name(key)


def test_f_does_not_reveal_the_room_without_the_flag():
    """Called out on its own because it is the one that ruins a playtest.

    `F` holds the whole room and everybody in it visible. A stranger who found
    it would have solved the game by accident and told us the dark was easy.
    """
    shell = started()
    shell.key(pygame.K_f)
    shell.frame()
    assert shell.run.opening.held is False


def test_the_three_controls_still_work_without_the_flag():
    shell = started()
    shell.key(pygame.K_t)
    shell.frame()
    assert shell.run.cone.enabled is True
    shell.key(pygame.K_SPACE)
    charges = shell.run.spray.charges
    shell.frame()
    assert shell.run.spray.charges == charges - 1
    x = shell.run.player.x
    shell.frame(dx=1)
    assert shell.run.player.x > x


def test_with_the_flag_the_debug_keys_work_exactly_as_before():
    """A representative spread: a hold, a toggle, a cycle and a placeholder."""
    shell = started(debug=True)
    run = shell.run
    assert shell.debug is not None

    shell.key(pygame.K_f)
    assert run.opening.held is True

    glow = run.glow.enabled
    shell.key(pygame.K_g)
    assert run.glow.enabled is not glow

    calls = run.calls_on
    shell.key(pygame.K_y)
    assert run.calls_on is not calls

    speed = run.roaming.step_every
    shell.key(pygame.K_s)
    assert run.roaming.step_every != speed

    lives = run.panel.values["lives"]
    shell.key(pygame.K_3)
    assert run.panel.values["lives"] == lives - 1

    shell.key(pygame.K_c)
    assert not any(run.field.charge)


def test_the_flag_is_read_from_the_command_line():
    assert spike1.DEBUG_FLAG == "--debug"


def test_the_flag_is_not_named_on_any_screen_a_tester_sees():
    """Documented for a developer, not for the person we are testing on."""
    from spikes import screens
    words = " ".join(
        [screens.TITLE, screens.START_PROMPT, screens.AGAIN_PROMPT,
         screens.STOP_PROMPT, *screens.STORY, *screens.WARNING]
        + [f"{k} {v}" for k, v in screens.CONTROLS]
    ).upper()
    assert "DEBUG" not in words
