"""The speaker behind the sonar. Pygame, and it does not port.

This is the host layer, exactly as `frontend/display.py` is: it takes the
portable decision in `buzz.Sonar` -- click, or do not click -- and makes a
noise. On the Spectrum this file becomes a handful of OUTs to port 254 and
nothing else changes, which is the point of keeping the decision elsewhere.

A click here is a short burst that decays to nothing, so it reads as a tick
rather than a beep. There is no numpy, so it is packed by hand.
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


class Speaker:
    """Plays a click or a tick when asked. Silent and harmless with no device.

    **One channel, because a Spectrum has one beeper.** The session never asks
    for both on a frame -- the sonar wins the speaker and the body's tick drops
    the beat -- and playing them down the same channel is what keeps that
    honest rather than merely intended.
    """

    def __init__(self, volume: float = 0.35) -> None:
        self.volume = volume
        self.available = False
        self._click = None
        self._tick = None
        self._channel = None

    def open(self) -> bool:
        """Prepare the voice. Returns whether there is anything to hear."""
        try:
            import pygame
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            init = pygame.mixer.get_init()
            if init is None:
                return False
            self._click = pygame.mixer.Sound(
                buffer=click_wave(stereo=init[2] > 1))
            self._click.set_volume(self.volume)
            self._tick = pygame.mixer.Sound(
                buffer=tick_wave(stereo=init[2] > 1))
            self._tick.set_volume(self.volume)
            self._channel = pygame.mixer.Channel(0)
            self.available = True
        except Exception:
            # No device, no mixer, no problem. Sound is the first thing to go
            # on a machine that cannot make a noise.
            self.available = False
        return self.available

    def click(self) -> None:
        """One tick. Cuts off any click still sounding, so a fast rattle stays
        a rattle rather than smearing into a tone."""
        if self.available:
            self._channel.play(self._click)

    def tick(self) -> None:
        """One body tick. The same channel as the click, deliberately: there is
        one speaker, and the sonar has already been given first refusal."""
        if self.available:
            self._channel.play(self._tick)

    def close(self) -> None:
        if self.available and self._channel is not None:
            self._channel.stop()
