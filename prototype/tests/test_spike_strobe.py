"""A level opens on a strobe (issue #94): three one-frame flashes of the
whole room, five dark frames between, the game held, nothing remembered."""

from spikes import lighting, session as S
from spikes.session import Intent, Session
from spotlight.core.constants import COLS
from spikes.layout import PLAY_ROWS


def _lit(run) -> int:
    return sum(1 for cy in range(PLAY_ROWS) for cx in range(COLS)
               if run.field.level_at(cx, cy) == lighting.LIT)


def _shown(run) -> int:
    return sum(1 for cy in range(PLAY_ROWS) for cx in range(COLS)
               if run.field.level_at(cx, cy) != lighting.DARK)


def test_the_opening_is_black_then_three_flashes_then_black():
    """Two seconds completely black -- not a cell lit, not even the sign --
    the three one-frame flashes five dark frames apart, two seconds more of
    black, and only then play (issues #94, #95)."""
    assert (S.STROBE_ON, S.STROBE_OFF, S.STROBE_FLASHES) == (1, 5, 3)
    assert S.STROBE_FRAMES == 18 and S.OPENING_BLACK == 100
    assert S.OPENING_FRAMES == 218
    run = Session(seed=1, strobe=True)
    shown, cracks = [], 0
    for _ in range(S.OPENING_FRAMES):
        run.step()
        shown.append(_shown(run))
        cracks += sum(1 for name, _c in run.moments.raised if name == "strobe")
    flashes = [i for i, n in enumerate(shown) if n]
    assert flashes == [100, 106, 112], flashes
    assert all(shown[i] == COLS * PLAY_ROWS for i in flashes), "a flash is the whole room"
    assert cracks == 3, "the crack did not sound once per flash"
    assert run.frame == 0


def test_the_game_is_held_and_the_log_is_empty_through_the_strobe():
    run = Session(seed=1, strobe=True)
    start = (run.player.x, run.player.y)
    flies = [(c.cx, c.cy) for c in run.place.swarm.clegs]
    blood = [w.blood for w in run.rescue.workers]
    for _ in range(S.OPENING_FRAMES):
        events = run.step(Intent(dx=1, dy=1, spray=True))
        assert events == [] and run.frame == 0
    assert (run.player.x, run.player.y) == start, "the player moved"
    assert [(c.cx, c.cy) for c in run.place.swarm.clegs] == flies, "a fly moved"
    assert [w.blood for w in run.rescue.workers] == blood, "somebody bled"
    assert not run.log and run.spray.charges == 5
    run.step(Intent(dx=1))
    assert run.frame == 1 and run.player.x == start[0] + 1, "play did not begin"


def test_a_flash_shows_everybody_and_leaves_nothing_behind():
    run = Session(seed=1, strobe=True)
    run.place.roaming.enabled = False        # the beam makes prey; not its test
    for _ in range(S.OPENING_BLACK + 1):
        run.step()                                   # through the black to the first flash
    here = [w for w in run.rescue.workers if w.room == run.here]
    for worker in here:
        assert all(run.field.reveals_at(*c) for c in worker.cells())
    assert not run._lit_people(run.place), "the flash made prey"
    run.step()                                       # dark
    assert _lit(run) < COLS * PLAY_ROWS // 4
    dark_again = [c for w in here for c in w.cells()
                  if run.field.level_at(*c) == lighting.DARK]
    assert dark_again, "the flash left a memory of the people's cells"
    assert run.place.strobe.memory == 0


def test_the_strobe_ends_off_and_never_comes_back():
    run = Session(seed=1, strobe=True)
    for _ in range(S.OPENING_FRAMES + 200):
        run.step()
    assert not run.place.strobe.enabled and run.strobe == 0
    assert _lit(run) < COLS * PLAY_ROWS // 4


