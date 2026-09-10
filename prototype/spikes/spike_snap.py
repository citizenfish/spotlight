"""A frame, as a PNG, from a machine with no screen. Host-side and it does not port.

Issue #45. **Nobody in this project had ever seen a frame of the game.** Every
playtest note so far was written from a `.json` and a `.txt` -- the headless
driver opens no window, and the agents that play and judge the game cannot open
one either. So the art has never been reviewed by anybody except the user, at
the user's own keyboard, and the look-and-feel round is about to ask two agents
to have an opinion about it.

This module is the whole of the answer: take the `core.Screen` the game already
draws into, resolve it exactly as the window does, and write a file.

Two rules, and both of them are about the picture being trustworthy:

* **The colour comes from `frontend.display.resolve`**, which is the same call
  the window makes. A snapshot with its own copy of the ink/paper/bright rules
  would be a second thing to get wrong, and a screenshot that could disagree
  with the window is worth less than no screenshot at all, because somebody
  would act on it.
* **Scaling is nearest-neighbour at integer factors only.** A smoothed
  screenshot of a 1-bit display is a lie: it invents colours the Spectrum does
  not have and softens exactly the hard pixel edges that are the subject under
  review. x3 exists because 256x192 on a modern monitor is a postage stamp, and
  x1 is written alongside it because it is the only honest view of the pixels.

It is named `spike_*` so the portability suite exempts it, like `spike_buzz.py`:
pygame and files are host, and the port replaces this file with whatever an
emulator's screenshot key does.

**No display is opened.** An 8-bit paletted `Surface` can be created, palette
set, written to and saved with `pygame.display` never initialised at all --
checked on pygame 2.6.1 with `SDL_VIDEODRIVER=dummy` and no device. An earlier
draft called `pygame.display.init()` and a 1x1 `set_mode` first, on the
assumption that a surface needs a display behind it; it is not needed here and
was dropped, because a driver that quietly grabs a display is a driver that can
fail on a machine that has none.
"""

import os

import pygame

from spotlight.core.constants import SCREEN_H, SCREEN_W
from spotlight.core.screen import Screen
from spotlight.frontend.display import SURFACE_PALETTE, resolve

#: What a snapshot is scaled to unless asked otherwise. 1:1 is the truth and x3
#: is what a person can actually look at, so both are written every time and
#: whoever is reviewing picks.
DEFAULT_SCALES = (1, 3)


def surface(screen: Screen, flashing: bool = False) -> pygame.Surface:
    """The frame as an 8-bit paletted Surface at the true 256x192.

    `flashing` is the phase of the hardware flash, and it is a parameter rather
    than a clock because a snapshot has no time in it: a still of a flashing
    cell has to be able to show either half of the cycle, and the title
    screen's PRESS ANY KEY is flashing text that would otherwise only ever be
    photographed one way round.
    """
    surf = pygame.Surface((SCREEN_W, SCREEN_H), depth=8)
    surf.set_palette(SURFACE_PALETTE)
    buf = resolve(screen, bytearray(SCREEN_W * SCREEN_H), flashing)
    surf.get_buffer().write(bytes(buf))
    return surf


def enlarge(surf: pygame.Surface, scale: int) -> pygame.Surface:
    """Blow a frame up by a whole number, repeating pixels and nothing else.

    `pygame.transform.scale` is nearest-neighbour -- `smoothscale` is the one
    that interpolates -- so at an integer factor every source pixel becomes an
    exact scale x scale block. That is pinned by a test, because the difference
    between the two calls is one word and the wrong one would quietly blur
    every screenshot the look-and-feel round is judged from.
    """
    if scale < 1:
        raise ValueError(f"scale must be a whole number of pixels: {scale}")
    if scale == 1:
        return surf
    return pygame.transform.scale(
        surf, (surf.get_width() * scale, surf.get_height() * scale))


def save(screen: Screen, path: str, scale: int = 1,
         flashing: bool = False) -> str:
    """Write one PNG of `screen`. Returns the path it wrote.

    Any directories in `path` are made, because every caller here is writing
    into a run directory that may not exist yet and none of them wants to say
    so twice.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    pygame.image.save(enlarge(surface(screen, flashing), scale), path)
    return path


def save_scales(screen: Screen, base: str, scales=DEFAULT_SCALES,
                flashing: bool = False) -> list[str]:
    """Write the same frame at each scale. Returns the paths, in order.

    The scale is in the filename rather than a subdirectory so that a run's
    artefacts -- the two reports and its snapshots -- sort together in one
    listing. Somebody reading a run wants all of it in front of them.
    """
    return [save(screen, f"{base}_x{scale}.png", scale, flashing)
            for scale in scales]
