"""Guards the pixels+attributes -> RGB path, including surface formats.

Runs headless via SDL's dummy driver so it works in CI and over SSH.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from spotlight.core.constants import CELL, WHITE  # noqa: E402
from spotlight.core.screen import Screen, attr_byte  # noqa: E402
from spotlight.frontend.display import Display  # noqa: E402


@pytest.fixture
def display():
    pygame.init()
    d = Display(scale=2)
    yield d
    pygame.quit()


def test_render_resolves_ink_and_paper(display):
    screen = Screen()
    screen.set_attr(0, 0, attr_byte(ink=WHITE, paper=0, bright=True))
    screen.plot(0, 0, True)   # ink pixel
    screen.plot(1, 0, False)  # paper pixel
    display.render(screen)
    assert display.surface.get_at((0, 0))[:3] == (255, 255, 255)
    assert display.surface.get_at((1, 0))[:3] == (0, 0, 0)


def test_bright_bit_changes_the_shade(display):
    screen = Screen()
    screen.set_attr(0, 0, attr_byte(ink=WHITE, paper=0, bright=False))
    screen.plot(0, 0, True)
    display.render(screen)
    assert display.surface.get_at((0, 0))[:3] == (215, 215, 215)


def test_attribute_applies_to_the_whole_cell(display):
    """Two set pixels in one cell cannot have different colours."""
    screen = Screen()
    screen.set_attr(0, 0, attr_byte(ink=2, paper=0))  # red ink
    screen.plot(0, 0, True)
    screen.plot(CELL - 1, CELL - 1, True)
    display.render(screen)
    a = display.surface.get_at((0, 0))[:3]
    b = display.surface.get_at((CELL - 1, CELL - 1))[:3]
    assert a == b == (215, 0, 0)


def test_scaled_output_reaches_the_window(display):
    """Regression: an 8-bit surface cannot scale straight into the window."""
    screen = Screen()
    screen.set_attr(0, 0, attr_byte(ink=WHITE, paper=0, bright=True))
    screen.fill_cell_pixels(0, 0, True)
    display.render(screen)
    # Inside the frame, which since issue #75 sits inside a border: (1, 1) of
    # the window is margin now, so the probe is offset by the frame's origin.
    ox, oy = display.origin
    assert display.window.get_at((ox + 1, oy + 1))[:3] == (255, 255, 255)


# --- the border (issue #75) -------------------------------------------------
#
# The Spectrum's BORDER: a margin of colour round the 256x192, so the user
# can try whether a dark room inside a frame of colour reads as a room. Host
# code only -- no rule reads it and no snapshot shows it.

from spikes import spike1, spike_snap  # noqa: E402
from spotlight.core.constants import (  # noqa: E402
    BLUE, COLOUR_NAMES, RED, SCREEN_H, SCREEN_W, rgb,
)
from spotlight.frontend import display as display_mod  # noqa: E402


@pytest.fixture
def bordered():
    pygame.init()
    made = []

    def make(**kw):
        d = Display(scale=2, **kw)
        made.append(d)
        return d
    yield make
    pygame.quit()


@pytest.mark.parametrize("name", display_mod.BORDER_NAMES)
def test_border_colour_accepts_every_spectrum_colour_name(name):
    """Fifteen names for fifteen colours, each resolving to the palette's
    own RGB for it -- the same `rgb` the frame's ink and paper come from."""
    bright = name.startswith("bright-")
    base = name.removeprefix("bright-")
    assert display_mod.border_colour(name) == rgb(COLOUR_NAMES.index(base),
                                                  bright)


def test_there_are_fifteen_border_names_and_bright_black_is_not_one():
    """The Spectrum has fifteen colours, not sixteen: bright black is black."""
    assert len(display_mod.BORDER_NAMES) == 15
    assert "bright-black" not in display_mod.BORDER_NAMES


@pytest.mark.parametrize("name", [
    "orange", "bright-black", "", "brightred", "8", "bright red", "grey",
])
def test_border_colour_rejects_anything_else(name):
    with pytest.raises(ValueError, match="border colour"):
        display_mod.border_colour(name)


