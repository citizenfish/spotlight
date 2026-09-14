"""Sprites: 8x16 people, 8x8 objects, and one 16x8 body.

**Everything is drawn from above, the people included.** Ruled from play on
2026-09-13 (issue #78), overriding the day before. The people were asked for
from above on 2026-09-07 and drawn to those words twice; on 2026-09-12 the
user, shown a front-view figure beside the plan-view one in a played frame,
chose elevation (issue #72), the convention of Atic Atac, Sabre Wulf and
Gauntlet; and having played that build the user ruled the other way -- *"the
player and workers must be rendered as if overhead view ... it overrides all
previous decisions"*. The user has now seen both projections in play, not in
a mock, and the 2026-09-07 decision stands in full -- clarified the same day:
*directly* above, *"you should not see torso, only legs and arms moving"*. A
person from directly above is one compact mass of head and shoulders in the
middle of the box, and the arms and the legs come out from under it and are
what moves; nothing stacks below the head. See the vault's *2026-09-13 People
are drawn from above, and the rule goes* for the ruling and the grids, and
`assets/sprites/player.txt` for the drawing's own reasons.

**The bytes are not here.** Every figure is authored as a grid of `#` and `.`
in `assets/sprites/` and generated into `bitmaps_gen.py` by `tools/bitmaps.py`
(issue #48). They used to be declared here as hex *and* drawn in `assets/`, with
a test comparing the two -- which could say they disagreed but never which was
right. One source now, and the Z80 gets the same bytes from the same file.

**The people walk on four strides over three frames, and the cadence is four
pixels of travel.** Each walking figure has a neutral frame and two strides,
`NAME_N`, `NAME_A` and `NAME_B`, drawn in the cycle `N A N B`, and carries a
`walk.Stride` -- `Player.walk`, `Worker.walk` -- that advances every four
pixels the figure travels along either axis and at no other time. The player
moves a pixel a frame, so that is a new frame every four frames of walking,
about 12Hz, which is a walk; the cell cadence before it (issue #60) was a 6Hz
flip and the user played it and it read as a foot twitch under a sliding
blob. A figure that stops holds its stride. There is no still frame and no
idle counter. The stride is drawing state and nothing in the rules reads it:
the event log is byte-identical with the walk and without it, and the tests
pin that.

**The waiting worker does not walk; it waves on the shout.** `WORKER` is the
figure calling, arms up; `WORKER_W` is the wave, arms out, and it is drawn
for exactly the frames the worker's HELP is painted and no others. On the
event, never on a counter: a still figure given a counter to look alive was
refused twice (issues #60 and #72), and the shout already dirties the cells.

That overrides the 2026-09-10 refusal of people animation, which was made on a
byte count -- a second pre-shifted 8x16 frame is 512 bytes a figure -- and is
recorded as overruled rather than wrong. The user looked at a figure that slid
and asked for one that walked.

**The figures do not turn.** One orientation, head to the top of the
screen, and no mirror; the light is what says which way you are looking. The
2026-09-07 argument against facings survived both changes of projection --
four facings for three figures is about 10K of a 48K machine, and the cone is
the facing indicator, which in a game about light is the right one. The cost
is real and stated in the decision: with the torch off, nothing says which
way you are pointing.

**What the fade may remember.** The building is remembered; its inhabitants are
not. Walls, keys, bodies and nests stay drawn in ground the player is only
recalling, because they will still be where they were. People and Clegs move,
so drawing them from stale light would show the player where somebody is now
using light that has gone -- see `draw`'s `visible` argument.

**Every sprite is drawn with a mask a pixel wider than its ink** (issue #70).
Before a row's ink is set, every pixel its mask row names is cleared, so a
figure stands in a thin black halo on the stippled floor instead of being
made of it -- the thing The Great Escape did, and the thing the user's *clunky*
was measured to be in *Why the figures read as clunky*. The mask is the ink's
one-pixel dilation, clipped to the sprite's own box, and **it is derived by
`tools/bitmaps.py` and never drawn**: `MASKS` sits beside `BITMAPS` in the
generated table, and a change to a figure's hand changes its halo with it.
The port's sprite routine has been mask-and-OR since the cycle budget was
priced, so this is the prototype catching up with the model rather than the
model growing; the mask bytes cost the port nothing it was not already paying.
Tiles, the stipples and glyphs are not masked and composite by OR as they
always did -- see `draw`, and `MASK_OF` for how a sprite finds its own.

**The colour rule.** A sprite sets and clears pixels and never touches an
attribute. Each cell keeps whatever ink its light level gives it, so a sprite
spanning a light boundary is drawn part bright and part dim -- and two things
can never disagree about a cell's colour, because only one thing ever decides
it.

That is the whole mechanism for avoiding attribute clash, and it costs the
ability to tell entities apart by colour. So they are told apart by **size
first, silhouette second**: living people are 8x16, the objects are 8x8, and a
body is **16x8** -- two cells of a person, laid down.

**Half of the 2026-09-07 rule is withdrawn** (issue #59). It said *size says
whether a thing is a person and pose says whether it is alive*; the first half
stands and **orientation, not pose, now says whether a figure is upright**. A
cold reader given the built game called a corpse the person they were hunting
and called the player a bystander, twice in one session -- because pose reads on
a sprite sheet and does not survive to a stippled floor at six pixels across.
See `BODY`.

**The two-cell class, and what it costs the port.** A body is the first
drawable that is not eight pixels wide, so a row of it is two bytes and the
sprite routine has to know that. It is **cell-aligned**, so neither byte is
shifted or masked and there is no pre-shift table -- the same trick that took a
Cleg from 1,654 T-states to 830, and it is paid for by the fact that a body does
not move. `body_cells` is the rule for which two cells it lies across; **the
rule is authored, not guessed**, and it lives there because a coder inventing it
would be making a level-design decision in a drawing routine.

**A door is the one other 8x16 thing**, and it is 8x16 because it is the
person-shaped hole you walk out through. It is never mistaken for a person
because it never moves and it stands in a wall.

Drawing is byte-per-pixel here because that is how `core.screen` models the
display. On real hardware an 8-pixel-wide sprite at an arbitrary x needs its
rows shifted across two bytes and masked, which is where the cost lives -- see
issue #11.
"""

