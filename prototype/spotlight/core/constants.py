"""ZX Spectrum hardware constants.

These are not arbitrary tuning values -- they are the limits of the port target.
The prototype renders through this model so that anything that looks right in
Pygame also fits on real hardware. See CLAUDE.md, "Designing for the port".
"""

# --- Screen geometry -------------------------------------------------------

SCREEN_W = 256
SCREEN_H = 192

CELL = 8                      # attribute cell is 8x8 pixels
COLS = SCREEN_W // CELL       # 32
ROWS = SCREEN_H // CELL       # 24

# --- Timing ----------------------------------------------------------------

FRAME_RATE = 50               # 50Hz interrupt on a PAL Spectrum

# --- Colour ----------------------------------------------------------------
# Eight base colours, indexed 0-7, in Spectrum order. Each attribute cell picks
# one INK and one PAPER from this set, plus a single BRIGHT bit shared by both.
# That is the whole palette for an 8x8 cell -- the cause of attribute clash.

BLACK, BLUE, RED, MAGENTA, GREEN, CYAN, YELLOW, WHITE = range(8)

COLOUR_NAMES = (
    "black", "blue", "red", "magenta", "green", "cyan", "yellow", "white",
)

# RGB for normal and bright intensity. Bright black is identical to black,
# which is why the Spectrum has 15 distinct colours rather than 16.
_NORMAL = 0xD7
_BRIGHT = 0xFF


def rgb(colour: int, bright: bool = False) -> tuple[int, int, int]:
    """Return the RGB triple for a Spectrum colour index."""
    if not 0 <= colour <= 7:
        raise ValueError(f"colour index out of range: {colour}")
    level = _BRIGHT if bright else _NORMAL
    # Bit 0 = blue, bit 1 = red, bit 2 = green.
    return (
        level if colour & 0b010 else 0,
        level if colour & 0b100 else 0,
        level if colour & 0b001 else 0,
    )


PALETTE = tuple(rgb(c, False) for c in range(8))
PALETTE_BRIGHT = tuple(rgb(c, True) for c in range(8))
