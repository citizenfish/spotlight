"""Sprites: 8x16 people, 8x8 objects, positioned by pixel.

**Everything in the play area is drawn from above, people included.** Decided
from play on 2026-09-07 -- the Cleg is an 8x8 bug seen from overhead and it
reads; the player and the workers were front-facing standing figures in a world
seen from the ceiling, and they were the only things in the room that were. See
the vault's *People are drawn from above* for the argument and *Screen Layout*
for the bytes.

**The bytes are not here.** Every figure is authored as a grid of `#` and `.`
in `assets/sprites/` and generated into `bitmaps_gen.py` by `tools/bitmaps.py`
(issue #48). They used to be declared here as hex *and* drawn in `assets/`, with
a test comparing the two -- which could say they disagreed but never which was
right. One source now, and the Z80 gets the same bytes from the same file.

What that means for anything drawn later: a head at the top with nothing above
it and no neck, shoulders as the widest part immediately under it, arms outside
the shoulder line with a gap, short legs and no feet, and eleven or twelve drawn
rows inside the sixteen-row box, because foreshortening is what a view from
above does.

**The figures do not turn.** One orientation, head toward the top of the screen.
An 8x16 sprite has a long axis and so does an overhead person, so a figure that
turned would need a 16x16 sprite -- a second sprite format rather than more data
-- and four facings for three figures is about 10K of a 48K machine. The cone is
the facing indicator, and in a game about light that is the right one. The cost
is real and stated in the decision: with the torch off, nothing says which way
you are pointing.

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
first, silhouette second**: **people are 8x16 whether or not they are alive**,
everything else is 8x8. A body was the exception to that rule and is now the
proof of it -- size says whether a thing is a person, pose says whether it is
still alive.

Drawing is byte-per-pixel here because that is how `core.screen` models the
display. On real hardware an 8-pixel-wide sprite at an arbitrary x needs its
rows shifted across two bytes and masked, which is where the cost lives -- see
issue #11.
"""

from spotlight.core.constants import CELL, SCREEN_H, SCREEN_W

from .bitmaps_gen import BITMAPS
from .layout import PLAY_ROWS

PLAY_BOTTOM_PX = PLAY_ROWS * CELL

# --- people, 8x16 ----------------------------------------------------------

#: The player: the one in kit, seen from above. Full-width square shoulders,
#: arms held clear of the body, a wide planted stance. **The only figure that
#: touches both edges of its column at the shoulders** -- the widest thing in
#: the room is you.
PLAYER = BITMAPS["PLAYER"]

#: A trapped worker, waiting: arms up and out, which is the silhouette of
#: somebody calling for help and exactly what they are doing. Narrower
#: shoulders than the player, because no kit. **The only figure that touches
#: both edges above the head**, which is the near-inverse of the player and a
#: much larger difference than the helmet it replaces.
WORKER = BITMAPS["WORKER"]

#: The same person, freed and walking behind you: arms down. Only the arms
#: move, so it reads as the same body having stopped signalling.
#:
#: It exists because raised arms *mean* "I still need reaching", and leaving
#: them up on somebody already following you is a lie the player would act on.
#: It costs nothing to keep true: a worker is drawn from their state, so
#: somebody released by the player's death goes back to arms up on the frame
#: they are dropped.
FOLLOWER = BITMAPS["FOLLOWER"]

#: Somebody who died. **8x16, because it is a person**: seen from directly
#: above, somebody lying down has the same plan as somebody standing up, so the
#: tell cannot be the outline and it is the **pose**. Every living figure is
#: symmetric about its centre column; this one is not, anywhere -- the head
#: lolls off the axis, one arm is flung out higher than the other, and the legs
#: splay unevenly.
#:
#: It replaces an 8x8 slab that spike 1 called the weakest of the six sprites
#: and that issue #31 said read as debris. It is also drawn at the person's own
#: position now: the old sprite was offset down a cell to sit at their feet, and
#: that offset went with it.
BODY = BITMAPS["BODY"]

# --- everything else, 8x8 --------------------------------------------------

#: A Cleg: fat body, splayed legs.
CLEG = BITMAPS["CLEG"]

#: A nest: a bounded mass, deliberately angular so it cannot be mistaken for a
#: Cleg. An organic blob read too much like the thing it spawns.
NEST = BITMAPS["NEST"]

#: A spotlight lying on the floor: a lamp with its beam spreading below.
LAMP = BITMAPS["LAMP"]

KEY = BITMAPS["KEY"]

#: Every drawable, for tests and the sprite sheet.
SPRITES = {
    "player": PLAYER, "worker": WORKER, "follower": FOLLOWER, "body": BODY,
    "cleg": CLEG, "nest": NEST, "key": KEY, "lamp": LAMP,
}

#: The four that are people, and so are 8x16 and drawn from above.
PEOPLE = ("player", "worker", "follower", "body")

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
