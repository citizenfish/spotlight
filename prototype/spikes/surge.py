"""The mains surge: the whole building, for a second, once a minute.

Issue #53, from *Art Direction* section 9 and *Light and Darkness#The mains*.
**Designed long ago and never built**, and it is the beat the whole
memorisation premise rests on: the building's power is failing rather than
dead, and when it surges you are handed the plan -- rooms, doors, keys, the
people, the nests, the flies -- and then it is taken away again. What you have
afterwards is whatever you managed to hold in your head, which is the reason
this is a game about attention rather than reflexes.

Two things live here and nothing else: **when it fires**, and **what it
draws**. Both are portable -- integers, cell counts and byte writes, no pygame
and no floats -- because both have to survive the port.

**A surge is not a light.** It adds no charge to any field, it is in no room's
list of sources, and it lures nothing. Two sentences in the design read like a
contradiction and are not: the plan *shows* Clegs, as single red pixels, which
is half of what makes this a memorisation beat rather than a floor plan; and
the surge *attracts* none, because a fly climbs toward light and a light that
is everywhere offers nothing to climb toward. This module writes pixels and
attributes and stops. If a surge ever moved the repaint counter -- which counts
cells whose *light level* changed -- it has been implemented as a light and it
is wrong.

**The freeze is the shell's, and it is the mechanism slice D already built.**
`Schedule.take` hands the host a number of frames in which it must not step the
game, exactly as `moments.Moments.take_pause` does. The session is never told.
If the session held instead, its frame counter would advance through the freeze,
every event after it would be stamped differently, and every run log in the
project would move -- which is the guarantee this whole round is measured by. A
plan you have to read while being bitten is not a memorisation beat, so the
freeze is real; it simply is not the session's.

**What it costs, said out loud rather than discovered later.** A surge changes
no light level, so the existing repaint figures do not move and must not. What
it does cost is **two whole-screen repaints the counter cannot see**: one on the
frame the plan appears, one on the frame the play area comes back. In the port
model those are the same 704-cell frames as a room entry, at roughly 146
T-states a cell -- about 102,620 T-states against 52,416 spendable, 196% before
an entity is drawn. That is the pre-existing overrun the tile slice already
recorded, arriving by another door, twice every forty to seventy seconds. It is
not this slice's to fix, the dirty-cell retrofit is owed elsewhere, and this
slice must not become the reason it is skipped. **Every other frame of a surge
costs nothing at all** -- forty-nine of the fifty, at the default -- because
nothing on screen changes while the plan is held.
"""

from spotlight.core.constants import (
    BLACK, CELL, COLS, GREEN, MAGENTA, RED, SCREEN_W, WHITE,
)
from spotlight.core.screen import attr_byte

from .building import DOOR, KEY, WALL
from .layout import PLAY_BOTTOM, PLAY_ROWS, PLAY_TOP
from .sources import xorshift16

# --- when it fires ----------------------------------------------------------

#: How long the plan stays on screen, in frames -- counting the frame it is
#: drawn on, which is a played frame, and then the frames the host holds for.
#:
#: **Provisional, and it is the user's number to settle at a keyboard.**
#: Nobody else moves it. It is one named constant with nothing derived from it,
#: and `spike1 --surge-frames N` overrides it, so a sitting can try five values
#: without five rebuilds. When the user settles it the value is recorded in the
#: design notes and this line changes; until then it is a default with a reason
#: rather than an answer.
#:
#: The reason, because a default with no reasoning is the one that never gets
#: revisited:
#:
#: * **50 frames is one second, four times the quarter-second the prototype
#:   once ran**, when a player reported that people were "not reliably showing"
#:   during a surge. The reveal was working; the surge was too short to take
#:   anything in.
#: * **48 frames is a hardware floor.** The player's mark and the nests are
#:   drawn with the FLASH bit, which the ULA blinks sixteen frames on and
#:   sixteen off, free-running and synchronised with nothing. A window shorter
#:   than 48 frames can straddle two off-phases and show the player's mark as
#:   two part-blinks and never once whole -- and finding yourself on the plan is
#:   the precondition for using it. 50 is that floor with two frames to spare.
#: * The tension being settled is real: too short and the surge gives nothing;
#:   too long and it stops being a glimpse and becomes a map, which undoes the
#:   premise.
SURGE_FRAMES = 50

