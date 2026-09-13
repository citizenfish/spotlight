"""One command that writes everything somebody judging the look has to see.

Issue #45. The look-and-feel round asks two playtester agents and the user to
have an opinion about the art, and until now the only way to see any of it was
to be sitting at the user's keyboard. `--snap` on the driver photographs a run;
this is the other half -- the things that are **not** a run and would otherwise
never be photographed at all: the two screens either side of the game, the
sprites at the size they are actually drawn, and each room both fully lit and
as it looks when you are in it with a torch.

Three choices worth stating, because each of them is the sheet being useful
rather than merely correct:

* **The lit shots use `sources.Flash.hold`**, the debug reveal the `F` key has
  used since the spike, rather than a new "draw everything" path. A second way
  to light a room is a second thing that can disagree with the game about what
  is in the room -- and the whole value of these images is that they are what
  the game draws.
* **The played shots hold the torch on, and one of them does not.** With it
  off the honest picture is very nearly a black rectangle, which is true to
  the game and of limited use for judging a sprite; so the walk, the body and
  the lamp are judged with the torch on. But **the torch is off for 80 to 95
  per cent of a run** (the tester's figure, 2026-09-11), and every mock before
  the after-look-1 round was drawn with it on -- which is how the walls could
  be reviewed for three rounds and still be reported as "no texture" by the
  user. Since issue #62 the sheet carries the near room at the same played
  frame with the torch off, because that is the frame the game is played in.
* **The ending screen's numbers are invented, and deliberately.** They are
  chosen to fill every row -- somebody out, somebody dead, somebody still
  inside, and a time with two digits in the minutes place -- so the sheet shows
  the layout under load. Taking them from a real run instead would repaint this
  image every time a constant moved, and a gallery whose files churn is a
  gallery nobody can diff between rounds.

Host-side, named `spike_*` so the portability suite exempts it: it exists to
make PNGs for people, and nothing on a Spectrum will ever run it.

The tile sheet arrived with issue #48: every wall and doorway tile at both
light levels, and a joined-up plan drawn through the real mask arithmetic, so
that a seam in the masonry is visible in a picture rather than only findable by
somebody counting pixels.

Issue #49 added the fourth room shot, and it is the one thing here that is set
up rather than played. **`LAMP_ON` cannot be photographed from a bot run**:
every authored spotlight starts unlit, a floor light only lights by being
swapped for a burning one, and `spotlight_swaps` is 0 in every run any bot has
ever made. `swapped_room` makes the swap happen with the game's own rule and
the game's own code rather than lighting one in the level data, which would be
a change to where the light in this building is. **And the sheet is where art
is named, not where it is judged** -- both faults that slice fixed passed on a
black-paper sprite sheet and failed on a lit floor, because a floor stipple is
itself a fill, so the room shots are what a reviewer looks at.

**The people have a sheet of their own since issue #72.** Eight frames took
the sprite sheet past what fits between its heading and its legend, and a
walk cannot be judged from frames in a grid anyway: the people sheet puts each
figure on a row, its frames labelled on the left and its walk on the right as
a strip -- the cycle `N A N B` twice over, each stride drawn four pixels
further along than the last, with four pixels of floor between the boxes so
the strides can be told apart. The played rooms are photographed on each of
the four strides, so a reviewer has the walk where a figure is actually seen.
"""

import os

from spotlight.core.constants import (
    BLACK, CELL, COLS, CYAN, ROWS, SCREEN_H, SCREEN_W, WHITE, YELLOW,
)
from spotlight.core.screen import Screen, attr_byte

from . import bots, floor, lighting, moments, player as player_mod
from . import screens, scene, sprites
from . import session as session_mod, tiles, walk
from . import spike_snap
from . import building
from .building import EAST

#: How many frames into a run the "as played" shot of a room is taken.
#: Six seconds: long enough that the opening flash has faded and the swarm has
#: started moving, short enough that the torch is still lit.
PLAYED_FRAMES = 300

#: The seed every gallery run uses, so the same command twice writes the same
#: pictures. A gallery that changed under you could not be used to review a
#: change to the art.
GALLERY_SEED = 1

#: The ending the sheet shows, and the counts underneath it. See the module
#: docstring for why these are invented rather than played.
ENDING = session_mod.NO_LIVES
ENDING_COUNTS = dict(rescued=2, lost=4, inside=1, total=7, seconds=154)


def _attr(ink: int, bright: bool = False) -> int:
    return attr_byte(ink=ink, paper=BLACK, bright=bright)


# --- the sprite sheet -------------------------------------------------------

#: Blocks across the sheet, and how big each is in cells.
#:
#: Three across at ten wide leaves the right-hand block eleven columns of the
#: thirty-two, which is what DOOR LOCKED needs -- `sprites.SPRITES` is ordered
#: so the door pair lands there, and `test_spike_gallery` fails if a caption
#: ever overruns its block. Three rows per block: two for the sprite, because
#: the 8x16 ones fill both, and one for its name underneath.
#:
#: The blank row the blocks used to carry went when the sheet grew from eight
#: entries to fourteen. Seventeen with the people's second frames (issue #60)
#: filled every row between the heading and the legend exactly, and the third
#: frames (issue #72) would have taken it to nineteen, which does not fit --
#: so the people moved to a sheet of their own, `draw_people_sheet`, and this
#: one holds the objects, the doors and the body: twelve entries with the
#: Cleg's third frame (issue #73), four rows.
#: `test_spike_gallery` says so before anything prints into the legend.
_ACROSS = 3
_BLOCK_W = 10
_BLOCK_H = 3
_LEFT = 1
_TOP = 3

#: The stippled ground under each sprite on the sheet, in cells from the
#: block's left edge: the sprite's own cell or two, and a cell of floor either
#: side of it, so the halo is seen against stipple that carries on unbroken
#: past the box. Two rows deep, because the box is.
_GROUND = range(2, 6)


