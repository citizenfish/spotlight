"""One speaker: the fourteen effects, and who gets it when two things want it.

Issue #54, from *Music and Sound#The sound table* for the waveform data and
*Art Direction#8. The moments* for the ids and the priorities -- where those
two disagree, Art Direction wins and the table here follows it.

Slice D gave fourteen events a flash, a pause and a sound id and nothing read
an id. Meanwhile the sonar and a body's tick were wired straight from the
session to a mixer channel by a path of their own. **A Spectrum has one
speaker**, so an arbitration order is a design decision rather than an
implementation detail, and until everything goes down one voice the order is a
sentence in a note rather than a thing the build obeys. This module is the
voice, and it is the only place a sound is chosen.

**This module makes no noise.** It decides, per frame, what the speaker should
be doing; `spike_sound.py` turns that into audio and is the only part that is
not portable. Same seam as `buzz`/`spike_buzz`, and the same seam as
`core`/`frontend`.

## The order, and what it does and does not mean

    sonar click > body tick > effect > music.

The sonar wins because it is the player's only warning in the dark. The tick
wins over an effect because it is continuous information and an effect is a
one-off. There is no music in this slice and it yields to everything.

That order was written before anybody had heard it, and hearing it (the audio
sketch, 2026-09-10) raised what the order does not say: **a click is one frame
and an effect is five to sixty-six**, so a click does not displace an effect,
it lands in the middle of one and punches twenty milliseconds out of it. That
was listened to and ruled in *When the sonar lands inside an effect*, and this
module inherits the ruling:

* **An effect that has started owns the voice for its whole length. A click
  landing inside it is dropped, not queued.** So the sonar's priority is
  absolute over the music and **not** over an effect.
* **A dropped click does not touch the sonar's counter.** The next click comes
  when the counter says so. This is the load-bearing half of the rule: the
  sonar's rate *is* the distance, and a counter that restarted on a drop would
  make rate mean something else. `buzz.Sonar` is never told about any of this,
  which is how it stays true.

Three more rules the ruling does not cover, all built deliberately:

1. **A click and an effect wanting the same frame: the click wins and the
   effect never starts.** The effect has not started, so it does not yet own
   anything. This is the designer's reading rather than the user's words, it is
   written here and pinned by a test *so that it is not settled by accident*,
   and if it ever turns out to swallow a bite the player needed, this is the
   paragraph to argue with.
2. **Ownership is against the clicks, not against another effect.** A
   priority-1 effect pre-empts a sounding priority-0 one and cuts it off; a
   priority-0 arriving during anything is dropped; a priority-1 arriving during
   a priority-1 is dropped, first come. That is *Art Direction*'s older rule
   and the two are not in conflict: ownership is what a click loses to, and
   priority is what another effect wins by.
3. **The body's tick is treated exactly as the sonar's click.** It is the same
   shape of thing -- one frame, unpitched, a rate rather than a shape. It beats
   a fresh effect and it is dropped inside a running one. **The ruling was made
   about the click; extending it to the tick is this slice's**, and it is
   flagged here so it is findable if it is wrong.

**Nothing is ever queued.** A loser is not heard, and the state this costs is
one running effect, its remaining frames and its priority -- three bytes, which
is what makes it portable.

## What a note is

A note is two integers: a **period** in T-states and a **duty denominator**.

    period = 3_500_000 // frequency_in_hz
    high   = period // duty_den      (1:2 is a square, 1:4 a quarter, ...)

Duty is the only timbre a single bit has and it is free -- the same loop with
two different delay constants.

**Glides are linear in the period, not in the frequency.** A Z80 decrements a
delay constant; it does not compute a frequency. A glide from 900Hz to 260Hz
over five frames steps the *period* evenly, which is a different curve from
stepping the pitch evenly, and it is the curve the machine can afford. It sags
towards the low end and that is what it sounds like on the target. **This is
not a bug and it is not to be fixed.**

**A rasp is a jittered delay constant**, from a small LFSR -- not a modulated
frequency. Nothing else in the game has an unstable pitch, which is what makes
a rasp mean *Cleg*. The jitter is written in the table as a swing in Hz because
that is how a listener describes it, and it is converted to a pair of periods
**at the ends of the segment**, so the player routine glides two delay
constants and never divides. See `Segment`.

The rule the table is built on, so that a fifteenth row can be judged: the two
continuous voices are unpitched clicks, therefore **every effect is pitched and
moves**; good news rises, bad news falls; and anything about the Clegs is
rasped rather than pitched. `SFX_HATCHED` is the one deliberate exception --
it rises, because it is a thing being born, and it rises *as a rasp*, which is
the only way this voice has of saying that a rising line is not good news.
"""

