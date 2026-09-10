"""Marking lit floor.

A lit cell with no pixels set is just black -- ink on black paper with no ink
drawn. So without this, light reveals *objects* but never its own shape, and the
player cannot tell how far their spotlight reaches.

Stippling the floor fixes that, and doing it at two densities gives the fade a
contrast step the palette cannot. LIT and DIM differ by only 255 against 215 on
one channel, which is nearly invisible on a moving sprite; four dots against one
is not.

**The dots are not here.** Both stipples are authored in `assets/tiles/floor.txt`
and generated into `bitmaps_gen.py` by `tools/bitmaps.py` (issue #51). They were
the oldest bitmaps in the game and the last art still declared as hex inside
drawing code, which meant the drift test that guards every other bitmap did not
guard them and the port had no `DEFB` for them. The densities themselves did not
move -- that transcription was checked by regenerating the whole gallery and
comparing it byte for byte -- and they are tuned rather than chosen: see the
asset file for what is measured against them.
"""

from spotlight.core.constants import CELL, COLS

from .bitmaps_gen import BITMAPS
from .layout import PLAY_ROWS
from .lighting import DIM, LIT

#: Four dots, evenly spread -- fully lit ground.
STIPPLE_LIT = BITMAPS["FLOOR_LIT"]

#: One dot -- ground you are remembering rather than seeing.
STIPPLE_DIM = BITMAPS["FLOOR_DIM"]

PATTERNS = {LIT: STIPPLE_LIT, DIM: STIPPLE_DIM}


def draw(screen, field, is_solid) -> None:
    """Stipple every lit, non-solid cell according to its light level."""
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            pattern = PATTERNS.get(field.level_at(cx, cy))
            if pattern is None or is_solid(cx, cy):
                continue
            x0, y0 = cx * CELL, cy * CELL
            for dy, bits in enumerate(pattern):
                if not bits:
                    continue
                base = (y0 + dy) * 256 + x0
                for dx in range(CELL):
                    if bits & (0x80 >> dx):
                        screen.pixels[base + dx] = 1
