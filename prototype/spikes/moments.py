"""Fourteen things that happen, each given a beat: a flash, a pause, a sound id.

Issue #52, from *Art Direction* section 8. About twenty-five kinds of thing
happen in a run and until now the screen mentioned none of them: you freed
somebody and nothing acknowledged it, your torch died and the only trace was a
bar you were not looking at. A moment is the smallest possible acknowledgement
-- at most three things, and usually one.

**This module makes no noise.** Every moment carries a sound id, nothing in the
game reads one, and the voice is the slice after this. That seam is deliberate
rather than awkward: the ids and the priorities were argued next to the events
they belong to, before there was a waveform to argue them next to, so that the
events could be raised before there was anything to play them.

Two rules govern the whole table, and a fifteenth moment added later has to
pass both:

* **A moment may flash only cells the player is already being shown.** Flashing
  something in the dark is a light that costs nothing, and this game does not
  have one of those. A moment tests the cell's light level at the instant it is
  raised and simply does not flash a dark cell.
* **A pause is only permitted on an event that ends something.** A pause during
  play is a change to the pace of the game. Endings and deaths may stop the
  clock; a bite may not.

Which is why **a bite has no flash and a worker's death has none.** Bites are
frequent, and a bar that alerts constantly is furniture rather than an alert;
workers are usually not on lit ground, so there would be nothing to flash, and
a death already has its own channel in the shout. Neither is an oversight and
neither is to be tidied up.

**A flash is the hardware FLASH bit and it is not a light.** Bit 7 of the
attribute byte, which the ULA blinks for free at 16 frames on and 16 off. A
moment writes an attribute and never touches the light field: no charge, no
source, no reveal. The cell's ink and paper are chosen by exactly what chose
them before -- light sets the level, contents set the hue -- and the moment
sets one bit on top of that. The repaint figures are how that is kept honest:
if a moment ever moved the count of cells changing light level, it has been
implemented as a light and it is wrong.

**A flash is a fixed list of cells, captured when the moment is raised, and it
follows nothing.** A freed worker flashes the two cells they were standing in
at the instant they were freed, not the two they are standing in now. That is
what a moment *is* -- it marks where a thing happened -- and it is also why it
costs nothing per frame.

**The dark-cell rule is self-enforcing after the raise.** A dark cell is black
ink on black paper, and flashing swaps ink and paper, so a cell that goes dark
part way through a flash simply stops showing anything. Hence the light level is
tested once, at the raise, and the flash is then left to run.

Portable: no pygame, no floats, integers and cell lists throughout. The pause is
the one thing here the session must never act on -- see `Moments.pause`.
"""

from dataclasses import dataclass

from .rescue import NEST_BROOD, NEST_SPAWN_EVERY

#: Bit 7 of an attribute byte. Named here because this module is where the
#: claim *a flash is one bit and nothing else* lives, and the test that pins
#: ink, paper and bright unchanged is written against it.
FLASH_BIT = 0b1000_0000

# --- the sound ids ----------------------------------------------------------
# Byte-sized, and an index into the table slice F will write, because that is
# what a sound id is on the target: one byte handed to a player routine. The
# names are the contract -- the next slice is entitled to assume this list is
# the list, so `test_spike_moments.py` pins all fourteen by name and value.

SFX_FREED = 0
SFX_DELIVERED = 1
SFX_BITE = 2
SFX_WORKER_DIED = 3
SFX_PLAYER_DIED = 4
SFX_TORCH_OUT = 5
SFX_DOOR = 6
SFX_SPRAY = 7
SFX_SPRAY_KILL = 8
SFX_NEST_TURNED = 9
SFX_HATCHED = 10
SFX_GAME_OVER = 11
SFX_ALL_OUT = 12
SFX_PICKUP = 13

#: id -> the name it is known by, so the sound slice has the table and so a
#: rename is a failing test rather than a silent one.
SOUND_NAMES = (
    "SFX_FREED", "SFX_DELIVERED", "SFX_BITE", "SFX_WORKER_DIED",
    "SFX_PLAYER_DIED", "SFX_TORCH_OUT", "SFX_DOOR", "SFX_SPRAY",
    "SFX_SPRAY_KILL", "SFX_NEST_TURNED", "SFX_HATCHED", "SFX_GAME_OVER",
    "SFX_ALL_OUT", "SFX_PICKUP",
)

# --- the moments ------------------------------------------------------------

M_FREED = "freed"
M_DELIVERED = "delivered"
M_BITE = "bite"
M_WORKER_DIED = "worker_died"
M_PLAYER_DIED = "player_died"
M_TORCH_OUT = "torch_out"
M_DOOR = "door"
M_SPRAY = "spray"
M_SPRAY_KILL = "spray_kill"
M_NEST_TURNED = "nest_turned"
M_HATCHED = "hatched"
M_GAME_OVER = "game_over"
M_ALL_OUT = "all_out"
M_PICKUP = "pickup"

