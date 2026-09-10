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

**The field holds no hue.** It used to remember which light lit each cell, so
that a cell with no colour of its own could take the searchlight's yellow --
built in issue #12, switched off, and never adopted. Issue #47 took it away,
because light-supplied hue and per-room colour cannot both be had: a light's
hue only ever reaches cells whose *contents* have none, and after the per-room
palettes every cell has one. The searchlight's yellow would never have fired on
anything. What replaces the *this light is somebody else's* tell is the beam's
fifth-of-a-second wake, which no other source has, and the visible housing a
later slice of this round gives it. That is weaker than the yellow was, and is
recorded as weaker: if a human session says the far room still reads as broken,
the decision reopens rather than being defended.

The saving is real and is the reason it is worth writing down: **one charge
byte per cell and no hue byte**, so the field's per-cell state halves -- 704
bytes here and on the Z80.

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
        field.add(cx, cy, LIT, CHARGE_LIT)        # each source contributes
        field.commit()                            # fold in, then decay
        field.paint(screen, ink)                  # write attributes

    **A light says how bright and never what colour.** The two switches that
    used to be here, and the per-cell hue array they read, were withdrawn by
    issue #47; see the module docstring for why they could not survive
    per-room colour.
    """

    __slots__ = ("charge", "display",
                 "_illum", "_memory", "_reveal", "_touched")

    def __init__(self) -> None:
        self.charge = bytearray(_CELLS)
        #: The level each cell actually shows: the fade, overridden by any
        #: source shining on it now. Rebuilt by `commit`.
        self.display = bytearray(_CELLS)
        self._illum = bytearray(_CELLS)
        self._memory = bytearray(_CELLS)
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
            memory: int = CHARGE_LIT, reveals: bool = True) -> None:
        """Contribute light to a cell. **Brightest wins** -- nothing sums.

        `level` is how bright the cell reads while this source is on it.
        `memory` is the charge it tops the cell up to, which is how long the
        cell goes on being remembered once the source has gone. The two are
        independent: a searchlight is as bright as a spotlight and forgotten far
        sooner.

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
        if reveals and level > self._reveal[idx]:
            self._reveal[idx] = level

    def commit(self) -> None:
        """Decay everything, top up what was lit, then work out what shows.

        A cell that already remembers more than the source can give it -- the
        cone has just left and the searchlight is passing over -- keeps its
        charge. The longer memory is the truer one.
        """
        self.charge[:] = self.charge.translate(_DECAY)
        for idx in self._touched:
            memory = self._memory[idx]
            if memory > self.charge[idx]:
                self.charge[idx] = memory

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

    def prey_at(self, cx: int, cy: int) -> bool:
        """Is somebody standing here **plainly** lit, rather than glimpsed?

        Your own glow shows you a worker at arm's length, and that is enough to
        draw them -- but it is dim, and a person in the dark is ignored by
        Clegs. Prey is somebody a *lit* revealing light is on, which is your
        carried spotlight, a spotlight burning on the floor, or the searchlight
        catching you out in the open.

        Room lights are not on that list, and deliberately: they show the room
        and not who is in it, to Clegs exactly as to the player. One rule.
        """
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return False
        return self._reveal[cy * COLS + cx] >= LIT

    def catch_up(self, frames: int) -> None:
        """Age the whole field by `frames`, in one pass.

        **The fade keeps running while you are out of a room** -- time passes
        everywhere, so ducking out and back leaves your memory warm and coming
        back two minutes later leaves it black. Done naively that means keeping
        and decaying a 704-byte field for every room in the building, which a
        48K machine will not spend on remembered light and a 50Hz frame will not
        spend the cycles on either.

        It dissolves rather than needing solving, and the reason is that the
        fade is short: about three seconds, against roughly five to cross a
        room. **You cannot get two rooms away inside the life of the fade.** So
        the port keeps a field for the room you are in and the one you just
        left, stamps it with the frame you left, and applies the elapsed decay
        in one pass on re-entry. The fade is a monotone countdown, so this is
        exactly equivalent to having decayed it every frame, and it costs
        nothing at all while you are away.

        This building has two rooms, so both fields are resident and this is
        never called with a gap by the game itself -- it is called with zero
        every time the player crosses. It is built and tested now because the
        equivalence is the whole of the argument, and a rule that is only true
        in a comment is a rule nobody can check. It stops being free if the
        player ever moves faster than a walk, or if rooms ever get smaller.
        """
        if frames <= 0:
            return
        if frames >= CHARGE_LIT:
            self.charge[:] = bytes(len(self.charge))
        else:
            table = bytes(max(0, c - frames) for c in range(256))
            self.charge[:] = self.charge.translate(table)
        self.display[:] = self.charge.translate(_LEVEL_OF)
        # Nothing is shining on the room you were not in, so nothing reveals
        # anybody in it either. Clearing this is what stops a worker who was
        # standing in your cone as you walked out being prey for ever.
        for idx in self._touched:
            self._illum[idx] = 0
            self._memory[idx] = 0
            self._reveal[idx] = 0
        self._touched.clear()

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
        lets a room's floor be yellow and a door be magenta without breaking
        the rule -- and it is why per-room colour costs nothing per frame: the
        ink map is the room's own, and the translate table does the rest.

        The light itself never supplies a hue. It did until issue #47, for
        cells whose contents had none; per-room colour leaves no such cell.
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


