"""The title and ending screens: what a stranger is told, and when.

Issue #15. The testers are people who do not know Spectrum games, so nothing
about the vocabulary of one can be assumed. These tests pin the things that
were missing rather than the layout, which is free to move:

* the three controls, **named on screen**, because they were named only in a
  module docstring and `T` -- the whole bargain -- was invisible;
* an ending that says *which* of the three endings happened, because the window
  used to just shut;
* a tally that adds up, because the printed report could lose people.
"""

import pytest

from spotlight.core.constants import COLS
from spotlight.core.screen import Screen

from spikes import screens, session
from screenreader import glyph_at, read, rows


@pytest.fixture
def title():
    screen = Screen()
    screens.draw_title(screen)
    return screen


def read_logo(screen) -> str:
    """The word the double-height logo spells, read back off the screen.

    The 8x8 font reader cannot see the logo -- these are not font glyphs -- so
    the letters are recognised by their own sixteen bytes, top half and bottom
    half of each cell column. Reading the screen rather than the constants is
    the same discipline as `screenreader`: a test on the table alone would pass
    with the drawing code deleted.
    """
    from spikes.logo_gen import BITMAPS

    letters = {rows_: name[len("LOGO_"):] for name, rows_ in BITMAPS.items()}
    word = ""
    for cx in range(COLS):
        glyph = (glyph_at(screen, cx, screens.LOGO_TOP)
                 + glyph_at(screen, cx, screens.LOGO_TOP + 1))
        if any(glyph):
            word += letters.get(glyph, "?")
    return word


def test_the_title_names_the_game(title):
    """It used to read `SPOTLIGHT` out of the 8x8 font; since issue #56 the
    name is a double-height face, so it is read back through its own table."""
    assert read_logo(title) == "SPOTLIGHT"


def test_the_title_names_all_three_controls(title):
    """The whole control scheme, on screen, in words.

    A stranger cannot guess that `T` exists, and until they press it the game
    they are playing is not the game the design is about.
    """
    text = rows(title)
    for key, verb in screens.CONTROLS:
        assert any(key in line and verb in line for line in text), (key, verb)


def test_the_title_says_what_the_game_is_before_it_says_which_keys(title):
    """Plain words first: seven people, hurt, get them out before they die.

    Ordered deliberately. A control list is meaningless to somebody who does
    not yet know what they are being asked to do.
    """
    text = rows(title)
    story_row = min(i for i, line in enumerate(text) if "SEVEN PEOPLE" in line)
    keys_row = min(i for i, line in enumerate(text) if "ARROW KEYS" in line)
    assert story_row < keys_row
    joined = " ".join(text)
    assert "BLEED" in joined
    assert "EXIT DOOR" in joined


def test_the_title_states_the_bargain(title):
    """The one thing the playtest is actually asking about."""
    joined = " ".join(rows(title))
    assert "TORCH SHOWS YOU THE ROOM" in joined
    assert "SHOWS THE BITING FLIES" in joined


def test_the_title_tells_them_to_press_a_key(title):
    assert screens.START_PROMPT in rows(title)


@pytest.mark.parametrize("ending", [session.ALL_OUT, session.NOBODY_LEFT,
                                    session.NO_LIVES])
def test_every_ending_says_which_one_happened(ending):
    screen = Screen()
    screens.draw_ending(screen, session.ENDING_TEXT[ending], 3, 2, 2, 7, 92)
    text = rows(screen)
    assert session.ENDING_TEXT[ending][0] in text
    assert session.ENDING_TEXT[ending][1] in text


def test_the_three_endings_read_differently():
    """Not just present -- distinguishable. All three used to be one `print`."""
    headlines = {session.ENDING_TEXT[e][0]
                 for e in (session.ALL_OUT, session.NOBODY_LEFT,
                           session.NO_LIVES)}
    assert len(headlines) == 3


def test_the_ending_tally_adds_up_on_screen():
    """Out plus died plus still inside is everybody, read off the screen.

    The spike printed "0 out, 0 lost, 4 never found" for a room of seven,
    because three in the tail were in no column at all. Whatever the screen
    says, a player can add it up, so it has to add up.
    """
    screen = Screen()
    screens.draw_ending(screen, session.ENDING_TEXT[session.NO_LIVES],
                        3, 2, 2, 7, 92)
    text = rows(screen)
    out = next(line for line in text if line.startswith("GOT OUT"))
    died = next(line for line in text if line.startswith("DIED"))
    inside = next(line for line in text if line.startswith("STILL INSIDE"))
    assert out.endswith("3 OF 7")
    assert int(died.split()[-1]) == 2
    assert int(inside.split()[-1]) == 2
    assert 3 + 2 + 2 == 7