from dataclasses import dataclass

from .moments import (
    MOMENTS, SFX_ALL_OUT, SFX_BITE, SFX_DELIVERED, SFX_DOOR, SFX_FREED,
    SFX_GAME_OVER, SFX_HATCHED, SFX_NEST_TURNED, SFX_PICKUP, SFX_PLAYER_DIED,
    SFX_SPRAY, SFX_SPRAY_KILL, SFX_TORCH_OUT, SFX_WORKER_DIED, SOUND_NAMES,
)

#: T-states a second on a 48K Spectrum. Every period in this module is in these
#: units, because a delay constant is what the port wants and a frequency is
#: not -- see the module docstring.
TSTATES = 3_500_000


def period_of(hz: int) -> int:
    """The delay constant for a pitch: whole T-states in one cycle.

    Integer division, deliberately. The sound table's own model quotes the
    pitch a `45 + 13n` T-state loop actually reaches, and nothing in the table
    goes above 2kHz -- below which the grid is finer than seven cents, so the
    rounding here is inaudible. It starts to bite around 3kHz and is useless by
    8kHz, which is a region this design does not visit.
    """
    return TSTATES // hz


def high_of(period: int, duty: int) -> int:
    """T-states the bit is held high in one cycle. `duty` is the denominator."""
    return period // duty


# --- the noise, and the rasp ------------------------------------------------

#: The tap word of a 16-bit Galois LFSR: x^16 + x^14 + x^13 + x^11 + 1, which
#: is maximal-length and is one shift and one XOR on a Z80. **Named so both
#: machines make the same noise**, which is the whole reason it is here and not
#: in the host: a spray that hisses differently on the Spectrum is a different
#: sound, not the same sound rendered twice.
#:
#: Deliberately **not** `sources.xorshift16`. That chain is the game's random
#: stream -- every fly's temperament comes off it -- and a speaker that drew
#: from it would make audio a thing that changes the run. Audio decides
#: nothing, and it also draws nothing.
LFSR_TAPS = 0xB400

#: The LFSR's starting state. Any non-zero word will do; this one is fixed so
#: that a rendered spray is byte-identical from run to run and a test can pin
#: it.
LFSR_SEED = 0xACE1


def lfsr_next(state: int) -> int:
    """One step of the noise generator. Never returns zero from a non-zero."""
    bit = state & 1
    state >>= 1
    if bit:
        state ^= LFSR_TAPS
    return state


def jittered(state: int, low: int, high: int) -> int:
    """A delay constant somewhere between two, chosen by the LFSR.

    A multiply and a shift rather than a modulo, because a Z80 has neither
    division nor a cheap remainder. The span of a rasp is small -- tens of
    T-states out of thousands -- so the eight bits taken here are plenty.
    """
    span = high - low
    if span <= 0:
        return low
    return low + ((state & 0xFF) * span >> 8)


# --- what the speaker does for one frame ------------------------------------

#: Note kinds. One byte on the target, and the player routine branches on it
#: once per frame rather than once per cycle.
SILENT = 0
TONE = 1
RASP = 2
NOISE = 3


@dataclass(frozen=True)
class Note:
    """What the speaker does for one frame: a delay constant and a duty.

    `period` and `period_hi` are the same for a `TONE`. For a `RASP` they are
    the two ends of the jitter -- the short delay and the long one, which is
    the high pitch and the low one -- and the host picks between them with the
    LFSR each cycle. For `NOISE`, `period` is the T-states between LFSR steps
    and `duty` means nothing.
    """

    kind: int
    period: int = 0
    period_hi: int = 0
    duty: int = 2

    @property
    def high(self) -> int:
        """T-states the bit is high in one cycle of `period`."""
        return high_of(self.period, self.duty)


