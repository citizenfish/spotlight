"""The two tunes, as data, and the one thing that breaks them up.

Issue #55, from *Music and Sound#The tunes, as data* for the grid and the two
tables and *Music and Sound#The dropout, in the prototype* for the ruling this
module obeys. Portable: no pygame, no numpy, no float literal, and every entry
in every table is an integer -- **so that the port inherits data rather than a
performance.** The sketch that settled the idiom was a throwaway script and only
its WAVs were kept, which is exactly how a tune stops being data, and this
module is the answer to that.

`spike_sound.py` turns what is decided here into audio and is the only part that
is not portable. Same seam as `sounds`/`spike_sound`, `buzz`/`spike_buzz` and
`core`/`frontend`.

## Where the tunes play

The theme on the title screen, the ostinato in play from the first frame of a
run, and **nothing on the ending screen** -- the ending is silence and a count
and it stays that way.

## The grid

    a unit   12 frames, 240ms
    a bar    8 units, as three cells of 3, 3, 2
    ostinato 12 bars -- 1,152 frames, 23.0s, and it loops
    theme    12 bars and a one-bar tag -- 1,248 frames, 25.0s, and it loops

The bass takes the two three-unit cells and the two-unit cell is the answer: the
bass again in most bars, the motif in the few where it speaks. **The bass and
the motif take turns inside the bar because a single bit cannot sound two
notes**, and there are no chords anywhere in either tune. That is not a
limitation being worked around; it is why the idiom was chosen.

**The tables are a reconstruction and are labelled as one in the vault.** What
survived the sketch is the durations, the idiom and a description; the grid is
derived from the durations and the pitches were authored fresh. They are meant
to be argued with, and *Music and Sound#What to listen for* already says which
way: if the idiom is wrong the fix is not chords, because there are none
available -- it is to let the motif move further and to break the 3-3-2 more
often. **That costs a table and not a line of code**, which is the whole reason
the tunes are written this way, and `test_spike_tune.py` pins it by changing a
table and watching the render move.

## The dropout, which is the point of the slice

Music is not budgeted. It takes the leftover of the frame:

    leftover = 52,416 - fixed - 830 * clegs          T-states

where 830 is `building.CLEG_COST` and is read from there rather than copied.
**No budget in this build carries its own copy of an entity's cost** -- the
ruling of 2026-09-11, made after this module carried one for five days and
priced the music at twice the drawing.

and renders **whole half-cycles of the note in play until that leftover is
spent.** A frame that affords three plays three and then nothing; a frame that
affords none is silent. No fade, no envelope, no smoothing across frames and no
buffering.

**Half-cycles are indivisible because a beeper flips a bit or it does not.**
That is the one and only floor, and it is not a compromise: the machine cannot
produce a third of a flip. Everything above the floor breaks up exactly as it
falls out.

**Why it is driven from the budget and not from a curve.** The audio sketch
thinned the music with a load curve that sounded right, and *Music and Sound*
records that curve's `fixed` term and its map from a swarm to a Cleg count as
**invented for the sketch**. The prototype does not run on a 3.5MHz Z80, so it
has no genuine scarcity to be faithful to -- anything it does under load is a
model, and reproducing an invented one convincingly would look like evidence.
So the figures below are the measured ones, from
*2026-09-06 The 48K cycle budget* via `building.ENTITY_CEILING`, and there is
one place to change them when the port measures a real routine.

## How rarely it fires, and why that was accepted

Stated rather than buried, because it is the price of getting the cost right.
Measured over 172,011 frames -- seven bots, five seeds, counting the flies in
the room the player is actually in -- and with a peak population anywhere in
the sample of **twenty-five**:

    at a Cleg of 830        at the withdrawn 1,654
    bass gone from 21       from 11
    all music gone from 35  from 18
    frames with the bass gone   0.24%       13.37%
    frames with no music at all 0.00%        1.19%

**So at the honest cost the music does not quite go in an ordinary room.** That
is a real loss and the ruling of 2026-09-11 accepted it with its eyes open: the
dropout's arithmetic property is untouched and only the worst case moved, and
the warning the dropout was carrying has a better home anyway. Since slice F
the music also loses whole frames outright to the sonar, the tick and the
effects, measured at 8.2% of frames at the edge of hearing against 21.9% at
contact. That thinning tracks **distance**, which a player can act on, where a
population-driven dropout tracks something they cannot.

The leftover curve stays, unchanged in kind, firing rarely. **The day a room
really is full, the music really should go** -- and if the design wants the
music to thin in rooms that are merely busy, that has to be authored in the
tables, not bought back by mispricing a fly.

## What this cannot tell anybody, stated rather than left to be believed

**Timing jitter is not modelled.** The host renders exact periods at 44.1kHz and
the machine flips a bit from a loop whose length wobbles by a few T-states. The
prototype's disintegration is therefore *cleaner* than the target's and its
steady pitches steadier. Pitch stability under a variable frame is open, it is
not closeable by a Python synth, and nothing rendered from this module may be
read as evidence about it.

## What fell out of the arithmetic and was not designed

Worth knowing before listening, because it sounds like a fault and is not:
**the bass is the first thing the load takes and the motif is the last.** A
half-cycle of A2 is 15,909 T-states, so a frame affords at most two of them even
with nothing on screen, and none at all past twenty Clegs; a half-cycle of A4 is
3,977, so the answering motif is still there at thirty-four. Under load the tune
loses its floor before it loses its voice. That is not a choice anybody made --
it is what *whole half-cycles of the leftover* means when the bass is two
octaves below the motif -- and if it is wrong, *Music and Sound* has already
ruled which way to fix it: the in-game music becomes sparser still, in the
tables above, rather than the engine becoming kinder.

**An idea tried and put back**, because obvious ideas get had twice: rendering
the *remaining* fraction of a half-cycle at the end of a frame, so that a frame
with 1.7 half-cycles' worth of leftover sounds for all of it. It is smoother and
it is a lie -- the bit is flipped by a loop that either completes or does not,
and a fragment claims a pitch the fragment does not contain.
"""