def test_the_ending_says_how_long_it_took():
    screen = Screen()
    screens.draw_ending(screen, session.ENDING_TEXT[session.ALL_OUT],
                        7, 0, 0, 7, 92)
    assert any("1:32" in line for line in rows(screen))


def test_the_ending_names_the_key_to_go_again():
    screen = Screen()
    screens.draw_ending(screen, session.ENDING_TEXT[session.ALL_OUT],
                        7, 0, 0, 7, 10)
    text = rows(screen)
    assert screens.AGAIN_PROMPT in text
    assert screens.STOP_PROMPT in text


def test_minutes_and_seconds():
    """92 seconds does not read as a minute and a half to anybody."""
    assert screens.mmss(0) == "0:00"
    assert screens.mmss(9) == "0:09"
    assert screens.mmss(92) == "1:32"
    assert screens.mmss(600) == "10:00"


def test_screens_use_one_ink_per_cell():
    """Two colours per 8x8 cell is the hardware, so a screen cannot cheat.

    Cheap to state and worth stating: these are the only two screens in the
    game drawn as prose, and prose is where somebody would reach for a colour
    per word.
    """
    from spotlight.core.screen import unpack_attr
    screen = Screen()
    screens.draw_title(screen)
    for attr in screen.attrs:
        _ink, paper, _bright, _flash = unpack_attr(attr)
        assert paper == 0        # black paper everywhere; ink carries the text


def test_every_ending_fits_on_the_screen():
    """Thirty-two cells and no wrapping: `write` clips, so a line one word too
    long loses the word silently and the player is told half a sentence.

    Found by writing a truer line for `ABANDONED` and counting afterwards.
    """
    for name, lines in session.ENDING_TEXT.items():
        for line in lines:
            assert len(line) <= COLS, f"{name}: {line!r} is {len(line)} cells"


# --- the logo, and the words it is not allowed to touch (issue #56) ---------

#: The face, as the vault's *Art Direction* specifies it and as issue #56
#: repeats it, byte for byte.
#:
#: **This is the test the slice needed most and it is the dullest one here.**
#: The glyphs were moved from hex in a note into a grid of `#` and `.` in
#: `assets/logo/logo.txt`, by hand, sixteen rows eight times. The only real risk
#: in that is a mis-transcribed row, which nobody would see on a title screen --
#: one wrong pixel in the waist of an S reads as a slightly different S. So the
#: authored art is compared against the numbers that were agreed, and a slipped
#: row fails here rather than shipping.
LOGO_FACE = {
    "S": (0x3C, 0x7E, 0xE7, 0xE0, 0xE0, 0xF0, 0x7C, 0x3E,
          0x07, 0x03, 0x03, 0xE7, 0xE7, 0x7E, 0x3C, 0x00),
    "P": (0xFC, 0xFE, 0xE7, 0xE3, 0xE3, 0xE7, 0xFE, 0xFC,
          0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0x00),
    "O": (0x3C, 0x7E, 0xE7, 0xC3, 0xC3, 0xC3, 0xC3, 0xC3,
          0xC3, 0xC3, 0xC3, 0xC3, 0xE7, 0x7E, 0x3C, 0x00),
    "T": (0xFF, 0xFF, 0x3C, 0x3C, 0x3C, 0x3C, 0x3C, 0x3C,
          0x3C, 0x3C, 0x3C, 0x3C, 0x3C, 0x3C, 0x3C, 0x00),
    "L": (0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0xE0,
          0xE0, 0xE0, 0xE0, 0xE0, 0xE0, 0xFF, 0xFF, 0x00),
    "I": (0xFF, 0xFF, 0x3C, 0x3C, 0x3C, 0x3C, 0x3C, 0x3C,
          0x3C, 0x3C, 0x3C, 0x3C, 0x3C, 0xFF, 0xFF, 0x00),
    "G": (0x3C, 0x7E, 0xE7, 0xC3, 0xC0, 0xC0, 0xC0, 0xCF,
          0xCF, 0xC3, 0xC3, 0xC3, 0xE7, 0x7E, 0x3C, 0x00),
    "H": (0xC3, 0xC3, 0xC3, 0xC3, 0xC3, 0xC3, 0xC3, 0xFF,
          0xFF, 0xC3, 0xC3, 0xC3, 0xC3, 0xC3, 0xC3, 0x00),
}


def test_the_generated_logo_is_the_face_that_was_agreed():
    from spikes.logo_gen import BITMAPS

    assert {name[len("LOGO_"):]: rows_ for name, rows_ in BITMAPS.items()} \
        == LOGO_FACE