#: The earliest a run's first surge may come. A player should be able to meet
#: the beat inside the first minute -- it is the game's rhythm and not a late
#: reward -- but not before they have found out what the dark is for.
FIRST_MIN = 1500

#: The floor of the gap between surges, and how many values above it there are.
#: Forty to seventy seconds at 50Hz, inclusive at both ends.
#:
#: **Drawn from the run's seed rather than fixed**, so that a sweep of runs
#: samples the distribution instead of watching the same surge over and over --
#: the lesson the searchlight's entry station taught the hard way, when every
#: run in a sweep began with the beam in the same corner.
#:
#: `state % INTERVAL_SPREAD` is a 16-bit divide, which is not cheap on a Z80;
#: it happens once a minute, which is why it does not matter. The first surge
#: uses the same spread from a lower floor, so there is one spread constant and
#: two floors rather than two distributions.
INTERVAL_MIN = 2000
INTERVAL_SPREAD = 1501


class Schedule:
    """When the next surge is due, and how long the host owes when it fires.

    One per run. **It holds no game state and decides nothing about the game**:
    it is told the frame number and whether the player is mid-threshold, and it
    answers with frames the *host* must not step. Nothing in a run reads a
    surge back, so a surge cannot change a run -- which is what makes the event
    logs byte-identical across this slice.

    The seed is its **own link at the end of the run's xorshift chain**, after
    the Cleg, beam and brood seeds. That placement is the whole of the
    requirement: derive it anywhere earlier and every seed downstream shifts,
    every fly in the building behaves differently, and every event log in the
    project moves.

    Worth knowing and accepted: because a single xorshift chain is one cycle,
    the surge's stream is the brood's stream one link along, so the nth interval
    and the nth hatchling are drawn from the same integer. They are consumed for
    entirely unrelated things -- an interval in frames against a fly's
    temperament -- and the alternative is a salt, which buys independence at the
    cost of being able to state where the seed comes from in one sentence. If a
    surge is ever seen to correlate with a hatchling, this is the paragraph that
    explains it and the salt is the fix.
    """

    __slots__ = ("state", "frames", "due", "count", "owed", "deferred")

    def __init__(self, seed: int, frames: int = SURGE_FRAMES) -> None:
        if frames < 1:
            # A surge of no frames is a surge nobody sees, and it would make
            # `take` -- which returns 0 for "nothing owed" -- unable to say
            # that one had happened. `--surge-frames 0` is therefore a mistake
            # rather than a setting.
            raise ValueError(f"a surge lasts at least one frame, not {frames}")
        self.state = seed or 1
        #: How long the plan stays up. Passed in so that `--surge-frames` can
        #: override it without a second constant existing anywhere.
        self.frames = frames
        self.count = 0
        #: Frames the host owes, taken once by whoever agrees to hold.
        self.owed = 0
        #: How many frames a due surge has been held back for by a crossing.
        #: Instrumentation: a deferral that never ended would be a surge that
        #: was silently dropped, and this is how that would be seen.
        self.deferred = 0
        self.due = FIRST_MIN + self._roll()

    def _roll(self) -> int:
        """One draw from the interval spread, advancing our own stream."""
        self.state = xorshift16(self.state)
        return self.state % INTERVAL_SPREAD

    def update(self, frame: int, mid_threshold: bool = False) -> bool:
        """One frame of the schedule. True on the frame a surge fires.

        **A surge that comes due mid-threshold waits rather than being
        dropped.** A screen that changes twice in two frames is a glitch and
        not a beat: the player who is halfway through a doorway is about to be
        shown a different room, and dropping the plan on top of that would read
        as the display breaking. So the due frame stands and the surge fires on
        the first frame the player is wholly in one room -- at a pixel a frame
        that is at most eight frames later, and it is never lost.

        The next surge is scheduled from the frame this one **fires**, not from
        the frame it was due, so a deferral does not silently shorten the gap
        that follows it.
        """
        if frame < self.due:
            return False
        if mid_threshold:
            self.deferred += 1
            return False
        self.count += 1
        self.owed = self.frames
        self.due = frame + INTERVAL_MIN + self._roll()
        return True

    def take(self) -> int:
        """How many frames the host owes, taken once. Zero for everybody else.

        Called by the host loop and by nothing inside the game, exactly like
        `Moments.take_pause`. Whoever takes it is agreeing not to step the
        session for that many frames. The headless driver takes it only to know
        that a surge happened -- it draws the plan and steps straight on, since
        its frames are frames of simulation and a hold there would mean the same
        `--frames` bought fewer of them and every run would end somewhere new.
        """
        owed, self.owed = self.owed, 0
        return owed


