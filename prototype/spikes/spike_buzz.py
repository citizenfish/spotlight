"""The two built voices: the sonar's click and a body's tick, as samples.

This is the host layer, exactly as `frontend/display.py` is: it takes the
portable decision in `buzz.Sonar` -- click, or do not click -- and makes a
noise. On the Spectrum this file becomes a handful of OUTs to port 254 and
nothing else changes, which is the point of keeping the decision elsewhere.

A click here is a short burst that decays to nothing, so it reads as a tick
rather than a beep. There is no numpy, so it is packed by hand.

**These two waves are tuned and they do not move** (issue #54). 180 samples at
a four-sample half-cycle for the click; a doubled 120-sample burst at nine
samples with a ninety-sample gap for the tick. They were settled by ear against
`buzz.interval_for`'s rates, they are quoted in *Music and Sound* as figures the
sound table was built around rather than decided by, and `test_spike_sounds.py`
pins them byte for byte against the commit before the one speaker arrived. A
slice that wants a different click is arguing with the note, not with this file.

**The speaker that used to live here has gone** (issue #54). It played these
two and nothing else, straight from the session, while the fourteen effects had
no voice at all -- two audio paths, of which one obeyed the design's
arbitration order and the other did not exist. There is now one:
`sounds.Voice` decides and `spike_sound.Speaker` plays. What changed is who
owns the speaker; the waves below are byte for byte what they were.

One known infidelity is inherited and stays: `click_wave` decays its burst to
nothing, which is a Pygame convenience. **A beeper has no amplitude** -- on the
machine a click is a flat burst that stops dead -- and the sound table's own
account of the audio sketch says the same. Left alone deliberately, because the
rates were tuned by ear against exactly this click.
"""

import struct

_RATE = 44100
_AMPLITUDE = 11000

#: Samples in one click. About four milliseconds -- long enough to hear, short
#: enough that six a second is a rattle rather than a tone.
_SAMPLES = 180

#: Samples per half-cycle. Small is bright and ticky; large is a thud.
_HALF = 4

# --- the body's tick (issue #33) -------------------------------------------
#
# **A lower, doubled click against the sonar's single one.** Not a different
# rate: rate is already carrying the meaning -- in Spotlight a quickening tick
# always means you have less time than you did, and it says so for the swarm
# closing, for a worker bleeding out and for a body about to turn. Three
# speakers, one sentence. What tells them apart has to be timbre, so the body
# gets a longer half-cycle (a lower pitch) and two beats where the sonar has
# one.
#
# On a Spectrum both are OUTs to port 254 and the difference is the delay
# between the flips, which is the cheapest way there is to have two voices on
# one beeper.

#: Samples per half-cycle for the body's tick. Twice the sonar's, so an octave
#: down and unmistakably a different thing in the dark.
_BODY_HALF = 9

#: Samples in each beat of the doubled click, and the gap between the two.
_BODY_SAMPLES = 120
_BODY_GAP = 90


def click_wave(samples: int = _SAMPLES, half: int = _HALF,
               stereo: bool = True) -> bytes:
    """One click: a square burst whose amplitude decays to silence."""
    out = bytearray()
    for i in range(samples):
        # Linear decay, so the burst ends at zero and does not click twice.
        level = _AMPLITUDE * (samples - i) // samples
        sign = 1 if (i // half) % 2 == 0 else -1
        sample = struct.pack("<h", sign * level)
        out += sample * (2 if stereo else 1)
    return bytes(out)


def tick_wave(samples: int = _BODY_SAMPLES, half: int = _BODY_HALF,
              gap: int = _BODY_GAP, stereo: bool = True) -> bytes:
    """The body's tick: two of the same burst, lower, with a gap between."""
    beat = click_wave(samples, half, stereo)
    silence = bytes(2 * (2 if stereo else 1) * gap)
    return beat + silence + beat