def block_at(n: int) -> tuple[int, int]:
    """Where the nth entry's block starts, in cells."""
    return (_LEFT + (n % _ACROSS) * _BLOCK_W,
            _TOP + (n // _ACROSS) * _BLOCK_H)


def block_width(n: int) -> int:
    """How many columns the nth entry's caption may use.

    The last block in a row gets whatever is left of the screen, which is one
    column more than the others -- and that column is the difference between
    DOOR LOCKED fitting and printing over its neighbour.
    """
    if n % _ACROSS == _ACROSS - 1:
        return COLS - (_LEFT + (_ACROSS - 1) * _BLOCK_W)
    return _BLOCK_W


def sprite_top(cy: int, height: int) -> int:
    """The y, in pixels, of a sprite of that height in a block starting at `cy`.

    **Every sprite stands on its own caption**: the box's bottom edge is the
    row above the name, whatever height the box is. An 8x16 figure therefore
    fills both rows of the block and an 8x8 object fills the lower one.

    Top-aligning them was tried first and read wrong. With three rows to a
    block, a top-aligned 8x8 object sits one row under the *previous* block's
    caption and two rows above its own, so the eye pairs it with the wrong
    name -- which on the one sheet in the game whose job is naming things is
    the whole of the job.
    """
    return (cy + _BLOCK_H - 1) * CELL - height


def stipple_cell(screen: Screen, cx: int, cy: int) -> None:
    """One cell of lit floor, drawn with the game's own stipple by OR.

    The block is the one the cell's position picks (issue #71), exactly as in
    a room, so the ground under a sprite on the sheet is the noise the game
    draws and not a lattice the game no longer has.
    """
    floor.stipple(screen, cx, cy, lighting.LIT)


def label(name: str) -> str:
    """What an entry is called on the sheet.

    The key from `sprites.SPRITES`, upper-cased, with the underscore as a
    space, because the game's font has no underscore in it and a missing glyph
    would print as the error block.
    """
    return name.upper().replace("_", " ")


def draw_sprite_sheet(screen: Screen) -> None:
    """Every sprite in the game, on a grid, named in the game's own font.

    **The sizes are shown, not stated.** Each block is two cell rows tall, so
    the 8x16 people fill it, the 8x8 objects fill half of it and the 16x8 body
    lies along the bottom of it, and the difference between a person, a thing
    and a corpse is visible in the picture rather than only in the caption.
    That difference is load-bearing -- `sprites` tells entities apart by size
    first and silhouette second, because a sprite may not choose its own colour
    -- so a sheet that lined everything up neatly would be hiding the one
    property the art has to get right.

    **And the sheet is not evidence** (issue #59). It showed a sprawled body
    for three rounds while the played screen showed a person-shaped smudge, so
    a picture of this sheet does not settle whether a sprite reads. That is
    what `body_room` is for, and why the walk is photographed in a played
    room on every stride rather than judged from the frames on a sheet.

    **The standing figures are not on it since issue #72**; they are on
    `draw_people_sheet`, with their walk. Eight frames of people took this
    grid past what fits between its heading and its legend, and a grid could
    not show a walk anyway. The body stays here: it is a person, but it does
    not walk, and it is the one sprite whose size has to be seen beside the
    objects'.

    **Every sprite stands on lit stipple** (issue #70), a patch of floor a
    cell wider than its box on either side, so the mask can be seen doing its
    job: the dots stop a pixel short of the ink inside the box and carry on
    unbroken outside it. On black paper the halo is invisible, and a sheet
    that could not show the one thing the round added would be no use for
    judging it.

    Labelled in the game's font rather than anything prettier, for the same
    reason the rest of the sheet is drawn through `core.Screen`: what a reviewer
    is looking at has to be made of the things the Spectrum can make.
    """
    screen.clear(_attr(WHITE))
    heading = "SPRITE SHEET"
    screens.write(screen, screens.centre(heading), 1, heading, YELLOW,
                  bright=True)

    for n, (name, sprite) in enumerate(sheet_entries()):
        cx, cy = block_at(n)
        # Three cells in, so the 8-pixel sprite sits over the middle of its
        # caption rather than at one end of it. The 16-wide body starts there
        # too and takes the cell after it, which is still inside its block.
        px, py = (cx + 3) * CELL, sprite_top(cy, len(sprite))
        ground(screen, cx + _GROUND.start, cx + _GROUND.stop - 1, cy)
        # clip_bottom is the play area's floor in the game and there is no play
        # area here, so it is opened up to the whole screen; without that the
        # bottom row of the grid would be cut off mid-sprite.
        sprites.draw(screen, sprite, px, py, clip_bottom=SCREEN_H)
        people = name in sprites.PEOPLE
        screens.write(screen, cx, cy + 2, label(name),
                      YELLOW if people else CYAN, bright=True)

    legend = (("YELLOW - BODY 16X8, PEOPLE SHEET", YELLOW),
              ("CYAN - OBJECTS 8X8, DOORS 8X16", CYAN))
    for i, (line, ink) in enumerate(legend):
        screens.write(screen, screens.centre(line), ROWS - 3 + i, line, ink,
                      bright=True)


def sheet_entries() -> list:
    """What the sprite sheet shows, in order: every drawable that is not a
    standing figure's frame. The people are on their own sheet."""
    return [(name, sprite) for name, sprite in sprites.SPRITES.items()
            if name not in sprites.FRAMES]


def ground(screen: Screen, first_cx: int, last_cx: int, cy: int) -> None:
    """Two rows of lit floor from `first_cx` to `last_cx` inclusive, on which
    a sprite is then drawn with its mask, in the order the game draws them."""
    for gx in range(first_cx, last_cx + 1):
        for gy in (cy, cy + 1):
            stipple_cell(screen, gx, gy)
            screen.set_attr(gx, gy, _attr(WHITE, bright=True))


# --- the people sheet -------------------------------------------------------
#
# A row per standing figure (issue #72): the figure's name, its unique frames
# each on their own patch of floor with a letter underneath, and for the two
# that walk, the walk itself laid out as a strip.

#: The first figure's block, and how many rows each takes: the name, two rows
#: of sprite, a row of captions, and a gap.
_PEOPLE_TOP = 3
_PEOPLE_BLOCK_H = 5

#: The columns a figure's unique frames stand in, each on a patch of floor a
#: cell either side, with a cell of black between one patch and the next.
#: The worker's two are a column further apart than a walker's three, because
#: their captions are words rather than letters and CALL and WAVE printed as
#: one word on the first sheet.
_FRAME_CX = {"player": (2, 6, 10), "follower": (2, 6, 10), "worker": (2, 7)}

#: Where the walk strip starts, in cells; how far apart its strides are, in
#: pixels; and how many strides it shows.
#:
#: **Twelve pixels a stride: the eight of the box and the four the figure
#: travelled.** The cadence is four pixels of travel, so consecutive frames of
#: the walk are four pixels apart on screen and overlap by half a box; drawn
#: that way a strip is a smear. Adding the box's own width between them keeps
#: the four-pixel advance visible -- each stride sits one third of a box
#: further right than a plain grid would put it -- and leaves four pixels of
#: floor between boxes so the halo is seen against stipple, not against the
#: next stride. Eight strides is the cycle twice.
_STRIP_CX = 14
_STRIP_PITCH = sprites.WIDTH + walk.STRIDE_PIXELS
_STRIP_STRIDES = 2 * walk.STRIDES

#: The caption under each unique frame: a letter for a walker's, and words for
#: the waiting worker's two, which are not strides.
_FRAME_CAPTIONS = {
    "player": ("N", "A", "B"), "follower": ("N", "A", "B"),
    "worker": ("CALL", "WAVE"),
}

#: The walk cycle each walker's strip is drawn from, by figure name. The
#: waiting worker has none: it does not walk.
_WALKS = {"player": sprites.PLAYER_FRAMES, "follower": sprites.FOLLOWER_FRAMES}


def people_rows() -> list:
    """The figures on the people sheet, top to bottom, with the top row of
    each one's block. Walkers first, so the two strips sit together."""
    order = ("player", "follower", "worker")
    return [(name, _PEOPLE_TOP + i * _PEOPLE_BLOCK_H)
            for i, name in enumerate(order)]


def people_sheet_entries() -> list:
    """Every sprite the people sheet draws, as `(caption, sprite, px, py)`.

    The unique frames of each figure first, then its walk strip. The test
    reads this back to check every entry is drawn where it says, on stipple,
    inside its halo -- the sheet and the test share one layout so that they
    cannot disagree about where a figure is.
    """
    entries = []
    for name, top in people_rows():
        py = (top + 1) * CELL
        for cx, caption, sprite in zip(_FRAME_CX[name], _FRAME_CAPTIONS[name],
                                       sprites.STANDING[name]):
            entries.append((caption, sprite, cx * CELL, py))
        cycle = _WALKS.get(name)
        if cycle is None:
            continue
        for k in range(_STRIP_STRIDES):
            entries.append((None, cycle[k % walk.STRIDES],
                            _STRIP_CX * CELL + k * _STRIP_PITCH, py))
    return entries


def strip_cells(top: int) -> range:
    """The columns of floor under a walk strip in the block starting at `top`:
    a cell before the first stride to a cell after the last."""
    last_px = _STRIP_CX * CELL + (_STRIP_STRIDES - 1) * _STRIP_PITCH \
        + sprites.WIDTH - 1
    return range(_STRIP_CX - 1, last_px // CELL + 2)


def draw_people_sheet(screen: Screen) -> None:
    """The three standing figures, every frame of each, and the walk.

    **A row per figure.** The name on the left; the unique frames -- three for
    a walker, two for the waiting worker -- each on its own patch of lit
    stipple with a caption under it; and, for the player and the follower,
    the walk as a strip: the cycle `N A N B` twice, each stride drawn four
    pixels further along than the last with the box's width between them (see
    `_STRIP_PITCH`), so what the eye is shown in play at twelve strides a
    second can be read at leisure as a sequence.

    **The worker's second frame is the wave, not a stride**, and the sheet
    says so in its captions: CALL and WAVE rather than letters. The wave plays
    for the frames the shout is painted, which a played room shows when it
    happens to catch one; here both are simply shown.

    Every figure stands on stipple with its halo, as on the sprite sheet and
    for the same reason (issue #70). What this sheet is for is naming the
    frames and showing the cycle; whether the figures *read* as people
    walking is judged in the played rooms, on each of the four strides.
    """
    screen.clear(_attr(WHITE))
    heading = "PEOPLE"
    screens.write(screen, screens.centre(heading), 1, heading, YELLOW,
                  bright=True)
    for name, top in people_rows():
        screens.write(screen, 1, top, name.upper(), YELLOW, bright=True)
        for cx, caption in zip(_FRAME_CX[name], _FRAME_CAPTIONS[name]):
            ground(screen, cx - 1, cx + 1, top + 1)
            # A one-letter caption sits under the box; a word starts a cell
            # to the left so it is centred on it near enough.
            screens.write(screen, cx if len(caption) == 1 else cx - 1,
                          top + 3, caption, CYAN, bright=True)
        if name in _WALKS:
            cells = strip_cells(top)
            ground(screen, cells.start, cells.stop - 1, top + 1)
            screens.write(screen, _STRIP_CX, top, "4 PX A STRIDE", CYAN,
                          bright=True)
    for _caption, sprite, px, py in people_sheet_entries():
        sprites.draw(screen, sprite, px, py, clip_bottom=SCREEN_H)

    legend = (("WALK N A N B, 4 PIXELS A STRIDE", CYAN),
              ("THE WORKER WAVES ON THE SHOUT", CYAN))
    for i, (line, ink) in enumerate(legend):
        screens.write(screen, screens.centre(line), ROWS - 3 + i, line, ink,
                      bright=True)


# --- the tile sheet ---------------------------------------------------------

#: The plan at the bottom of the tile sheet, drawn once lit and once dim.
#:
#: **It is there to show the seams**, and it is chosen so that every one of them
#: is in the picture: borders four cells deep so that there are interior cells
#: with masonry on all four sides and joints that have to line up across a cell
#: boundary in both axes, a void so that faces and end caps are drawn, and a
#: one-cell-thick partition with a `d` gap in it, which is the case the doorway
#: character was added for -- room A's inner door. If the masonry ever stops
#: tiling, it shows here as a broken course or a doubled joint.
#:
#: Twenty-two cells wide rather than the full thirty-two since issue #71, so
#: that the floor's 32x32 tile fits beside it at the same height: a 4x4-cell
#: tile is exactly as tall as the plan, and the floor's two densities sit
#: beside the wall's two, lit beside lit and remembered beside remembered.
#: Nothing the plan is there to show needed the ten columns -- the seams are
#: in the interior and the ends, and both are still here.
PLAN = (
    "######################",
    "####.........d....####",
    "####.........#....####",
    "######################",
)

#: Where the plan is drawn: lit first, then the same plan remembered.
_PLAN_LIT_TOP = ROWS - 8
_PLAN_DIM_TOP = ROWS - 4

#: Where the floor's 32x32 tile is drawn, in cells: beside each plan, at the
#: same rows, the sixteen blocks in the arrangement a room would give them --
#: `floor.tile_index` on the sheet's own cell coordinates, which is what makes
#: the picture the tile and not sixteen blocks in a row. The column is a
#: multiple of four so that block 00 is top-left, as the asset draws it.
_FLOOR_LEFT = 28 - floor.TILE

#: The tile rows: a label, the sixteen tiles two columns apart, and the mask
#: number under each in hexadecimal -- one character, because a tile is one
#: cell wide and a two-digit label would not sit under it.
_TILE_TOP = 3
_TILE_BLOCK = 4
_TILE_STEP = 2


def plan_is_wall(cx: int, cy: int) -> bool:
    """`PLAN`'s solidity, with **off the plan counting as wall**.

    The same rule a room follows, written out here rather than borrowed, so
    that the sheet is drawn by the same mask arithmetic the game uses and can
    disagree with it if it ever breaks.
    """
    if not (0 <= cy < len(PLAN) and 0 <= cx < len(PLAN[0])):
        return True
    return PLAN[cy][cx] == "#"


def draw_plan(screen: Screen, top: int, table, doorways: bool = True) -> None:
    """One copy of the plan, drawn with `table` for its walls."""
    for cy, row in enumerate(PLAN):
        for cx, char in enumerate(row):
            mask = tiles.mask_at(plan_is_wall, cx, cy)
            if char == "#":
                rows = table[mask]
            elif char == "d" and doorways:
                rows = tiles.DOORWAY[mask]
            else:
                continue
            tiles.blit(screen, cx, top + cy, rows)
            screen.set_attr(cx, top + cy,
                            _attr(WHITE, bright=table is tiles.WALL_LIT))


def draw_tile_sheet(screen: Screen) -> None:
    """Every wall and doorway tile, and a plan built out of them.

    Three things a reviewer has to be able to see and could not before:

    * **that all sixteen masks are distinct in both variants** -- an earlier
      masonry interior put a mortar course on row 7, which made *south open*
      invisible and collapsed four pairs of masks onto each other;
    * **that a remembered wall is a line with the courses faintly in it and a
      lit one is made of something**, side by side and at the same size --
      the outline alone until issue #62, and mask 15 now draws its courses
      where it drew nothing; and
    * **that the masonry has no seam in either axis**, which no table of bytes
      will ever show anybody.
    """
    screen.clear(_attr(WHITE))
    heading = "TILE SHEET"
    screens.write(screen, screens.centre(heading), 1, heading, YELLOW,
                  bright=True)

    variants = (("WALL, LIT - OUTLINE AND MASONRY", tiles.WALL_LIT, True),
                ("WALL, DIM - OUTLINE AND COURSES", tiles.WALL_DIM, False),
                ("DOORWAY - RETURNS INTO A GAP", tiles.DOORWAY, True))
    for n, (label, table, bright) in enumerate(variants):
        top = _TILE_TOP + n * _TILE_BLOCK
        screens.write(screen, 0, top, label, CYAN, bright=True)
        for mask in range(len(table)):
            cx = mask * _TILE_STEP
            tiles.blit(screen, cx, top + 1, table[mask])
            screen.set_attr(cx, top + 1, _attr(WHITE, bright=bright))
            # The mask in hexadecimal, so it is one character and sits under
            # its own tile. The tiles are in mask order, which is the whole
            # reason the game needs no lookup, and the labels say so.
            screens.write(screen, cx, top + 2, f"{mask:X}", YELLOW)

    label = "JOINED UP: LIT, DIM"
    screens.write(screen, 0, _PLAN_LIT_TOP - 1, label, CYAN, bright=True)
    draw_plan(screen, _PLAN_LIT_TOP, tiles.WALL_LIT)
    draw_plan(screen, _PLAN_DIM_TOP, tiles.WALL_DIM)
    # **The floor's tile, whole, at both densities** (issue #71): the thing a
    # reviewer has to be able to see is that there is no row of dots for the
    # eye to run along, which no table of sixteen blocks shows anybody.
    screens.write(screen, _FLOOR_LEFT, _PLAN_LIT_TOP - 1, "FLOOR", CYAN,
                  bright=True)
    draw_floor_tile(screen, _FLOOR_LEFT, _PLAN_LIT_TOP, lighting.LIT)
    draw_floor_tile(screen, _FLOOR_LEFT, _PLAN_DIM_TOP, lighting.DIM)


def draw_floor_tile(screen: Screen, left: int, top: int, level: int) -> None:
    """The 32x32 floor tile at `level`, its top-left block at `(left, top)`.

    Drawn by the game's own `floor.stipple` on the sheet's cell coordinates,
    so `left` and `top` are multiples of `floor.TILE` and the picture is the
    tile as the asset draws it -- block 00 top-left, 15 bottom-right.
    """
    assert left % floor.TILE == 0 and top % floor.TILE == 0
    for cy in range(top, top + floor.TILE):
        for cx in range(left, left + floor.TILE):
            floor.stipple(screen, cx, cy, level)
            screen.set_attr(cx, cy, _attr(WHITE, bright=level == lighting.LIT))


# --- the furniture sheet ----------------------------------------------------

#: Each kind of furniture as the sheet lists it: the legend character and a
#: caption. In the game's font, because the legend characters themselves are
#: not in it -- the font is capitals, digits and a handful of punctuation --
#: so the sheet names the thing and the map character is in `building`.
FURNITURE_CAPTIONS = (
    (building.PIPE_H, "PIPE RUN"),
    (building.PIPE_V, "RISER"),
    (building.CRATE, "CRATE"),
    (building.DESK_L, "DESK, LEFT HALF"),
    (building.DESK_R, "DESK, RIGHT HALF"),
    (building.CABINET, "CABINET"),
    (building.GRATING, "GRATING - FLOOR"),
)

#: The list's rows: one per kind, from here down, the lit tile in `_LIT_COL`,
#: the dim tile in `_DIM_COL` and the caption after them.
_FURNITURE_TOP = 3
_LIT_COL, _DIM_COL, _CAPTION_COL = 1, 3, 5

#: A plan with every kind in it, so the seams can be seen: the pipe run
#: joining the outer wall and meeting the riser, the riser joining the walls
#: top and bottom, a crate on its own, a desk in each of two rows, three
#: cabinets stacked, and two gratings on the floor. Every piece here is on a
#: cell the plan calls solid or, for the gratings, floor -- the same rule the
#: rooms are held to -- and the wall cells beside the furniture are drawn by
#: the game's own mask arithmetic, so they show whether a wall ends against a
#: pipe the way it ends against masonry, which is the thing a reviewer has to
#: be able to see.
FURNITURE_PLAN = (
    "################################",
    "#......|......[]......c........#",
    "#======|..x...........c..%.%...#",
    "#......|......[]......c........#",
    "################################",
)

_FURNITURE_PLAN_LIT_TOP = ROWS - 2 * len(FURNITURE_PLAN) - 1
_FURNITURE_PLAN_DIM_TOP = ROWS - len(FURNITURE_PLAN)


def furniture_plan_is_wall(cx: int, cy: int) -> bool:
    """`FURNITURE_PLAN`'s solidity: `building.SOLID`, off the plan wall."""
    if not (0 <= cy < len(FURNITURE_PLAN) and 0 <= cx < len(FURNITURE_PLAN[0])):
        return True
    return FURNITURE_PLAN[cy][cx] in building.SOLID


def draw_furniture_plan(screen: Screen, top: int, level: int) -> None:
    """One copy of the furniture plan at `level`, LIT or DIM.

    Walls by `tiles.mask_at` over the plan's solidity, so a wall next to a
    pipe is drawn as the game would draw it; furniture by the map character,
    lit or dim, with no mask; the floor stippled so the grating sits in the
    ground it belongs to; the attributes white for solid and cyan for floor,
    as a room's palette would have them, so the grating can be seen taking
    the floor's hue.
    """
    lit = level == lighting.LIT
    wall_table = tiles.WALL_LIT if lit else tiles.WALL_DIM
    furniture = tiles.FURNITURE if lit else tiles.FURNITURE_DIM
    for cy, row in enumerate(FURNITURE_PLAN):
        for cx, char in enumerate(row):
            solid = char in building.SOLID
            if char == building.WALL:
                rows = wall_table[tiles.mask_at(furniture_plan_is_wall, cx, cy)]
                tiles.blit(screen, cx, top + cy, rows)
            elif char in building.FURNITURE:
                tiles.blit(screen, cx, top + cy, furniture[char])
            else:
                floor.stipple(screen, cx, top + cy, level)
            screen.set_attr(cx, top + cy,
                            _attr(WHITE if solid else CYAN, bright=lit))


def draw_furniture_sheet(screen: Screen) -> None:
    """Every kind of furniture, lit and remembered, and a plan built of them.

    Issue #74. Two things a reviewer has to be able to see:

    * **each tile on its own at both levels**, so the dim rule -- every other
      pixel, the phase alternating by row -- can be judged as a ghost of the
      lit tile and not as a second drawing; and
    * **the furniture joined up with walls**, because a solid piece is a wall
      to its neighbours' masks and the picture has to show a wall ending
      against a pipe the way it ends against masonry.

    The dim tiles are read from `tiles.FURNITURE_DIM` and not recomputed
    here, so the sheet shows what the game draws and can disagree with the
    rule's test if the two ever part.
    """
    screen.clear(_attr(WHITE))
    heading = "FURNITURE SHEET"
    screens.write(screen, screens.centre(heading), 1, heading, YELLOW,
                  bright=True)
    screens.write(screen, _LIT_COL, _FURNITURE_TOP - 1, "L", CYAN, bright=True)
    screens.write(screen, _DIM_COL, _FURNITURE_TOP - 1, "D", CYAN, bright=True)
    for n, (kind, caption) in enumerate(FURNITURE_CAPTIONS):
        cy = _FURNITURE_TOP + n
        tiles.blit(screen, _LIT_COL, cy, tiles.FURNITURE[kind])
        screen.set_attr(_LIT_COL, cy, _attr(WHITE, bright=True))
        tiles.blit(screen, _DIM_COL, cy, tiles.FURNITURE_DIM[kind])
        screen.set_attr(_DIM_COL, cy, _attr(WHITE))
        screens.write(screen, _CAPTION_COL, cy, caption, YELLOW)

    label = "JOINED UP: LIT, DIM"
    screens.write(screen, 0, _FURNITURE_PLAN_LIT_TOP - 1, label, CYAN,
                  bright=True)
    draw_furniture_plan(screen, _FURNITURE_PLAN_LIT_TOP, lighting.LIT)
    draw_furniture_plan(screen, _FURNITURE_PLAN_DIM_TOP, lighting.DIM)


# --- the rooms --------------------------------------------------------------

def enter(run, index: int):
    """Get the player into room `index`, by walking through the door.

    Teleporting `here` would be one line, and it would be a picture of a room
    the game never put the player in: entering a room fires its opening flash,
    migrates any fly riding the player, and logs the crossing. So the player is
    stood in the doorway -- which is the same convenience the doorway tests use
    -- and then *walks*, and every rule about arriving somewhere runs.

    Only rooms with a door straight from the one the run starts in can be
    reached this way. The playtest building is two rooms and that is enough;
    a third room reached only through a second would need a route, and the day
    that exists is the day to write one.
    """
    if run.here == index:
        return run
    door = scene.BUILDING[run.here].doorway_to(index)
    if door is None:
        raise ValueError(
            f"no doorway from room {run.here} to room {index}; "
            "the gallery cannot walk somewhere it cannot walk")
    run.player.x = door.column * CELL
    run.player.y = (door.middle - 1) * CELL
    facing = 1 if door.side == EAST else -1
    for _ in range(32):
        run.step(session_mod.Intent(dx=facing))
        if run.here == index:
            return run
    raise RuntimeError(f"the player would not walk into room {index}")


def lit_room(index: int) -> tuple:
    """One room fully revealed, as `(run, screen)`.

    The run comes back as well as the picture because what is *painted* on a
    wall -- the exit sign, and anybody shouting -- is a property of the frame
    and not of the room, and a caller checking the walls has to know which
    cells were painted over. Nothing else needs it, which is why `room_screen`
    keeps the simpler signature.
    """
    run = session_mod.Session(seed=GALLERY_SEED)
    enter(run, index)
    screen = Screen()
    # The debug reveal, held: the room and everybody in it, which is what a
    # reviewer needs and what the player is deliberately never given.
    run.place.opening.hold(True)
    run.step()
    run.draw(screen)
    return run, screen


def room_screen(index: int, lit: bool, frames: int = PLAYED_FRAMES,
                stride: int | None = None, torch: bool = True) -> Screen:
    """One room, drawn: fully revealed, or as it looks after `frames` of play.

    A fresh session each time. Sharing one would mean the second picture was of
    a building the first had already spent a torch and a swarm on, and a shot
    labelled "the far room" would quietly be a shot of the far room *after the
    near one had gone wrong*.

    `stride` is which step of the walk every walking figure in the picture is
    drawn on -- 0 to 3 over the cycle `N A N B` -- or `None` for whichever
    each of them was actually on. **The walk is judged in a played room, on
    every stride of the same instant** (issues #60 and #72): the people sheet
    shows the frames side by side with their names underneath, which is where
    art is named and not where it is judged, and a single played frame shows
    one stride of a walk with no way to see the others. So the same kept
    frame is drawn four times, and the pictures differ only in the walkers'
    arms and legs. The waiting worker is not a walker: it is drawn as the
    game had it, calling or waving, on all four.

    `torch` is whether the listener holds the torch on. **Off is the frame the
    game is played in** (issue #62): the same bot, the same seed and the same
    frame count, with the room lit by the glow, the searchlight and whatever
    the fade still remembers. It is the frame the wall tiles are judged on,
    because a remembered wall is what a player sees beside them nearly all of
    the time and a lit one is what they see under the cone for a moment.
    """
    if lit:
        return lit_room(index)[1]
    run = session_mod.Session(seed=GALLERY_SEED)
    enter(run, index)
    screen = Screen()

    bot = bots.make("listener", seed=GALLERY_SEED, light=torch)
    kept = None
    for _ in range(frames):
        run.step(bot.intent(run))
        if run.over is not None:
            break
        # The bot is free to walk back out of the room it was put in, and the
        # picture has to be of the room on the label. Walking it back in costs
        # a crossing and nothing else.
        if run.here != index:
            enter(run, index)
            continue
        draw_on_stride(run, screen, stride)
        if standing_clear(run):
            kept = copy_of(screen)
    # **The last frame with the player wholly on screen, not simply the last
    # frame.** The listener spends a good part of a sample stood in the doorway
    # deciding, and mid-crossing the figure is half off the edge -- the first
    # version of this sheet photographed the far room with the player at x=-6,
    # which is a real frame of a real run and a useless portrait of a room.
    return kept if kept is not None else copy_of(screen)


#: Which frame of the opening flash is photographed. The second: the first
#: is the frame a player sees first and the flash is at full strength on
#: either, so this is one frame in from the edge of the window rather than on
#: it, and it is inside the shortest flash anybody could set.
FLASH_SHOT_FRAME = 2


def flash_room(index: int = scene.NEAR) -> Screen:
    """A room during its opening flash, with the people in it (issue #64).

    **The picture the user asked for**: they saw a room light up fully and
    empty, and then found people in it. The ruling is that the flash shows
    the workers and the Clegs without making anybody prey, and this is the
    frame that shows it -- the whole room lit, every worker and every fly
    drawn in their own colours, and the player at the start cell.

    Photographed from the run's own flash rather than from `Flash.hold`, so
    what is in the picture is what the flash draws and not what the debug
    view draws: the two share a source but only one of them is the game.
    """
    run = session_mod.Session(seed=GALLERY_SEED)
    enter(run, index)
    for _ in range(FLASH_SHOT_FRAME):
        run.step()
    if not run.place.opening.enabled:
        raise RuntimeError("the opening flash has gone out, so this would be "
                           "a picture of the fade and not of the flash")
    screen = Screen()
    run.draw(screen)
    return screen


def draw_on_stride(run, screen: Screen, stride: int | None) -> None:
    """Draw the run's current frame with every walker on step `stride`.

    The stride counters are drawing state and nothing in the rules reads them
    -- that is the contract the walk was built under, and the tests hold it
    -- so setting them for one drawing and putting them back leaves the run
    exactly where it was. `None` draws the frame as the game would.

    **They are put back rather than left**, even though the run could not
    tell: a gallery that quietly changed a run's state would be the first
    thing here that did, and the next reader would have to work out whether
    it mattered.
    """
    if stride is None:
        run.draw(screen)
        return
    people = [run.player] + list(run.rescue.workers)
    was = [person.walk.index for person in people]
    for person in people:
        person.walk.index = stride
    try:
        run.draw(screen)
    finally:
        for person, index in zip(people, was):
            person.walk.index = index


#: How far the player walks off the light they have just put down, so that the
#: burning lamp is photographed rather than the player's boots. Three cells is
#: clear of an 8x16 figure and still inside the pool it is making.
SWAP_STEPS = 24

#: And how long to stand there afterwards. The opening flash lights the whole
#: room and the memory of it takes about three seconds to go out, so a frame
#: taken straight after the swap is a picture of a fully lit room with a lamp
#: in it -- which shows the sprite and hides the thing the sprite is for. Held
#: until the flash has faded, so what is on screen is the pool the lamp itself
#: is making.
SWAP_SETTLE = 200


def swapped_room(index: int = scene.NEAR) -> Screen:
    """A spotlight **burning on the floor**, which no bot has ever produced.

    `LAMP_ON` cannot be photographed from a played run and that is a fact about
    the game rather than about the gallery: every authored spotlight starts
    unlit, a floor light only lights by being swapped for a burning one, and
    `spotlight_swaps` is 0 in every run any bot has ever made. So the picture
    is set up here instead.

    **Nothing about the level moves to get it.** Lighting one in the level data
    would be a change to where the light in this building is, which is a
    level-design dial and a gameplay change this round forbids. What happens
    instead is the game's own swap rule, fired by the game's own code: the
    player is stood on the room's first authored spotlight -- the same
    convenience `enter` uses to stand them in a doorway -- the torch is
    switched on, and `Spotlights.tick` leaves the burning light behind exactly
    as it would if somebody had walked there. Then the player walks off it, so
    the lamp is not underneath a figure.

    It raises rather than returning a picture of nothing if the swap does not
    happen, because a sheet that quietly showed an unlit spare would be worse
    than no sheet at all -- it is the one image on it nobody can check against
    a run.
    """
    run = session_mod.Session(seed=GALLERY_SEED)
    enter(run, index)
    lights = [l for l in run.kit.floor if l.room == index]
    if not lights:
        raise ValueError(f"room {index} authors no spotlight to swap")
    light = lights[0]
    # Standing on it: x is the cell, y is the cell the *feet* are in.
    run.player.x = light.cx * CELL
    run.player.y = (light.cy + 1) * CELL - player_mod.HEIGHT
    run.step(session_mod.Intent(torch=True))
    if not light.burning:
        raise RuntimeError(
            "the swap did not leave a burning light on the floor, so there is "
            "nothing here to photograph")
    for _ in range(SWAP_STEPS):
        run.step(session_mod.Intent(dx=1))
    for _ in range(SWAP_SETTLE):
        run.step()
    screen = Screen()
    run.draw(screen)
    return screen


#: Frames of ordinary play before the freeing, so that the room has been lit
#: once and is remembered. **A moment tests the light when it is raised**, and
#: on frame one no light has been cast at all -- the field is built at the end
#: of a step -- so a freeing on the first frame would raise no flash and the
#: sheet would be a picture of the rule working, captioned as a picture of it
#: failing.
FREE_SETTLE = 20

#: And how many frames after it the picture is taken, out of the flash's
#: sixteen. Enough that the player has walked off the cells and the flash is
#: visibly *where it happened* rather than where anybody is standing.
FREE_WALK = 10


def freed_room(index: int = scene.NEAR) -> Screen:
    """A moment's flash, on a played frame, set up the way a swap is.

    Issue #52. A flash is the one thing on screen that a still cannot show by
    itself -- it is two halves of a hardware cycle -- so the gallery writes both
    halves of one, exactly as it has done for the title screen's prompt since
    that prompt was first reviewed as though it were plain white text.

    **Nothing about the level or the rules moves to get it.** The player is
    stood on a waiting worker -- the same convenience `enter` uses to stand them
    in a doorway -- and then the game's own `Rescue.reach` frees them and the
    session's own `_moment` raises `M_FREED` over the two cells they were
    standing in. Then the player walks away from those cells, which is the
    picture worth having: **a flash marks where a thing happened and follows
    nothing**, so the two cells go on flashing behind them.

    It raises rather than returning a picture of nothing if the freeing does not
    happen, for the same reason `swapped_room` does: a sheet that quietly showed
    an ordinary frame would be the one image on it nobody could check.
    """
    run = session_mod.Session(seed=GALLERY_SEED)
    enter(run, index)
    for _ in range(FREE_SETTLE):
        run.step()
    waiting = run.rescue.alive_waiting(index)
    if not waiting:
        raise ValueError(f"room {index} has nobody waiting to be freed")
    worker = waiting[0]
    run.player.x, run.player.y = worker.x, worker.y
    # The torch goes on in the same step, because the picture is of a lit room
    # and because the sheet's other played shots hold it on too.
    run.step(session_mod.Intent(torch=True))
    raised = [name for name, _cells in run.moments.raised]
    if moments.M_FREED not in raised:
        raise RuntimeError(
            "nobody was freed, so there is no moment here to photograph")
    for _ in range(FREE_WALK):
        run.step(session_mod.Intent(dx=1))
    screen = Screen()
    run.draw(screen)
    if not any(attr & moments.FLASH_BIT for attr in screen.attrs):
        raise RuntimeError(
            "the flash had gone by the time the picture was taken")
    return screen


#: How long the gallery will play a run looking for somebody to have died.
#:
#: A body is not a thing a picture can set up: somebody has to bleed out or be
#: eaten, and on the gallery seed the first death in the near room is around
#: frame 3,000. The limit is generous rather than tight because what it guards
#: against is an infinite loop, not a slow one.
BODY_LIMIT = 6000

#: How far from the body the player is stood for the portrait, in cells.
#: Two: clear of the body's own two cells, and close enough that one torch
#: lights both and that the pair is one glance rather than two.
BODY_GAP = 2


def body_room(index: int = scene.NEAR) -> Screen:
    """**A body in a played room, beside somebody standing up** (issue #59).

    The sheet is not evidence, and this picture exists because it was not. BODY
    was drawn sprawled and obvious at sheet scale for three rounds, was
    reviewed as such twice, and in a played room at the size it actually
    appears it read as a person standing next to you -- twice in one session,
    in two different rooms, confidently. **A picture of the sprite sheet cannot
    settle whether a sprite reads**, and the rule written down after the doors
    said so already; this is the rule getting a photograph of its own.

    So: a real run, played until somebody actually dies, on the stippled floor,
    at the light the game gives it, **with the player stood beside the corpse**
    -- which is the comparison a reviewer has to be able to make and the one
    the sheet cannot, because on the sheet they are in different blocks with
    their names underneath.

    **Nothing about the level or the rules moves to get it.** The statue plays,
    so nobody is rescued and the torch is untouched until the picture is taken;
    the body arrives on the game's own clock; and the only convenience is the
    one `enter` and `freed_room` already use -- the player is stood somewhere,
    then the game runs an ordinary frame.

    It raises rather than returning a picture of nothing if the run produces no
    body, or if the body would be photographed in the dark, for the same reason
    `swapped_room` does: a sheet that quietly showed an ordinary frame would be
    the one image on it nobody could check.
    """
    run = session_mod.Session(seed=GALLERY_SEED)
    enter(run, index)
    # The statue, and with the torch off: it saves nobody, so the deaths happen
    # on the level's own clock, and it spends no light before the frame that
    # needs it.
    playing = bots.make("statue", seed=GALLERY_SEED, light=False)
    for _ in range(BODY_LIMIT):
        run.step(playing.intent(run))
        if run.over is not None:
            break
        if run.rescue.bodies(index):
            break
    bodies = run.rescue.bodies(index)
    if not bodies:
        raise RuntimeError(
            f"nobody died in {BODY_LIMIT} frames of the gallery run, so the "
            f"body would be photographed by being drawn on an empty room")
    body = bodies[0]
    room = scene.BUILDING[index]
    cells = sprites.body_cells(*body.cell(), room.is_solid)
    stand = _standing_room(room, cells)
    if stand is None:
        raise RuntimeError("there is nowhere to stand beside the body")
    cx, facing = stand
    run.player.x = cx * CELL
    run.player.y = (cells[0][1] - 1) * CELL
    # One ordinary frame: the torch comes on and the player turns to face the
    # body. Turning costs a step, which is why he is stood two cells clear.
    run.step(session_mod.Intent(dx=facing, torch=True))
    screen = Screen()
    run.draw(screen)
    field = run.place.field
    if any(field.level_at(cx, cy) == lighting.DARK for cx, cy in cells):
        raise RuntimeError(
            "the body is in the dark, so the picture is of an unlit floor")
    return screen


def _standing_room(room, cells) -> tuple | None:
    """A column beside the body to stand the player in, and which way to face.

    Either side, the near side first, and the box has to fit: a person is two
    cells tall, so both of them have to be clear or the picture is of somebody
    standing inside a wall.
    """
    left, row = cells[0]
    right = cells[-1][0]
    for cx, facing in ((right + BODY_GAP, -1), (left - BODY_GAP, 1)):
        if not 0 <= cx < COLS:
            continue
        if any(room.is_solid(cx, row - dy) for dy in (0, 1)):
            continue
        return cx, facing
    return None


#: How long the gallery will play a run looking for a frame with a nest on it.
#:
#: A nest is a body twenty seconds after a death, so it is the one thing on the
#: surge plan that a run has to be played *into* rather than set up: the statue
#: on the gallery seed turns its first at frame 4,000. The limit is generous
#: rather than tight because what it guards against is an infinite loop, not a
#: slow one -- and if the game ever stops producing a nest in two minutes of
#: play, that is a finding rather than a broken sheet.
SURGE_LIMIT = 6000


def surge_screen() -> Screen:
    """The mains surge, on a played frame: the whole building plan.

    Issue #53. **The one picture in the game that shows both rooms at once**,
    and the beat the whole memorisation premise rests on -- so the sheet has to
    show it with something in it. A plan of two empty rooms would be a picture
    of the geometry working and would say nothing about the thing the surge is
    for, which is that it hands you *the people* as well as the building.

    So the run is played until there is a nest in the building, because a nest
    is the one mark on the plan that cannot be set up: it is a body twenty
    seconds after a death, and both halves of that have to actually happen. The
    workers, the flies and the player are there from the first frame.

    **The statue plays it**, which is the one choice here worth arguing. The
    listener reaches the same state at frame 3,200 and rescues five people on
    the way, so its plan has one green mark left on it -- a truthful frame of a
    good run and a poor picture of what a surge hands over. The statue saves
    nobody, so the plan carries five people in both rooms, a nest, the swarm
    and a player standing on open floor, which is what a reviewer has to be able
    to look at. Nothing about the level or the rules moves either way.

    **The surge is drawn by the game's own code on an ordinary frame** --
    `Session.draw_surge`, exactly as the shell calls it -- rather than by
    anything this module knows about plans. It is not scheduled: waiting for a
    real one would mean playing a run until its own seed said so, and the
    picture would then be of whatever frame that landed on rather than of a
    frame with a nest in it. What is photographed is the drawing, which is what
    the sheet is for.

    It raises rather than returning a picture of nothing if the run never
    produces one, for the same reason `swapped_room` does: a sheet that quietly
    showed an empty plan would be the one image on it nobody could check.
    """
    run = session_mod.Session(seed=GALLERY_SEED)
    playing = bots.make("statue", seed=GALLERY_SEED)
    for _ in range(SURGE_LIMIT):
        run.step(playing.intent(run))
        if run.over is not None:
            break
        if run.rescue.nests() and run.rescue.alive_waiting():
            break
    if not (run.rescue.nests() and run.rescue.alive_waiting()):
        raise RuntimeError(
            f"no nest and somebody alive in {SURGE_LIMIT} frames of the "
            f"gallery run, so the plan would be photographed without them")
    screen = Screen()
    # The ordinary frame first and the plan over the top of it, which is what
    # the shell does: the play area is replaced and the status strip is left
    # exactly where it is, still reading out the run underneath.
    run.draw(screen)
    run.draw_surge(screen)
    return screen


def standing_clear(run) -> bool:
    """Is the player far enough from the edges to be a picture of a room?

    A cell in from either side. Only a framing rule -- it decides which frame is
    photographed and nothing about the frame itself.
    """
    return CELL <= run.player.x <= SCREEN_W - 2 * CELL


def copy_of(screen: Screen) -> Screen:
    """A still of a screen. The play area is repainted every frame, so a frame
    that is not copied is gone by the time anybody wants it."""
    still = Screen()
    still.pixels[:] = screen.pixels
    still.attrs[:] = screen.attrs
    return still


def slug(name: str) -> str:
    """A room's name as a filename: 'the far room' -> 'the-far-room'."""
    return "-".join(name.lower().split())


# --- the whole gallery ------------------------------------------------------

def write(out_dir: str, scales=spike_snap.DEFAULT_SCALES) -> list[str]:
    """Write every sheet into `out_dir`. Returns the paths, in order written.

    The order is the order somebody should look at them in: the screen the
    player sees first, the screen they see last, the cast, then the rooms.
    """
    os.makedirs(out_dir, exist_ok=True)
    paths: list[str] = []

    def sheet(name: str, screen: Screen, flashing: bool = False) -> None:
        paths.extend(spike_snap.save_scales(
            screen, os.path.join(out_dir, name), scales, flashing))

    title = Screen()
    screens.draw_title(title)
    sheet("title", title)
    # The same screen with the flash bit inverted, because PRESS ANY KEY is a
    # flashing cell and a still can only ever show one half of the cycle. Both
    # halves are on screen in front of a real player, so both are in the
    # gallery -- the first time this was written, the prompt was reviewed as
    # though it were plain white text.
    sheet("title-flashed", title, flashing=True)

    ending = Screen()
    screens.draw_ending(ending, session_mod.ENDING_TEXT[ENDING],
                        **ENDING_COUNTS)
    sheet("ending", ending)

    sheet_screen = Screen()
    draw_sprite_sheet(sheet_screen)
    sheet("sprites", sheet_screen)

    people_screen = Screen()
    draw_people_sheet(people_screen)
    sheet("people", people_screen)

    tile_screen = Screen()
    draw_tile_sheet(tile_screen)
    sheet("tiles", tile_screen)

    furniture_screen = Screen()
    draw_furniture_sheet(furniture_screen)
    sheet("furniture", furniture_screen)

    for index, room in enumerate(scene.BUILDING.rooms):
        sheet(f"room-{slug(room.name)}-lit", room_screen(index, lit=True))
        # **The same played instant four times, with every walker on each
        # stride of the cycle in turn** (issues #60 and #72), so the walk can
        # be judged where a figure is actually seen -- on the stipple, at the
        # light the game gives it, beside whoever else is in the room -- and
        # not on the sheet. One picture of a walk shows one stride; the four
        # are the walk.
        for stride in range(walk.STRIDES):
            sheet(f"room-{slug(room.name)}-played-{stride}",
                  room_screen(index, lit=False, stride=stride))
    # **The frame the game is played in** (issue #62): the near room at the
    # same played instant with the torch off, which is where the remembered
    # walls are seen and where they were never photographed before. Feet as
    # the game had them -- the walk is judged on the pair above, not here.
    sheet(f"room-{slug(scene.BUILDING[scene.NEAR].name)}-torch-off",
          room_screen(scene.NEAR, lit=False, torch=False))
    # **During the opening flash, with the people in it** (issue #64): the
    # one whole-room moment the game gives, which used to hide everybody.
    sheet(f"room-{slug(scene.BUILDING[scene.NEAR].name)}-flash",
          flash_room(scene.NEAR))
    # The one thing on the sprite sheet that a played frame cannot otherwise
    # show: a spotlight burning where somebody put it down.
    sheet(f"room-{slug(scene.BUILDING[scene.NEAR].name)}-swapped",
          swapped_room(scene.NEAR))
    # A moment's flash, in both halves of the cycle (issue #52). A still can
    # only ever show one half, and a reviewer given one half of a flash reads it
    # as a cell that is simply the wrong colour.
    freed = freed_room(scene.NEAR)
    near = slug(scene.BUILDING[scene.NEAR].name)
    sheet(f"room-{near}-freed", freed)
    sheet(f"room-{near}-freed-flashed", freed, flashing=True)
    # **A body, in a played room, beside somebody standing up** (issue #59).
    # The sprite sheet said the body read for three rounds and the played
    # screen said otherwise, so this is the picture a redraw is judged on.
    sheet(f"room-{near}-body", body_room(scene.NEAR))
    # The mains surge (issue #53), in both halves of the cycle for the same
    # reason: the player's mark and the nests are drawn with the FLASH bit, and
    # a still can only ever show one half of it. **The half where the player is
    # inverted is the half you find yourself in**, so a reviewer given only the
    # other one would be looking at a plan with no player on it.
    surged = surge_screen()
    sheet("surge", surged)
    sheet("surge-flashed", surged, flashing=True)
    return paths