# --- what it draws ----------------------------------------------------------

#: Pixels per map cell on the plan.
#:
#: A room is 32x22 cells, so a plan is 128x88 pixels -- sixteen attribute cells
#: by eleven -- and two rooms fill the screen's width exactly. One pixel per
#: cell would put a whole room in four attribute cells and colour would mean
#: nothing; eight would fit one room. **Four is the only scale at which the
#: building fits and colour still works.**
SCALE = 4

#: The play-area row the plan starts on, and how many rows it takes.
#:
#: Rows 6 to 16 inclusive. The rows above and below it are cleared and **left
#: empty on purpose**: the design parks score and time remaining there, both are
#: unbuilt mechanics, and building them here would be the gameplay change this
#: round forbids. Rescued-of-quota is already on the status strip permanently,
#: the strip stays visible underneath a surge, and there is no clock in this
#: game at all -- so there is nothing to leave out and nothing to invent. The
#: space is reserved rather than free.
PLAN_TOP = 6
PLAN_ROWS = (PLAY_ROWS * SCALE) // CELL          # 11

#: Attribute columns one room occupies. Two rooms, sixteen each, thirty-two.
ROOM_COLS = (COLS * SCALE) // CELL               # 16

#: How many rooms fit across the screen at this scale. **A third room is a
#: design question this slice does not answer** -- the playtest building is two
#: and the plan is drawn for the building it has. `draw` refuses rather than
#: quietly showing half a building, because a plan that silently omits a room is
#: worse than no plan: the player would memorise a building that is not there.
ROOMS_ACROSS = COLS // ROOM_COLS                 # 2

#: Black on black: the rows the plan does not use, and every cell of it with
#: nothing in it. A plan cell holding only floor draws nothing and keeps black
#: paper, which is what makes the walls read as a plan rather than as a grid.
BLANK = attr_byte(ink=BLACK, paper=BLACK)

# What is on the plan, in the order that decides a shared attribute cell.
# **Four map cells share one 8x8 attribute cell, and the clash rule is kept by
# priority rather than by compromise**: the cell takes the hue of the most
# important thing in it. There is still exactly one chooser per cell, so clash
# is still impossible, and it degrades in the direction you want -- a worker
# standing against a wall turns that patch green, which is the thing you needed
# to know.
P_PLAYER, P_WORKER, P_NEST, P_CLEG, P_KEY, P_DOOR, P_WALL, P_NOTHING = range(8)

#: What each of them is drawn in. A key takes the hue of the door it opens,
#: which is why it is magenta here and not a colour of its own.
HUE = (WHITE, GREEN, RED, RED, MAGENTA, MAGENTA, WHITE, BLACK)

#: What flashes: the player, so you find yourself first, and the nests.
#:
#: The FLASH bit is per attribute cell like the ink, so **a wall sharing a cell
#: with the player blinks along with him.** That is accepted rather than fixed:
#: finding yourself on the plan is the precondition for using it, and one
#: blinking 8x8 patch is a small price for the only mark you have to find before
#: the plan is any use at all.
FLASHES = (True, False, True, False, False, False, False, False)

#: How big a mark each thing gets, in pixels. A wall or a door is the whole 4x4
#: cell; a person, a nest or a key is a 2x2 mark inside it; a Cleg is one pixel.
#: Anything smaller than the cell is centred in it, so a mark sits where the
#: thing is rather than in the corner of where the thing is.
SIZE = (2, 2, 2, 1, 2, SCALE, SCALE, 0)

#: A row of set pixels, long enough for the widest thing drawn. The prototype
#: keeps one byte per pixel; on the Z80 a 4x4 block at a four-pixel boundary is
#: a nibble mask OR'd into a byte, which is where this becomes cheap.
_ON = b"\x01" * SCALE


def cells_written() -> int:
    """Attribute cells a surge frame writes: the whole play area.

    Named as a function of the layout rather than as a literal, because it is
    the number the port model is priced against and it must move if the play
    area ever does. The plan clears every play row and repaints it, and the
    frame the play area comes back does the same, so a surge costs two of these
    and the light-level repaint counter can see neither.
    """
    return COLS * PLAY_ROWS


