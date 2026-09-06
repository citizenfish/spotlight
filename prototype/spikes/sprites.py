"""Sprites: 8x16 people, 8x8 everything else, positioned by pixel.

**What the fade may remember.** The building is remembered; its inhabitants are
not. Walls, keys, bodies and nests stay drawn in ground the player is only
recalling, because they will still be where they were. People and Clegs move,
so drawing them from stale light would show the player where somebody is now
using light that has gone -- see `draw`'s `visible` argument.

**The colour rule.** A sprite sets pixels and never touches an attribute. Each
cell keeps whatever ink its light level gives it, so a sprite spanning a light
boundary is drawn part bright and part dim -- and two things can never disagree
about a cell's colour, because only one thing ever decides it.

That is the whole mechanism for avoiding attribute clash, and it costs the
ability to tell entities apart by colour. So they are told apart by **size
first, silhouette second**: people are 8x16 and everything else is 8x8, which
does most of the work before shape has to.

Drawing is byte-per-pixel here because that is how `core.screen` models the
display. On real hardware an 8-pixel-wide sprite at an arbitrary x needs its
rows shifted across two bytes and masked, which is where the cost lives -- see
issue #11.
"""

from spotlight.core.constants import CELL, SCREEN_H, SCREEN_W

from .layout import PLAY_ROWS

PLAY_BOTTOM_PX = PLAY_ROWS * CELL

# --- people, 8x16 ----------------------------------------------------------

#: The player: an emergency worker, distinguished by the helmet.
PLAYER = (
    0x00,  # ........
    0x3C,  # ..####..   helmet
    0x7E,  # .######.   brim
    0x18,  # ...##...
    0x3C,  # ..####..   head
    0x18,  # ...##...
    0x7E,  # .######.   shoulders
    0xDB,  # ##.##.##   arms out
    0xDB,  # ##.##.##
    0x3C,  # ..####..   torso
    0x3C,  # ..####..
    0x3C,  # ..####..
    0x24,  # ..#..#..   legs
    0x24,  # ..#..#..
    0x66,  # .##..##.   feet
    0x00,  # ........
)

#: A trapped worker: same build, no helmet, arms down.
WORKER = (
    0x00,
    0x18,  # ...##...   head
    0x3C,  # ..####..
    0x3C,  # ..####..
    0x18,  # ...##...
    0x7E,  # .######.   shoulders
    0x5A,  # .#.##.#.   arms down
    0x5A,  # .#.##.#.
    0x3C,  # ..####..   torso
    0x3C,  # ..####..
    0x3C,  # ..####..
    0x24,  # ..#..#..   legs
    0x24,  # ..#..#..
    0x66,  # .##..##.   feet
    0x00,
    0x00,
)

# --- everything else, 8x8 --------------------------------------------------

#: A QuirkyCleg: fat body, splayed legs.
CLEG = (
    0x00,
    0x42,  # .#....#.   legs out
    0x24,  # ..#..#..
    0x7E,  # .######.   body
    0xFF,  # ########
    0x7E,  # .######.
    0x24,  # ..#..#..   legs
    0x42,  # .#....#.
)

#: A body: something lying down. Deliberately flat, to read as fallen.
BODY = (
    0x00,
    0x00,
    0x00,
    0x7E,  # .######.
    0xFF,  # ########
    0xFF,  # ########
    0x00,
    0x00,
)

#: A nest: a bounded mass, deliberately angular so it cannot be mistaken for a
#: Cleg. An organic blob read too much like the thing it spawns.
NEST = (
    0x00,
    0xFF,  # ########   rim
    0x81,  # #......#
    0xBD,  # #.####.#   something inside
    0xBD,  # #.####.#
    0x81,  # #......#
    0xFF,  # ########
    0x00,
)

#: A spotlight lying on the floor: a lamp with its beam spreading below.
LAMP = (
    0x00,
    0x18,  # ...##...   handle
    0x3C,  # ..####..
    0x7E,  # .######.   dome
    0xFF,  # ########   lens
    0x66,  # .##..##.   beam
    0x24,  # ..#..#..
    0x00,
)

KEY = (
    0x00,
    0x1C,  # ...###..   ring
    0x22,  # ..#...#.
    0x22,  # ..#...#.
    0x1C,  # ...###..
    0x08,  # ....#...   shaft
    0x0E,  # ....###.   teeth
    0x00,
)

#: Every drawable, for tests and the sprite sheet.
SPRITES = {
    "player": PLAYER, "worker": WORKER, "cleg": CLEG,
    "body": BODY, "nest": NEST, "key": KEY, "lamp": LAMP,
}

WIDTH = 8


def draw(screen, sprite: tuple[int, ...], x: int, y: int,
         clip_bottom: int = PLAY_BOTTOM_PX, visible=None) -> None:
    """Draw a sprite at pixel (x, y). Sets pixels; never writes an attribute.

    Pixels are set, never cleared, so a sprite composites over what is already
    there rather than punching a hole in it.

    `visible` is an optional test taking a cell and returning whether the
    sprite may be drawn in it. People and Clegs pass one, so that they show
    only where a light is actually on them; the building's fixtures do not,
    because the fade is allowed to remember those. Drawing is already per cell,
    so a worker half inside a beam is drawn half -- the same mechanism that
    gives a figure its two-tone edge, cutting all the way to nothing.
    """
    shown: dict[tuple[int, int], bool] = {}
    for dy, bits in enumerate(sprite):
        py = y + dy
        if not 0 <= py < min(SCREEN_H, clip_bottom):
            continue
        cy = py // CELL
        base = py * SCREEN_W
        for dx in range(WIDTH):
            if not bits & (0x80 >> dx):
                continue
            px = x + dx
            if not 0 <= px < SCREEN_W:
                continue
            if visible is not None:
                cell = (px // CELL, cy)
                ok = shown.get(cell)
                if ok is None:
                    ok = shown[cell] = bool(visible(*cell))
                if not ok:
                    continue
            screen.pixels[base + px] = 1


def cells_spanned(x: int, y: int, height: int) -> set[tuple[int, int]]:
    """Which attribute cells a sprite at (x, y) touches.

    An 8-wide sprite at an x that is not a multiple of 8 straddles two columns;
    an 8-tall one at an odd y straddles two rows. So an 8x8 sprite can span four
    cells, and each of them keeps its own colour.
    """
    return {
        (cx, cy)
        for cx in range(x // CELL, (x + WIDTH - 1) // CELL + 1)
        for cy in range(y // CELL, (y + height - 1) // CELL + 1)
    }
