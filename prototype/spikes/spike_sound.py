"""The speaker behind everything: one channel, and a WAV of what it did.

Issue #54. The host half of `sounds.py`, exactly as `spike_buzz` is the host
half of `buzz` and `frontend/display.py` is the host half of `core.screen`. It
takes a per-frame decision -- click, tick, this frame of that effect, or
nothing -- and turns it into audio. **It decides nothing.** On the Spectrum
this file becomes a tone loop, a noise loop and a table of delay constants, and
nothing else changes, which is the whole point of keeping the arbitration
somewhere else.

**One audio path.** Before this slice the sonar and the body's tick had a
speaker of their own in `spike_buzz.Speaker` and the fourteen effects had no
voice at all. `spike_buzz.Speaker` is gone; its two waves stay exactly where
they were, untouched, because they are tuned and because moving them would have
made a byte-for-byte comparison with the commit before impossible to state.
What changed is who owns the speaker, not what a click sounds like.

**It also renders to file, which is what makes any of this judgeable.** Nobody
reviewing this game can open a window, and until now nobody could listen to it
either:

    --bank DIR   one WAV per effect, plus the sonar at its three rates and the
                 body's tick, and stop
    --wav FILE   a whole run's audio, alongside its two reports

**The run render is a recording, not a re-derivation.** It is built from the
list of decisions the arbiter actually made, frame by frame, recorded as the
run was played. A render that re-ran the arbitration over the event log would
be a second performance that nobody heard, which is not evidence about the
first one.

Both work headless with no audio device: a machine with no speaker writes the
files and says nothing. That is the same rule the driver has had since phase 2
and it is why any of these numbers exist.

## The infidelities, stated rather than discovered

* **`click_wave` decays its burst to nothing.** A beeper has no amplitude: on
  the machine a click is a flat burst that stops dead. This is inherited from
  issue #33, it is known, it is deliberately not fixed here, and the sound
  table's own note about the sketch says the same thing.
* **44.1kHz is a cleaner square than a Z80 makes**, and the sample rate rounds
  every period: a delay constant becomes a whole number of samples, so a pitch
  here is within a fraction of a percent of the pitch there rather than equal
  to it. The port's own pitch grid is the coarser of the two.
* **The spray's noise is aliased.** Its LFSR steps every 70 T-states, which is
  about 1.13 steps per sample at 44.1kHz, so the file cannot contain what the
  machine emits; it contains a sampling of it. The shift register and its tap
  are `sounds`', so both machines run the same sequence -- it is the rendering
  that is approximate, not the noise.
* **No pitch wobble is modelled.** The real thing flips a bit from a loop whose
  timing varies with what the frame had left, which *Music and responsiveness*
  flags as the largest open risk in the whole audio approach. Everything here
  is rock steady and the machine will not be.
"""

import argparse
import os
import struct
import sys
import wave

from . import buzz, rescue, sounds, spike_buzz, tune

#: Sample rate, and the amplitude of the one bit. Both are `spike_buzz`'s, so
#: an effect and a click sit at the same loudness -- **everything in this game
#: is at one loudness because everything will be**. If an effect seems too loud
#: next to the sonar that cannot be fixed by turning it down; it is fixed by
#: making it shorter, or higher, or not making it.
RATE = spike_buzz._RATE
AMPLITUDE = spike_buzz._AMPLITUDE

#: Frames a second, and therefore samples in one frame of audio. 882 exactly at
#: 44.1kHz, which is why the arithmetic below is all whole numbers.
FRAME_RATE = 50
FRAME_SAMPLES = RATE // FRAME_RATE

#: A frame of silence, and the unit everything else is padded to.
SILENT_FRAME = bytes(2 * FRAME_SAMPLES)


def samples_of(tstates: int) -> int:
    """T-states as whole samples at 44.1kHz. Rounds down; see the docstring."""
    return tstates * RATE // sounds.TSTATES


def _pack(levels) -> bytes:
    return struct.pack(f"<{len(levels)}h", *levels)