# --- pricing what gets redrawn (issue #46) ---------------------------------

#: The metrics `Repaint.stats` produces, in the order they read best. Named
#: here so that a report can lay out the columns without a run to ask, and so
#: that a run with the counter switched off still has the keys.
REPAINT_METRICS = (
    "cells_changed_per_100f",
    "cells_changed_p95",
    "cells_changed_p99",
    "cells_changed_max",
    "frames_unchanged_percent",
    "wall_cells_changed_per_100f",
    "wall_cells_changed_p95",
    "wall_cells_changed_p99",
    "wall_cells_changed_max",
)


class Repaint:
    """How many cells change light level from one frame to the next.

    **Instrumentation and nothing else.** It changes no rule and no constant,
    it is off in the game, and a port carries none of it. It exists because the
    look-and-feel round changes what is drawn in eight slices and each one has
    to be priced against the port model before the next starts -- and the
    number that prices them is how many cells change level in a frame, because
    that is the class of work a dirty-cell port actually does. Before this the
    only way to get the figure was to difference frames from outside the game,
    which cost about four minutes of Python a suite and produced a number that
    could not be compared slice to slice without re-running everything.

    **It counts against what was last on screen, not against what a field last
    held.** One `LightField` per room and one screen: walking through a doorway
    replaces every cell of the picture, so the cells the port would have to
    repaint on that frame are the ones where the new room's levels differ from
    the old room's. A per-field counter cannot see that frame at all -- it
    would price room A's quiet decay while room B is being looked at -- so the
    previous levels are kept here, beside the screen, rather than in the field.
    Issue #46 suggested the field; this is the one place the implementation
    departs from it, and the crossing frames are the reason.

    Two counts per frame, because they price different work:

    * **cells whose level changed**, which is the dirty-cell list; and
    * **how many of those are solid**, which prices wall texture, since a
      wall's pixels only need redrawing when its tile variant changes.

    Kept as a histogram -- one counter per possible count -- so that mean, p95,
    p99 and max come out of integer arithmetic with nothing sorted and nothing
    stored per frame. That is what a Z80 would do if it ever wanted this. It
    would use 256 counters and clamp; here there is one per possible count,
    because clamping at 255 would throw away exactly the whole-field frames the
    number was wanted for -- the opening flash lights all 704 cells to the same
    charge, so they cross both fade thresholds in lockstep and three frames per
    room entry change everything at once.

    The mean is reported per hundred frames rather than per frame, because the
    metrics block is all-integer by design and 3.06 cells a frame is a number
    with two decimal places in it. `blood_per_worker` keeps tenths for the same
    reason.

    **What it does not count**, checked rather than assumed: a cell's attribute
    can also change without its light level moving, because the contents choose
    the hue -- a shout appearing over a doorway, the exit sign, a key coming
    into view. Differencing the drawn attributes of a whole listener run against
    this counter, the two agreed on 4,712 frames of 4,725 and the thirteen that
    differed were those, at two to four cells each. So the light term is very
    nearly the whole bill, and the hue term is small enough to leave out of a
    number that is about light. If a slice ever makes contents change hue often
    -- animation would -- that stops being true and this needs saying again.
    """

    __slots__ = ("frames", "total", "wall_total", "_hist", "_wall_hist",
                 "_shown")

    def __init__(self) -> None:
        self.frames = 0
        self.total = 0
        self.wall_total = 0
        self._hist = [0] * (_CELLS + 1)
        self._wall_hist = [0] * (_CELLS + 1)
        #: What the screen is showing. Starts all-dark because that is what a
        #: display holds before the first frame is drawn -- which is why the
        #: opening flash reads as 704 changed cells rather than as nothing.
        self._shown = bytes(_CELLS)

    def frame(self, levels, solid) -> int:
        """Count one frame's changes. Returns how many cells changed level.

        `levels` is the field being shown, `solid` a byte per cell that is 1
        where a wall is. Three frames in four change nothing at all -- the
        player moves a pixel a frame, so change arrives in bursts when
        something crosses a cell boundary -- so the whole-buffer comparison
        first is not an optimisation for its own sake, it is the common case.
        """
        changed = wall = 0
        if levels != self._shown:
            shown = self._shown
            for idx in range(_CELLS):
                if levels[idx] != shown[idx]:
                    changed += 1
                    wall += solid[idx]
            # A copy, because `commit` rewrites `display` in place.
            self._shown = bytes(levels)
        self.frames += 1
        self.total += changed
        self.wall_total += wall
        self._hist[changed] += 1
        self._wall_hist[wall] += 1
        return changed

    def crossed(self) -> None:
        """Forget what was on screen, as if the display had been cleared.

        Not used by the session -- a crossing is a change like any other and
        counting it as one is the point -- but a caller that blanks the screen
        for its own reasons has to be able to say so, or the next frame is
        priced against a picture nobody can see.
        """
        self._shown = bytes(_CELLS)

    def stats(self) -> dict:
        """Mean, p95, p99 and max, for both counts. All integers.

        `None` throughout for a run with no frames in it, which is an answer
        rather than a row of zeroes claiming nothing ever changed.
        """
        if not self.frames:
            return {key: None for key in REPAINT_METRICS}
        return {
            "cells_changed_per_100f": 100 * self.total // self.frames,
            "cells_changed_p95": self._percentile(self._hist, 95),
            "cells_changed_p99": self._percentile(self._hist, 99),
            "cells_changed_max": self._largest(self._hist),
            "frames_unchanged_percent": 100 * self._hist[0] // self.frames,
            "wall_cells_changed_per_100f":
                100 * self.wall_total // self.frames,
            "wall_cells_changed_p95": self._percentile(self._wall_hist, 95),
            "wall_cells_changed_p99": self._percentile(self._wall_hist, 99),
            "wall_cells_changed_max": self._largest(self._wall_hist),
        }

    def _percentile(self, hist, per_cent: int) -> int:
        """Nearest rank, from the histogram: the smallest count that at least
        `per_cent` of frames came in at or under.

        Integer ranking on purpose. Interpolating between two counts would
        invent a cell that never changed, and the tail is what this number is
        read for.
        """
        rank = (per_cent * self.frames + 99) // 100
        seen = 0
        for count, frames in enumerate(hist):
            seen += frames
            if seen >= rank:
                return count
        return _CELLS

    @staticmethod
    def _largest(hist) -> int:
        for count in range(len(hist) - 1, -1, -1):
            if hist[count]:
                return count
        return 0