from dataclasses import dataclass

from . import building

# --- the grid ---------------------------------------------------------------

#: Frames in a unit: 12, which is 240ms. **The unit is the note**, not the
#: cell -- see `ARTICULATION` below.
UNIT_FRAMES = 12

#: The bar, as three cells of 3, 3, 2 units. The two threes are the bass and
#: the two is the answer.
CELL_UNITS = (3, 3, 2)

#: Units in a bar, and frames in a bar: 8 and 96.
BAR_UNITS = sum(CELL_UNITS)
BAR_FRAMES = BAR_UNITS * UNIT_FRAMES

#: How much of a unit the note sounds for, in frames; the rest is a rest.
#:
#: **This is a reading and it is flagged as one.** The vault's tables give one
#: pitch per *cell*, and a three-unit cell played as one tone is 720ms of held
#: pitch -- a drone, where the idiom the note describes is "a driving bass
#: ostinato ... sparse, pulsing". The grid names a unit at all, which a
#: per-cell tune would have no use for, and the note table carries a rest at
#: index 0 that neither tune table ever names. Both only make sense if the unit
#: is the note and the cell is the pitch it repeats on, so that is how it is
#: built: three pulses of A2 rather than one long A2.
#:
#: Eight frames of twelve is two thirds, which is an articulation and not a
#: staccato -- enough gap to hear the pulse, not so much that the bass stops
#: driving. **It is one constant and changing it changes no code.** If the
#: designer rules that a cell is one held note, this becomes `UNIT_FRAMES` and
#: everything else stands.
ARTICULATION = 8

# --- the note table ---------------------------------------------------------
#
# Period in T-states at 3.5MHz, `3_500_000 // hz`, because a delay constant is
# what the port wants and a frequency is not. Quoted from the vault rather than
# computed, so that a table entry is a table entry; `test_spike_tune.py` checks
# each one against `sounds.period_of` and would catch a typo in either.

