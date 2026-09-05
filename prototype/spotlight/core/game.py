"""Game state and the per-frame update.

WALKING SKELETON. This is deliberately not a design. It exists to prove the
loop -- input to state to screen -- runs end to end at 50Hz through the
attribute model. The actual mechanics come from the spec notes in the vault
(../spotlight_kb) by way of a GitHub issue; replace this when that lands.

Nothing in this module may import pygame.
"""

from .constants import BLACK, CELL, COLS, ROWS, WHITE, YELLOW
from .screen import Screen, attr_byte

DARK = attr_byte(ink=BLACK, paper=BLACK)
LIT = attr_byte(ink=YELLOW, paper=BLACK, bright=True)
PLAYER = attr_byte(ink=WHITE, paper=BLACK, bright=True)


class Game:
    """Player position on the attribute grid, and a radius of light."""

    def __init__(self) -> None:
        self.x = COLS // 2
        self.y = ROWS // 2
        self.light_radius = 3

    def update(self, dx: int, dy: int) -> None:
        """Advance one frame. dx/dy are -1, 0 or 1 in cell units."""
        self.x = max(0, min(COLS - 1, self.x + dx))
        self.y = max(0, min(ROWS - 1, self.y + dy))

    def draw(self, screen: Screen) -> None:
        """Paint the world as attribute cells -- the port has to do the same."""
        screen.clear(DARK)
        r = self.light_radius
        for cy in range(self.y - r, self.y + r + 1):
            for cx in range(self.x - r, self.x + r + 1):
                if not (0 <= cx < COLS and 0 <= cy < ROWS):
                    continue
                # Squared distance keeps this integer-only.
                if (cx - self.x) ** 2 + (cy - self.y) ** 2 <= r * r:
                    screen.set_attr(cx, cy, LIT)
                    screen.fill_cell_pixels(cx, cy, on=False)
                    # A single ink pixel per lit cell: enough to read the lit
                    # area without pretending we have per-pixel colour.
                    screen.plot(cx * CELL + CELL // 2, cy * CELL + CELL // 2)
        screen.set_attr(self.x, self.y, PLAYER)
        screen.fill_cell_pixels(self.x, self.y, on=True)