def test_the_logo_costs_eight_glyphs_not_nine():
    """**128 bytes, and the note that priced it says 144.**

    Both figures come from the same sentence and only one of them can be right:
    *eight glyphs, because T appears twice* and *eight glyphs at sixteen bytes
    is 144*. Eight sixteen-byte glyphs are 128 bytes; 144 is nine of them, which
    is the count before the repeated `T` was noticed. The saving is real and
    small, and it is recorded here rather than quietly fixed in the code so that
    the memory table in the vault can be corrected against something.

    What the figure is for, and why it is worth a test at all: it is the number
    the *font, not a picture* decision was taken on, against 6,912 bytes for a
    screen-sized logo. Sixteen bytes a glyph and not thirty-two, because the
    face is double-**height** only -- double-width would be 256 bytes here and,
    at two cells a letter, the spaced form would not fit across 32 columns, and
    the spacing is the thing a first-time reader praised.
    """
    from spikes.logo_gen import BITMAPS

    assert len(BITMAPS) == 8, "T is drawn once and used twice"
    assert all(len(rows_) == 16 for rows_ in BITMAPS.values())
    assert sum(len(rows_) for rows_ in BITMAPS.values()) == 128


def test_the_logo_stands_in_the_columns_the_title_string_gives_it(title):
    """**The spacing is not re-invented, it is inherited.**

    Every letter is drawn at the column its character occupies in the centred
    `TITLE` string, so the gaps are the ones two cold readers saw. A test that
    only checked the letters were legible would let somebody re-space them.
    """
    assert screens.TITLE == "S P O T L I G H T"
    top = screens.LOGO_TOP
    expected = {}
    for i, char in enumerate(screens.TITLE):
        if char != " ":
            expected[screens.centre(screens.TITLE) + i] = LOGO_FACE[char]

    for cx in range(COLS):
        halves = (glyph_at(title, cx, top), glyph_at(title, cx, top + 1))
        if cx in expected:
            assert halves == (expected[cx][:8], expected[cx][8:]), cx
        else:
            # The air between the letters, and it has to stay air: the letters
            # are 8 pixels wide edge to edge, so a logo shifted by one column
            # would have them touching.
            assert halves == ((0,) * 8, (0,) * 8), cx


def test_the_logo_colours_both_of_its_cell_rows(title):
    """Bright yellow on black, on the bottom row as well as the top.

    Worth its own test because the failure is silent and specific to this
    machine: colour is per cell, the screen is cleared to white ink, and a glyph
    that set only its top row's attribute would draw the top half of the word in
    yellow and the bottom half in white.
    """
    from spotlight.core.constants import BLACK, YELLOW
    from spotlight.core.screen import unpack_attr

    top = screens.LOGO_TOP
    for i, char in enumerate(screens.TITLE):
        if char == " ":
            continue
        cx = screens.centre(screens.TITLE) + i
        for cy in (top, top + 1):
            ink, paper, bright, flash = unpack_attr(title.get_attr(cx, cy))
            assert (ink, paper, bright, flash) == (YELLOW, BLACK, True, False)


def test_the_logo_sits_on_rows_one_and_two_and_the_prose_moved_down_one(title):
    """The one layout change the slice is allowed: everything below shifts by a
    row. Nothing is re-wrapped, re-centred or given a new column."""
    text = rows(title)
    assert text[0] == ""
    assert screens.LOGO_TOP == 1
    for i, line in enumerate(screens.STORY):
        assert text[5 + i] == line
    for i, (key, verb) in enumerate(screens.CONTROLS):
        assert text[12 + i] == f"{key}{' ' * (screens._VERB_COL - 2 - len(key))}{verb}"
    for i, line in enumerate(screens.WARNING):
        assert text[17 + i] == line
    assert text[22] == screens.START_PROMPT


def test_the_start_prompt_still_flashes(title):
    """The only movement on the screen, and the one thing that has to be
    noticed. A layout shift is exactly the sort of edit that drops an argument.
    """
    from spotlight.core.screen import unpack_attr

    cx = screens.centre(screens.START_PROMPT)
    for i in range(len(screens.START_PROMPT)):
        _ink, _paper, _bright, flash = unpack_attr(title.get_attr(cx + i, 22))
        assert flash is True


# --- the words themselves ---------------------------------------------------