from spotlight.core.constants import CELL, COLS, SCREEN_H, SCREEN_W

from .bitmaps_gen import BITMAPS, MASKS
from .layout import PLAY_ROWS

PLAY_BOTTOM_PX = PLAY_ROWS * CELL

# --- people, 8x16, from directly above --------------------------------------

#: The player, neutral: the lamp at the front of his helmet, the helmet a
#: disc, the shoulders either side of it at the full width of the box -- the
#: kit -- his hands at the sides and his toes together behind. Rows 5 to 7
#: are the mass and never move. **The only figure with a full-width row**, and
#: it is at the shoulders: the widest thing in the room is you.
#:
#: **One mark, the lamp, and no bar** (issue #72, kept by #78). From issue #49
#: to #72 he wore a solid bar under his feet as well, because the first
#: plan-view figure had nothing else to tell him from a follower on lit floor.
#: The helmet disc six wide and the kit eight wide do that now, in the middle
#: columns where the eye is; the contract passes every frame of him against
#: every frame of the other two without the bar and without the lamp, and the
#: bar's five-pixel clause went with it. The reasoning and what it replaced
#: are in `assets/sprites/player.txt`.
PLAYER_N = BITMAPS["PLAYER_N"]

#: The player, striding: one arm swung forward up the screen beside the
#: helmet, the other back beside the toes, one leg out behind. The head and
#: the shoulders do not move.
PLAYER_A = BITMAPS["PLAYER_A"]

#: The other stride: frame A in the mirror, so across a cycle the figure stays
#: centred over its column and never leans.
PLAYER_B = BITMAPS["PLAYER_B"]

#: The player's walk cycle, indexed by `Player.stride`: four steps over three
#: frames, so drawing him is a table lookup rather than a branch, exactly as a
#: Cleg's wing is. Neutral between each stride is what makes the legs read as
#: passing each other rather than flicking.
PLAYER_FRAMES = (PLAYER_N, PLAYER_A, PLAYER_N, PLAYER_B)

#: A trapped worker, waiting and calling: the same person as the follower with
#: the arms up -- which from directly above is hands beside the crown, ahead
#: of the shoulders, and nothing else, and is the whole of the signal. The
#: hands sit either side of where the player's lamp is, so the two are never
#: the same shape where a glow finds them.
WORKER = BITMAPS["WORKER"]

