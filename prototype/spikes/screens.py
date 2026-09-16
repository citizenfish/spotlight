"""The title screen and the ending screen: a run with a beginning and an end.

Issue #15. Before this the window opened straight into the game and
closed on the last life, and everything the player needed to know was either in
a module docstring or printed to a terminal they were not looking at.

**Everything here is written for somebody who has never played a game like
this.** That decision was taken with the playtest plan and it is what all the
wording below is for. No vocabulary is assumed:

* Not "lives". A stranger does not know that three of something means three
  attempts, so the screen says *tries* and the ending says what ran out.
* Not that a bar going down is bad. The title says in words that the people are
  bleeding and that the clock is what kills them.
* Not that a key exists because a game usually has one. `T` is the whole bargain
  the design rests on and nothing on screen said the key was there.
* Not that a shape is a person. The title says there are seven people and that
  they have to be walked out.

The bargain gets its own paragraph, because it is the one thing we want a
tester to have an opinion about: the torch shows you the room, and it shows the
flies where you are.

Both screens draw through `core.Screen` like everything else -- 8x8 glyphs from
the game's own font, one ink per cell -- so they are the same two colours per
cell the Spectrum will have, and neither is a Pygame text overlay that would
have to be rebuilt at port time.

**The words are not touched, and that is the larger half of issue #56.** Two
people have now read this screen cold, one of whom does not play games like
this, and both of them found it doing its job. What issue #56 redrew is the
frame -- the title became a double-height logo and everything below it moved
down one row -- and `test_screens.py` pins `STORY`, `CONTROLS`, `WARNING` and
all three prompts character for character, so a later tidy-up has to argue with
a failing test rather than with nobody. The strongest temptation in a look round
is to rewrite prose that is already working, and for most testers this screen is
the only instructions they will ever read.

Issue #76 laid the searchlight's beam across the title, on the cells the words
leave empty and on no other -- see `draw_beam`. The same pin holds: every text
cell is the same pixels and the same attribute byte with the beam as without.
"""

from spotlight.core.constants import (
    BLACK, CELL, COLS, CYAN, GREEN, RED, ROWS, SCREEN_W, WHITE, YELLOW,
)
from spotlight.core.screen import Screen, attr_byte

from . import font
from .floor import stipple
from .lighting import LIT
from .logo_gen import BITMAPS as LOGO

#: The title, spaced out. It used to be drawn in the 8x8 font, where the space
#: was the only size there was; since issue #56 it is drawn as double-height
#: glyphs and **the string is still what decides the columns** -- one glyph per
#: non-space character, at the column that character occupies in the centred
#: string. That is not a trick to save code. The letter-spacing here is the
#: spacing a first-time reader called legible at 1:1, and deriving the logo from
#: the string is what guarantees it stays that spacing rather than a new one
#: that happens to look similar.
TITLE = "S P O T L I G H T"

#: The cell row the logo's top half sits on; its bottom half is the row under
#: it. Everything below moved down one row to make space, which the screen had.
LOGO_TOP = 1

#: What the game is, in plain words, before any control is named. A stranger
#: who reads only this should know what they are being asked to do.
STORY = (
    "SEVEN PEOPLE ARE HURT AND",
    "TRAPPED IN A DARK BUILDING.",
    "FIND THEM, AND WALK THEM OUT",
    "THROUGH THE RED EXIT DOOR",
    "BEFORE THEY BLEED TO DEATH.",
)

#: The whole control scheme. Three of them, named as keys and as verbs.
CONTROLS = (
    ("ARROW KEYS", "WALK"),
    ("T", "TORCH ON AND OFF"),
    ("SPACE", "FLYSPRAY"),
)

#: The bargain, which is the thing the playtest is actually about.
WARNING = (
    "YOUR TORCH SHOWS YOU THE ROOM.",
    "IT ALSO SHOWS THE BITING FLIES",
    "WHERE YOU ARE.",
)

