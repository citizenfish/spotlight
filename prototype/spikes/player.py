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

#: Pixels per frame. At 50Hz, 1 is a slow walk and 2 is brisk.
SPEED = 1

#: A person is 8 wide and 16 tall.
WIDTH, HEIGHT = 8, 16

#: How far the player is nudged sideways to fit through a gap they are almost
#: lined up with. Half a cell, so any approach can be corrected.
#:
#: Without this, an 8-wide sprite only fits a one-cell doorway when its x is an
#: exact multiple of 8 -- one position in eight. Everything else stops dead
#: against the door frame, which reads as the controls being broken rather than
#: as the player being misaligned.
NUDGE = CELL // 2

#: facing -> (dx, dy), and its inverse.
STEP = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}


class Player:
    """Position in pixels, facing in cells."""

    __slots__ = ("x", "y", "facing")

    def __init__(self, x: int, y: int, facing: int = RIGHT) -> None:
        self.x, self.y = x, y
        self.facing = facing

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
        """The cell directly in front, where the cone starts and spray lands."""
        sx, sy = STEP[self.facing]
        return self.cx + sx, self.cy + sy