class Synth:
    """A speaker with one bit, rendered a frame at a time.

    The phase carries across frames on purpose: an effect is a glide split into
    twenty-millisecond pieces, and restarting the cycle every frame would put a
    click at 50Hz through the middle of every sound in the game. The Z80 has
    the same property for free, because it is in the middle of a delay loop
    when the interrupt fires.
    """

    __slots__ = ("pos", "cycle", "high", "lfsr", "acc")

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.pos = 0
        self.cycle = 0
        self.high = 0
        self.lfsr = sounds.LFSR_SEED
        self.acc = 0

    def frame(self, note: sounds.Note) -> bytes:
        """One frame -- 882 samples -- of whatever the note says."""
        if note.kind == sounds.SILENT:
            return SILENT_FRAME
        if note.kind == sounds.NOISE:
            return self._noise(note)
        return self._tone(note)

    def _tone(self, note: sounds.Note) -> bytes:
        levels = []
        for _ in range(FRAME_SAMPLES):
            if self.pos >= self.cycle:
                period = note.period
                if note.kind == sounds.RASP:
                    # **A rasp is a jittered delay constant**, picked afresh
                    # each cycle -- not a modulated frequency and not a
                    # per-frame wobble. That is what makes it sound like a
                    # Cleg rather than like a siren, and it is one call to the
                    # shift register per cycle on the target too.
                    self.lfsr = sounds.lfsr_next(self.lfsr)
                    period = sounds.jittered(self.lfsr, note.period,
                                             note.period_hi)
                self.cycle = max(1, samples_of(period))
                self.high = samples_of(sounds.high_of(period, note.duty))
                self.pos = 0
            levels.append(AMPLITUDE if self.pos < self.high else -AMPLITUDE)
            self.pos += 1
        return _pack(levels)

    def _noise(self, note: sounds.Note) -> bytes:
        """The spray: the shift register clocked every `period` T-states.

        The accumulator counts in T-states times the sample rate so that it
        stays whole: one sample is `TSTATES` of those units, one LFSR step is
        `period * RATE` of them.
        """
        levels = []
        step = note.period * RATE
        for _ in range(FRAME_SAMPLES):
            self.acc += sounds.TSTATES
            while self.acc >= step:
                self.acc -= step
                self.lfsr = sounds.lfsr_next(self.lfsr)
            levels.append(AMPLITUDE if self.lfsr & 1 else -AMPLITUDE)
        return _pack(levels)


