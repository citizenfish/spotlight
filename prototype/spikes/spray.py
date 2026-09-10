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

from .bitmaps_gen import BITMAPS
from .layout import PLAY_ROWS
from .sources import _AXES

#: Scattered droplets, so sprayed ground reads differently from lit floor.
#:
#: **The droplets are not here.** They are authored in `assets/tiles/spray.txt`
#: and generated into `bitmaps_gen.py` by `tools/bitmaps.py` (issue #51). They
#: had been declared as hex in this module since the spike, which left them
#: outside the drift test that guards every other bitmap and gave the port
#: nothing to assemble. Not one pixel moved in the transcription -- the gallery
#: was regenerated and compared byte for byte -- and the pattern's density and
#: its stagger against the floor's columns are both load-bearing, so the asset
#: file, not this line, is where the reasoning lives.
STIPPLE = BITMAPS["SPRAY"]

#: Frames a patch stays active. 50 is one second.
PATCH_FRAMES = 250

#: How wide the patch is at each distance ahead: index 0 is one cell ahead,
#: index 1 the cell beyond that. Half-widths, so 1 means three cells across
#: and 0 means one.
#:
#: **A table indexed by distance, never a formula** (issue #42). The patch used
#: to be a constant half-width at every distance, which made it a 3x2 block
#: with square corners; a per-distance width drops the far corners and costs a
#: `LD A,(HL)` on the Z80, where anything wanting a square root or a multiply
#: would not port at all. The table only ever shrinks with distance, which is
#: what makes the shape taper away from the player rather than end square.
HALF_WIDTH = (1, 0)

#: How far ahead of the player the patch reaches. Read off the table so the
#: two cannot disagree.
REACH = len(HALF_WIDTH)