#: **`S`, and not any key** (issue #63). Any-key start is what a tester leaning
#: on the keyboard, or pressing `T` for the torch while still reading the
#: controls, triggers by accident -- and this screen is the only instructions
#: most testers ever read. `S` is not a game key, so nothing a player reaches
#: for in play starts a run they had not finished reading about.
START_PROMPT = "PRESS S TO START"
AGAIN_PROMPT = "PRESS SPACE TO PLAY AGAIN"
STOP_PROMPT = "PRESS ESC TO STOP"

#: Column the control descriptions line up in, so the keys read as a list.
_VERB_COL = 15


def _attr(ink: int, bright: bool = False, flash: bool = False) -> int:
    return attr_byte(ink=ink, paper=BLACK, bright=bright, flash=flash)


def write(screen: Screen, cx: int, cy: int, text: str, ink: int = WHITE,
          bright: bool = False, flash: bool = False) -> None:
    """Draw text and colour the cells it lands in.

    `font.draw_text` sets pixels only -- in the play area the light decides the
    attribute, and it would be wrong for a glyph to choose its own. These
    screens have no light in them, so they set their own.
    """
    font.draw_text(screen, cx, cy, text)
    attr = _attr(ink, bright, flash)
    for i in range(len(text)):
        if 0 <= cx + i < COLS and 0 <= cy < ROWS:
            screen.set_attr(cx + i, cy, attr)