SILENCE = Note(SILENT)


@dataclass(frozen=True)
class Segment:
    """One stretch of an effect: a pitch, or a glide, or a rasp, or noise.

    `start` and `end` are in Hz because that is how the sound table is written
    and how a listener argues with it; **everything downstream is in periods**,
    and the conversion happens once, here, at the two ends. A glide is then a
    linear step between two delay constants, which is what the machine can
    afford -- see the module docstring on why that is not the same curve as a
    linear glide in pitch and is not to be corrected.

    `jitter` is the swing in Hz that makes the pitch a rasp. It is turned into
    a *pair* of glides -- the short delay and the long one -- so that a rasp
    costs the player routine two subtractions a frame and no division at all.
    """

    frames: int
    start: int = 0
    end: int = 0
    duty: int = 2
    jitter: int = 0
    #: Noise rather than a pitch: the LFSR stepped every `start` T-states.
    #: `SFX_SPRAY` is the only one, and it is the only sound in the game with
    #: no pitch in it at all.
    noise: bool = False

    def note(self, i: int) -> Note:
        """The note for frame `i` of this segment, counting from zero."""
        if self.noise:
            return Note(NOISE, self.start, self.start, 0)
        last = self.frames - 1
        if self.jitter:
            # Two glides, one for each end of the swing. A higher frequency is
            # a shorter delay, so `start + jitter` is the *low* period.
            low = _glide(period_of(self.start + self.jitter),
                         period_of(self.end + self.jitter), i, last)
            high = _glide(period_of(self.start - self.jitter),
                          period_of(self.end - self.jitter), i, last)
            return Note(RASP, low, high, self.duty)
        period = _glide(period_of(self.start), period_of(self.end), i, last)
        return Note(TONE, period, period, self.duty)


def _glide(first: int, last_value: int, i: int, last: int) -> int:
    """Step a delay constant evenly from `first` to `last_value`.

    Divided by the number of *steps* rather than the number of frames, so the
    last frame of a segment lands exactly on the pitch the table names. A
    one-frame segment is its first value and nothing else.
    """
    if last <= 0 or first == last_value:
        return first
    return first + (last_value - first) * i // last


@dataclass(frozen=True)
class Effect:
    """One row of the sound table: an id, a priority, and a shape.

    `priority` is not decided here. It is *Art Direction*'s, it is already
    written down in `moments.Moment.priority`, and `test_spike_sounds.py`
    checks the two agree rather than letting a second copy drift.
    """

    sound: int
    priority: int
    segments: tuple

    @property
    def frames(self) -> int:
        return sum(s.frames for s in self.segments)

    def note(self, frame: int) -> Note:
        """What the speaker does on frame `frame` of this effect.

        Past the end it is silent, which cannot happen through `Voice` and is
        here so that a caller rendering a file cannot walk off the end of a
        sound and get an exception instead of a silence.
        """
        if frame < 0:
            return SILENCE
        for segment in self.segments:
            if frame < segment.frames:
                return segment.note(frame)
            frame -= segment.frames
        return SILENCE


#: T-states between steps of the LFSR in `SFX_SPRAY`. From the sound table, and
#: it is the whole of that sound: a hiss is a shift register clocked fast.
SPRAY_STEP = 70