REST = 0
G2 = 1
A2 = 2
A3 = 3
C4 = 4
E4 = 5
G4 = 6
A4 = 7

#: Delay constants, indexed by the eight names above. A rest is zero, which is
#: how the sequencer says "no flips this unit" without a second flag.
PERIODS = (0, 35714, 31818, 15909, 13358, 10606, 8928, 7954)

#: What each one is called and what it sounds at, for the tests and for
#: anybody reading a render. Data, not decoration: the pitch is a design
#: decision and belongs to the vault, and this is where the build says which
#: pitch it thinks it was given.
NOTE_HZ = (0, 98, 110, 220, 262, 330, 392, 440)
NOTE_NAMES = ("rest", "G2", "A2", "A3", "C4", "E4", "G4", "A4")

#: **Duty is 1:2 throughout -- a square -- and that is deliberate rather than
#: lazy.** Timbre in this game means something: a rasp is a Cleg, and the sound
#: table spends the only other timbre the machine has on the effects. The bass
#: and the motif differ in octave and in nothing else.
DUTY = 2

# --- the two tunes ----------------------------------------------------------
#
# One row a bar, three pitches a row: the 3-unit cell, the 3-unit cell and the
# 2-unit answer. **These are the tune.** Nothing below this line reads them
# except the sequencer, and the sequencer does not care what is in them.

#: The in-game music: an A pedal with one lean on G, and a motif that answers
#: three times in twelve bars. Twelve bars, 1,152 frames, 23.0s, and it loops.
OSTINATO_BARS = (
    (A2, A2, A2),   # 1
    (A2, A2, A2),   # 2
    (A2, A2, A2),   # 3
    (A2, A2, E4),   # 4   the motif speaks
    (A2, A2, A2),   # 5
    (A2, A2, A2),   # 6
    (A2, A2, A2),   # 7
    (A2, A2, C4),   # 8   and again, a tone lower
    (G2, G2, G2),   # 9   the one lean on G
    (G2, G2, G2),   # 10
    (A2, A2, A2),   # 11
    (A2, A2, A3),   # 12  the bass answers itself an octave up, and it loops
)

#: The title theme: the same grid and the same pedal, with the motif speaking
#: every other bar and moving further, and a tag that lands on the tonic an
#: octave up. Twelve bars and a tag, 1,248 frames, 25.0s, and it loops.
THEME_BARS = (
    (A2, A2, A2),   # 1
    (A2, A2, E4),   # 2
    (A2, A2, A2),   # 3
    (A2, A2, G4),   # 4
    (A2, A2, A2),   # 5
    (A2, A2, A4),   # 6   the furthest the motif goes
    (A2, A2, A2),   # 7
    (A2, A2, G4),   # 8
    (G2, G2, G2),   # 9   the lean on G, as the ostinato has it
    (G2, G2, E4),   # 10
    (A2, A2, A2),   # 11
    (A2, A2, C4),   # 12
    (A2, A2, A3),   # tag
)