def centre(text: str) -> int:
    """The column that centres `text`, clamped to the screen."""
    return max(0, (COLS - len(text)) // 2)


def mmss(seconds: int) -> str:
    """Minutes and seconds. A run is minutes long, and 92 does not read as one."""
    return f"{seconds // 60}:{seconds % 60:02d}"


def draw_logo(screen: Screen, top: int = LOGO_TOP) -> None:
    """`SPOTLIGHT` in double-height block letters, two cell rows tall.

    Issue #56. The title used to be one row of the 8x8 font with a space
    between each letter, which is a caption rather than a logo -- and on a
    machine whose two most famous games both drew their titles as double-height
    text it was the one place this build was not doing the hardware justice.

    **The columns come from `TITLE`.** Each non-space character is drawn at the
    column it occupies in the centred string, so the letter-spacing is the one
    that was read and approved rather than a new one invented here. Change the
    string and the logo moves with it; there is no second layout to keep in
    step.

    **Drawn as two 8x8 halves, one per cell row**, through the same
    `font.draw_glyph` everything else on this screen uses. That is not a
    convenience: an 8x16 glyph on the Spectrum is written as two cell-aligned
    eight-byte runs anyway, because the display file is addressed by cell row,
    so this is the shape the port's routine already has to take.

    **Attributes on both rows of every glyph**, bright yellow on black. A glyph
    that coloured only its top half would be half a word in white -- the cells
    are cleared to white ink by `draw_title` -- and that is exactly the sort of
    thing an attribute-grid machine punishes.

    The table is imported from `logo_gen`, which nothing on the play path
    imports: 128 bytes that are paid for once, on a screen that is not the game.
    (The decision note and issue #56 both say 144, which is nine glyphs'
    worth; there are eight, because `T` is drawn once and used twice. See
    `test_screens.test_the_logo_costs_eight_glyphs_not_nine`.)
    """
    attr = _attr(YELLOW, bright=True)
    col = centre(TITLE)
    for i, char in enumerate(TITLE):
        if char == " ":
            continue
        rows = LOGO[f"LOGO_{char}"]
        cx = col + i
        font.draw_glyph(screen, cx, top, rows[:8])
        font.draw_glyph(screen, cx, top + 1, rows[8:])
        screen.set_attr(cx, top, attr)
        screen.set_attr(cx, top + 1, attr)


#: **The beam across the title** (issue #76). The searchlight's own disc --
#: radius 3, the integer test `sources.Roaming.emit` uses -- walked down a
#: diagonal from off the top right: at `step` the centre is
#: `(BEAM_START_X - step, BEAM_START_Y + step // 2)`, one column left and half
#: a row down per step, for `BEAM_STEPS` steps. Forty steps take it from
#: (34, -4), wholly off the screen, to (-5, 15), wholly off it again, so the
#: beam enters and leaves like a light passing rather than one switched on.
#: The title's searchlight (issue #104, Look and feel 3 row 11): the housing
#: bolted at a cell in the top-right corner, and its disc, standing still,
#: centred two cells down and in. The beam of #76 ran a diagonal through the
#: story text and read as dust at 1:1; a pool that does not move is the
#: fixture the player will meet in the room, seen before they meet it.
POOL_RADIUS = 3
HOUSING_CELL = (30, 0)
POOL_CENTRE = (28, 2)


def _has_ink(screen: Screen, cx: int, cy: int) -> bool:
    """Whether `draw_words` set any pixel in the cell. A space between two
    words has none, so the beam runs through the spaces and round the words."""
    for dy in range(CELL):
        start = (cy * CELL + dy) * SCREEN_W + cx * CELL
        if any(screen.pixels[start:start + CELL]):
            return True
    return False


def pool_cells(screen: Screen) -> set[tuple[int, int]]:
    """The cells the pool is drawn on, given the words already on `screen`.

    The disc, clipped to the screen, minus every cell that holds a pixel and
    minus the housing's own cell. Computed as a set before a dot is drawn,
    and it has to be: the pool is itself pixels, and a routine that tested
    cells as it went would find its own earlier dots and call them text.

    The disc test is `Roaming.emit`'s written out rather than called: the
    title has no light field, and the same eleven-word test in two places is
    cheaper than one made to be thrown away.
    """
    r2 = POOL_RADIUS * POOL_RADIUS
    x, y = POOL_CENTRE
    cells = set()
    for dy in range(-POOL_RADIUS, POOL_RADIUS + 1):
        for dx in range(-POOL_RADIUS, POOL_RADIUS + 1):
            if dx * dx + dy * dy > r2:
                continue
            cx, cy = x + dx, y + dy
            if 0 <= cx < COLS and 0 <= cy < ROWS \
                    and (cx, cy) != HOUSING_CELL \
                    and not _has_ink(screen, cx, cy):
                cells.add((cx, cy))
    return cells


def draw_pool(screen: Screen) -> None:
    """The searchlight's housing and its pool, standing still, in the corner.

    Issue #104, replacing the moving beam of #76 (ruling 10 of *Look and feel
    2*, overturned by row 11 of *Look and feel 3*): the beam ran a diagonal
    through the story text, and at 1:1 the reviewers read it as dust on the
    only briefing a tester gets. The reference's device -- one ink that never
    shares a cell with the words -- stands; the object is now the fixture the
    player meets in the room, seen before they meet it, and it does not move.

    **Non-bright yellow, on cells that hold no text, and never the other way
    round.** The logo is bright yellow and the keys are bright yellow; the
    pool is the same hue a step dimmer, which reads as light rather than as
    more words. The housing's cell is bright white, as it is in the room.

    **The words are not touched.** Same pixels, same attributes, same rows
    and columns as before the pool: `test_screens` pins every text cell with
    and without it.

    **Nothing resident, nothing per frame.** One disc of twenty-nine cells
    and one sprite, drawn once on a screen with no clock running.
    """
    from . import sprites
    attr = _attr(YELLOW)
    for cx, cy in pool_cells(screen):
        stipple(screen, cx, cy, LIT)
        screen.set_attr(cx, cy, attr)
    hx, hy = HOUSING_CELL
    sprites.draw(screen, sprites.HOUSING, hx * CELL, hy * CELL,
                 clip_bottom=ROWS * CELL)
    screen.set_attr(hx, hy, _attr(WHITE, bright=True))


def draw_title(screen: Screen) -> None:
    """The first thing a tester sees, and for many of them the only instructions.

    The words, then the beam across them (issue #76). The order is the rule:
    the beam is laid on whatever cells the words left empty, so the words go
    down first and the beam finds its way round them. Drawn the other way the
    words would land on stippled cells and the beam would have to be scrubbed
    out from under them.
    """
    draw_words(screen)
    draw_pool(screen)


def draw_words(screen: Screen) -> None:
    """The title without its beam: the logo, the prose and the prompt.

    This is what `draw_title` was before issue #76, split out so a test can
    hold the words alone against the words with the beam and show every text
    cell identical. Every row below the logo moved down one when the logo
    arrived (issue #56) and nothing was re-wrapped, re-centred or reworded on
    the way: story on 5-9, controls on 12-14, the bargain on 17-19, the prompt
    on 22.
    """
    screen.clear(_attr(WHITE))
    draw_logo(screen)

    for i, line in enumerate(STORY):
        write(screen, 2, 5 + i, line, WHITE)

    for i, (key, verb) in enumerate(CONTROLS):
        write(screen, 2, 12 + i, key, YELLOW, bright=True)
        write(screen, _VERB_COL, 12 + i, verb, WHITE)

    for i, line in enumerate(WARNING):
        write(screen, 1, 17 + i, line, CYAN)

    # The three badges on the strip, taught here in one line (issue #90): a
    # badge is a picture you have to have been taught, and row 20 was empty.
    draw_badge_legend(screen)

    # Flashing, because it is the one thing that has to be noticed and the
    # attribute flash bit costs nothing on the target. It is also the only
    # movement on an otherwise static screen.
    write(screen, centre(START_PROMPT), 23, START_PROMPT, WHITE, bright=True,
          flash=True)


#: The strip's three badges and what each counts, as (mark, ink, word).
BADGE_LEGEND = (
    (font.WITH_MARK, GREEN, "WITH YOU"),
    (font.DEAD_MARK, RED, "DEAD"),
    (font.LEFT_MARK, WHITE, "LEFT"),
    (font.SAFE_MARK, GREEN, "SAFE"),
)
#: Row 21 since issue #104 (Look and feel 3 row 11): the legend sat hard
#: against the warning's last line and read as a fourth line of it.
BADGE_LEGEND_ROW = 21


def draw_badge_legend(screen: Screen, row: int = BADGE_LEGEND_ROW) -> None:
    """One line: each mark in its own colour, its word in white after it,
    a cell between entries. Four marks since issue #96, thirty-one cells."""
    width = sum(1 + 1 + len(word) + 1 for _m, _i, word in BADGE_LEGEND) - 1
    cx = (COLS - width) // 2
    for mark, ink, word in BADGE_LEGEND:
        font.draw_glyph(screen, cx, row, mark)
        screen.set_attr(cx, row, _attr(ink))
        write(screen, cx + 2, row, word, WHITE)
        cx += 1 + 1 + len(word) + 1


def draw_ending(screen: Screen, headline: tuple[str, str], rescued: int,
                lost: int, inside: int, total: int, seconds: int) -> None:
    """How the run went, on the screen, in words and numbers that add up.

    Three counts and a time. The three counts are deliberately everybody --
    out, dead, and still in the building -- because the spike's report could
    lose people: three workers in the tail when the last life went appeared in
    no column, and a run reported "0 out, 0 lost, 4 never found" with seven
    people in the room. Anybody reading this screen can add it up, so it has to
    be addable.

    `headline` is the two lines from `session.ENDING_TEXT`. Issue #20 changes
    which endings can happen and issue #21 adds a room; both are new entries in
    that table rather than changes here.
    """
    screen.clear(_attr(WHITE))
    # The logo, since issue #104 (Look and feel 3 row 12): it is resident
    # for the opening anyway, and the ending was the one screen still a
    # bare table. Everything below it moved down two rows; nothing reworded.
    draw_logo(screen, top=1)
    first, second = headline
    write(screen, centre(first), 5, first, WHITE, bright=True)
    write(screen, centre(second), 7, second, WHITE)

    rows = (
        ("GOT OUT ALIVE", f"{rescued} OF {total}", GREEN),
        ("DIED", f"{lost}", RED),
        ("STILL INSIDE", f"{inside}", YELLOW),
        ("TIME TAKEN", mmss(seconds), WHITE),
    )
    for i, (label, value, ink) in enumerate(rows):
        row = 10 + i * 2
        write(screen, 4, row, label, WHITE)
        write(screen, 4 + _VERB_COL, row, value, ink, bright=True)

    write(screen, centre(AGAIN_PROMPT), 19, AGAIN_PROMPT, WHITE, bright=True,
          flash=True)
    write(screen, centre(STOP_PROMPT), 21, STOP_PROMPT, WHITE)