#: The fourteen, in the order *Art Direction* argues them, with the pitches,
#: duties, lengths and priorities of *Music and Sound#The sound table*. **None
#: of those figures is this module's to change**: they were settled by ear and
#: an argument with them is an argument with the note.
#:
#: Where a row names several pitches, the frames are split evenly between them
#: unless the split does not divide -- `SFX_DELIVERED` holds its top note for
#: the odd two frames, `SFX_GAME_OVER` its bottom fall for the odd two -- which
#: is the split the sketch's own durations imply and is the only figure in this
#: table that is a reading rather than a quotation.
#:
#: Two rasps in the table have no swing written against them -- the 110Hz rasp
#: in `SFX_PLAYER_DIED` and the 120Hz one in `SFX_TORCH_OUT`. The note says
#: "rasp" and gives no figure, so a swing is chosen here (+/-15 Hz, in the
#: neighbourhood of the +/-18 the note *does* give for `SFX_NEST_TURNED`) and
#: it is flagged as a choice rather than a quotation so the designer can
#: overrule it in one line.
EFFECTS = {
    # Good news rises: two notes, C5 then G5.
    SFX_FREED: Effect(SFX_FREED, 0, (
        Segment(6, 523, 523, 2),
        Segment(6, 785, 785, 2),
    )),
    # The best news in the game, and the only four-note rise in it.
    SFX_DELIVERED: Effect(SFX_DELIVERED, 0, (
        Segment(6, 523, 523, 2),
        Segment(6, 658, 658, 2),
        Segment(6, 785, 785, 2),
        Segment(8, 1048, 1048, 2),
    )),
    # Five frames, and the shortest thing that still reads as a shape rather
    # than a click. **The most frequent sound in the game by a distance**: if
    # twenty of them grate, the note's own answer is that it should be shorter
    # and lower and stop trying to be a shape -- not that it should be quieter,
    # because a beeper has no quieter.
    SFX_BITE: Effect(SFX_BITE, 0, (
        Segment(5, 900, 260, 4),
    )),
    # A Cleg is in this, so it wobbles; then the voice gives out.
    SFX_WORKER_DIED: Effect(SFX_WORKER_DIED, 1, (
        Segment(12, 700, 230, 2, jitter=40),
        Segment(6, 210, 150, 3),
    )),
    SFX_PLAYER_DIED: Effect(SFX_PLAYER_DIED, 1, (
        Segment(20, 620, 150, 2),
        Segment(12, 110, 110, 3, jitter=15),
        Segment(8, 90, 62, 3),
    )),
    SFX_TORCH_OUT: Effect(SFX_TORCH_OUT, 0, (
        Segment(6, 660, 660, 4),
        Segment(6, 494, 494, 4),
        Segment(6, 330, 330, 4),
        Segment(6, 120, 120, 6, jitter=15),
    )),
    # Two frames. A door is crossed constantly and this is a knock, not a tune.
    SFX_DOOR: Effect(SFX_DOOR, 0, (
        Segment(2, 233, 175, 8),
    )),
    SFX_SPRAY: Effect(SFX_SPRAY, 0, (
        Segment(6, SPRAY_STEP, SPRAY_STEP, 0, noise=True),
    )),
    SFX_SPRAY_KILL: Effect(SFX_SPRAY_KILL, 0, (
        Segment(1, 1995, 1995, 2),
        Segment(2, 1500, 900, 4),
    )),
    # A body becoming a nest: the lowest rasp in the game, and the widest duty.
    SFX_NEST_TURNED: Effect(SFX_NEST_TURNED, 1, (
        Segment(24, 105, 105, 8, jitter=18),
    )),
    # The deliberate exception to *good news rises*: it goes up because it is
    # being born, and it goes up as a rasp because it is a Cleg. The swing
    # widens as it climbs, which is the note's `+/-40 then +/-90`.
    SFX_HATCHED: Effect(SFX_HATCHED, 0, (
        Segment(15, 200, 410, 6, jitter=40),
        Segment(15, 410, 620, 6, jitter=90),
    )),
    SFX_GAME_OVER: Effect(SFX_GAME_OVER, 1, (
        Segment(16, 330, 330, 3),
        Segment(16, 247, 247, 3),
        Segment(16, 196, 196, 3),
        Segment(18, 110, 98, 3),
    )),
    SFX_ALL_OUT: Effect(SFX_ALL_OUT, 1, (
        Segment(10, 440, 440, 2),
        Segment(10, 658, 658, 2),
        Segment(10, 880, 880, 2),
        Segment(10, 785, 785, 2),
        Segment(10, 880, 880, 2),
    )),
    SFX_PICKUP: Effect(SFX_PICKUP, 0, (
        Segment(8, 880, 1313, 2),
    )),
}