#: How long a readout on the status strip flashes when a moment alerts it.
#: `Panel.alert` already owns the mechanism and its default is 96; the two
#: strip moments name their own frames here so that the table is the one place
#: any of this is written down.
TORCH_OUT_FRAMES = 96
PICKUP_FRAMES = 32

#: How long before a spawn a nest starts telling you, and `M_HATCHED`'s frame
#: count -- they are the same number because they are the same flash. Two
#: seconds, which is why it cannot be driven by the `HATCHED` event: it is a
#: tell, not a report.
TELL_FRAMES = 100


@dataclass(frozen=True)
class Moment:
    """One row of the table: what flashes, for how long, and what it sounds.

    `frames` is how long the flash lasts and is 0 for the moments that have no
    flash at all. `pause` is frames the *shell* holds for and is 0 for
    everything that is not an ending or a death. `strip` names status-strip
    readouts to alert instead of play-area cells, because the strip already has
    the mechanism for it and a second one would be a second thing to keep in
    step.

    `priority` is a **sound** priority and nothing in this slice reads it.
    Priority 1 pre-empts a sounding priority-0 effect; 0 never pre-empts
    anything. It is here because the sound slice must not have to invent it.
    """

    name: str
    sound: int
    priority: int = 0
    frames: int = 0
    pause: int = 0
    strip: tuple = ()
    #: True when the flash is a *state* somewhere else in the game rather than
    #: a list of cells captured here -- see `hatch_is_near`. The moment is
    #: still raised, because it still has a sound; it simply does not start a
    #: flash of its own, because one is already running and stopping it at the
    #: right moment is the state's business, not a frame count's.
    state_flash: bool = False


#: The table, in the order *Art Direction* argues it. What each one *flashes*
#: is not here, because it is different every time it happens -- the cells are
#: passed in at the raise by whoever knew where the thing happened. What is here
#: is everything that is fixed: how long, whether it stops the clock, what it
#: will sound like, and which readout on the strip it alerts.
MOMENTS = {
    m.name: m for m in (
        Moment(M_FREED, SFX_FREED, 0, frames=16),
        Moment(M_DELIVERED, SFX_DELIVERED, 0, frames=32),
        # No flash: bites are frequent, and a bar that alerts on every one is
        # furniture rather than an alert.
        Moment(M_BITE, SFX_BITE, 0),
        # No flash, and it must not gain one: they are usually not on lit
        # ground, and the death already has a channel in the shout.
        Moment(M_WORKER_DIED, SFX_WORKER_DIED, 1),
        Moment(M_PLAYER_DIED, SFX_PLAYER_DIED, 1, frames=16, pause=25),
        # The LIGHT bar *and* its flag: the table says both, and they are two
        # regions on the strip.
        Moment(M_TORCH_OUT, SFX_TORCH_OUT, 0, frames=TORCH_OUT_FRAMES,
               strip=("light", "lit")),
        # No flash: the screen flicks to a different room, which is already the
        # largest visual event in the game.
        Moment(M_DOOR, SFX_DOOR, 0),
        # Raised at the call site rather than from an event, because there is
        # no `SPRAY_FIRED` in the run log and this slice must not add one: a new
        # kind in the log is a changed log, and every baseline in this round
        # rests on the log not changing.
        Moment(M_SPRAY, SFX_SPRAY, 0),
        Moment(M_SPRAY_KILL, SFX_SPRAY_KILL, 0, frames=8),
        Moment(M_NEST_TURNED, SFX_NEST_TURNED, 1, frames=32),
        Moment(M_HATCHED, SFX_HATCHED, 0, frames=TELL_FRAMES,
               state_flash=True),
        Moment(M_GAME_OVER, SFX_GAME_OVER, 1, pause=50),
        Moment(M_ALL_OUT, SFX_ALL_OUT, 1, pause=50),
        Moment(M_PICKUP, SFX_PICKUP, 0, frames=PICKUP_FRAMES,
               strip=("light",)),
    )
}


# --- the two flashes that are states rather than moments --------------------
# In their own place because they do not fit the table above and forcing them
# into it would be worse. Neither needs new state and neither touches the light
# field.

def body_is_flashing(body) -> bool:
    """Does this body flash? Its whole window, until it is doused or turns.

    **The visual half of the tick**, and it had never been built: a body has
    been making a noise since issue #33 and showing nothing. It fires only
    where the player can already see the ground, so it hands over nothing a lit
    floor was not handing over anyway, and it costs a bit in an attribute byte.

    `Worker.ticking` is deliberately the same predicate the tick uses: a body
    you can hear is a body you can see if you are looking at it, and two
    predicates that were meant to agree would eventually not.
    """
    return body.ticking


