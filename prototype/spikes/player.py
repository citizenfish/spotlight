"""The player: pixel movement, facing, and wall collision.

Responsiveness is a stated design requirement, not a nicety, so input is read
every frame and acted on the same frame. Nothing here buffers, smooths or
accelerates -- a key down means moving now, a key up means stopped now.

Movement is by pixel, per the spike 1 finding, but collision is tested against
the **cell** grid, because that is what the Z80 will have: a byte per cell, not
a pixel-level map.
"""

from spotlight.core.constants import CELL

from .layout import PLAY_ROWS
from .sources import DOWN, LEFT, RIGHT, UP
from .walk import Stride

#: Pixels per frame. At 50Hz, 1 is a slow walk and 2 is brisk.
SPEED = 1

#: A person is 8 wide and 16 tall.
WIDTH, HEIGHT = 8, 16

#: How far the player is nudged sideways to fit through a gap they are almost
#: lined up with. **A whole cell.**
#:
#: Without this, an 8-wide sprite only fits a one-cell doorway when its x is an
#: exact multiple of 8 -- one position in eight. Everything else stops dead
#: against the door frame, which reads as the controls being broken rather than
#: as the player being misaligned.
#:
#: Half a cell to a whole one with issue #23, because **the failing case is not
#: the one the assist was written for.** Lining up with a gap is never more
#: than four pixels away, so half a cell covers it -- but *clearing a wall your
#: head is already inside* can need seven, and that is what leaves a walker
#: grinding against geometry. Measured: a random walker spent 29-42% of its
#: pressing frames blocked, in stretches of up to fourteen seconds, which no
#: first-timer does.
#:
#: The loop below tries the smallest offset first and stops at the first one
#: that works, so seven pixels only ever happens when nothing smaller does. The
#: cost of raising the ceiling is therefore the rare case, not the common one.
NUDGE = CELL

#: facing -> (dx, dy), and its inverse.
STEP = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}


class Player:
    """Position in pixels, facing in cells, and where he is in his stride."""

    __slots__ = ("x", "y", "facing", "walk")

    def __init__(self, x: int, y: int, facing: int = RIGHT) -> None:
        self.x, self.y = x, y
        self.facing = facing
        #: **Where he is in the walk cycle** (issue #72): a `walk.Stride`,
        #: stepped in `move` after both axes have resolved, advancing every
        #: four pixels of travel along either axis and at no other time. The
        #: cadence is movement, as a Cleg's wing is on a step; it was one bit
        #: flipped on a cell crossing (issue #60), which the user played and
        #: found too slow to read as a walk -- see `walk` for the argument.
        #:
        #: **Drawing state, and nothing in the rules reads it.** The event log
        #: is byte-identical with it and without it, and a test pins that by
        #: setting it by hand every frame and comparing the logs. It adds no
        #: dirty cell either: it only changes on a frame he moved, and on such
        #: a frame he is being erased and redrawn anyway.
        self.walk = Stride(x, y)

    @property
    def stride(self) -> int:
        """0-3: the index into `sprites.PLAYER_FRAMES`, the cycle `N A N B`."""
        return self.walk.index

    # --- where the player is, in cells --------------------------------------

    @property
    def cx(self) -> int:
        """The cell column the player's centre is in."""
        return (self.x + WIDTH // 2) // CELL

    @property
    def cy(self) -> int:
        """The cell row the player's feet are in.

        Feet rather than centre: a person is two cells tall, and what matters
        for lighting and collision is the ground they are standing on.
        """
        return (self.y + HEIGHT - 1) // CELL

    def body_cells(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """The two cells the player is standing in: their feet, and their head.

        A person is 8x16 -- two cells tall, one wide when aligned -- and this
        is that pair, taken from the centre column so a sprite straddling two
        columns still answers for one of them.

        Not the same question as `occupied_cells`, which is the honest box and
        can be six cells while straddling both axes. That is what reaching a
        worker and touching the exit ask, because an outstretched arm counts.
        This is the narrower one -- *where is this person standing* -- and it
        is what issue #39 needed: a spray charge douses a fresh body the
        player's own two cells overlap, whichever way they are facing. On the
        Z80 that is two compares, at the moment a charge is spent and never
        per frame.

        `cy - 1` can be -1 if the player is somehow against the top of the
        play area. Nothing is ever at row -1, so it simply never matches and
        needs no clamp.
        """
        return ((self.cx, self.cy), (self.cx, self.cy - 1))

    def occupied_cells(self):
        """Every cell the sprite overlaps."""
        return {
            (cx, cy)
            for cx in range(self.x // CELL, (self.x + WIDTH - 1) // CELL + 1)
            for cy in range(self.y // CELL, (self.y + HEIGHT - 1) // CELL + 1)
        }

    # --- movement -----------------------------------------------------------

    def _blocked(self, x: int, y: int, is_solid) -> bool:
        """Would the sprite's box overlap a solid cell at this position?"""
        for cx in range(x // CELL, (x + WIDTH - 1) // CELL + 1):
            for cy in range(y // CELL, (y + HEIGHT - 1) // CELL + 1):
                if is_solid(cx, cy):
                    return True
        return False

    def move(self, dx: int, dy: int, is_solid) -> bool:
        """Step by (dx, dy) in units of SPEED. Returns True if anything moved.

        The axes are resolved separately, so walking into a wall at an angle
        slides along it rather than stopping dead. Stopping dead on a diagonal
        feels broken, and the player would blame the controls.

        A blocked move is retried with a small sideways nudge, so walking into a
        doorway you are nearly lined up with takes you through it instead of
        stopping against the frame. See NUDGE.
        """
        if dx:
            self.facing = RIGHT if dx > 0 else LEFT
        elif dy:
            self.facing = DOWN if dy > 0 else UP

        moved = False
        if dx:
            moved |= self._step(dx * SPEED, 0, is_solid)
        if dy:
            moved |= self._step(0, dy * SPEED, is_solid)
        # The stride is judged once, after both axes have resolved, so a
        # diagonal step is one stride and not two, and a nudge that carries
        # the figure sideways counts as the travel it is. See `walk`.
        self.walk.moved_to(self.x, self.y)
        return moved

    def _step(self, dx: int, dy: int, is_solid) -> bool:
        """One axis, with corner assist."""
        nx, ny = self.x + dx, self.y + dy
        if not self._blocked(nx, ny, is_solid):
            self.x, self.y = nx, ny
            return True

        # Blocked. Are we nearly lined up with a gap? Try the smallest nudge
        # first, so the player is never moved further than necessary.
        for offset in range(1, NUDGE + 1):
            for sign in (1, -1):
                if dx:                      # moving horizontally: nudge in y
                    tx, ty = nx, self.y + sign * offset
                else:                       # moving vertically: nudge in x
                    tx, ty = self.x + sign * offset, ny
                if not self._blocked(tx, ty, is_solid):
                    self.x, self.y = tx, ty
                    return True
        return False

    def ahead(self) -> tuple[int, int]:
        """The cell directly in front, where the spray lands."""
        sx, sy = STEP[self.facing]
        return self.cx + sx, self.cy + sy