def patch_cells(cx: int, cy: int, facing: int,
                is_solid=None) -> list[tuple[int, int]]:
    """The cells a burst covers: a short taper on the ground ahead of you.

    Facing down from `@`, on open floor::

        . @ .
        X X X
        . X .

    Four cells: three across one step ahead, one beyond that. It used to be a
    3x2 block of six with square corners, which read as a stamped rectangle
    rather than something sprayed (issue #42). The corners are dropped by
    `HALF_WIDTH` being a table indexed by distance instead of one constant, so
    the four facings stay reflections of each other -- the shape is written
    once in forward-and-sideways terms and `_AXES` turns it, and there is no
    per-facing case anywhere.

    At eight-pixel cells, four cells is not going to read as a circle. What it
    reads as is **not a rectangle**, and that was the whole of the ask.

    **The patch got smaller, and only smaller.** The new shape is a strict
    subset of the old block: same reach, same three-wide near row, two far
    corners gone. Widening it to round it off was available -- a five-cell
    diamond one step deeper reads rounder still -- and was rejected, because
    reaching a cell further is a power change dressed as a shape change. The
    two uses the design leans on both survive the trim: the near row is three
    across, so it still plugs the three-row connecting doorway in one burst,
    and a body's two cells still fall inside the patch in every facing.

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
    moment a charge is spent, laying no ground at all. That kept the footprint
    exactly what it always was -- until issue #44, which grew it deliberately
    and by a design decision, below. `Session._douse_underfoot` is untouched by
    that: it does not go through the patch at all.

    **Poison lies on floor, not on wall** (issue #41). Pass `is_solid` -- the
    room's own `Room.is_solid`, the single authority on where anything may
    stand -- and any cell it calls solid is dropped. Without it a burst fired
    at a wall laid ground inside the wall and the drawing coloured it, so the
    wall took the spray stipple and hue: from (2, 1) in the main room facing
    **left**, four of the six cells were wall. Nothing can ever stand on those
    cells, so they killed nothing; the charge was spent and bought only a
    stain. Dropping them could only ever shrink a patch, never move or widen
    it -- which held until issue #44 gave a dropped cell somewhere to fall back
    to, below. What still holds is that a dropped cell never lands further away
    than it was aimed.

    The screen-bounds clip is *not* made redundant by that check and must stay
    ahead of it. `Room.is_solid` answers for the column just past a doorway by
    asking the room next door, so at a doorway it will happily call x = -1
    walkable -- and a patch is keyed by room index, so a cell beyond this
    room's wall would poison the same-numbered cell of the room you are in
    rather than the one you sprayed into.

    **A cell the room refuses rebounds one step toward you** (issue #44). The
    burst is authored in forward-and-sideways terms -- `(d, k)`, `d` from 1 and
    `k` bounded by `HALF_WIDTH` -- so a blocked cell falls back to `(d - 1, k)`:
    one decrement along the axis already loaded, the sideways offset untouched,
    one fallback per blocked cell and each decided on its own. Written that way
    it is **one rule in all four facings** -- no new table, no per-facing case,
    and the four shapes stay reflections of one another. Before this a charge
    fired at a wall laid nothing at all and was still spent; it now buys the
    ground between you and the wall instead.

    Three consequences, all of them intended:

    * `(2, 0)` falls back to `(1, 0)`, which is already in the near row, so it
      dedupes rather than widening anything.
    * `(1, +/-1)` falls back to `(0, +/-1)` -- ground **level with the player**,
      which no burst had ever laid. That is the cost of the rule and it is why
      it needed a design decision rather than a bug fix: the footprint may
      shrink freely but may not grow, and laying a cell the burst has never laid
      counts as growing.
    * `(1, 0)` falls back to `(0, 0)`, the player's own cell, and is **refused**
      -- that poison is lost. *Your own cell is never sprayed* is the rule that
      keeps the spray area denial rather than a weapon, so the rebound does not
      get to buy an exception to it. A charge therefore still does not buy
      something in every case: over the playtest building 7.1% of bursts aim a
      rebound at the player's own cell.

    **Only a cell refused by the room rebounds.** A cell clipped by the screen
    bounds does not, for the same reason the clip sits ahead of the solid check
    -- past a doorway the room next door is answering, and a patch is keyed by
    room, so a cell out of bounds is not this room's to fall back from.

    **A rebound cell that is itself solid loses the poison and does not chain.**
    There is no second fallback: one step means no per-burst worst case, poison
    cannot be walked through a wall's thickness, and a chain from `(2, 0)` would
    arrive at `(0, 0)` by a route the rule refuses directly.

    Reach is unchanged and no cell is laid further away than before -- the
    fallback only ever moves a cell toward the player. Measured over all 3,920
    standing-cell-by-facing combinations in the playtest building the burst
    never exceeds four cells and no corner stacks two rebounds onto one floor
    cell: the fallback map is one to one, so a corner drops more and stacks
    nothing.

    **Tried and rejected: the polite rebound.** A blocked cell sliding toward
    the burst's own centre line first -- `(d, k)` to `(d, k - sign k)`, only
    falling back when `k` is already 0 -- looks kinder because it never lays a
    cell level with the player. It is an **exact no-op** over the whole
    building: not one burst in 3,920 changes, because the cell it slides into is
    on the same row as the blocked one and a wall that blocks one blocks the
    other. The value of this rule and its cost are the same fact, so there is no
    version that buys anything without growing the footprint.

    `is_solid` defaults to None, which asks for the geometry alone -- and with
    no room to refuse a cell there is nothing to rebound, so the shape tests see
    the taper unchanged. That is for callers testing the shape; anything laying
    real ground passes the room.
    """
    fx, fy, sx, sy = _AXES[facing]

    def cell(d, k):
        return cx + fx * d + sx * k, cy + fy * d + sy * k

    cells = []
    seen = set()

    def lay(x, y):
        # (2, 0) rebounds onto (1, 0), which the near row already holds, so a
        # burst can name the same cell twice. `Spray.patches` is a dict and
        # would swallow that, but the returned list is what "never more than
        # four cells" is counted from, so it must not double-count.
        #
        # **The dedupe is a prototype convenience.** On the Z80 the patch is a
        # table of cells with a timer and laying one is a store, so writing the
        # same cell twice costs a second store and nothing else; there is no
        # `seen` set to port.
        if (x, y) not in seen:
            seen.add((x, y))
            cells.append((x, y))

    for d in range(1, REACH + 1):
        half = HALF_WIDTH[d - 1]
        for k in range(-half, half + 1):
            x, y = cell(d, k)
            if not (0 <= x < COLS and 0 <= y < PLAY_ROWS):
                continue          # not this room's cell, so nothing to rebound
            if is_solid is not None and is_solid(x, y):
                if (d - 1, k) == (0, 0):
                    continue      # the player's own cell: refused, poison lost
                x, y = cell(d - 1, k)
                # Same two checks, in the same order, and no second fallback.
                if not (0 <= x < COLS and 0 <= y < PLAY_ROWS):
                    continue
                if is_solid(x, y):
                    continue
            lay(x, y)
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
        (issue #41) -- they fall back one step toward the player instead and
        are stored there if that cell is floor (issue #44).

        **The charge is still spent** when a burst lays nothing at all, which
        the rebound makes rare rather than impossible: over the playtest
        building it happens on 5 of 3,920 standing-cell-by-facing combinations,
        all of them with the player against the building's outer wall, plus
        every burst whose only blocked cell aims its rebound at the player's
        own cell. There the charge is spent and the mistake is the player's --
        whether that should refund or warn is a design question and the code
        should not settle it by accident.
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