#: The wave: the arms thrown out wide and up the screen, hands at the edges.
#: Drawn for exactly the frames the worker's HELP is painted
#: (issue #72) -- on the
#: event, never on a counter -- and `WORKER` again when the word clears. See
#: `assets/sprites/worker.txt` for why breathing was refused instead.
WORKER_W = BITMAPS["WORKER_W"]

#: Indexed by whether the worker is shouting this frame: `WORKER_FRAMES[False]`
#: is calling, `WORKER_FRAMES[True]` is the wave.
WORKER_FRAMES = (WORKER, WORKER_W)

#: The same person, freed and walking behind you, neutral: hands at the
#: sides below the shoulders, no lamp, and a head disc four wide where the
#: player has a helmet disc six wide. Shoulders six wide where his are eight.
#:
#: It exists because raised arms *mean* "I still need reaching", and leaving
#: them up on somebody already following you is a lie the player would act on.
#: It costs nothing to keep true: a worker is drawn from their state, so
#: somebody released back to waiting goes back to arms up on the frame they are
#: dropped -- and keeps their stride, which says which foot is forward and
#: nothing about what they are.
FOLLOWER_N = BITMAPS["FOLLOWER_N"]

#: The follower striding: the same swing and scissor as the player's.
FOLLOWER_A = BITMAPS["FOLLOWER_A"]

#: The other stride: frame A in the mirror.
FOLLOWER_B = BITMAPS["FOLLOWER_B"]

#: The follower's walk cycle, indexed by `Worker.stride`.
FOLLOWER_FRAMES = (FOLLOWER_N, FOLLOWER_A, FOLLOWER_N, FOLLOWER_B)

#: Somebody who died. **16 wide and 8 tall, cell-aligned, lying across two
#: cells of one row** -- the only drawable in the game that is wider than it is
#: tall, and that is the whole of the tell. Fifty-five pixels of ink against 44
#: for a worker and 84 for the player, spread *along* the floor rather than
#: stacked up it.
#:
#: **It was 8x16 and the tell was the pose, and the pose did not survive to the
#: played screen** (issue #59). A cold reader picked a corpse for a person
#: twice in one session and was confident both times. The reasoning behind the
#: old drawing was sound and its premise was false: seen from above a fallen
#: person is *longer* than a standing one, and an eight-pixel box cannot
#: express length, so pose was the only tell the box left -- and pose is a
#: sprite-sheet property. The argument, the two refused alternatives and the
#: three properties this drawing has to keep are in
#: `assets/sprites/body.txt`, beside the drawing.
#:
#: **Its rows are pairs of bytes**, not bare ones, because a row of it is two
#: bytes written into two cells. `draw` takes either.
BODY = BITMAPS["BODY"]

# --- doors, 8x16 -----------------------------------------------------------
#
# **A door is person-sized because it is the person-shaped hole you walk out
# through**, so it is the one thing that is 8x16 without being a person.

#: A way out you can use: two jambs, a four-pixel gap, no head and no sill.
#: **Where the wall stops and returns**, which is the same thing the doorway
#: tiles say -- a way through is the place the masonry ends.
DOOR_OPEN = BITMAPS["DOOR_OPEN"]

#: A way out that wants a key: a closed frame with a leaf and a keyhole. It is
#: **open at neither end where the open door is open at both**, so the pair
#: differs in outline and not in fill. Nothing in the playtest building is
#: locked, so this is drawn and unexercised; it exists because the shape rule
#: only means anything as a pair.
DOOR_LOCKED = BITMAPS["DOOR_LOCKED"]

# --- everything else, 8x8 --------------------------------------------------

#: A Cleg, wings out. **The frame flips when the fly steps a cell**, and since
#: issue #61 on the clock while it is attached to somebody and in place when
#: an idle fly twitches -- see `clegs.Cleg.wing`, which holds the bit and the
#: cost argument, and `assets/sprites/cleg.txt` for the drawing's reasons.
CLEG_A = BITMAPS["CLEG_A"]

