"""Flyspray: lingering patches on the floor.

The spray is **area denial, not a weapon**. Firing does not shoot anything out
of the air -- it lays a patch of ground that kills Clegs which enter it, for a
few seconds, and then clears.

That changes what it is for. You do not aim it at a Cleg; you put it where Clegs
are going to be: across a doorway your workers are filing through, behind you in
the room you are leaving, on a nest to stop it spawning, or on a fresh body
before it turns.

It has no effect at all on a Cleg that has already attached. Once one is on you,
the damage is decided -- see the design notes on Clegs.
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


def patch_cells(cx: int, cy: int, facing: int,
                is_solid=None) -> list[tuple[int, int]]:
    """The cells a burst covers: a short block on the ground ahead of you.

    **The loop starts one cell ahead and must go on doing so.** The player's
    own cell is never sprayed, so a burst cannot kill the fly that is already
    on you -- that is what keeps this area denial rather than a weapon, and
    `test_you_do_not_spray_your_own_cell` is there to stop it being widened by
    accident.

    That deliberate gap did cost something, and the fix is not here. A person
    is two cells tall, so facing **up** put the patch on the player's own upper
    cell and a charge spent standing on a fresh body doused it -- in that one
    facing and no other (issue #39). Widening the patch to cover the player
    would have fixed it and turned the spray into a weapon, so instead
    `Session._douse_underfoot` reaches the body under the player's feet at the
    moment a charge is spent, laying no ground at all. The patch's footprint is
    exactly what it always was.

    **Poison lies on floor, not on wall** (issue #41). Pass `is_solid` -- the
    room's own `Room.is_solid`, the single authority on where anything may
    stand -- and any cell it calls solid is dropped. Without it a burst fired
    at a wall laid ground inside the wall and the drawing coloured it, so the
    wall took the spray stipple and hue: from (2, 1) in the main room facing
    **left**, four of the six cells were wall. Nothing can ever stand on those
    cells, so they killed nothing; the charge was spent and bought only a
    stain. Dropping them can only ever shrink a patch, never move or widen it.

    The screen-bounds clip is *not* made redundant by that check and must stay
    ahead of it. `Room.is_solid` answers for the column just past a doorway by
    asking the room next door, so at a doorway it will happily call x = -1
    walkable -- and a patch is keyed by room index, so a cell beyond this
    room's wall would poison the same-numbered cell of the room you are in
    rather than the one you sprayed into.

    `is_solid` defaults to None, which asks for the geometry alone. That is for
    callers testing the shape; anything laying real ground passes the room.
    """
    fx, fy, sx, sy = _AXES[facing]
    cells = []
    for d in range(1, REACH + 1):
        for k in range(-HALF_WIDTH, HALF_WIDTH + 1):
            x, y = cx + fx * d + sx * k, cy + fy * d + sy * k
            if not (0 <= x < COLS and 0 <= y < PLAY_ROWS):
                continue
            if is_solid is not None and is_solid(x, y):
                continue
            cells.append((x, y))
    return cells


class Spray:
    """Charges, and the patches currently on the floor."""

    def __init__(self, charges: int = 5) -> None:
        self.charges = charges
        #: (room, cell) -> frames remaining.
        #:
        #: The room is in the key because sprayed ground stays where it was
        #: laid (issue #21): put a patch across a doorway your workers are
        #: filing through, walk into the next room, and it is still poisoning
        #: the doorway behind you. Cell (17, 4) exists in every room in the
        #: building, so a patch without a room would poison all of them.
        self.patches: dict[tuple[int, tuple[int, int]], int] = {}

    @property
    def empty(self) -> bool:
        return self.charges <= 0

    def fire(self, cx: int, cy: int, facing: int, room: int = 0,
             is_solid=None) -> bool:
        """Lay a patch ahead. Returns False if there is nothing left to fire.

        `is_solid` is the room's, and the cells it rejects are never stored
        (issue #41). **The charge is still spent** when every cell of a burst
        fired into a wall is dropped: whether firing at a wall should refund,
        warn, or stand as the player's mistake is a design question, and the
        code should not settle it by accident. Today it stands as a mistake.
        """
        if self.empty:
            return False
        self.charges -= 1
        for cell in patch_cells(cx, cy, facing, is_solid):
            # Re-spraying refreshes rather than stacking; there is no such
            # thing as doubly-poisoned ground.
            self.patches[(room, cell)] = PATCH_FRAMES
        return True

    def tick(self) -> None:
        """Age every patch by a frame and clear the expired ones."""
        expired = []
        for key, left in self.patches.items():
            left -= 1
            if left <= 0:
                expired.append(key)
            else:
                self.patches[key] = left
        for key in expired:
            del self.patches[key]

    def covers(self, cx: int, cy: int, room: int = 0) -> bool:
        return (room, (cx, cy)) in self.patches

    def cells_in(self, room: int = 0) -> list[tuple[int, int]]:
        """The patches lying in one room, for drawing it."""
        return [cell for (at, cell) in self.patches if at == room]

    def in_room(self, room: int = 0):
        """`covers`, bound to one room -- what `Swarm.tick` wants handed to it."""
        return lambda cx, cy: (room, (cx, cy)) in self.patches

    def kills(self, entities, room: int = 0) -> list:
        """Whichever of `entities` are standing in spray. They die."""
        return [e for e in entities if self.covers(e.cx, e.cy, room)]