def hatch_is_near(age: int, hatched: int, owed: int,
                  brood: int = NEST_BROOD,
                  every: int = NEST_SPAWN_EVERY) -> bool:
    """Is this nest within `TELL_FRAMES` of placing one, or still owing one?

    `age` is frames since the body turned, `hatched` is how many of the brood
    it has placed, `owed` is what it has earned and not yet placed. A nest earns
    a spawn every `every` frames of its life, so *within a hundred frames* is
    arithmetic on the clock the nest already keeps and nothing new is stored.

    **A spawn the valve holds leaves the nest still flashing**, which is true
    rather than a bug: it is still owed one, and the tell is about what is
    coming rather than about the frame counter. That is the whole of the
    `owed > 0` branch.

    A nest that has placed its whole brood tells you nothing further -- there is
    no seventh spawn to warn about -- and burning out is not an event.
    """
    if owed > 0:
        return True
    if hatched >= brood:
        return False
    due = hatched * every
    return 0 <= due - age <= TELL_FRAMES


class Flash:
    """One live flash: some cells, in one room, for a few more frames."""

    __slots__ = ("room", "cells", "frames")

    def __init__(self, room: int, cells: tuple, frames: int) -> None:
        self.room = room
        self.cells = cells
        self.frames = frames


class Moments:
    """What has just happened, and what is still flashing because of it.

    One per run. It holds no game state and decides nothing: every moment is
    raised by the code that already knew the thing had happened, so a moment
    cannot get out of step with the event it belongs to.
    """

    __slots__ = ("flashes", "raised", "pause")

    def __init__(self) -> None:
        #: The live flashes, oldest first.
        self.flashes: list[Flash] = []
        #: What was raised this frame, as `(name, cells)`, cleared by `begin`.
        #: The sound slice reads this; nothing else does yet.
        self.raised: list[tuple] = []
        #: Frames the **shell** owes, and the one thing in this module the
        #: session must never act on. A pause is frames in which the game is
        #: not stepped, owned by the host loop: if the session honoured it the
        #: frame counter would advance during it, every event in every log
        #: would move, and the round's standing guarantee that the logs are
        #: byte-identical would be broken. The headless driver ignores it
        #: entirely, or the same `--frames` would buy fewer stepped frames and
        #: the tail of every log would shift.
        self.pause = 0

    def begin(self) -> None:
        """One frame of ageing, at the top of a step and before any raise.

        Ticked at the *start* so that a moment raised during this frame gets
        every one of its frames on screen: raised on frame N with 16 frames, it
        is drawn on N to N+15 and gone on N+16.
        """
        self.raised = []
        if self.flashes:
            live = []
            for flash in self.flashes:
                flash.frames -= 1
                if flash.frames > 0:
                    live.append(flash)
            self.flashes = live

    def raise_moment(self, name: str, cells=(), room: int = 0, lit=None):
        """Raise one moment. Returns its row of the table.

        `lit(cx, cy)` answers *is the player being shown this cell*, and cells
        it refuses are dropped -- see the module docstring for why. **The moment
        is raised either way**: a moment over dark ground still has a sound and
        still counts, it simply has nothing to flash. Losing the raise as well
        would silence a moment for being unlucky about where it happened.
        """
        moment = MOMENTS[name]
        shown = tuple(cells)
        if lit is not None:
            shown = tuple(cell for cell in shown if lit(cell[0], cell[1]))
        self.raised.append((name, shown))
        if moment.pause:
            # The longer of the two, not the sum. Losing the last life raises a
            # death and an ending on the same frame, and that is one beat --
            # two pauses back to back would read as the game hanging twice.
            self.pause = max(self.pause, moment.pause)
        if moment.frames and shown and not moment.state_flash:
            self.flashes.append(Flash(room, shown, moment.frames))
        return moment

    def take_pause(self) -> int:
        """How many frames the shell owes, taken once. Zero for everybody else.

        Called by the host loop and by nothing inside the game. Whoever takes it
        is agreeing to not step the session for that many frames.

        **And to go on running the sound player through them** (issue #57).
        The speaker is not part of the game step on the target -- it is the
        50Hz interrupt, which does not stop because the game logic paused -- so
        a host that holds frames must call `sounds.Voice.audio_frame` for each
        one. The shell did not, and a player's death went on owning the voice
        for twenty-five frames after the sound had finished, with every sonar
        click in them dropped to protect a silence. See `spike1.Shell.frame`.
        """
        owed, self.pause = self.pause, 0
        return owed

    def cells(self, room: int) -> set:
        """Every play-area cell flashing in `room` this frame.

        A flash belongs to the room it was raised in, because the screen shows
        one room: a moment in the far room must not paint itself onto the near
        one when the player walks through a doorway.
        """
        found = set()
        for flash in self.flashes:
            if flash.room == room:
                found.update(flash.cells)
        return found

    def sounds(self) -> list:
        """What wants to be heard this frame, as `(sound id, priority)`.

        Nothing calls this yet and that is the point of the seam: the ids and
        the priorities are fixed here so that slice F writes a voice and not a
        table.
        """
        return [(MOMENTS[name].sound, MOMENTS[name].priority)
                for name, _cells in self.raised]