def origin(room: int, cx: int, cy: int) -> tuple[int, int]:
    """Where a map cell's block starts on the plan, in pixels."""
    return (room * ROOM_COLS * CELL + cx * SCALE,
            PLAN_TOP * CELL + cy * SCALE)


def attr_cell(room: int, cx: int, cy: int) -> tuple[int, int]:
    """Which attribute cell a map cell shares. Two by two of them per cell."""
    return (room * ROOM_COLS + cx // 2, PLAN_TOP + cy // 2)


def _fill(screen, px: int, py: int, size: int) -> None:
    """A filled square of `size` pixels at (px, py). No bounds checking: the
    plan's geometry is fixed and every block of it is on screen by
    construction, which `test_spike_surge` asserts rather than assumes."""
    for row in range(py, py + size):
        start = row * SCREEN_W + px
        screen.pixels[start:start + size] = _ON[:size]


def _claim(best, room: int, cx: int, cy: int, kind: int) -> None:
    """Give an attribute cell to `kind` if nothing more important holds it."""
    acx, acy = attr_cell(room, cx, cy)
    index = (acy - PLAN_TOP) * COLS + acx
    if kind < best[index]:
        best[index] = kind


def draw(screen, rooms, marks=()) -> int:
    """The building plan, over the play area. Returns the cells written.

    `rooms` is the building's rooms in the building's own room order, and
    `marks` is everything that is not the building itself, as
    `(room, cx, cy, kind)` -- the people, the player, the flies, the nests. The
    plan is drawn from level data and a list of positions and reads no light
    field, which is the whole of the claim that a surge is not a light.

    **The status strip is not touched**, which is how it stays exactly where it
    is: it is not part of the surge, it is already on screen from the frame
    before, and rescued-of-quota has been on it permanently since the strip
    existed.
    """
    if len(rooms) > ROOMS_ACROSS:
        raise ValueError(
            f"the plan fits {ROOMS_ACROSS} rooms across and this building has "
            f"{len(rooms)}; a wider building needs a scale decision, not a "
            f"silently cropped plan")
    screen.clear_rows(PLAY_TOP, PLAY_BOTTOM, BLANK)
    best = bytearray([P_NOTHING]) * (COLS * PLAN_ROWS)

    for index, room in enumerate(rooms):
        for cy in range(PLAY_ROWS):
            row = room.rows[cy]
            for cx in range(COLS):
                char = row[cx]
                # Floor draws nothing, and neither does a doorway character: a
                # `d` is a hole in a wall, and a hole in the white line is
                # exactly how a plan says there is a way through. The gaps are
                # the doors you can walk, and the magenta blocks are the way
                # out of the building.
                if char == WALL:
                    kind = P_WALL
                elif char == DOOR:
                    kind = P_DOOR
                elif char == KEY:
                    # Keys are authored as map characters today and there are
                    # none in the playtest building. When they become
                    # placements -- *building.py* says they will be, because a
                    # key is put in a room rather than made of anything -- this
                    # branch goes and they arrive as marks like everybody else.
                    kind = P_KEY
                else:
                    continue
                _fill(screen, *origin(index, cx, cy), SIZE[kind])
                _claim(best, index, cx, cy, kind)

    for room, cx, cy, kind in marks:
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS) \
                or not 0 <= room < len(rooms):
            # A fly can stand on the column just past a doorway, which belongs
            # to the room next door and is not a cell of this one. It is drawn
            # by the room it is really in on the frame it gets there; dropping
            # it here is a pixel, and the alternative is the plan drawing a fly
            # outside its own room's rectangle.
            continue
        px, py = origin(room, cx, cy)
        size = SIZE[kind]
        # Centred in the 4x4 the map cell owns, so a 2x2 mark sits over the
        # middle of the cell and a Cleg's single pixel sits in the middle of
        # that. Integer halves, and SCALE is even, so nothing rounds.
        offset = (SCALE - size) // 2
        _fill(screen, px + offset, py + offset, size)
        _claim(best, room, cx, cy, kind)

    for index, kind in enumerate(best):
        if kind == P_NOTHING:
            continue
        screen.set_attr(index % COLS, PLAN_TOP + index // COLS,
                        attr_byte(ink=HUE[kind], paper=BLACK, bright=True,
                                  flash=FLASHES[kind]))
    return cells_written()
