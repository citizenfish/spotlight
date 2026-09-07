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
"""

from spotlight.core.constants import (
    BLACK, COLS, CYAN, GREEN, RED, ROWS, WHITE, YELLOW,
)
from spotlight.core.screen import Screen, attr_byte

from . import font

#: The title, spaced out. There is no larger font, so the space is the size.
TITLE = "S P O T L I G H T"

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


def draw_title(screen: Screen) -> None:
    """The first thing a tester sees, and for many of them the only instructions."""
    screen.clear(_attr(WHITE))
    write(screen, centre(TITLE), 2, TITLE, YELLOW, bright=True)

    for i, line in enumerate(STORY):
        write(screen, 2, 4 + i, line, WHITE)

    for i, (key, verb) in enumerate(CONTROLS):
        write(screen, 2, 11 + i, key, YELLOW, bright=True)
        write(screen, _VERB_COL, 11 + i, verb, WHITE)

    for i, line in enumerate(WARNING):
        write(screen, 1, 16 + i, line, CYAN)

    # Flashing, because it is the one thing that has to be noticed and the
    # attribute flash bit costs nothing on the target. It is also the only
    # movement on an otherwise static screen.
    write(screen, centre(START_PROMPT), 21, START_PROMPT, WHITE, bright=True,
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