#: The same Cleg, wings swept back. Head and axis the same; twenty pixels
#: differ, so that a flip is visible as a flip even under the eight-pixel
#: jump of a step (issue #61 -- the first pair differed by eight and read as
#: no animation at all). Four fewer pixels of ink, deliberately: the pulse.
CLEG_B = BITMAPS["CLEG_B"]

#: The same Cleg, wings half swept: the frame between the other two (issue
#: #73). Drawn twice a beat, on the way out and on the way back, so that the
#: wingbeat passes through a middle position instead of snapping between two
#: pictures. Ten pixels from A, eighteen from B, none of them on a lit
#: stipple dot; see `assets/sprites/cleg.txt`.
CLEG_M = BITMAPS["CLEG_M"]

#: The wingbeat as a cycle, indexed by the fly's own two-bit phase
#: (`clegs.Cleg.wing`), so that drawing a swarm is a table lookup rather than
#: a branch per fly. Four entries for three frames: M is in it twice, and
#: `clegs.WING_CYCLE` says four so the phase cannot run off the table.
CLEG_FRAMES = (CLEG_A, CLEG_M, CLEG_B, CLEG_M)

#: A nest: a squat, dense mass with a broken top edge and an off-centre lip.
#: Redrawn for issue #49 -- it was a rim with a bar in it, which at 1:1 is a
#: horizontal dash and reads as a UI element.
NEST = BITMAPS["NEST"]

#: A spotlight lying on the floor, dark: a hollow octagon.
LAMP_OFF = BITMAPS["LAMP_OFF"]

#: The same spotlight burning: the octagon filled.
LAMP_ON = BITMAPS["LAMP_ON"]

#: The searchlight's mount: a ring with a lens in it, bolted to its corner.
#: **Empty is dark, filled is burning, a lens is bolted down.**
HOUSING = BITMAPS["HOUSING"]

#: The ceiling fixture over an authored room light: a strip light seen from
#: above. Deliberately **not** an octagon, because a thing you walk under must
#: not look like a thing you can pick up.
BATTEN = BITMAPS["BATTEN"]

KEY = BITMAPS["KEY"]

#: The three figures on their feet, each with its unique frames, keyed by the
#: figure's name: three for a walker, two for the waiting worker. **They are
#: told apart inside one 8x16 box** -- by the lamp, the helmet, the kit and
#: the arms, in the middle columns -- and the contract that says so runs over
#: every frame of one against every frame of another (twenty-one pairs since
#: issue #72), because a player mid-stride stands beside a follower on the
#: other stride as often as not. A body is not in this table, and since issue
#: #59 that is the point: it is told from all three by the box itself.
STANDING = {
    "player": (PLAYER_N, PLAYER_A, PLAYER_B),
    "worker": (WORKER, WORKER_W),
    "follower": (FOLLOWER_N, FOLLOWER_A, FOLLOWER_B),
}

#: Every frame of every standing figure by its sheet name -- `player_n`,
#: `worker_w` -- in the order the people sheet shows them. The figure a frame
#: belongs to is the name before the last underscore, or the whole name for
#: `worker`, which has no letter because it is the figure at rest.
FRAMES = {
    "player_n": PLAYER_N, "player_a": PLAYER_A, "player_b": PLAYER_B,
    "follower_n": FOLLOWER_N, "follower_a": FOLLOWER_A,
    "follower_b": FOLLOWER_B,
    "worker": WORKER, "worker_w": WORKER_W,
}

#: Every drawable, for tests: the eight people frames, then everything else.
#:
#: **The order of the rest is the order they are laid out on the sprite
#: sheet** (three across), and it is chosen so that the one caption that
#: fills a ten-column block, DOOR LOCKED at eleven characters, sits in the
#: right-hand column, which is the only one with a column to spare. The
#: people are not on that sheet since issue #72 -- eight frames took it past
#: what fits between its heading and its legend -- and have a sheet of their
#: own with the walk laid out on it. `test_spike_gallery` pins that no
#: caption overruns its block or touches its neighbour, so a sprite inserted
#: here without a thought about the layout fails the suite rather than
#: quietly printing over one.
#:
#: The Cleg's three frames fill one row in the order a wingbeat draws them,
#: A M B (issue #73), so the beat can be read across the sheet; the two
#: doors stand in the right column, which is the only place DOOR LOCKED fits.
SPRITES = {
    **FRAMES,
    "body": BODY, "nest": NEST, "key": KEY,
    "cleg_a": CLEG_A, "cleg_m": CLEG_M, "cleg_b": CLEG_B,
    "lamp_off": LAMP_OFF, "lamp_on": LAMP_ON, "door_locked": DOOR_LOCKED,
    "housing": HOUSING, "batten": BATTEN, "door_open": DOOR_OPEN,
}