class Tune:
    """A table of bars, and where in it a frame counter is.

    **It holds no position of its own.** Every method takes the frame, so the
    same tune can be read by a render and by a run without either one moving
    the other, and so that the sequencer's place is a function of the clock
    rather than a thing that can drift from it. See `Music`.
    """

    __slots__ = ("name", "bars")

    def __init__(self, name: str, bars: tuple) -> None:
        self.name = name
        self.bars = bars

    @property
    def frames(self) -> int:
        """How long the tune is. It loops, so this is also its modulus."""
        return len(self.bars) * BAR_FRAMES

    @property
    def seconds(self) -> int:
        """How long it runs, to the nearest second.

        Rounded rather than floored, so the two tunes report the 23s and 25s
        the vault records rather than 23 and 24. The grid is exact in frames
        and a second is not the unit anything is built in.
        """
        return (self.frames + 25) // 50

    def bar(self, frame: int) -> int:
        """Which bar a frame falls in, counting from zero."""
        return (frame % self.frames) // BAR_FRAMES

    def note(self, frame: int) -> int:
        """The note index sounding on this frame, or `REST`.

        A rest comes out of the articulation rather than out of the table:
        eight frames of every twelve sound and the other four are the gap that
        makes a repeated pitch a pulse rather than a drone.
        """
        frame %= self.frames
        within = frame % BAR_FRAMES
        if within % UNIT_FRAMES >= ARTICULATION:
            return REST
        bar = self.bars[frame // BAR_FRAMES]
        for cell, units in enumerate(CELL_UNITS):
            span = units * UNIT_FRAMES
            if within < span:
                return bar[cell]
            within -= span
        return REST      # unreachable: the three cells cover the bar

    def period(self, frame: int) -> int:
        """The delay constant sounding on this frame, or zero for a rest."""
        return PERIODS[self.note(frame)]


#: The two tunes, built once. A `Tune` holds no state, so one of each is
#: enough and a test may hand a different table to the same class.
OSTINATO = Tune("ostinato", OSTINATO_BARS)
THEME = Tune("theme", THEME_BARS)

TUNES = {"ostinato": OSTINATO, "theme": THEME}


# --- the frame's leftover ---------------------------------------------------

#: T-states in a real 50Hz frame on a 48K: 312 scan lines of 224. Everything
#: here converts to time at 3.5MHz, so this is also what a frame of audio is
#: worth -- 882 samples at 44.1kHz, exactly.
FRAME_TSTATES = 69888

#: What a frame has to spend, after the flat quarter *2026-09-06 The 48K cycle
#: budget* holds back for contention, the interrupt and a margin. **The
#: difference between this and `FRAME_TSTATES` is not silence anybody chose**;
#: it is time the music routine is not running in, and it is why a frame of
#: music can never fill a frame of audio however quiet the room is.
SPENDABLE_TSTATES = 52416

#: What the music player's own per-frame overhead costs, in T-states.
#:
#: **A named zero, so that a zero can move** (the ruling of 2026-09-11, and the
#: same trick `building.FIXTURE_COST` already uses). *The 48K cycle budget*
#: says in as many words that sound beyond the sonar click is unbudgeted, so
#: the speaker routine genuinely is not paid for anywhere in the sum below and
#: a margin for it would be defensible. It is priced at nothing today because
#: nobody has measured a real tone loop -- and it is *named*, and it is on the
#: fixed term rather than on a fly, because the speaker routine costs the same
#: whatever is on screen. The day somebody measures one, the arithmetic here
#: finds it by itself and `WORST_CLEGS` moves with it.
#:
#: **What this replaces, because obvious ideas get had twice.** Until
#: 2026-09-11 the margin was hidden inside a doubled Cleg: the music priced a
#: fly at 1,654 T-states where the drawing priced it at 830. That claimed the
#: uncertainty was proportional to the swarm, which nothing supports, and it
#: re-denominated a music decision in an entity's sprite format, which is
#: exactly the mistake `building.py` warns about at `CLEG_COST`.
MUSIC_OVERHEAD_TSTATES = 0

#: What the frame's fixed work costs -- the fade, the dirty attributes, the
#: stipple, input and the player logic, plus the music player's own overhead
#: above. Derived rather than quoted, from the same ceiling the entity valve
#: enforces, so that there is **one** figure in the build and a port
#: measurement moves both together.
FIXED_TSTATES = (SPENDABLE_TSTATES - building.ENTITY_CEILING
                 + MUSIC_OVERHEAD_TSTATES)

#: The most Clegs the port model says can be on screen at once: the entity
#: ceiling, less the player who is always drawn, divided by a Cleg. Thirty-six,
#: arrived at here by arithmetic so that it moves when the model does. This is
#: what "the worst case" means in the dropout test, and at it the leftover
#: affords nothing at all.
#:
#: **It was eighteen until 2026-09-11**, because this module priced a Cleg at
#: 1,654 -- the pixel-positioned figure, right on 2026-09-06 and wrong from
#: 2026-09-07, when cell-aligned Clegs were taken and a fly stopped needing a
#: pre-shift and a second byte column. Eighteen is the *pixel-positioned*
#: ceiling and it is withdrawn. The worst case did not change because anything
#: got louder: rooms got cheaper, and a room in which the music dies is now a
#: room twice as full as one that used to kill it.
WORST_CLEGS = ((building.ENTITY_CEILING - building.PERSON_COST)
               // building.CLEG_COST)


def leftover(clegs: int) -> int:
    """T-states the frame has left for music with this many Clegs about.

    `52,416 - fixed - 830n`, floored at zero, and the 830 is
    **`building.CLEG_COST`, read and not copied**. A Cleg costs one thing in
    this build and every budget in it reads that one thing; the day this module
    kept its own copy is the day the music quietly became twice as pessimistic
    as the drawing, and nobody noticed for five days.

    **Music is not budgeted**: this is what is left when everything that
    matters has been paid for, which is the whole of why the score drops away
    as the building turns against you and comes back when things calm. Nobody
    implements that; it falls out of here.
    """
    spare = (SPENDABLE_TSTATES - FIXED_TSTATES
             - building.CLEG_COST * clegs)
    return spare if spare > 0 else 0


def half_of(period: int) -> int:
    """T-states in half a cycle -- the smallest thing the beeper can do.

    Duty is 1:2 throughout, so this is the period halved. A rest has no
    half-cycle and returns zero, which callers read as *nothing to render*.
    """
    return period // DUTY


def half_cycles(spare: int, period: int) -> int:
    """Whole half-cycles of `period` that fit in `spare` T-states.

    **The ruling, in one integer division.** Whole ones only: the engine never
    renders a fragment shorter than a half-cycle, not because a fragment sounds
    bad but because a beeper flips a bit or it does not.
    """
    half = half_of(period)
    if half <= 0:
        return 0
    return spare // half


# --- what the speaker does for one frame of music ---------------------------

@dataclass(frozen=True)
class Slice:
    """One frame of music: a delay constant and how many flips there is time for.

    Two integers, which is what the port's player routine holds -- and `halves`
    is a count it decrements, not a length it divides. `Slice(0, 0)` is a frame
    with no music in it, whether because the tune is resting, because something
    louder owned the frame or because the leftover afforded nothing.
    """

    period: int = 0
    halves: int = 0

    @property
    def half(self) -> int:
        """T-states in each of the half-cycles this frame renders."""
        return half_of(self.period)

    @property
    def tstates(self) -> int:
        """How long the frame's music actually lasts. Always a whole multiple
        of `half`, which is the ruling stated as arithmetic."""
        return self.halves * self.half

    @property
    def sounding(self) -> bool:
        return self.halves > 0


SILENCE = Slice()


#: The keys `Music.stats()` returns, so a report can lay out its columns for a
#: run that had no music at all without asking one what it would have called
#: them. They are carried in `sounds.SOUND_METRICS` alongside the starvation
#: figures, because the music's three states are three ways of losing a frame
#: and reading them apart is the whole of judging the dropout.
MUSIC_METRICS = (
    "music_frames_heard",
    "music_frames_taken",
    "music_frames_starved",
    "music_frames_resting",
    "music_half_cycles",
)


class Music:
    """The sequencer: where the tune is, and what the frame can afford of it.

    One per run (the ostinato) and one per title screen (the theme). It decides
    nothing about the game, reads no game state and is the bottom of the
    arbitration order -- `sounds.Voice` owns it and asks it last, on a frame
    nothing else wanted.

    **The position advances with the frame counter whether or not the note was
    heard.** That is the rule this class exists to enforce: a silenced tune
    keeps its place in time rather than stretching, because *the music is a
    thing happening in the room, not a file being played*. A tune that stretched
    under load would be a different tune, and it would stretch exactly when the
    building is at its worst.

    The counter is this object's own rather than the session's, for the same
    reason the effect clock is: **on the target the player routine runs off the
    50Hz interrupt, and the interrupt does not stop because the game logic
    paused.** A moment's pause and a mains surge are frames the game does not
    step, and the music goes on through them. See `sounds.Voice.audio_frame`.
    """

    __slots__ = ("tune", "frame", "slice", "clegs", "heard", "taken",
                 "starved", "resting", "halves")

    def __init__(self, tune: Tune | None = None) -> None:
        #: Which tune, or None for silence -- which is what the ending screen
        #: is and what it stays.
        self.tune = tune
        #: Audio frames since this sequencer was made. **The position is a
        #: function of this and of nothing else.**
        self.frame = 0
        #: What the last frame came to.
        self.slice = SILENCE
        #: The Cleg count the last frame was priced against, kept so that a
        #: frame the game did not step is priced at the load that was on screen
        #: when it stopped. Nothing moved during it, so nothing else can be
        #: true.
        self.clegs = 0
        self.heard = 0
        self.taken = 0
        self.starved = 0
        self.resting = 0
        self.halves = 0

    # --- what is playing ---------------------------------------------------

    def play(self, tune: Tune | None) -> None:
        """Start a tune from its beginning, or stop with `None`.

        **It resets the position**, which is the one place a tune's place is
        allowed to move for a reason other than the clock: a title screen shown
        twice starts its theme twice, and a new run starts the ostinato at bar
        one. Nothing in play calls this.
        """
        self.tune = tune
        self.frame = 0
        self.slice = SILENCE

    @property
    def position(self) -> int:
        """Where in the tune the next frame is. Zero when nothing is playing."""
        if self.tune is None:
            return 0
        return self.frame % self.tune.frames

    # --- the frame ---------------------------------------------------------

    def update(self, clegs: int = 0, free: bool = True) -> Slice:
        """One frame. `free` is whether anything louder took it.

        The order is the point: the position is worked out from the counter
        first and the counter advances last, **and neither depends on `free` or
        on `clegs`.** A frame taken by the sonar costs the music that frame and
        nothing else.
        """
        self.clegs = clegs
        self.slice = self._slice(clegs, free)
        self.halves += self.slice.halves
        self.frame += 1
        return self.slice

    def audio_frame(self) -> Slice:
        """A frame the sound player ran and the game did not step.

        Priced at the load that was on screen when the game stopped, because
        nothing moved. It is not free: a paused frame is a frame of an effect
        or of silence, never one of music, since `Voice` only asks the music
        for a frame nothing else wanted -- so the caller passes `free` itself.
        """
        return self.update(self.clegs, free=False)

    def _slice(self, clegs: int, free: bool) -> Slice:
        if self.tune is None:
            return SILENCE
        if not free:
            # **A frame with a sonar click, a body tick or an effect in it is a
            # frame with no music**, by design and not by accident. The frame
            # is the unit of arbitration and there is no queue.
            self.taken += 1
            return SILENCE
        period = self.tune.period(self.frame)
        if not period:
            self.resting += 1
            return SILENCE
        halves = half_cycles(leftover(clegs), period)
        if not halves:
            # The building has taken the frame without anything being heard at
            # all. This is the disintegration, and it is counted apart from the
            # frames something else owned because they are different losses.
            self.starved += 1
            return SILENCE
        self.heard += 1
        return Slice(period, halves)

    # --- what a report asks it ---------------------------------------------

    def stats(self) -> dict:
        """The dropout, in four counts and a total. All integers."""
        return {
            "music_frames_heard": self.heard,
            "music_frames_taken": self.taken,
            "music_frames_starved": self.starved,
            "music_frames_resting": self.resting,
            "music_half_cycles": self.halves,
        }