class MusicSynth:
    """The music, a frame at a time, carrying the beeper's own bit between them.

    Issue #55. A frame of music is two integers -- a delay constant and a count
    of **whole half-cycles** the frame's leftover afforded -- and this turns
    them into samples. It holds one piece of state, which is the state a
    beeper has: **which way the bit is currently set.**

    **The rest of the frame is the bit held, not silence.** A beeper has no
    amplitude and no zero; between flips the speaker cone simply stays where it
    was put. Rendering the unspent part of a frame as zeroes would be an
    amplitude the machine has not got, and it would turn the dropout into a
    50Hz amplitude modulation -- a buzz that is an artefact of the rendering
    rather than a property of the engine. Holding the level is what the machine
    does and it is what this does.

    **It is silent until the music first sounds**, so a run played without
    music renders byte for byte as it did before this slice: there is no bit to
    hold if nothing ever flipped one.

    Cached by `(period, halves, level)`, which is a few dozen blocks in the
    whole game -- seven pitches, a handful of affordable counts and two levels.
    Rendering a run frame by frame without it is eight million samples of
    Python for a three-minute run.
    """

    __slots__ = ("level", "active", "_cache")

    def __init__(self) -> None:
        #: +1 or -1: which way the bit is set. It starts low, as a machine
        #: that has not yet made a noise does.
        self.level = -1
        #: Has the music ever sounded? Until it has, a frame with no music in
        #: it is true silence rather than a held level.
        self.active = False
        self._cache = {}

    def frame(self, period: int, halves: int) -> bytes:
        """One frame: `halves` half-cycles of `period`, then the bit held."""
        if halves <= 0:
            return self.held()
        self.active = True
        key = (period, halves, self.level)
        block = self._cache.get(key)
        if block is None:
            block = self._build(period, halves)
            self._cache[key] = block
        # An odd number of flips leaves the bit the other way up, which is why
        # the level is part of the key: the same note in the same frame is a
        # different block depending on where the last one left the speaker.
        if halves % 2:
            self.level = -self.level
        return block

    def held(self) -> bytes:
        """A frame with no music in it: the bit where the last frame left it."""
        if not self.active:
            return SILENT_FRAME
        return _pack([AMPLITUDE * self.level] * FRAME_SAMPLES)

    def took(self, block: bytes) -> None:
        """Another voice had the frame; take the bit as that voice left it.

        There is one speaker and one bit. A click or an effect drives it too,
        so the music picks up from wherever that sound stopped rather than from
        where the music itself last was -- which is the difference between a
        joint and a step in the middle of a file.
        """
        if not self.active or len(block) < 2:
            return
        last = struct.unpack("<h", block[-2:])[0]
        self.level = 1 if last > 0 else -1

    def _build(self, period: int, halves: int) -> bytes:
        # Fifty samples at the top of the table and two hundred at the bottom,
        # so a half-cycle is never rounded away to nothing here. A note added
        # above about 3.5kHz would be, and would need the `max(1, ...)` that
        # `Synth._tone` carries for the effects -- which is a different
        # rendering and would break the whole-half-cycle arithmetic this
        # engine is judged on. The tune table does not go near it.
        half = samples_of(tune.half_of(period))
        level = self.level
        levels = []
        for _ in range(halves):
            # **The flip comes first.** The leftover buys flips, and a frame
            # that affords one flips once and then holds for the rest of the
            # frame -- which is a click, and is exactly what the dropout has
            # left at eighteen Clegs.
            level = -level
            levels.extend([AMPLITUDE * level] * half)
        # The budget cannot afford a whole frame of tone by construction --
        # the leftover is at most `ENTITY_CEILING` T-states and a frame is
        # `FRAME_TSTATES` -- so this never truncates. Sliced anyway, because a
        # table change that broke that should make a quiet file rather than an
        # exception.
        levels = levels[:FRAME_SAMPLES]
        levels.extend([AMPLITUDE * level] * (FRAME_SAMPLES - len(levels)))
        return _pack(levels)


def effect_frames(sound: int) -> list:
    """One effect as a list of frames of audio, in order.

    A list rather than one block because that is how it is played back: an
    effect cut off by a priority-1 arrival is heard for the frames it got, and
    a run render slices the frames the arbiter said were heard. The whole thing
    joined is what the live speaker plays and what `--bank` writes.
    """
    effect = sounds.EFFECTS[sound]
    synth = Synth()
    return [synth.frame(effect.note(i)) for i in range(effect.frames)]


def _padded(wave_bytes: bytes) -> bytes:
    """One of the two built voices, padded out to a whole frame.

    A click is 180 samples of a frame's 882 and a tick is 330 of them. **The
    frame is the unit of arbitration** -- a frame with a click in it is a frame
    nothing else gets, which is the sketch's own finding about what the sonar
    costs the music -- so the rest of the frame is silence rather than
    something else's.
    """
    if len(wave_bytes) >= len(SILENT_FRAME):
        return wave_bytes[:len(SILENT_FRAME)]
    return wave_bytes + bytes(len(SILENT_FRAME) - len(wave_bytes))


class Bank:
    """Every sound the game can make, built once, in host format.

    Built lazily by whoever needs it -- the live speaker, the run render and
    `--bank` all share it, so there is one place a sound is turned into
    samples and no chance of the file and the speaker disagreeing.
    """

    def __init__(self) -> None:
        self.click = _padded(spike_buzz.click_wave(stereo=False))
        self.tick = _padded(spike_buzz.tick_wave(stereo=False))
        self.effects = {sound: effect_frames(sound) for sound in sounds.EFFECTS}
        #: The music's bit (issue #55). **This is the one thing in here that
        #: carries state from frame to frame**, and it has to: the music is
        #: rendered as it is played rather than looked up, because a frame of
        #: it depends on how many half-cycles the frame could afford and on
        #: which way the last flip left the speaker. So `frame` must be called
        #: in the order the decisions were made -- which is how it is called in
        #: every path there is, and what a caller replaying a run out of order
        #: would break.
        self.music = MusicSynth()

    def frame(self, decision: tuple) -> bytes:
        """The audio for one recorded decision. Always a whole frame.

        **In order.** See `self.music`: everything above the music is a lookup
        and the music is a performance.
        """
        kind, sound, index, period, halves = decision
        if kind == sounds.CLICK:
            block = self.click
        elif kind == sounds.TICK:
            block = self.tick
        elif kind == sounds.EFFECT:
            frames = self.effects[sound]
            block = (frames[index] if 0 <= index < len(frames)
                     else SILENT_FRAME)
        else:
            # **Nothing louder wanted the frame, so the music has it** -- or
            # it has nothing to play, or the building took the time, and all
            # three come out of `MusicSynth` because all three leave the bit
            # where it was.
            return self.music.frame(period, halves)
        self.music.took(block)
        return block

    def whole(self, sound: int) -> bytes:
        return b"".join(self.effects[sound])


