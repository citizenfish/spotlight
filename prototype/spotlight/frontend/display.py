"""Presents a core.Screen on a real display using Pygame.

This is the only place that knows about pixels-on-a-monitor. The Spectrum owns
its display model in core.screen; this module just scales it up so a modern
screen can show it. Keeping the split means the port replaces this file and
nothing else.
"""

import pygame

from ..core.constants import (
    CELL, COLS, PALETTE, PALETTE_BRIGHT, ROWS, SCREEN_H, SCREEN_W,
)
from ..core.screen import Screen, unpack_attr

#: Palette index = colour + 8 if bright. Matches the translate tables below.
_SURFACE_PALETTE = list(PALETTE) + list(PALETTE_BRIGHT)

#: Frames between flash inversions. Real hardware toggles every 16 frames.
FLASH_PERIOD = 16


def _build_tables() -> tuple[list[bytes], list[bytes]]:
    """Precompute a translate table per attribute byte, for both flash phases.

    Each table maps a pixel value (0 = clear, 1 = set) onto a palette index, so
    a whole cell row converts in one C-level ``bytes.translate`` call.
    """
    normal: list[bytes] = []
    inverted: list[bytes] = []
    for attr in range(256):
        ink, paper, bright, flash = unpack_attr(attr)
        offset = 8 if bright else 0
        ink_idx, paper_idx = ink + offset, paper + offset
        base = bytearray(256)
        base[0], base[1] = paper_idx, ink_idx
        normal.append(bytes(base))
        # During the second half of a flash cycle, ink and paper swap.
        swapped = bytearray(base)
        if flash:
            swapped[0], swapped[1] = ink_idx, paper_idx
        inverted.append(bytes(swapped))
    return normal, inverted


_TABLES_NORMAL, _TABLES_FLASHED = _build_tables()


class Display:
    """Owns the Pygame window and blits Screen contents into it."""

    def __init__(self, scale: int = 3, title: str = "Spotlight") -> None:
        self.scale = scale
        self.window = pygame.display.set_mode(
            (SCREEN_W * scale, SCREEN_H * scale)
        )
        pygame.display.set_caption(title)
        # 8-bit paletted surface at true Spectrum resolution.
        self.surface = pygame.Surface((SCREEN_W, SCREEN_H), depth=8)
        self.surface.set_palette(_SURFACE_PALETTE)
        # transform.scale needs matching formats, and the window is not 8-bit,
        # so the paletted frame is blitted through a scratch surface that
        # already carries the display format.
        self._scratch = pygame.Surface((SCREEN_W, SCREEN_H)).convert(self.window)
        self._buffer = bytearray(SCREEN_W * SCREEN_H)
        self._frame = 0

    def render(self, screen: Screen) -> None:
        """Resolve pixels + attributes into colour, then present the frame."""
        flashing = (self._frame // FLASH_PERIOD) % 2 == 1
        tables = _TABLES_FLASHED if flashing else _TABLES_NORMAL
        pixels, attrs, buf = screen.pixels, screen.attrs, self._buffer

        for cy in range(ROWS):
            for cx in range(COLS):
                table = tables[attrs[cy * COLS + cx]]
                left = cx * CELL
                for row in range(cy * CELL, cy * CELL + CELL):
                    start = row * SCREEN_W + left
                    buf[start:start + CELL] = pixels[
                        start:start + CELL
                    ].translate(table)

        self.surface.get_buffer().write(bytes(buf))
        self._scratch.blit(self.surface, (0, 0))
        pygame.transform.scale(self._scratch, self.window.get_size(), self.window)
        pygame.display.flip()
        self._frame += 1
