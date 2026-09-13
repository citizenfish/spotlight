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
line you once saw, with the courses of the brick still faintly in it. So lit
draws outline plus masonry, and dim draws the outline plus the two mortar
courses **dotted**, at the same rows, with no joints.

**The dim set was the outline alone until issue #62**, and mask 15 -- a cell
deep inside a wall mass, with no outline to remember -- drew nothing. That was
by design and it was what a player saw for most of a run: the torch is off for
80 to 95 per cent of one, so the walls beside you were plan lines nearly all
the time, and the user reported it as "the walls need more texture, I think
this is a render bug". It was not -- zero mismatches in 890,471 cell checks --
and the ruling was that the remembered wall keeps its courses, so the flip
between lit masonry and remembered outline under the cone is smaller. The
courses are dotted because solid ones read as ladder rungs on a north-south
run; see `assets/tiles/wall_dim.txt`, which is where that rule is kept beside
the art. The fade was not touched: a longer hold for wall cells was a different
option of the same ruling and was not chosen.

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
from .building import FURNITURE as FURNITURE_KINDS
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

#: A wall you are only remembering: the outline, and the mortar courses as a
#: dotted line. Mask 15 is the two courses and nothing else (8 pixels; it was
#: empty before issue #62).
WALL_DIM = _table("WALL_DIM")

#: The returns for a `d` cell: short ticks continuing each wall it touches into
#: the opening. One table, drawn at either light level, because a doorway's
#: returns *are* its shape -- there is no texture to take away.
DOORWAY = _table("DOORWAY")


# --- furniture (issue #74) ---------------------------------------------------
#
# Things that are simply there. A solid piece is a wall cell wearing its own
# tile and a grating is a floor cell wearing its own, and this is the whole of
# what the drawing knows about them: **the tile is looked up by the map
# character, and the mask is not computed at all.** A crate is a crate
# whichever walls it touches, which is what makes it a crate and not more
# masonry, and it is also why a furniture cell costs the port less than a wall
# cell -- no four bit tests, one table entry.
#
# **It never draws the masonry underneath.** The obvious alternative -- draw
# the wall tile and OR the crate over it -- was not tried, because it cannot
# work: the wall tile's outline is the crate's outline and its courses would
# run through the lid. A furniture cell draws instead of, not on top of.

#: The bit each row of a dim tile keeps: every other pixel, and the phase
#: alternates by row so the ghost is a checker and not a set of stripes.
#: Even rows keep the even pixels (bit 7 is pixel 0), odd rows the odd ones.
DIM_EVEN, DIM_ODD = 0xAA, 0x55


def dim_of(rows) -> tuple:
    """The remembered variant of a lit tile: the rule, and the whole of it.

    Row `y` ANDed with `DIM_EVEN` when `y` is even and `DIM_ODD` when odd, so
    a remembered crate is the crate's ghost -- the Knight Lore coarser dither
    -- and nobody draws a second set of tiles that could drift from the
    first. The wall's dim set is authored, because *its* rule (outline plus
    dotted courses) is not a function of the lit tile; furniture has no such
    rule, only less of itself.

    **Generated at load and not by the converter**, on purpose: the port
    stores the 56 lit bytes and applies the rule as it draws -- an `and`
    per row, 56 T-states a cell with the eight rows unrolled and the masks
    immediate, about 130 with a register mask flipped each row -- rather
    than holding a second 56-byte table. Either is affordable, and only a
    dim furniture cell whose level just changed pays it. The prototype does
    at load what the port does per cell so that the generated files hold
    what the port's ROM holds. If the port ends up storing the dim table
    instead, this is where to say so.

    **One tile the rule does not thin**: the grating as authored is three
    rows of dots on the odd pixels of odd rows, the half the rule keeps, so
    its ghost is itself. Found building this and left as drawn -- see the
    asset's header and `tests/test_spike_furniture.py`, which pins it until
    the designer says whether the tile or the rule gives.
    """
    return tuple(bits & (DIM_ODD if y & 1 else DIM_EVEN)
                 for y, bits in enumerate(rows))


#: Which tile each furniture character wears, lit. Keyed by the legend
#: character because that is what the map holds and what the drawing reads;
#: the tile's name is the asset's business. `GRATING` is in here too, so the
#: floor pass can look it up the same way, but `draw` below never draws it:
#: a grating is floor and floor is `floor.draw`'s.
FURNITURE = {
    kind: BITMAPS[name]
    for kind, name in zip(FURNITURE_KINDS, ("PIPE_H", "PIPE_V", "CRATE",
                                            "DESK_L", "DESK_R", "CABINET",
                                            "GRATING"))
}

#: The same, remembered: `dim_of` each lit tile, once, at load.
FURNITURE_DIM = {kind: dim_of(rows) for kind, rows in FURNITURE.items()}


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

    **A solid furniture cell draws its own tile instead of the wall's** (issue
    #74), at the same two levels by the same rule -- lit tile at LIT, dim
    tile at DIM or under paint -- and computes no mask. Its *neighbours'*
    masks see it as wall, because `is_wall` does; that is what makes a pipe
    run along a partition read as one thing and the partition's end cap
    still cap it. The grating is not drawn here: it is floor, and floor is
    `floor.draw`'s to stipple.
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
            dim = level == DIM or (cx, cy) in painted
            kind = room.furniture_at(cx, cy) if wall else None
            if kind is not None:
                rows = (FURNITURE_DIM if dim else FURNITURE)[kind]
            else:
                mask = mask_at(is_wall, cx, cy)
                if not wall:
                    rows = DOORWAY[mask]
                elif dim:
                    rows = WALL_DIM[mask]
                else:
                    rows = WALL_LIT[mask]
            blit(screen, cx, cy, rows)


def ink_of(rows) -> int:
    """How many pixels a tile sets. For checking art, not for drawing."""
    return sum(bin(bits).count("1") for bits in rows)
