"""The two-row status strip.

Left half is what is being done to you; right half is what you can do.

Two rules the issue is explicit about:

* **Dim ink on black, never bright.** On a screen that is mostly black, a
  brightly lit panel would be the most eye-catching thing on it, and the
  player's attention belongs in the dark where the Clegs are.
* **Repaint only what changed.** The strip is static between changes, and
  repainting it every frame would spend time the 48K has not got.
"""

from dataclasses import dataclass

from spotlight.core.constants import BLACK, CYAN, RED, WHITE, YELLOW
from spotlight.core.screen import Screen, attr_byte

from . import font
from .layout import ACTION_LEFT, STATUS_LEFT, STRIP_BOTTOM, STRIP_TOP

#: Labels are the dimmest thing on screen; values carry a little colour.
LABEL_INK = WHITE

#: TALLY draws "n/m" -- a count against a total, which a row of pips cannot do
#: once the total stops being small enough to count at a glance.
BAR, COUNT, FLAG, TALLY = "bar", "count", "flag", "tally"


def bar_pips(value: int, full: int, pips: int = 6) -> int:
    """How many pips a bar shows for `value` out of `full`.

    **Rounded up**, so the bar reads empty only when the thing itself is empty.
    Truncating instead showed a carried spotlight as flat for its last five
    seconds while it was still burning, and showed a full one as a third full
    because the scale is the biggest light in the level rather than the one in
    your hand. Between them that reads as the spotlight failing rather than as
    the spotlight draining, which is the difference between a bug and a budget.
    """
    if value <= 0:
        return 0
    return min(pips, -(-value * pips // max(1, full)))


@dataclass(frozen=True)
class Region:
    """Where a readout lives and how it is drawn. All non-bright."""

    row: int
    col: int
    width: int
    ink: int
    kind: str
    glyph: tuple[int, ...] = font.BAR_FULL
    #: TALLY only: drawn one cell to the left of the number, as its label.
    badge: tuple[int, ...] | None = None

    @property
    def attr(self) -> int:
        return attr_byte(ink=self.ink, paper=BLACK, bright=False)


_TOP, _BOTTOM = STRIP_TOP, STRIP_TOP + 1

#: Static labels: (row, col, text).
LABELS = (
    (_TOP, STATUS_LEFT, "BLOOD"),
    (_BOTTOM, STATUS_LEFT, "LIVES"),
    (_TOP, ACTION_LEFT, "LIGHT"),
    (_BOTTOM, ACTION_LEFT, "SPRAY"),
)

REGIONS: dict[str, Region] = {
    "blood": Region(_TOP, STATUS_LEFT + 6, 8, RED, BAR),
    "lives": Region(_BOTTOM, STATUS_LEFT + 6, 3, RED, COUNT, font.HEART),
    "light": Region(_TOP, ACTION_LEFT + 6, 6, YELLOW, BAR),
    "lit": Region(_TOP, ACTION_LEFT + 13, 1, YELLOW, FLAG, font.LIT),
    "spray": Region(_BOTTOM, ACTION_LEFT + 6, 5, CYAN, COUNT, font.PIP),
    "keys": Region(_BOTTOM, ACTION_LEFT + 12, 1, CYAN, FLAG, font.KEY),
    # Bottom left, in the gap the three hearts leave. A badge and up to five
    # characters, so "10/12" fits without a word of label -- there is no room
    # for one and the little figure says it.
    "rescued": Region(_BOTTOM, STATUS_LEFT + 11, 5, WHITE, TALLY,
                      badge=font.PERSON),
}


class Panel:
    """Holds the readout values and repaints only what has changed."""

    def __init__(self) -> None:
        self.values: dict[str, int] = {name: 0 for name in REGIONS}
        #: TALLY denominators, set once when the level is known.
        self.totals: dict[str, int] = {name: 0 for name in REGIONS}
        self._dirty: set[str] = set(REGIONS)

    def set_total(self, name: str, total: int) -> None:
        """How many there are to find. The denominator of a tally."""
        if self.totals[name] != int(total):
            self.totals[name] = int(total)
            self._dirty.add(name)

    # --- values ------------------------------------------------------------

    def set(self, name: str, value: int) -> bool:
        """Set a readout. Returns True if it actually changed."""
        if name not in REGIONS:
            raise KeyError(f"no such readout: {name}")
        value = int(value)
        region = REGIONS[name]
        if region.kind == FLAG:
            value = 1 if value else 0
        elif region.kind == TALLY:
            value = max(0, min(self.totals[name], value))
        else:
            value = max(0, min(region.width, value))
        if self.values[name] == value:
            return False
        self.values[name] = value
        self._dirty.add(name)
        return True

    @property
    def dirty(self) -> frozenset[str]:
        return frozenset(self._dirty)

    # --- drawing -----------------------------------------------------------

    def draw_labels(self, screen: Screen) -> None:
        """Paint the static labels. Once, not per frame."""
        label_attr = attr_byte(ink=LABEL_INK, paper=BLACK, bright=False)
        for row, col, text in LABELS:
            font.draw_text(screen, col, row, text)
            for i in range(len(text)):
                screen.set_attr(col + i, row, label_attr)

    def draw(self, screen: Screen, force: bool = False) -> list[tuple[int, int]]:
        """Repaint dirty readouts. Returns the cells actually touched."""
        names = set(REGIONS) if force else set(self._dirty)
        touched: list[tuple[int, int]] = []
        for name in sorted(names):
            touched.extend(self._draw_region(screen, name))
        self._dirty.clear()
        return touched

    def _draw_region(self, screen: Screen, name: str) -> list[tuple[int, int]]:
        region = REGIONS[name]
        value = self.values[name]
        if region.kind == TALLY:
            return self._draw_tally(screen, region, value, name)
        touched = []
        for i in range(region.width):
            if region.kind == BAR:
                glyph = font.BAR_FULL if i < value else font.BAR_EMPTY
            elif region.kind == COUNT:
                glyph = region.glyph if i < value else font.BLANK
            else:
                glyph = region.glyph if value else font.BLANK
            cx = region.col + i
            font.draw_glyph(screen, cx, region.row, glyph)
            screen.set_attr(cx, region.row, region.attr)
            touched.append((cx, region.row))
        return touched

    def _draw_tally(self, screen: Screen, region, value: int,
                    name: str) -> list[tuple[int, int]]:
        """Draw "n/m", with the badge in the cell before it.

        Left-aligned and padded, so the slash does not walk about as the
        numbers change -- a readout that moves is one the eye has to find again
        every time it changes, which is the opposite of what it is for.
        """
        touched = []
        text = f"{value}/{self.totals[name]}"[:region.width]
        text += " " * (region.width - len(text))
        if region.badge is not None:
            font.draw_glyph(screen, region.col - 1, region.row, region.badge)
            screen.set_attr(region.col - 1, region.row, region.attr)
            touched.append((region.col - 1, region.row))
        for i, ch in enumerate(text):
            cx = region.col + i
            font.draw_glyph(screen, cx, region.row,
                            font.GLYPHS.get(ch, font.BLANK))
            screen.set_attr(cx, region.row, region.attr)
            touched.append((cx, region.row))
        return touched




def blank_strip(screen: Screen) -> None:
    """Clear the strip rows to black without disturbing the play area."""
    screen.clear_rows(STRIP_TOP, STRIP_BOTTOM, attr_byte(ink=LABEL_INK, paper=BLACK))