# --- who gets the speaker ---------------------------------------------------

#: What the voice is doing this frame. One of these and never two: there is one
#: speaker, and this is where that stops being a promise and becomes a value.
NOTHING = 0
CLICK = 1
TICK = 2
EFFECT = 3

#: How long the sonar may go quiet before this is a finding rather than a
#: measurement. Twelve frames is a quarter of a second, and it is the figure
#: *When the sonar lands inside an effect* named when it closed: past it, the
#: ruling reopens as *let the effect finish, with a cap*, which is a design
#: decision and not a constant to tune here. Nothing in this module acts on it;
#: it is reported and that is all.
#:
#: **And it was exceeded on the first measurement.** Over seven bots and five
#: seeds, 7.6% of clicks were dropped and the worst silence was 87 frames --
#: 1.74 seconds -- with a Cleg nine cells off, from a death and a hatching
#: falling back to back. At contact rates the worst was 49 frames with six
#: clicks lost in a row. So the ruling reopens, and the report says so in every
#: run rather than this file quietly making the effects shorter.
#:
#: One thing the measurement showed that the ruling could not have known: **a
#: single dropped click costs a whole interval of silence by arithmetic**, so
#: at the edge of hearing one drop is 46 frames and is nothing like four drops
#: at contact. A limit stated in frames alone cannot tell those apart, which is
#: why `Drought` carries the interval alongside the frames.
QUIET_LIMIT = 12


class Drought:
    """How often one of the two clicking voices was dropped, and for how long.

    Kept for the sonar and for the body's tick, because the ruling that lets an
    effect own the voice explicitly did **not** settle whether a *run* of
    effects can starve them -- a bite is five frames and bites arrive fastest
    exactly when the sonar does. That was left for this slice to measure rather
    than assume, so it is measured here, in the arbiter, where the drops are.

    `quiet` is the figure to compare with `QUIET_LIMIT`: frames from a click
    that was dropped to the next click that was heard. It is *not* the gap
    between clicks -- at the edge of hearing that is 46 frames by design and
    means nothing -- it is silence the sonar did not ask for.

    **And it stops the moment the voice has nothing to say.** The first version
    of this counted on regardless, and a wandering bot that dropped one click
    and then walked out of every Cleg's range reported 1,111 frames of
    starvation -- twenty-two seconds of a silence nobody was owed. A sonar with
    no Cleg within its reach is *supposed* to be silent, so an interval of
    `NEVER` closes the measurement and the figure means what the ruling meant by
    it. Worth remembering, because the wrong version of this figure would have
    reopened a closed design thread on the strength of an empty room.

    **`quiet_interval` is what makes the frames readable**, and it was added
    when the first real measurements came back. One click dropped at the edge
    of hearing is 46 frames of silence *by arithmetic* -- the next click was
    never due sooner -- and that is nothing like four clicks dropped at contact,
    which is the same silence with a fly on you. So the interval in force
    during the worst stretch is carried alongside it: small is the dangerous
    one.
    """

    __slots__ = ("sounded", "dropped", "run", "longest_run", "_quiet",
                 "_longest_quiet", "_interval", "_worst_interval")

    def __init__(self) -> None:
        self.sounded = 0
        self.dropped = 0
        #: Consecutive drops with nothing heard between them.
        self.run = 0
        self.longest_run = 0
        self._quiet = 0
        self._longest_quiet = 0
        #: The closest the threat got during the stretch of silence being
        #: measured, as the interval the counter was on: smaller is nearer.
        self._interval = 0
        self._worst_interval = 0

    def frame(self, wanted: bool, sounded: bool, interval: int = 1) -> None:
        """One frame. `interval` of `buzz.NEVER` means nothing to say."""
        if not interval:
            # Nothing to warn about: whatever silence follows is the design's
            # and not the speaker's. Close the measurement rather than let it
            # run on into an empty room.
            self._close()
            return
        if self._quiet:
            self._quiet += 1
            if interval < self._interval:
                self._interval = interval
        if wanted and not sounded:
            self.dropped += 1
            self.run += 1
            if self.run > self.longest_run:
                self.longest_run = self.run
            if not self._quiet:
                self._quiet = 1
                self._interval = interval
        if sounded:
            self.sounded += 1
            self.run = 0
            self._close()

    def _close(self) -> None:
        """Bank whatever silence was running and start again from nothing."""
        if self._quiet > self._longest_quiet:
            self._longest_quiet = self._quiet
            self._worst_interval = self._interval
        self._quiet = 0
        self._interval = 0

    @property
    def quiet(self) -> int:
        """The longest unasked-for silence, including one still running.

        A run that ends while the voice is still being drowned out counts: the
        alternative is a figure that quietly forgives the worst case in every
        run that ended on a death, which is exactly when it happens.
        """
        return max(self._longest_quiet, self._quiet)

    @property
    def quiet_interval(self) -> int:
        """The rate the voice was on during that silence. Small is near."""
        if self._quiet > self._longest_quiet:
            return self._interval
        return self._worst_interval


