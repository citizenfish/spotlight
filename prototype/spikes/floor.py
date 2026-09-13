"""Marking lit floor.

A lit cell with no pixels set is just black -- ink on black paper with no ink
drawn. So without this, light reveals *objects* but never its own shape, and the
player cannot tell how far their spotlight reaches.

Stippling the floor fixes that, and doing it at two densities gives the fade a
contrast step the palette cannot. LIT and DIM differ by only 255 against 215 on
one channel, which is nearly invisible on a moving sprite; four dots against one
is not.

**The stipple is a noise tile over four cells, not a lattice** (issue #71,
from *The light trail* in the vault). Until then every lit cell wore the same
8x8 pattern -- four dots on a four-pixel pitch -- and other people who saw the
game called the light trail *blocky*. Measured, the word was the lattice: a
set pixel had another four to its right eight times in ten, so any lit region,
whatever its outline, had straight rows of dots in it for the eye to run along
and read as a rectangle or a staircase of them. The Great Escape's gravel, the
reference, is a 32-pixel repeat with nothing lining up at the cell pitch, and
that is what the floor is now: a 32x32 tile of sixteen cells, four dots in
every one and no two dots adjacent anywhere in it, and **a cell wears the block
its position picks** -- `(cy & 3) * 4 + (cx & 3)`, in play-area cell
coordinates. Same densities, same hard cell edge, same light field; only the
arrangement moved, which is why the event log could be pinned byte-identical
across the change and was.

**A painted cell draws no stipple.** The lattice happened to fall between the
letters of a sign written on the floor; the noise does not (`E:X:I:T` in the
mock), so a sign or a shout on floor now sits on black, as a glyph on a wall
already sits on the dim outline: paint hides texture and never shape, one rule
for both grounds. It is one fewer cell to repaint, not one more.

**The dots are not here.** All thirty-two blocks are authored in
`assets/tiles/floor.txt` -- the whole 32x32 tile is drawn in its header, so it
can be read as the picture it is -- and generated into `bitmaps_gen.py` by
`tools/bitmaps.py` (issue #51). The dim block for each cell keeps the first of
its lit block's four dots in reading order and clears the other three, so
lit -> dim is a thinning: the one dot you remember is one of the four you saw.

**On the port** the index is the same arithmetic on the same two low bits, and
the cheap way to get it is worth writing down here because it is not obvious:
the low byte of a cell's *attribute address* is `(cy & 7) << 5 | cx`, so
`ld a,l / and $63` gives `(cy & 3) << 5 | (cx & 3)` in eleven T-states, which
is the block's offset with `cx & 3` still in the low bits. From there:

* a 100-byte lookup (sixteen live entries) that moves those two bits up by
  three -- `ld e,a / ld d,>LOOKUP / ld a,(de) / ld e,a / ld d,>TABLE` -- is 40
  T-states for the whole address, **about 30 over the `ld hl,STIPPLE` it
  replaces**;
* shifting them in code instead of looking them up is 53, about 43 over;
* building the index from `cx` and `cy` held in registers, the obvious
  listing, is 65, about 55 over.

Whichever, it is per *restored* floor cell only -- a cell whose level did not
change is not repainted -- and the repaint figures did not move, because which
block a cell wears changes what it is painted with and never whether it is
painted. The two densities are one page: 128 bytes each, chosen by the high
byte as the old two stipples were.
"""

from spotlight.core.constants import CELL, COLS

from .bitmaps_gen import BITMAPS
from .building import GRATING
from .layout import PLAY_ROWS
from .lighting import DIM, LIT
from .tiles import FURNITURE, FURNITURE_DIM, blit

#: Cells per side of the repeat. The tile is `TILE` x `TILE` cells and a cell's
#: block is chosen by its coordinates modulo this, which is `& 3` because it
#: is a power of two -- the whole reason it is four and not, say, three.
TILE = 4

#: How many blocks a density has: one per cell of the tile, in reading order.
BLOCKS = TILE * TILE