def test_not_one_word_of_the_screen_has_been_rewritten():
    """**The prose is pinned character for character, and on purpose.**

    Two people have read this screen cold -- one of them somebody who does not
    play games like this -- and both found it doing its job. For most testers it
    is the only instructions they will ever read, and every choice in it is
    deliberate: *tries* rather than *lives*, because a stranger does not know
    that three of something means three attempts; the bar going down explained
    in words; `T` named, because nothing on screen said the key existed; and a
    shape called a person.

    The strongest temptation in a look-and-feel round is to improve prose that
    is already working, and an improvement here is a regression by a different
    name. So a later tidy-up has to argue with this test rather than with
    nobody. **If a word genuinely should change, it changes in a session with a
    player behind it, and this test is edited in the same commit.**
    """
    assert screens.STORY == (
        "SEVEN PEOPLE ARE HURT AND",
        "TRAPPED IN A DARK BUILDING.",
        "FIND THEM, AND WALK THEM OUT",
        "THROUGH THE RED EXIT DOOR",
        "BEFORE THEY BLEED TO DEATH.",
    )
    assert screens.CONTROLS == (
        ("ARROW KEYS", "WALK"),
        ("T", "TORCH ON AND OFF"),
        ("SPACE", "FLYSPRAY"),
    )
    assert screens.WARNING == (
        "YOUR TORCH SHOWS YOU THE ROOM.",
        "IT ALSO SHOWS THE BITING FLIES",
        "WHERE YOU ARE.",
    )
    assert screens.START_PROMPT == "PRESS ANY KEY TO START"
    assert screens.AGAIN_PROMPT == "PRESS SPACE TO PLAY AGAIN"
    assert screens.STOP_PROMPT == "PRESS ESC TO STOP"


def test_the_words_on_the_screen_are_the_words_in_the_constants(title):
    """The pin above is on the constants; this is what ties them to the glass.

    Without it the strings could be pinned and the screen drawn from something
    else entirely -- which is the same fault `screenreader` exists for.
    """
    text = rows(title)
    for line in screens.STORY + screens.WARNING:
        assert line in text
    assert screens.START_PROMPT in text


# --- the ending screen is not touched ---------------------------------------

#: The ending screen at `4b8fe6f`, the commit before the logo landed: a digest
#: of its 49,152 pixels and of its 768 attribute bytes, for three endings.
#:
#: **A digest rather than a golden image** because the whole claim is
#: *identical* -- there is no interesting subset to compare, and a stored copy
#: of the screen would be 50K of test fixture. What a digest costs is
#: diagnosis: when it fails it says the screen moved and not how. That is the
#: right trade for a test whose job is to catch a slice wandering into a screen
#: it was told to leave alone.
ENDING_BEFORE = {
    "ALL_OUT": ("124ba92534bfb871", "e05ff76b0b3b0c70"),
    "NOBODY_LEFT": ("474f8ce5c57043ba", "25b7bafb86b42a1d"),
    "NO_LIVES": ("1d3f05e78ccbbefe", "f7bc79fea899d97c"),
}


@pytest.mark.parametrize("name", sorted(ENDING_BEFORE))
def test_the_ending_screen_is_untouched_to_the_pixel(name):
    """Issue #56 redraws the title and **nothing else**.

    The ending screen was reviewed and the verdict was that the values carry the
    colour and the labels do not -- the only place in this build where colour is
    doing semantic work by itself. A look round is exactly when a screen like
    that gets a logo bolted onto it out of symmetry, so this test says no: same
    pixels, same attribute bytes, same everything.
    """
    import hashlib

    screen = Screen()
    screens.draw_ending(screen, session.ENDING_TEXT[getattr(session, name)],
                        3, 2, 2, 7, 92)
    digest = (hashlib.sha256(bytes(screen.pixels)).hexdigest()[:16],
              hashlib.sha256(bytes(screen.attrs)).hexdigest()[:16])
    assert digest == ENDING_BEFORE[name], (
        "the ending screen has moved. Issue #56 says it does not; if a later "
        "slice changes it deliberately, re-take these digests in that commit.")


# --- the logo is not resident during play -----------------------------------

def _imports_logo(statement: str) -> bool:
    """Whether importing something drags `logo_gen` in with it.

    Run in a fresh interpreter, because by the time this test runs the suite has
    imported half the game and `sys.modules` says nothing about who imported
    what.
    """
    import pathlib
    import subprocess
    import sys

    root = pathlib.Path(__file__).resolve().parents[1]
    code = f"{statement}\nimport sys\nprint('spikes.logo_gen' in sys.modules)"
    done = subprocess.run([sys.executable, "-c", code], cwd=root,
                          capture_output=True, text=True, check=True)
    return done.stdout.strip() == "True"


def test_the_play_path_does_not_import_the_logo():
    """128 bytes that are wanted on one screen and never during a run.

    On the Spectrum that means the logo lives outside the resident set; in
    Python the only mechanical form that rule can take is this one -- the
    modules the game plays through must not reach the table. It is why the logo
    is generated into `logo_gen.py` of its own rather than into `bitmaps_gen.py`
    with the sprites and the tiles, which everything that draws imports.

    The positive half matters as much: if `screens` stopped importing it the
    negative half would pass with the logo deleted.
    """
    assert _imports_logo("import spikes.screens")
    assert not _imports_logo("import spikes.scene")
    assert not _imports_logo("import spikes.session")
    assert not _imports_logo("import spikes.sprites, spikes.tiles, spikes.floor")