def test_a_session_driven_directly_does_not_strobe_and_the_shell_does():
    """The strobe is the window's opening: the shell and the demo ask for it,
    and a session built by the driver, the gallery or a test starts at frame
    one as it always did."""
    import pygame
    from spikes import spike1
    from spotlight.core.screen import Screen
    run = Session(seed=1)
    run.step()
    assert run.frame == 1 and run.strobe == 0
    shell = spike1.Shell(Screen())
    shell.key(pygame.K_s)
    assert shell.run.strobe == S.OPENING_FRAMES


def test_a_held_strobe_leaves_the_game_exactly_as_frame_nought():
    """A bot not asked during the hold makes the same run, event for event,
    with the strobe and without: the frame counter, the charge, the display,
    the shout lists and the swarm are all where frame nought left them."""
    from spikes import bots
    logs = []
    for strobe in (False, True):
        run = Session(seed=0xBEEF, strobe=strobe)
        bot = bots.make("listener", seed=0xBEEF)
        while run.over is None and run.frame < 1500:
            run.step(bot.intent(run) if not run.strobe else Intent())
        logs.append([(e.frame, e.kind, e.who, e.count) for e in run.log])
    assert logs[0] == logs[1]


# --- the flies stay out of it, and the logo sits on the black (issue #97) ------

def _play_area_ink(screen) -> set:
    from spotlight.core.constants import CELL, SCREEN_W
    return {(x, y) for y in range(PLAY_ROWS * CELL) for x in range(SCREEN_W)
            if screen.pixels[y * SCREEN_W + x]}


def test_a_flash_shows_the_people_and_not_the_flies(monkeypatch):
    from spikes import sprites
    from spotlight.core.screen import Screen
    run = Session(seed=1, strobe=True)
    for _ in range(S.OPENING_BLACK + 1):
        run.step()                                   # the first flash
    drawn = []
    real = sprites.draw
    monkeypatch.setattr(sprites, "draw",
                        lambda screen, sprite, *a, **k: drawn.append(sprite) or real(screen, sprite, *a, **k))
    run.draw(Screen())
    assert not any(s in sprites.CLEG_FRAMES for s in drawn), "a fly was drawn in the flash"
    assert any(s in sprites.WORKER_FRAMES for s in drawn), "no worker was drawn in the flash"


def test_the_black_is_the_logo_and_the_strip_and_nothing_else():
    from spikes import screens
    from spotlight.core.screen import Screen
    run = Session(seed=1, strobe=True)
    run.step()                                       # black, frame one of the opening
    frame = Screen()
    run.draw(frame)
    logo = Screen()
    screens.draw_logo(logo, top=S.OPENING_LOGO_TOP)
    assert _play_area_ink(frame) == _play_area_ink(logo), \
        "the black has something on it besides the logo"
    assert _play_area_ink(logo), "the logo drew nothing"
    assert S.OPENING_LOGO_TOP == 10, "two rows, centred in twenty-two"
    # After the opening the logo is gone and the room is drawn.
    for _ in range(S.OPENING_FRAMES):
        run.step()
    after = Screen()
    run.draw(after)
    assert _play_area_ink(after) != _play_area_ink(logo)


# --- the strip is black through the opening (issue #105) -------------------------

def test_the_strip_is_black_on_every_held_frame_and_painted_with_the_first_played():
    from spikes.layout import STRIP_TOP, STRIP_BOTTOM
    from spotlight.core.screen import Screen, unpack_attr
    run = Session(seed=1, strobe=True)
    for i in range(S.OPENING_FRAMES):
        run.step()
        if i % 20 and i not in (100, 106, 112):
            continue
        screen = Screen()
        run.draw(screen)
        for cy in range(STRIP_TOP, STRIP_BOTTOM):
            for cx in range(COLS):
                assert unpack_attr(screen.get_attr(cx, cy))[:2] == (0, 0), (i, cx, cy)
    run.step()
    assert run.frame == 1
    screen = Screen()
    run.draw(screen)
    from screenreader import rows
    text = rows(screen)
    assert "BLOOD" in text[STRIP_TOP] and "LIVES" in text[STRIP_TOP + 1]
    assert any(unpack_attr(screen.get_attr(cx, STRIP_TOP))[0] != 0 for cx in range(COLS))
