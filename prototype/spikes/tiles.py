"""Walls made of something, and doorways that look like doorways.

Issue #48, from *Art Direction* section 3. Before this a wall was
`fill_cell_pixels(on=True)`: a solid 8x8 block of ink, lit or remembered, near
or far. Three faults followed from that one line, and all three are what this
module exists to fix:

* **A remembered wall was as solid as a lit one**, so most of what was on screen
  most of the time was 64 pixels of white and a figure standing against it
  disappeared into it.
* **A one-cell doorway was not a door-shaped thing.** It was an absence, and an
  absence in a dark room is indistinguishable from a room that stops there.
* **A sign ate the wall it was painted on**, because `font.draw_glyph` clears
  the pixels it does not set -- measured at row 15 of room A, where three
  64-pixel wall cells came back at 10 to 17.

The rule everything below draws to:

    **Pattern is a property of light. Shape is a property of the building.**

A wall you can see is made of something; a wall you are only remembering is a
line you once saw. So lit draws outline plus masonry, dim draws the outline
alone, and mask 15 -- a cell deep inside a wall mass, with no outline to
remember -- draws nothing at all when it is only remembered.

**The tiles are not here.** They are authored in `assets/tiles/*.txt` and
generated into `bitmaps_gen.py` by `tools/bitmaps.py`, so the same bytes reach
the Z80 from the same file. The derivation that produced them -- one masonry
interior and four edge elements -- is written into the asset files and checked
against them by `tests/test_spike_tiles.py`, which means a tile can be checked
rather than merely believed while the *file* stays the source of what a wall
looks like.

--- what is refused, and why, so nobody adds it back ----------------------

**No per-room tile index map.** It is the obvious optimisation and it is
backwards on this machine. A wall's mask is fixed by room geometry and never
changes in play, so caching one byte per cell looks free -- but it is 704 bytes
of resident RAM per room against a demand of about a third of a cell a frame,
and recomputing the mask from an 88-byte solidity bitmap is roughly 120
T-states. 704 bytes is more than everything the whole look-and-feel round adds.
If a cache is ever wanted it is **one shared buffer rebuilt on room entry**, not
a map per room.

**No 8-neighbour blob tiling.** It would distinguish the inside corner where two
runs meet diagonally, which the 4-neighbour mask cannot. It costs 47 tiles per
variant -- 752 bytes for the pair -- for a detail nobody looking at a dark room
will miss.

**No rotation.** Six of the sixteen masks are distinct up to rotation and the
other ten are not generated from them: a rotated brick course is not a brick
course, so the symmetry is a fact about the mask and not about the art. Sixteen
tiles at eight bytes is 128 bytes a variant, and a runtime transpose to save 80
of them is not a trade anybody should make.
"""

from spotlight.core.constants import CELL, COLS, SCREEN_W

from .bitmaps_gen import BITMAPS
from .layout import PLAY_ROWS
from .lighting import DARK, DIM

#: The four neighbour bits. **Set when that neighbour is also wall**, and off
#: the room counts as wall -- which is what makes the outer wall show one face,
#: inward, and nothing get drawn against the screen edge.
NORTH, EAST, SOUTH, WEST = 1, 2, 4, 8

#: How many tiles a variant has. Four neighbours, so sixteen, and they are
#: **stored in mask order** so the game indexes the table with the mask and
#: needs no lookup at all.
MASKS = 16


def _table(prefix: str) -> tuple:
    return tuple(BITMAPS[f"{prefix}_{mask:02d}"] for mask in range(MASKS))


#: A wall you can see: outline plus masonry.
WALL_LIT = _table("WALL_LIT")

#: A wall you are only remembering: the outline alone. Mask 15 is empty.
WALL_DIM = _table("WALL_DIM")

#: The returns for a `d` cell: short ticks continuing each wall it touches into
#: the opening. One table, drawn at either light level, because a doorway's
#: returns *are* its shape -- there is no texture to take away.
DOORWAY = _table("DOORWAY")


def mask_at(is_wall, cx: int, cy: int) -> int:
    """The 4-neighbour mask for the cell at (cx, cy).

    `is_wall` must answer for cells **off** the room as well as in it, and must
    answer True there: off the room counts as wall, which is what makes the
    outer wall show one face -- inward -- and nothing get drawn against the
    screen edge. `Room.is_wall` does exactly that, and so does the gallery's
    test plan; the rule lives in the predicate rather than here so that this
    stays four bit tests and nothing else.

    **Recomputed, never stored** -- see the module docstring. On the Z80 this is
    four bit tests against an 88-byte solidity bitmap with an implicit solid
    border, about 120 T-states.
    """
    mask = 0
    if is_wall(cx, cy - 1):
        mask |= NORTH
    if is_wall(cx + 1, cy):
        mask |= EAST
    if is_wall(cx, cy + 1):
        mask |= SOUTH
    if is_wall(cx - 1, cy):
        mask |= WEST
    return mask


def blit(screen, cx: int, cy: int, rows) -> None:
    """Draw one 8x8 tile into a cell. **Sets pixels, never clears them.**

    The same rule as a sprite: everything in the play area composites over what
    is already there. It is also what lets a sign be painted on a wall rather
    than punched through it -- the glyph goes on top and the outline survives.

    No attribute is touched. Light chooses the brightness and the room's
    palette chooses the hue, and a tile is allowed no opinion about either.
    """
    x0, y0 = cx * CELL, cy * CELL
    for dy, bits in enumerate(rows):
        if not bits:
            continue
        base = (y0 + dy) * SCREEN_W + x0
        for dx in range(CELL):
            if bits & (0x80 >> dx):
                screen.pixels[base + dx] = 1


def draw(screen, room, field, painted=()) -> None:
    """Every wall and doorway in the room, at the level each cell is showing.

    `painted` is the cells a sign or a shout is written on. **A painted cell
    draws the dim variant whatever its light level**, so the wall's outline
    runs unbroken through the word and only the masonry is lost, where the
    paint is. One rule for signs and for walls: paint hides texture and never
    shape.

    A dark cell draws nothing. It would be invisible anyway -- DARK is black ink
    on black paper -- so this is the same picture for less work, and it is the
    picture the port draws too.
    """
    is_wall = room.is_wall
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            wall = is_wall(cx, cy)
            if not wall and not room.is_doorway(cx, cy):
                continue
            level = field.level_at(cx, cy)
            if level == DARK:
                continue
            mask = mask_at(is_wall, cx, cy)
            if not wall:
                rows = DOORWAY[mask]
            elif level == DIM or (cx, cy) in painted:
                rows = WALL_DIM[mask]
            else:
                rows = WALL_LIT[mask]
            blit(screen, cx, cy, rows)


def ink_of(rows) -> int:
    """How many pixels a tile sets. For checking art, not for drawing."""
    return sum(bin(bits).count("1") for bits in rows)