#: Every sprite-sheet entry that is a person, and so is captioned as one: the
#: eight standing frames, and the body lying down.
PEOPLE = tuple(FRAMES) + ("body",)

#: The two that are doors, and so are 8x16 without being people.
DOORS = ("door_open", "door_locked")

WIDTH = 8

#: The two-cell class: sixteen pixels across, which is BODY and nothing else.
WIDE = 16

#: Each sprite's mask, keyed by the sprite itself (issue #70). On the port a
#: sprite's record holds its mask bytes interleaved with its data, so the mask
#: is a property of the sprite and not an argument the caller has to remember;
#: this table is the prototype's way of saying the same thing, and it means
#: no call site had to change to be masked. Keyed by value: the generated
#: rows are tuples, and `test_every_silhouette_is_distinct` already promises
#: no two sprites share one. A sprite not in it -- a tile handed to `draw`, or
#: a test's own tuple -- draws by OR, exactly as everything did before.
MASK_OF = {BITMAPS[name]: mask for name, mask in MASKS.items()}


def row_bytes(row) -> tuple:
    """One row of a sprite, as its bytes, whatever width the sprite is.

    An 8-wide row is a bare integer because that is what every sprite in the
    game was until issue #59; a 16-wide row is a pair. The generated table
    keeps the pair as a tuple rather than flattening the block into sixteen
    bytes, so that anything treating `len(sprite)` as a height still gets the
    right answer and anything reading a row gets a shape it cannot silently
    misread.
    """
    return row if isinstance(row, tuple) else (row,)


def width_of(sprite) -> int:
    """How many pixels across a sprite is: 8, or 16 for the two-cell class."""
    return WIDTH * len(row_bytes(sprite[0]))


