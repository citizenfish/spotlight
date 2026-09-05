"""The Spectrum display model: a 1-bit bitmap plus a coarse attribute grid.

Rendering through this class is what keeps the prototype honest. Pixels carry
no colour of their own -- they are only set or clear. All colour lives in the
32x24 attribute grid, one ink and one paper per 8x8 cell. If a lighting effect
cannot be expressed here, it will not survive the port.

Attribute bytes use the real hardware layout, so this data can be handed
straight to the Z80 side:

    bit 7   flash
    bit 6   bright
    bits 5-3 paper
    bits 2-0 ink
"""

from .constants import BLACK, CELL, COLS, ROWS, SCREEN_H, SCREEN_W, WHITE


def attr_byte(ink: int, paper: int, bright: bool = False, flash: bool = False) -> int:
    """Pack ink/paper/bright/flash into a hardware attribute byte."""
    if not 0 <= ink <= 7:
        raise ValueError(f"ink out of range: {ink}")
    if not 0 <= paper <= 7:
        raise ValueError(f"paper out of range: {paper}")
    return (ink & 0b111) | ((paper & 0b111) << 3) | (bright << 6) | (flash << 7)


def unpack_attr(byte: int) -> tuple[int, int, bool, bool]:
    """Inverse of :func:`attr_byte` -- returns (ink, paper, bright, flash)."""
    return (
        byte & 0b111,
        (byte >> 3) & 0b111,
        bool(byte & 0b0100_0000),
        bool(byte & 0b1000_0000),
    )


DEFAULT_ATTR = attr_byte(ink=WHITE, paper=BLACK)


class Screen:
    """A Spectrum framebuffer. Pure data -- no rendering library involved."""

    __slots__ = ("pixels", "attrs")

    def __init__(self) -> None:
        # One byte per pixel is wasteful compared to the real 1bpp layout, but
        # this is the prototype; what matters is that a pixel is on or off.
        self.pixels = bytearray(SCREEN_W * SCREEN_H)
        self.attrs = bytearray([DEFAULT_ATTR] * (COLS * ROWS))

    # --- pixels ------------------------------------------------------------

    def clear(self, attr: int = DEFAULT_ATTR) -> None:
        """Blank every pixel and reset the whole attribute grid."""
        self.pixels[:] = bytes(len(self.pixels))
        self.attrs[:] = bytes([attr]) * len(self.attrs)

    def plot(self, x: int, y: int, on: bool = True) -> None:
        if 0 <= x < SCREEN_W and 0 <= y < SCREEN_H:
            self.pixels[y * SCREEN_W + x] = 1 if on else 0

    def point(self, x: int, y: int) -> bool:
        if 0 <= x < SCREEN_W and 0 <= y < SCREEN_H:
            return bool(self.pixels[y * SCREEN_W + x])
        return False

    def fill_cell_pixels(self, cx: int, cy: int, on: bool = True) -> None:
        """Set or clear all 64 pixels of one attribute cell."""
        if not (0 <= cx < COLS and 0 <= cy < ROWS):
            return
        value = 1 if on else 0
        for row in range(cy * CELL, cy * CELL + CELL):
            start = row * SCREEN_W + cx * CELL
            self.pixels[start:start + CELL] = bytes([value]) * CELL

    # --- attributes --------------------------------------------------------

    def set_attr(self, cx: int, cy: int, attr: int) -> None:
        if 0 <= cx < COLS and 0 <= cy < ROWS:
            self.attrs[cy * COLS + cx] = attr

    def get_attr(self, cx: int, cy: int) -> int:
        if 0 <= cx < COLS and 0 <= cy < ROWS:
            return self.attrs[cy * COLS + cx]
        return DEFAULT_ATTR

    def attr_at_pixel(self, x: int, y: int) -> int:
        """The attribute governing the pixel at (x, y)."""
        return self.get_attr(x // CELL, y // CELL)