# --- recording a run --------------------------------------------------------

class Recorder:
    """The decisions a run's voice made, one tuple a frame.

    Three small integers a frame -- 9000 frames of a run is 27,000 of them --
    and it exists so that the WAV of a run is the performance the game gave.
    Nothing on the target records anything; this is the measuring instrument
    and it is host-side for the same reason the repaint counter is driver-side.
    """

    __slots__ = ("frames",)

    def __init__(self) -> None:
        self.frames = []

    def __call__(self, run) -> None:
        if run.voice is not None:
            self.frames.append(run.voice.decision())

    def render(self, bank: Bank | None = None) -> bytes:
        bank = bank or Bank()
        return b"".join(bank.frame(d) for d in self.frames)


# --- files ------------------------------------------------------------------

def write_wav(path: str, data: bytes) -> str:
    """Mono, 16-bit, 44.1kHz. Stdlib only, so it works with no host at all."""
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(data)
    return path


def sonar_wave(distance: int, clicks: int = 8, bank: Bank | None = None) -> bytes:
    """The sonar at the rate a Cleg that far away makes it.

    **Driven by the real counter**, `buzz.Sonar`, rather than by a gap written
    out here: the rate is the whole meaning of the sonar and a file that
    quoted the interval from memory could be right about a game that no longer
    exists. 46 frames at the edge of hearing, 29 halfway in, 8 on contact.
    """
    bank = bank or Bank()
    sonar = buzz.Sonar()
    out = []
    heard = 0
    while heard < clicks:
        if sonar.update(distance):
            heard += 1
            out.append(bank.click)
        else:
            out.append(SILENT_FRAME)
    return b"".join(out)


def tick_wave(bank: Bank | None = None) -> bytes:
    """A body's whole twenty seconds, fresh to about to turn.

    A real `rescue.Worker` is killed and ticked, and a real `buzz.Ticker` is
    fed its `tick_period`, for the same reason as above: the quickening is the
    information, and it belongs to the body rather than to this file.
    """
    bank = bank or Bank()
    body = rescue.Worker(0, 0)
    body.state = rescue.DEAD
    ticker = buzz.Ticker()
    out = []
    for _ in range(rescue.BODY_FRAMES):
        body.tick()
        out.append(bank.tick if ticker.update(body.tick_period)
                   else SILENT_FRAME)
    return b"".join(out)


# --- the tunes, rendered so the dropout can be judged ----------------------

def tune_wave(which, clegs: int = 0, loops: int = 1) -> bytes:
    """A whole tune at a fixed load, through the real sequencer.

    `clegs` is how many are on screen for every frame of it, so `0` is the tune
    with the building quiet and `tune.WORST_CLEGS` is the tune the port model
    says cannot be heard at all. Nothing here decides anything: the note comes
    from the table, the leftover from the budget, and the half-cycles from the
    two of them.
    """
    music = tune.Music(which)
    synth = MusicSynth()
    out = []
    for _ in range(which.frames * loops):
        slice_ = music.update(clegs, free=True)
        out.append(synth.frame(slice_.period, slice_.halves))
    return b"".join(out)


