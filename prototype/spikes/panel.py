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

#: How long a readout flashes when something happens to it: two seconds, which
#: is three blinks of the Spectrum's 32-frame flash cycle. Long enough to catch
#: an eye that was in the dark at the other end of the screen, short enough
#: that it is over before it becomes part of the furniture.
ALERT_FRAMES = 96


def bar_pips(value: int, full: int, pips: int = 6) -> int:
    """How many pips a bar shows for `value` out of `full`.

    **Rounded up**, so the bar reads empty only when the thing itself is empty.
    Truncating instead showed a carried spotlight as flat for its last five
    seconds while it was still burning, which reads as the spotlight failing
    rather than as the spotlight draining -- the difference between a bug and a
    budget.

    The other half of that fault was in the caller, not here: `full` used to be
    the strongest spotlight in the *building*, so a full light in the hand read
    four pips of six. `full` is now the capacity of the thing being measured,
    which is what makes the top of the scale reachable and this function's
    contract worth stating: **`value == full` must read every pip**. See
    `Session.cone_full` (issue #38).
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
    #: TALLY only: a word, drawn to the left of the number with a cell of gap,
    #: so the tally says what it is counting. It replaced a 6-pixel figure of a
    #: person (issue #31): the badge was legible to somebody who already knew
    #: what it was for, which is exactly the reader the playtest does not have.
    label: str | None = None

    @property
    def label_col(self) -> int:
        """Where the label starts: right-aligned against the gap before the
        number, so adding a letter grows the readout leftwards into the gap the
        hearts leave rather than pushing the digits about."""
        return self.col - 1 - len(self.label or "")

    def attr(self, flash: bool = False) -> int:
        return attr_byte(ink=self.ink, paper=BLACK, bright=False, flash=flash)


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
    # Against the bar, not a cell clear of it: they are one readout, and the
    # cell that gap used to cost is the tally's word (issue #31).
    "lit": Region(_TOP, ACTION_LEFT + 12, 1, YELLOW, FLAG, font.LIT),
    "spray": Region(_BOTTOM, ACTION_LEFT + 6, 5, CYAN, COUNT, font.PIP),
    "keys": Region(_BOTTOM, ACTION_LEFT + 12, 1, CYAN, FLAG, font.KEY),
    # Bottom left, in the gap the three hearts leave, and now filling it: the
    # word costs four cells and the tally is three, which is "0/7" through
    # "7/7" and every quota this building has. It used to be five cells wide so
    # that "10/12" fitted, and a two-digit quota is what paid for the word --
    # see `_draw_tally` for what a total too wide to fit does instead of lying.
    "rescued": Region(_BOTTOM, STATUS_LEFT + 15, 3, WHITE, TALLY,
                      label="SAFE"),
}


class Panel:
    """Holds the readout values and repaints only what has changed."""

    def __init__(self) -> None:
        self.values: dict[str, int] = {name: 0 for name in REGIONS}
        #: TALLY denominators, set once when the level is known.
        self.totals: dict[str, int] = {name: 0 for name in REGIONS}
        self._dirty: set[str] = set(REGIONS)
        #: Frames of flashing left on each readout. See `alert`.
        self._alerts: dict[str, int] = {}

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

    # --- alerts ------------------------------------------------------------

    def alert(self, name: str, frames: int = ALERT_FRAMES) -> None:
        """Flash a readout for a while, because something just happened to it.

        The strip is otherwise the quietest thing on the screen -- dim ink,
        repainted only when a number moves -- and that is deliberate. An alert
        is the exception: a readout that changed for a reason the player did
        not ask for and has to notice.

        It is the **attribute flash bit**, which the Spectrum blinks in
        hardware at no cost per frame: two repaints for the whole event, one to
        start it and one to stop it. Nothing here animates.
        """
        if name not in REGIONS:
            raise KeyError(f"no such readout: {name}")
        self._alerts[name] = frames
        self._dirty.add(name)

    def tick(self) -> None:
        """Count the alerts down. One frame, called whether or not it draws."""
        for name in list(self._alerts):
            self._alerts[name] -= 1
            if self._alerts[name] <= 0:
                del self._alerts[name]
                self._dirty.add(name)

    def flashing(self, name: str) -> bool:
        return name in self._alerts

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
        attr = region.attr(flash=name in self._alerts)
        if region.kind == TALLY:
            return self._draw_tally(screen, region, value, name, attr)
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
            screen.set_attr(cx, region.row, attr)
            touched.append((cx, region.row))
        return touched

    def _draw_tally(self, screen: Screen, region, value: int,
                    name: str, attr: int) -> list[tuple[int, int]]:
        """Draw "n/m", with the word that says what is being counted before it.

        Left-aligned and padded, so the slash does not walk about as the
        numbers change -- a readout that moves is one the eye has to find again
        every time it changes, which is the opposite of what it is for.

        **A total too wide for the region loses its denominator rather than its
        digits.** Truncating "10/12" to fit three cells draws "10/", which is
        not a smaller truth, it is a different one. The count alone is honest,
        and the word carries the meaning either way. Nothing in this building
        reaches it -- the quota is seven -- and if a level ever does, the strip
        wants reflowing rather than a readout that quietly rounds.
        """
        touched = []
        text = f"{value}/{self.totals[name]}"
        if len(text) > region.width:
            text = f"{value}"[:region.width]
        text += " " * (region.width - len(text))
        if region.label:
            font.draw_text(screen, region.label_col, region.row, region.label)
            for i in range(len(region.label)):
                cx = region.label_col + i
                screen.set_attr(cx, region.row, attr)
                touched.append((cx, region.row))
        for i, ch in enumerate(text):
            cx = region.col + i
            font.draw_glyph(screen, cx, region.row,
                            font.GLYPHS.get(ch, font.BLANK))
            screen.set_attr(cx, region.row, attr)
            touched.append((cx, region.row))
        return touched




def blank_strip(screen: Screen) -> None:
    """Clear the strip rows to black without disturbing the play area."""
    screen.clear_rows(STRIP_TOP, STRIP_BOTTOM, attr_byte(ink=LABEL_INK, paper=BLACK))
