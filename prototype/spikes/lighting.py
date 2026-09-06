"""The lighting model: three levels, brightest-wins composition, and the fade.

Light decides a cell's brightness and nothing else does. That single rule is
what makes attribute clash impossible -- there is only ever one thing choosing
a cell's attribute, so two things can never disagree about it.

Three levels only, because that is what the hardware gives for free: a colour
with its BRIGHT bit set, the same colour without it, and black.

The fade is stored as a **charge** per cell -- one byte, 704 of them for a whole
play area. A lit cell is topped up every frame it stays lit; an unlit one loses
a point per frame. The displayed level is a threshold on that charge, so a cell
decays LIT -> DIM -> DARK on its own with no timers to manage.

**A source says two things** (issue #12): how bright it reads *while it is
shining*, and how much memory it leaves *after it has gone*. Those were one
number, and one number cannot express them. A cell reads lit only above a high
charge, and charge is also the countdown, so anything bright enough to read as
lit was forced to leave a long memory behind it.

So the displayed level is the fade, **overridden by whatever is shining on the
cell right now**. A source that is present shows its own brightness whatever the
charge says; the charge is left to do only the job it is good at, which is
remembering. The carried cone reads lit and leaves a long bright trail. The
searchlight reads lit while the beam is on a cell and leaves a short dim one, so
the ground behind the beam goes out quickly instead of hanging around lit.

Cost: the override touches only the cells a source lit this frame, which is a
short list, not the whole field.

**A source also says whether it reveals people.** The fade remembers the
building; it must never remember who is standing in it, or a worker seen once
goes on showing in ground you are only recalling. So people and Clegs are drawn
only where a light is on them *this frame*, and only where that light is one
that reveals. Fixed room lighting shows you the room and not its occupants --
see the note in the vault, this is a design change and not merely a fix.

The field also remembers **which light lit each cell**, as a hue. Contents with
a colour of their own keep it; floor and walls, which have none, take the hue of
the light that lit them. That is how the searchlight gets to be yellow.

Decay applies to every cell every frame whether or not the player is looking,
which is what makes the fade keep running while you are out of a room.
"""

from spotlight.core.constants import BLACK, COLS, WHITE
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

#: What a sweeping light leaves behind. Well under the lit threshold, so the
#: ground behind the beam is dim the instant it passes, and short, so it is dark
#: again in well under a second. The one knob for how long the beam's wake
#: lingers -- `M` in the spike harness cycles it.
#:
#: 10 frames, a fifth of a second, settled by playing it. Short enough that the
#: wake is barely a trail at all -- the beam reads as a hole punched through the
#: dark rather than as a light smeared across it.
CHARGE_SWEEP = 10

assert CHARGE_LIT <= 0xFF, "charge must fit in a byte"

