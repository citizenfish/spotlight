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


class Speaker:
    """Plays a click when asked. Silent and harmless with no audio device."""

    def __init__(self, volume: float = 0.35) -> None:
        self.volume = volume
        self.available = False
        self._click = None
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

    def close(self) -> None:
        if self.available and self._channel is not None:
            self._channel.stop()
