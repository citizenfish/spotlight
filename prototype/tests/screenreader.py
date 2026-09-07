"""Read the text back off a `core.Screen`.

The title and ending screens are drawn as 8x8 glyphs into a 1-bit bitmap, so
asserting on them means either comparing pixel blobs -- which tells nobody what
broke -- or turning the pixels back into characters. This does the latter, by
inverting the font.

It matters that the tests read the *screen* rather than the string constants.
The acceptance criterion for issue #15 is that the controls are named on screen
and that the tally adds up on screen; a test that only checked the constants
would pass with the drawing code deleted.
"""

from spotlight.core.constants import CELL, SCREEN_W

from spikes import font

#: Glyph bitmap -> the character that draws it. The font has no duplicates.
_CHARS = {rows: ch for ch, rows in font.GLYPHS.items()}


def glyph_at(screen, cx: int, cy: int) -> tuple[int, ...]:
    """The eight bytes of the cell at (cx, cy), most significant bit leftmost."""
    return tuple(
        sum(screen.pixels[(cy * CELL + dy) * SCREEN_W + cx * CELL + dx]
            << (CELL - 1 - dx)
            for dx in range(CELL))
        for dy in range(CELL)
    )


def read(screen, cx: int, cy: int, width: int) -> str:
    """`width` cells of the row at (cx, cy), as text. Unknown glyphs read '?'."""
    return "".join(_CHARS.get(glyph_at(screen, cx + i, cy), "?")
                   for i in range(width))


def read_row(screen, cy: int) -> str:
    """A whole row, stripped. Enough to assert a line of prose is on screen."""
    from spotlight.core.constants import COLS
    return read(screen, 0, cy, COLS).strip()


def rows(screen, top: int = 0, bottom: int = 24) -> list[str]:
    return [read_row(screen, cy) for cy in range(top, bottom)]