def tune_under_load(which, worst: int = tune.WORST_CLEGS) -> bytes:
    """The tune with the room filling up, from nothing to the worst case.

    **The file the ruling is about.** The Cleg count climbs evenly across one
    pass of the tune, so what is heard is the leftover being eaten: the bass
    goes first, because a half-cycle of A2 is the longest thing in the table,
    then the middle of the tune, and at the worst case nothing at all. No fade
    and no envelope -- every step of it is `52,416 - fixed - 830n` and an
    integer division, where the 830 is `building.CLEG_COST` read through
    `tune.leftover`.

    **The climb is twice as long as it was**, because the worst case moved
    from eighteen Clegs to thirty-six on 2026-09-11 when the music stopped
    keeping its own doubled copy of a fly's cost. The file therefore spends
    much more of its length with the tune intact, which is the honest picture:
    a room has to be genuinely full before the leftover runs out.

    It is a *demonstration* and not a measurement: a swarm does not arrive at a
    constant rate. The measurement is a run render, where the count is whatever
    was in the room.
    """
    music = tune.Music(which)
    synth = MusicSynth()
    out = []
    frames = which.frames
    for frame in range(frames):
        clegs = frame * (worst + 1) // frames
        slice_ = music.update(clegs, free=True)
        out.append(synth.frame(slice_.period, slice_.halves))
    return b"".join(out)


def tune_with_sonar(which, bank: "Bank | None" = None) -> bytes:
    """The tune with a swarm closing over it and going away again.

    **The file the whole exercise exists for**, and the one the audio sketch
    named: the design has claimed since 2026-09-06 that *the music thinning out
    is itself a warning*, and this is what that sounds like. Two separate
    things thin it and both are real here, arbitrated by `sounds.Voice`:

    1. **The sonar takes the frame outright.** A click is four milliseconds of
       a twenty-millisecond frame, but the frame is the unit of arbitration, so
       a frame with a click in it is a silent frame for the music.
    2. **The frame runs out of time**, which is the dropout, and it is much the
       larger of the two.

    The swarm closes across the first half and goes back out across the second,
    because *the score comes back when things calm* is half of the claim and a
    file that only ever gets worse cannot show it. The distance drives a real
    `buzz.Sonar`, so the rate is the game's own; the count and the distance are
    a script and are not a measurement of anything.
    """
    bank = bank or Bank()
    music = tune.Music(which)
    voice = sounds.Voice(music)
    sonar = buzz.Sonar()
    frames = which.frames
    out = []
    for frame in range(frames):
        # Out and back: at the middle of the file the swarm is on top of you.
        toward = frame if frame * 2 < frames else frames - frame
        near = 2 * toward * (buzz.REACH - 1) // frames
        distance = buzz.REACH - 1 - near
        clegs = 2 * toward * tune.WORST_CLEGS // frames
        voice.update(sonar.update(distance), False, (),
                     sonar.interval, buzz.NEVER, clegs=clegs)
        out.append(bank.frame(voice.decision()))
    return b"".join(out)