def draw(screen, sprite, x: int, y: int,
         clip_bottom: int = PLAY_BOTTOM_PX, visible=None,
         columns: int | None = None, mask=None) -> None:
    """Draw a sprite at pixel (x, y). Clears its mask, sets its ink; never
    writes an attribute.

    **For each drawn row: clear every pixel the mask row sets, then set every
    pixel the ink row sets** (issue #70). Until then pixels were set and never
    cleared, so a figure on lit floor was made of the stipple it stood on;
    now it stands in a one-pixel black halo, inside its own box. Outside the
    mask nothing is touched, so a sprite still composites over the room
    rather than punching a box-shaped hole in it. The two passes are one loop
    here because the ink is inside the mask by construction: a pixel is set
    if it is ink, cleared if it is only halo, and left alone otherwise. That
    is the same picture as clear-then-OR and it is what the Z80's
    `AND mask : OR data` does per byte.

    `mask` is the sprite's own by default, from `MASK_OF`; a sprite with no
    entry draws by OR. It can be given explicitly, and the sprite sheet and
    the tests are the only callers that do.

    `visible` is an optional test taking a cell and returning whether the
    sprite may be drawn in it. People and Clegs pass one, so that they show
    only where a light is actually on them; the building's fixtures do not,
    because the fade is allowed to remember those. Drawing is already per cell,
    so a worker half inside a beam is drawn half -- the same mechanism that
    gives a figure its two-tone edge, cutting all the way to nothing. **The
    mask is under the same test**: a cell the ink may not be drawn in is a
    cell the mask may not clear either, or a figure half in a beam would punch
    a hole in the dark half and show, by the hole, where it was.

    `columns` is how many **bytes** of each row to draw, and it exists for one
    case: a body in a one-cell gap, which is drawn as its head end alone. The
    default is the whole sprite. It is a count of bytes rather than of pixels
    because on the Z80 that is a loop counter, and half a byte is not something
    that routine could do cheaply. It governs the mask as it governs the ink.
    """
    if mask is None and isinstance(sprite, tuple):
        mask = MASK_OF.get(sprite)
    shown: dict[tuple[int, int], bool] = {}
    for dy, row in enumerate(sprite):
        py = y + dy
        if not 0 <= py < min(SCREEN_H, clip_bottom):
            continue
        cy = py // CELL
        base = py * SCREEN_W
        octets = row_bytes(row)
        halo = row_bytes(mask[dy]) if mask else ()
        for octet, bits in enumerate(octets[:columns]):
            clear = halo[octet] if octet < len(halo) else 0
            touched = bits | clear
            if not touched:
                continue
            left = x + octet * WIDTH
            for dx in range(WIDTH):
                bit = 0x80 >> dx
                if not touched & bit:
                    continue
                px = left + dx
                if not 0 <= px < SCREEN_W:
                    continue
                if visible is not None:
                    cell = (px // CELL, cy)
                    ok = shown.get(cell)
                    if ok is None:
                        ok = shown[cell] = bool(visible(*cell))
                    if not ok:
                        continue
                screen.pixels[base + px] = 1 if bits & bit else 0


def cells_spanned(x: int, y: int, height: int,
                  width: int = WIDTH) -> set[tuple[int, int]]:
    """Which attribute cells a sprite at (x, y) touches.

    An 8-wide sprite at an x that is not a multiple of 8 straddles two columns;
    an 8-tall one at an odd y straddles two rows. So an 8x8 sprite can span four
    cells, and each of them keeps its own colour.

    `width` is the sprite's, and a 16-wide body drawn cell-aligned spans exactly
    the two cells `body_cells` chose -- never three, because it is aligned.
    """
    return {
        (cx, cy)
        for cx in range(x // CELL, (x + width - 1) // CELL + 1)
        for cy in range(y // CELL, (y + height - 1) // CELL + 1)
    }


# --- where a body lies ------------------------------------------------------

def body_cells(cx: int, cy: int, is_solid=None) -> tuple:
    """The cells a body at `(cx, cy)` is drawn across, left to right.

    **The body's stored position does not move; only the drawing snaps to a
    cell** (issue #59). `(cx, cy)` is the cell the worker fell in -- the one
    `Worker.cell` returns and every mechanism that reads a body has always read
    -- and this says which neighbour the drawing extends into. It returns two
    cells, or one when there is no room for two.

    **The rule is authored, in the vault decision and in
    `assets/sprites/body.txt`.** It is written down because it is the one part
    a coder would otherwise invent, and inventing it would be taking a
    level-design decision inside a drawing routine:

    * **It lies into the cell with floor in it.**
    * **If both neighbours are floor, it lies the way the room is wider** --
      that is, away from the nearer side wall. A room is exactly the play area,
      so this is one compare of `cx` against the middle column, which is what
      it costs on the Z80.
    * **If a wall refuses that cell, it falls back the other way**, which is
      the rule the spray's footprint already uses.
    * **If both neighbours are wall -- a one-cell gap -- only the head end is
      drawn, in the body's own cell.** One cell of it reads as somebody huddled
      in a doorway, which is the honest picture of what happened, and it is
      the only case in which a body is a single cell.

    **Lying west draws the same bytes one cell to the left; it does not
    mirror.** A mirrored copy would be a second sixteen-byte table on a machine
    where the art budget is the argument, and the decision priced this drawing
    at sixteen bytes. So the head end is in the body's own cell when it lies
    east and in the neighbour when it lies west; what is constant is that the
    stored cell is always one of the two.

    `is_solid` is the room's own, the single authority on what is walkable. It
    is optional so that tests and the sprite sheet can ask for the geometry
    alone -- with nothing to refuse a cell, the body lies whichever way the room
    is wider and stays there.
    """
    def free(col: int) -> bool:
        # The screen edge refuses a cell as firmly as a wall does, and it is
        # checked here rather than left to `is_solid`: the column past a
        # doorway answers for the room next door, which is somewhere this
        # room's drawing cannot go.
        return 0 <= col < COLS and not (is_solid is not None
                                        and is_solid(col, cy))

    # Away from the nearer side wall: the left half of the room lies east.
    first, second = (cx + 1, cx - 1) if cx < COLS // 2 else (cx - 1, cx + 1)
    for col in (first, second):
        if free(col):
            return (((cx, cy), (col, cy)) if col > cx
                    else ((col, cy), (cx, cy)))
    return ((cx, cy),)
