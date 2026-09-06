"""The lighting model: three levels, brightest-wins composition, and the fade.

Light decides a cell's colour and nothing else does. That single rule is what
makes attribute clash impossible -- there is only ever one thing choosing a
cell's ink, so two things can never disagree about it.

Three levels only, because that is what the hardware gives for free: a colour
with its BRIGHT bit set, the same colour without it, and black.

The fade is stored as a **charge** per cell -- one byte, 704 of them for a whole
play area. A lit cell is topped up to full charge every frame it stays lit; an
unlit one loses a point per frame. The displayed level is a threshold on that
charge, so a cell decays LIT -> DIM -> DARK on its own with no timers to manage.

Decay applies to every cell every frame whether or not the player is looking,
which is what makes the fade keep running while you are out of a room.
"""

from spotlight.core.constants import BLACK, COLS
from spotlight.core.screen import attr_byte

from .layout import PLAY_ROWS

# --- levels ----------------------------------------------------------------

DARK, DIM, LIT = 0, 1, 2

#: Frames for a fully lit cell to fade to black. The one tuning knob.
#: 50 frames is one second, so 150 is three.
FADE_FRAMES = 150

#: How long a cell keeps reading LIT after the light has left it -- a fifth of
#: the fade, so bright means *lit right now* and the long dim tail means
#: *remembered*. An even split made a cell look fully lit for a second and a
#: half after the light had moved on, which overstated what the player can see.
LIT_FRAMES = FADE_FRAMES // 5

CHARGE_LIT = FADE_FRAMES
LIT_THRESHOLD = FADE_FRAMES - LIT_FRAMES

#: A dim source tops up to exactly the lit threshold: bright enough to leave a
#: long memory, never bright enough to read as lit.
CHARGE_DIM = LIT_THRESHOLD

assert CHARGE_LIT <= 0xFF, "charge must fit in a byte"

#: Charge a source of each level tops a cell up to.
CHARGE_FOR = (0, CHARGE_DIM, CHARGE_LIT)

#: charge -> displayed level.
_LEVEL_OF = bytes(
    LIT if c > LIT_THRESHOLD else DIM if c > 0 else DARK for c in range(256)
)

#: charge -> charge, one frame later. Decay as a translate table costs nothing.
_DECAY = bytes(max(0, c - 1) for c in range(256))

_CELLS = COLS * PLAY_ROWS


def attr_for(level: int, ink: int) -> int:
    """The attribute a cell wears at a given light level.

    DARK is black ink on black paper -- not merely dim, but invisible.
    """
    if level == DARK:
        return attr_byte(ink=BLACK, paper=BLACK, bright=False)
    return attr_byte(ink=ink, paper=BLACK, bright=level == LIT)


#: (level << 3) | ink -> attribute byte, for per-cell ink maps.
_COMBINED = bytes(
    attr_for(min(i >> 3, LIT), i & 0b111) for i in range(256)
)

_ATTR_TABLES: dict[int, bytes] = {}


def _attr_table(ink: int) -> bytes:
    """level -> attribute byte, as a translate table, cached per ink."""
    table = _ATTR_TABLES.get(ink)
    if table is None:
        table = bytes(attr_for(min(level, LIT), ink) for level in range(256))
        _ATTR_TABLES[ink] = table
    return table


class LightField:
    """Per-cell light for one play area.

    Usage per frame::

        field.begin()
        field.add(cx, cy, LIT)      # each source contributes
        field.commit()              # fold in, then decay
        field.paint(screen, ink)    # write attributes
    """

    __slots__ = ("charge", "_illum", "_touched")

    def __init__(self) -> None:
        self.charge = bytearray(_CELLS)
        self._illum = bytearray(_CELLS)
        self._touched: list[int] = []

    # --- sources -----------------------------------------------------------

    def begin(self) -> None:
        """Start a frame. Clears what sources said last time."""
        for idx in self._touched:
            self._illum[idx] = 0
        self._touched.clear()

    def add(self, cx: int, cy: int, level: int = LIT) -> None:
        """Contribute light to a cell. **Brightest wins** -- levels never sum."""
        if level <= DARK or not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return
        idx = cy * COLS + cx
        if self._illum[idx] == 0:
            self._touched.append(idx)
        if level > self._illum[idx]:
            self._illum[idx] = level

    def commit(self) -> None:
        """Decay everything, then top up whatever a source lit this frame."""
        self.charge[:] = self.charge.translate(_DECAY)
        for idx in self._touched:
            topped = CHARGE_FOR[self._illum[idx]]
            if topped > self.charge[idx]:
                self.charge[idx] = topped

    # --- reading -----------------------------------------------------------

    def level_at(self, cx: int, cy: int) -> int:
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return DARK
        return _LEVEL_OF[self.charge[cy * COLS + cx]]

    def levels(self) -> bytes:
        """The whole field as one level per cell."""
        return self.charge.translate(_LEVEL_OF)

    def paint(self, screen, ink) -> None:
        """Write the play area's attributes. The strip is never touched.

        `ink` is either one colour for the whole area, or a per-cell map of
        them. The split of responsibility matters and is worth stating:

            **light decides brightness; the cell's contents decide hue.**

        Both are single-valued per cell, so there is still exactly one thing
        choosing a cell's attribute and clash remains impossible. It is what
        lets a key be cyan and a door be magenta without breaking the rule.
        """
        levels = self.levels()
        if isinstance(ink, int):
            screen.attrs[0:_CELLS] = levels.translate(_attr_table(ink))
            return
        if len(ink) != _CELLS:
            raise ValueError(f"ink map must be {_CELLS} cells, got {len(ink)}")
        screen.attrs[0:_CELLS] = bytes(
            _COMBINED[(lv << 3) | hue] for lv, hue in zip(levels, ink)
        )
