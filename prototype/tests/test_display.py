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
    assert display.window.get_at((1, 1))[:3] == (255, 255, 255)