#: The hue a cell wears when nothing has chosen one -- floor, walls, and a light
#: that has no colour of its own. Anything else in an ink map is a real colour
#: and the light does not override it.
UNCOLOURED = WHITE

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
        field.add(cx, cy, LIT, CHARGE_LIT, hue)   # each source contributes
        field.commit()                            # fold in, then decay
        field.paint(screen, ink)                  # write attributes

    Two switches, both for judging by eye (issue #12):

    * `light_hue` -- uncoloured cells take the hue of the light that lit them.
    * `hue_memory` -- whether a dim, remembered cell keeps that hue, or reverts
      to uncoloured because memory belongs to the player rather than the light.
    """

    __slots__ = ("charge", "display", "hue", "light_hue", "hue_memory",
                 "_illum", "_memory", "_pending_hue", "_reveal", "_touched")

    def __init__(self, light_hue: bool = False, hue_memory: bool = True) -> None:
        self.charge = bytearray(_CELLS)
        #: The level each cell actually shows: the fade, overridden by any
        #: source shining on it now. Rebuilt by `commit`.
        self.display = bytearray(_CELLS)
        self.hue = bytearray([UNCOLOURED]) * _CELLS
        self.light_hue = light_hue
        self.hue_memory = hue_memory
        self._illum = bytearray(_CELLS)
        self._memory = bytearray(_CELLS)
        self._pending_hue = bytearray(_CELLS)
        #: Cells a revealing light is on this frame. Never remembered.
        self._reveal = bytearray(_CELLS)
        self._touched: list[int] = []

    # --- sources -----------------------------------------------------------

    def begin(self) -> None:
        """Start a frame. Clears what sources said last time."""
        for idx in self._touched:
            self._illum[idx] = 0
            self._memory[idx] = 0
            self._reveal[idx] = 0
        self._touched.clear()

    def add(self, cx: int, cy: int, level: int = LIT,
            memory: int = CHARGE_LIT, hue: int = UNCOLOURED,
            reveals: bool = True) -> None:
        """Contribute light to a cell. **Brightest wins** -- nothing sums.

        `level` is how bright the cell reads while this source is on it.
        `memory` is the charge it tops the cell up to, which is how long the
        cell goes on being remembered once the source has gone. The two are
        independent: a searchlight is as bright as a spotlight and forgotten far
        sooner.

        The hue follows the **memory**, not the brightness, because the hue has
        to outlive the frame. A beam crossing ground you lit yourself does not
        recolour your memory of it.

        `reveals` says whether this light shows people, as opposed to showing
        the room they are in. It is deliberately not remembered.
        """
        if level <= DARK or not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return
        idx = cy * COLS + cx
        if self._illum[idx] == 0:
            self._touched.append(idx)
        if level > self._illum[idx]:
            self._illum[idx] = level
        if memory > self._memory[idx]:
            self._memory[idx] = memory
            self._pending_hue[idx] = hue
        if reveals:
            self._reveal[idx] = 1

    def commit(self) -> None:
        """Decay everything, top up what was lit, then work out what shows.

        A cell that already remembers more than the source can give it -- the
        cone has just left and the searchlight is passing over -- keeps its
        charge and its hue. The longer memory is the truer one.
        """
        self.charge[:] = self.charge.translate(_DECAY)
        for idx in self._touched:
            memory = self._memory[idx]
            if memory > self.charge[idx]:
                self.charge[idx] = memory
                self.hue[idx] = self._pending_hue[idx]

        # What the player sees is the fade, except where a light is shining
        # now. Only the cells a source touched this frame can differ, so this
        # walks the touched list rather than the field.
        self.display[:] = self.charge.translate(_LEVEL_OF)
        for idx in self._touched:
            if self._illum[idx] > self.display[idx]:
                self.display[idx] = self._illum[idx]

    # --- reading -----------------------------------------------------------

    def level_at(self, cx: int, cy: int) -> int:
        """What the cell shows: its memory, or the light on it right now."""
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return DARK
        return self.display[cy * COLS + cx]

    def reveals_at(self, cx: int, cy: int) -> bool:
        """Is a light that shows people on this cell right now?

        Never true from memory, however brightly the cell is remembered. This
        is what stops a worker seen once from staying on screen.
        """
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return False
        return bool(self._reveal[cy * COLS + cx])

    def remembered_at(self, cx: int, cy: int) -> int:
        """What the cell would show with every source switched off."""
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return DARK
        return _LEVEL_OF[self.charge[cy * COLS + cx]]

    def levels(self) -> bytes:
        """The whole field as one level per cell."""
        return bytes(self.display)

    def paint(self, screen, ink) -> None:
        """Write the play area's attributes. The strip is never touched.

        `ink` is either one colour for the whole area, or a per-cell map of
        them. The split of responsibility matters and is worth stating:

            **light decides brightness; the cell's contents decide hue.**

        Both are single-valued per cell, so there is still exactly one thing
        choosing a cell's attribute and clash remains impossible. It is what
        lets a key be cyan and a door be magenta without breaking the rule.

        With `light_hue` set, a cell whose contents are UNCOLOURED takes the hue
        of the light that lit it instead -- still one chooser per cell, it just
        consults the light when the contents have nothing to say.
        """
        levels = self.levels()
        if isinstance(ink, int):
            screen.attrs[0:_CELLS] = levels.translate(_attr_table(ink))
            return
        if len(ink) != _CELLS:
            raise ValueError(f"ink map must be {_CELLS} cells, got {len(ink)}")
        if self.light_hue:
            ink = self._with_light_hue(ink, levels)
        screen.attrs[0:_CELLS] = bytes(
            _COMBINED[(lv << 3) | hue] for lv, hue in zip(levels, ink)
        )

    def _with_light_hue(self, ink, levels) -> bytes:
        """Uncoloured contents take the light's hue; coloured ones keep theirs.

        Without `hue_memory`, only a cell that is lit right now shows the
        light's colour; a dim one falls back to uncoloured.
        """
        out = bytearray(ink)
        for idx in range(_CELLS):
            if ink[idx] != UNCOLOURED:
                continue
            if self.hue_memory or levels[idx] == LIT:
                out[idx] = self.hue[idx]
        return bytes(out)