def test_border_colour_forgives_case():
    """A flag typed at a keyboard is not a table lookup."""
    assert display_mod.border_colour("Bright-Red") == rgb(RED, True)
    assert display_mod.border_colour("BLUE") == rgb(BLUE, False)


def test_the_window_is_the_frame_inside_a_margin_of_four_cells(bordered):
    d = bordered(border="bright-red")
    margin = display_mod.BORDER_CELLS * CELL * d.scale
    assert d.origin == (margin, margin)
    assert d.window.get_size() == (SCREEN_W * d.scale + 2 * margin,
                                   SCREEN_H * d.scale + 2 * margin)


def test_the_margin_is_the_named_colour_and_the_frame_is_inside_it(bordered):
    d = bordered(border="bright-red")
    screen = Screen()
    screen.set_attr(0, 0, attr_byte(ink=WHITE, paper=BLUE, bright=True))
    screen.fill_cell_pixels(0, 0, True)
    d.render(screen)
    w, h = d.window.get_size()
    ox, oy = d.origin
    # All four margins, and the corners.
    for probe in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
                  (ox - 1, oy), (ox, oy - 1), (w - ox, oy), (ox, h - oy)):
        assert d.window.get_at(probe)[:3] == rgb(RED, True), probe
    # And the frame's first pixel is the frame's, not the border's.
    assert d.window.get_at((ox, oy))[:3] == rgb(WHITE, True)
    # The border survives a second frame: it is filled every render.
    d.render(screen)
    assert d.window.get_at((0, 0))[:3] == rgb(RED, True)


def test_the_default_border_is_black(bordered):
    """Today's window with a black margin -- what a Spectrum shows until the
    BORDER is set."""
    d = bordered()
    d.render(Screen())
    assert d.border == (0, 0, 0)
    assert d.window.get_at((0, 0))[:3] == (0, 0, 0)
    assert d.window.get_size() > (SCREEN_W * d.scale, SCREEN_H * d.scale)


def test_a_snapshot_with_a_border_set_is_byte_identical_to_one_without(
        bordered, tmp_path):
    """A snapshot is the Spectrum's 256x192 and nothing else. The window with
    a bright red border and the window with none photograph the same frame to
    the same bytes, and neither picture has a margin in it."""
    screen = Screen()
    screen.set_attr(3, 3, attr_byte(ink=WHITE, paper=BLUE, bright=True))
    screen.fill_cell_pixels(3, 3, True)
    paths = []
    for name in ("bright-red", "black"):
        d = bordered(border=name)
        d.render(screen)
        path = str(tmp_path / f"{name}.png")
        spike_snap.save(screen, path)
        paths.append(path)
        assert pygame.image.load(path).get_size() == (SCREEN_W, SCREEN_H)
    assert open(paths[0], "rb").read() == open(paths[1], "rb").read()


def test_the_border_flag_reaches_the_window_and_only_the_window(monkeypatch):
    """`--border COLOUR` beside `--scale`: the name is read off the command
    line, checked, and handed to `Display`. Nothing under `spikes/` or `core/`
    is told."""
    assert spike1.BORDER_FLAG == "--border"
    assert spike1.border_from([]) == display_mod.DEFAULT_BORDER == "black"
    assert spike1.border_from(["--border", "bright-blue"]) == "bright-blue"
    assert spike1.border_from(["--scale", "2", "--border", "red",
                               "--debug"]) == "red"
    with pytest.raises(ValueError):
        spike1.border_from(["--border", "orange"])


def test_a_bad_border_name_is_one_line_and_no_window(monkeypatch, capsys):
    """A mistyped colour fails before `pygame.init`, with the accepted names
    on stderr, rather than a window with a traceback behind it."""
    opened = []
    monkeypatch.setattr(spike1, "Display",
                        lambda *a, **k: opened.append(k) or (_ for _ in ()).throw(
                            AssertionError("a window was opened")))
    monkeypatch.setattr(spike1.pygame, "init",
                        lambda: (_ for _ in ()).throw(
                            AssertionError("pygame was initialised")))
    assert spike1.main(["--border", "orange"]) == 2
    err = capsys.readouterr().err
    assert "orange" in err and "bright-white" in err
    assert opened == []
