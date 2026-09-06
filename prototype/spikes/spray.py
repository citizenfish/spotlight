"""Flyspray: lingering patches on the floor.

The spray is **area denial, not a weapon**. Firing does not shoot anything out
of the air -- it lays a patch of ground that kills Clegs which enter it, for a
few seconds, and then clears.

That changes what it is for. You do not aim it at a Cleg; you put it where Clegs
are going to be: across a doorway your workers are filing through, behind you in
the room you are leaving, on a nest to stop it spawning, or on a fresh body
before it turns.

It has no effect at all on a Cleg that has already attached. Once one is on you,
the damage is decided -- see the design notes on QuirkyClegs.
"""

from spotlight.core.constants import COLS

from .layout import PLAY_ROWS
from .sources import _AXES

#: Scattered droplets, so sprayed ground reads differently from lit floor.
STIPPLE = (
    0x00,
    0x22,  # ..#...#.
    0x00,
    0x88,  # #...#...
    0x00,
    0x22,  # ..#...#.
    0x00,
    0x88,  # #...#...
)

#: Frames a patch stays active. 50 is one second.
PATCH_FRAMES = 250

#: How far ahead of the player the patch is laid, and how wide.
REACH = 2
HALF_WIDTH = 1


def patch_cells(cx: int, cy: int, facing: int) -> list[tuple[int, int]]:
    """The cells a burst covers: a short block on the ground ahead of you."""
    fx, fy, sx, sy = _AXES[facing]
    cells = []
    for d in range(1, REACH + 1):
        for k in range(-HALF_WIDTH, HALF_WIDTH + 1):
            x, y = cx + fx * d + sx * k, cy + fy * d + sy * k
            if 0 <= x < COLS and 0 <= y < PLAY_ROWS:
                cells.append((x, y))
    return cells


class Spray:
    """Charges, and the patches currently on the floor."""

    def __init__(self, charges: int = 5) -> None:
        self.charges = charges
        #: cell -> frames remaining
        self.patches: dict[tuple[int, int], int] = {}

    @property
    def empty(self) -> bool:
        return self.charges <= 0

    def fire(self, cx: int, cy: int, facing: int) -> bool:
        """Lay a patch ahead. Returns False if there is nothing left to fire."""
        if self.empty:
            return False
        self.charges -= 1
        for cell in patch_cells(cx, cy, facing):
            # Re-spraying refreshes rather than stacking; there is no such
            # thing as doubly-poisoned ground.
            self.patches[cell] = PATCH_FRAMES
        return True

    def tick(self) -> None:
        """Age every patch by a frame and clear the expired ones."""
        expired = []
        for cell, left in self.patches.items():
            left -= 1
            if left <= 0:
                expired.append(cell)
            else:
                self.patches[cell] = left
        for cell in expired:
            del self.patches[cell]

    def covers(self, cx: int, cy: int) -> bool:
        return (cx, cy) in self.patches

    def kills(self, entities) -> list:
        """Whichever of `entities` are standing in spray. They die."""
        return [e for e in entities if self.covers(e.cx, e.cy)]