def _table(prefix: str) -> tuple:
    return tuple(BITMAPS[f"{prefix}_{n:02d}"] for n in range(BLOCKS))


#: Four dots in every block -- fully lit ground.
FLOOR_LIT = _table("FLOOR_LIT")

#: One dot in every block, and it is one of the lit block's four -- ground you
#: are remembering rather than seeing.
FLOOR_DIM = _table("FLOOR_DIM")

TABLES = {LIT: FLOOR_LIT, DIM: FLOOR_DIM}

#: What a grating cell draws instead of the stipple, by level (issue #74).
#: A grating is floor -- walkable, remembered, the floor's hue -- wearing a
#: grille instead of the noise, so it is drawn here and by the same two
#: levels, and its dim tile is the lit one thinned by `tiles.dim_of` as every
#: piece of furniture's is.
GRATINGS = {LIT: FURNITURE[GRATING], DIM: FURNITURE_DIM[GRATING]}


def tile_index(cx: int, cy: int) -> int:
    """Which of the sixteen blocks the cell at play-area `(cx, cy)` wears.

    The low two bits of each coordinate, row-major, so `(cx, cy)` and
    `(cx + 4, cy + 4)` wear the same block and neighbours never do. On the
    port this is a mask, a shift and an add on the table base -- see the
    module docstring for the cheap form.
    """
    return ((cy & (TILE - 1)) << 2) | (cx & (TILE - 1))


def tile_at(level: int, cx: int, cy: int):
    """The rows a cell at `level` draws, or `None` if that level draws none.

    DARK draws nothing: it would be invisible anyway -- black ink on black
    paper -- and not drawing it is the same picture for less work.
    """
    table = TABLES.get(level)
    return None if table is None else table[tile_index(cx, cy)]


def dot_at(level: int, x: int, y: int) -> bool:
    """Whether the floor at `level` has a dot at screen pixel `(x, y)`.

    For checking a drawing against the floor it stands on, not for drawing:
    a test that wants to know whether a pixel under a sprite is a stipple dot
    has sixteen blocks to consult now, and this is the one place that knows
    which.
    """
    rows = tile_at(level, x // CELL, y // CELL)
    return bool(rows and rows[y % CELL] & (0x80 >> (x % CELL)))


def stipple(screen, cx: int, cy: int, level: int) -> None:
    """One cell of floor at `level`, by OR, in the block its position picks.

    Sets pixels and never clears them, like every tile: the play area
    composites. No attribute is touched -- light chooses the brightness and
    the room's palette the hue, and a stipple has no opinion about either.
    """
    rows = tile_at(level, cx, cy)
    if rows is None:
        return
    x0, y0 = cx * CELL, cy * CELL
    for dy, bits in enumerate(rows):
        if not bits:
            continue
        base = (y0 + dy) * 256 + x0
        for dx in range(CELL):
            if bits & (0x80 >> dx):
                screen.pixels[base + dx] = 1


def draw(screen, field, is_solid, painted=(), gratings=()) -> None:
    """Stipple every lit, non-solid, unpainted cell according to its level.

    `painted` is the same set `tiles.draw` takes -- the cells a sign or a
    shout is written on -- and those cells draw nothing here: the glyph goes
    down later on black. Solid cells draw nothing because a wall is already
    drawn and dotting it would only muddle the shape.

    `gratings` is the room's grating cells (issue #74). A grating draws its
    tile **instead of** the stipple at the same two levels -- it is a floor
    cell wearing a grille -- and under paint it draws nothing, as the
    stipple does not: paint hides texture. A set rather than a predicate for
    the same reason `painted` is one: the cells are fixed by the map and are
    collected once when the room is entered, and on the port they are the
    map byte this pass has already read to know the cell was floor.
    """
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            level = field.level_at(cx, cy)
            if level not in TABLES or is_solid(cx, cy) or (cx, cy) in painted:
                continue
            if (cx, cy) in gratings:
                blit(screen, cx, cy, GRATINGS[level])
            else:
                stipple(screen, cx, cy, level)
