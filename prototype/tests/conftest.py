"""Run headless unless the environment says otherwise.

The suite is required to pass headless, and four display tests call
`pygame.display.set_mode`. Without a dummy driver those open a real window,
which on a machine that is not expecting one takes fifteen seconds *each* --
turning a one-second suite into a minute of nothing happening.

Set before pygame is imported, and only if the caller has not chosen a driver
themselves, so running the spike with a real window still works.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
