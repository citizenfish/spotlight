"""The title screen and the ending screen: a run with a beginning and an end.

Issue #15. Before this the window opened straight into the opening flash and
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
"""

from spotlight.core.constants import (
    BLACK, COLS, CYAN, GREEN, RED, ROWS, WHITE, YELLOW,
)
from spotlight.core.screen import Screen, attr_byte

from . import font
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

START_PROMPT = "PRESS ANY KEY TO START"
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


def draw_title(screen: Screen) -> None:
    """The first thing a tester sees, and for many of them the only instructions.

    Every row below the logo moved down one when the logo arrived (issue #56)
    and nothing was re-wrapped, re-centred or reworded on the way: story on 5-9,
    controls on 12-14, the bargain on 17-19, the prompt on 22.
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

    # Flashing, because it is the one thing that has to be noticed and the
    # attribute flash bit costs nothing on the target. It is also the only
    # movement on an otherwise static screen.
    write(screen, centre(START_PROMPT), 22, START_PROMPT, WHITE, bright=True,
          flash=True)


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
    first, second = headline
    write(screen, centre(first), 3, first, WHITE, bright=True)
    write(screen, centre(second), 5, second, WHITE)

    rows = (
        ("GOT OUT ALIVE", f"{rescued} OF {total}", GREEN),
        ("DIED", f"{lost}", RED),
        ("STILL INSIDE", f"{inside}", YELLOW),
        ("TIME TAKEN", mmss(seconds), WHITE),
    )
    for i, (label, value, ink) in enumerate(rows):
        row = 9 + i * 2
        write(screen, 4, row, label, WHITE)
        write(screen, 4 + _VERB_COL, row, value, ink, bright=True)

    write(screen, centre(AGAIN_PROMPT), 19, AGAIN_PROMPT, WHITE, bright=True,
          flash=True)
    write(screen, centre(STOP_PROMPT), 21, STOP_PROMPT, WHITE)