#: The keys `stats()` returns, so a report can lay out its columns for a run
#: that had no voice at all without asking one what it would have called them.
SOUND_METRICS = (
    "sonar_clicks", "sonar_clicks_dropped", "sonar_quiet_frames",
    "sonar_quiet_interval", "sonar_drops_in_a_row", "body_ticks",
    "body_ticks_dropped", "body_quiet_frames", "body_quiet_interval",
    "body_drops_in_a_row", "effects_sounded", "effects_dropped",
    "effects_cut", "sound_frames",
)


class Voice:
    """The one speaker. Given what wants to be heard, says what is heard.

    One per run, updated once a frame after everything that could raise a
    sound. It holds no game state, reads no game state and changes none: the
    event log of a run is byte-identical with a voice and without one, which is
    the strongest form the promise *audio decides nothing* takes and is pinned
    by a test across five seeds and two bots.

    The state is one running effect, its remaining frames and its priority.
    Nothing is queued, so a loser is simply not heard.
    """

    __slots__ = ("kind", "sound", "index", "left", "priority", "started",
                 "clicks", "ticks", "effects_sounded", "effects_dropped",
                 "effects_cut", "frames_sounding")

    def __init__(self) -> None:
        #: What the speaker is doing this frame: NOTHING, CLICK, TICK, EFFECT.
        self.kind = NOTHING
        #: Which effect, and how far into it -- `index` 0 is the frame it
        #: starts on, which is how a host knows to begin a new sound rather
        #: than let one carry on.
        self.sound = -1
        self.index = 0
        self.started = False
        self.left = 0
        self.priority = 0
        self.clicks = Drought()
        self.ticks = Drought()
        self.effects_sounded = 0
        self.effects_dropped = 0
        #: Effects cut off part-way by a priority-1 arrival. Counted because a
        #: cut is the one case where a sound the player heard the start of does
        #: not finish, and it is the figure that would say the pre-emption rule
        #: is costing more than it buys.
        self.effects_cut = 0
        self.frames_sounding = 0

    # --- the frame ---------------------------------------------------------

    def update(self, click: bool, tick: bool, wants=(),
               sonar_interval: int = 1, tick_interval: int = 1) -> int:
        """Arbitrate one frame. Returns what the speaker does.

        `click` and `tick` are what the two counters wanted, raw: `buzz.Sonar`
        and `buzz.Ticker` are never told the answer, so a dropped click cannot
        reach back and reset a counter. That is the rule the sonar's whole
        meaning rests on -- rate is distance -- and keeping the counters
        ignorant is how it is enforced rather than remembered.

        `wants` is `[(sound id, priority), ...]` as raised this frame, in the
        order they were raised, which is what `moments.Moments.sounds()`
        returns.

        `sonar_interval` and `tick_interval` are the two counters' current
        intervals, `buzz.NEVER` when a voice has nothing to say at all. **They
        change no decision** and exist only so the starvation figures mean
        something: silence in an empty room is the design working, and four
        clicks lost at contact is not the same event as one lost at the edge of
        hearing. See `Drought`.
        """
        self.started = False
        running = self.left > 0

        # **The two clicking voices are settled first, and against the
        # running effect rather than against the effect table.** An effect
        # already sounding owns the voice, so they are dropped inside one; with
        # nothing sounding they take the frame outright, and anything raised on
        # this frame never starts.
        heard_click = click and not running
        heard_tick = tick and not click and not running

        for sound, priority in wants:
            self._request(sound, priority, blocked=heard_click or heard_tick)

        self.clicks.frame(click, heard_click, sonar_interval)
        self.ticks.frame(tick, heard_tick, tick_interval)

        if heard_click:
            self.kind = CLICK
        elif heard_tick:
            self.kind = TICK
        elif self.left > 0:
            self.kind = EFFECT
        else:
            self.kind = NOTHING
        if self.kind == EFFECT:
            # `index` is derived from what is left rather than counted
            # separately, so there is one number to be wrong about: the frame
            # being played now is the one the note and the host both read, and
            # a pre-emption that resets `left` resets the position with it.
            self.index = EFFECTS[self.sound].frames - self.left
            self.left -= 1
        if self.kind != NOTHING:
            self.frames_sounding += 1
        return self.kind

    def _request(self, sound: int, priority: int, blocked: bool) -> None:
        """One raised sound, against whatever owns the voice.

        `blocked` is the same-frame rule: a click or a tick has already taken
        this frame, the effect has not started, so it never starts. Deliberate,
        argued in the module docstring, and pinned by a test.
        """
        if blocked:
            self.effects_dropped += 1
            return
        if self.left > 0:
            if priority > self.priority:
                # Priority 1 cuts priority 0. Ownership is against the clicks;
                # it was never against a louder piece of news.
                self.effects_cut += 1
                self._start(sound, priority)
            else:
                self.effects_dropped += 1
            return
        self._start(sound, priority)

    def _start(self, sound: int, priority: int) -> None:
        self.sound = sound
        self.priority = priority
        self.index = 0
        self.left = EFFECTS[sound].frames
        self.started = True
        self.effects_sounded += 1

    # --- what the host asks it ---------------------------------------------

    @property
    def sounding(self) -> bool:
        return self.kind != NOTHING

    def note(self) -> Note:
        """The note for this frame, or silence. Effects only.

        A click and a tick are not notes: they are the two built voices in
        `spike_buzz`, unpitched by design, and the host plays them as the
        samples they have always been.
        """
        if self.kind != EFFECT:
            return SILENCE
        return EFFECTS[self.sound].note(self.index)

    def decision(self) -> tuple:
        """This frame as three integers, small enough to record for a whole run.

        `(kind, sound id, frame within the effect)`. A host renders a run's
        audio from a list of these, which is how the WAV is a recording of the
        performance the game gave rather than a second performance derived from
        the event log -- those are not the same thing and only one of them is
        evidence.
        """
        return (self.kind, self.sound if self.kind == EFFECT else -1,
                self.index if self.kind == EFFECT else 0)

    def stats(self) -> dict:
        """The starvation figures, for the run report. All integers."""
        return {
            "sonar_clicks": self.clicks.sounded,
            "sonar_clicks_dropped": self.clicks.dropped,
            "sonar_quiet_frames": self.clicks.quiet,
            "sonar_quiet_interval": self.clicks.quiet_interval,
            "sonar_drops_in_a_row": self.clicks.longest_run,
            "body_ticks": self.ticks.sounded,
            "body_ticks_dropped": self.ticks.dropped,
            "body_quiet_frames": self.ticks.quiet,
            "body_quiet_interval": self.ticks.quiet_interval,
            "body_drops_in_a_row": self.ticks.longest_run,
            "effects_sounded": self.effects_sounded,
            "effects_dropped": self.effects_dropped,
            "effects_cut": self.effects_cut,
            "sound_frames": self.frames_sounding,
        }

    def starved(self, limit: int = QUIET_LIMIT) -> bool:
        """Did either clicking voice go quiet for longer than the ruling allows?

        Reported, never acted on. If this is true of a real run, the answer is
        a design decision -- *let the effect finish, with a cap* -- and not a
        constant this module is entitled to move.
        """
        return max(self.clicks.quiet, self.ticks.quiet) > limit