#: The three distances the sonar is rendered at, and what to call them. The
#: edge of hearing is one cell inside `buzz.REACH`, because at the reach itself
#: it is silent by definition.
SONAR_RATES = (
    ("edge", buzz.REACH - 1),
    ("halfway", buzz.REACH // 2),
    ("contact", 0),
)

#: Silence between the effects in the combined file, so they can be told apart
#: by ear. One second, which is the sketch's own spacing.
BANK_GAP = FRAME_RATE


def bank_files(out_dir: str) -> list:
    """Write the whole bank into a directory. Returns the paths written.

    Eighteen files the issue asks for -- fourteen effects, three sonar rates
    and the body's tick -- plus `effects.wav`, which is all fourteen in table
    order with a second between them. The nineteenth is not padding: the
    question the sound table asks to be judged on is *do the fourteen tell each
    other apart*, and that is a question about them in sequence.
    """
    os.makedirs(out_dir, exist_ok=True)
    bank = Bank()
    paths = []
    joined = []
    gap = SILENT_FRAME * BANK_GAP
    for sound, name in enumerate(sounds.SOUND_NAMES):
        data = bank.whole(sound)
        # SFX_NEST_TURNED -> sfx-nest_turned.wav: the prefix becomes a
        # hyphen so the fourteen sort together, and the rest of the name is
        # left exactly as `moments.SOUND_NAMES` spells it.
        stem = name.lower().replace("_", "-", 1)
        paths.append(write_wav(os.path.join(out_dir, f"{stem}.wav"), data))
        joined.append(data)
    paths.append(write_wav(os.path.join(out_dir, "effects.wav"),
                           gap.join(joined)))
    for name, distance in SONAR_RATES:
        paths.append(write_wav(os.path.join(out_dir, f"sonar-{name}.wav"),
                               sonar_wave(distance, bank=bank)))
    paths.append(write_wav(os.path.join(out_dir, "tick.wav"),
                           tick_wave(bank=bank)))
    # The two tunes, and then the two files that are about the dropout rather
    # than about the tune (issue #55). `ostinato-with-sonar.wav` is the one the
    # design's four-year-old claim is judged on.
    paths.append(write_wav(os.path.join(out_dir, "theme.wav"),
                           tune_wave(tune.THEME)))
    paths.append(write_wav(os.path.join(out_dir, "ostinato.wav"),
                           tune_wave(tune.OSTINATO)))
    paths.append(write_wav(os.path.join(out_dir, "ostinato-under-load.wav"),
                           tune_under_load(tune.OSTINATO)))
    paths.append(write_wav(os.path.join(out_dir, "ostinato-with-sonar.wav"),
                           tune_with_sonar(tune.OSTINATO, bank=bank)))
    return paths


# --- the live speaker -------------------------------------------------------

class Speaker:
    """Plays what the voice decided. Silent and harmless with no device.

    **One channel, because a Spectrum has one beeper**, and now genuinely one:
    the sonar, the body's tick and the fourteen effects all come down it, and
    which of them is heard was settled in `sounds.Voice` before this class was
    asked to make a noise. There is no mixing here and there must never be one
    -- two things audible at once would be a sound the port cannot make.

    An effect is handed to the mixer whole on the frame it starts rather than a
    frame at a time. That is not a shortcut: `Voice` guarantees nothing will
    interrupt it except a priority-1 effect, and a priority-1 arrival calls
    `play` again, which stops the channel dead. Feeding 882 samples a frame
    would be the same performance with a chance of a gap in it.

    **The grace window made that convenience cost something** (issue #57). A
    click past frame 18 now punches a hole in a long effect, and playing the
    click stops the channel -- so the effect has to be started again from the
    frame after the hole, which is what `_tails` is for: the same sound from
    each frame it can ever be resumed at, built on demand and kept. About 260
    of them exist in the whole game and a run touches a handful.

    **This is a Pygame stand-in and the port does not have it.** On the
    Spectrum the player routine reads one note per interrupt from the table
    and simply reads the next one after the click; there is no such thing as
    resuming a sound because there was never a sound, only a sequence of
    frames. If this class is ever ported instead of replaced, `_tails` is the
    part to delete.
    """

    def __init__(self, volume: float = 0.35) -> None:
        self.volume = volume
        self.available = False
        self._sounds = {}
        #: `(sound, frame)` -> that effect played from that frame on. Built
        #: lazily because most of them are never needed; see the class
        #: docstring on why they exist at all.
        self._tails = {}
        self._frames = {}
        self._pygame = None
        self._stereo = False
        self._click = None
        self._tick = None
        self._channel = None
        #: The music's bit and the frames built from it (issue #55). Same
        #: synth as the file render uses, so the window and the WAV cannot
        #: disagree about what a frame of music is.
        self._music = MusicSynth()
        self._music_sounds = {}
        self._click_block = SILENT_FRAME
        self._tick_block = SILENT_FRAME

    def open(self) -> bool:
        """Prepare the voice. Returns whether there is anything to hear."""
        try:
            import pygame
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            init = pygame.mixer.get_init()
            if init is None:
                return False
            stereo = init[2] > 1
            self._pygame = pygame
            self._stereo = stereo
            bank = Bank()
            self._frames = bank.effects
            self._click_block = bank.click
            self._tick_block = bank.tick
            self._click = self._sound(pygame, _padded(
                spike_buzz.click_wave(stereo=stereo)))
            self._tick = self._sound(pygame, _padded(
                spike_buzz.tick_wave(stereo=stereo)))
            for sound in sounds.EFFECTS:
                data = bank.whole(sound)
                self._sounds[sound] = self._sound(
                    pygame, _stereo(data) if stereo else data)
            self._channel = pygame.mixer.Channel(0)
            self.available = True
        except Exception:
            # No device, no mixer, no problem. Sound is the first thing to go
            # on a machine that cannot make a noise.
            self.available = False
        return self.available

    def _sound(self, pygame, data: bytes):
        sound = pygame.mixer.Sound(buffer=data)
        sound.set_volume(self.volume)
        return sound

    def play(self, voice) -> None:
        """One frame's worth of speaker, from the arbiter's decision.

        Only three things ever start a sound: a click, a tick, and the frame an
        effect begins on. Every other frame of an effect is already playing,
        which is why this is called every frame and does nothing on most of
        them.
        """
        if not self.available or voice is None:
            return
        if voice.kind == sounds.CLICK:
            self._music.took(self._click_block)
            self._channel.play(self._click)
        elif voice.kind == sounds.TICK:
            self._music.took(self._tick_block)
            self._channel.play(self._tick)
        elif voice.kind == sounds.NOTHING:
            self._play_music(voice)
        elif voice.kind == sounds.EFFECT and voice.started:
            self._channel.play(self._sounds[voice.sound])
        elif voice.kind == sounds.EFFECT and voice.resumed:
            # The frame after a hole: the click that punched it stopped this
            # channel, so the rest of the effect is handed over again from
            # where the arbiter says it now is. See the class docstring -- the
            # target has no equivalent and needs none.
            self._channel.play(self._tail(voice.sound, voice.index))

    def _play_music(self, voice) -> None:
        """One frame of music, on the frame nothing else wanted.

        **A Pygame stand-in, and a cruder one than `_tails`.** The mixer is
        handed one frame of samples at a time, so the music is only as
        continuous as the host loop is punctual, and a frame the loop was late
        for is a gap the target would not have. On the Spectrum there is no
        such thing as handing over a frame of music: the player routine flips
        the bit with whatever time is left and the next interrupt finds it
        ready to carry on. **If this class is ever ported rather than replaced,
        this method and `_tails` are the two parts to delete.**

        Nothing is played for a frame with no music in it -- the channel is
        left alone, which is what a held bit sounds like through a mixer that
        has no concept of one.
        """
        if voice.music is None:
            return
        slice_ = voice.music.slice
        if not slice_.sounding:
            return
        key = (slice_.period, slice_.halves, self._music.level)
        sound = self._music_sounds.get(key)
        if sound is None:
            data = self._music.frame(slice_.period, slice_.halves)
            sound = self._sound(self._pygame,
                                _stereo(data) if self._stereo else data)
            self._music_sounds[key] = sound
        else:
            # Keep the bit in step even on a cache hit: the level is part of
            # the key, so the block is right, but the synth still has to know
            # which way this frame left the speaker.
            self._music.frame(slice_.period, slice_.halves)
        self._channel.play(sound)

    def _tail(self, sound: int, index: int):
        """The effect from `index` on, as one sound. Built once, then kept."""
        key = (sound, index)
        tail = self._tails.get(key)
        if tail is None:
            data = b"".join(self._frames[sound][index:])
            tail = self._sound(self._pygame,
                               _stereo(data) if self._stereo else data)
            self._tails[key] = tail
        return tail

    def close(self) -> None:
        if self.available and self._channel is not None:
            self._channel.stop()


def _stereo(data: bytes) -> bytes:
    """Mono samples doubled up, for a mixer that was opened in stereo."""
    out = bytearray()
    for i in range(0, len(data), 2):
        out += data[i:i + 2] * 2
    return bytes(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m spikes.spike_sound",
        description="Write every sound in the game as a WAV, and stop.")
    parser.add_argument("--bank", required=True,
                        help="directory the WAVs are written into")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    paths = bank_files(args.bank)
    print(f"\nsound bank: {len(paths)} files in {args.bank}")
    for path in paths:
        print(f"  -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
