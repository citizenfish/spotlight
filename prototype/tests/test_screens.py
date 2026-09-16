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
    from spikes.floor import FLOOR_LIT
    from spikes.logo_gen import BITMAPS

    letters = {rows_: name[len("LOGO_"):] for name, rows_ in BITMAPS.items()}
    word = ""
    for cx in range(COLS):
        halves = (glyph_at(screen, cx, screens.LOGO_TOP),
                  glyph_at(screen, cx, screens.LOGO_TOP + 1))
        # The beam (issue #76) runs through the logo's rows in the gaps
        # between the letters, and a lit floor block is ground, not a letter.
        # Either half may wear one; a half that is blank or a block is air.
        if all(half in FLOOR_LIT or not any(half) for half in halves):
            continue
        word += letters.get(halves[0] + halves[1], "?")
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

    from spikes.floor import FLOOR_LIT

    for cx in range(COLS):
        halves = (glyph_at(title, cx, top), glyph_at(title, cx, top + 1))
        if cx in expected:
            assert halves == (expected[cx][:8], expected[cx][8:]), cx
        else:
            # The air between the letters, and it has to stay air: the letters
            # are 8 pixels wide edge to edge, so a logo shifted by one column
            # would have them touching. Since issue #76 the air may hold the
            # beam's floor block instead of nothing -- and only that: a
            # shifted letter would be text in the gap, and the beam is never
            # laid on text, so the block here is proof the gap was empty.
            for half in halves:
                assert half == (0,) * 8 or half in FLOOR_LIT, cx


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
    # Row 0 holds only the searchlight's housing, in the corner (issue #104):
    # the reader shows a glyph it has no letter for as '?', and one of them.
    assert text[0].strip("? ") == "" and text[0].count("?") == 1
    assert screens.LOGO_TOP == 1
    for i, line in enumerate(screens.STORY):
        assert text[5 + i] == line
    for i, (key, verb) in enumerate(screens.CONTROLS):
        assert text[12 + i] == f"{key}{' ' * (screens._VERB_COL - 2 - len(key))}{verb}"
    for i, line in enumerate(screens.WARNING):
        assert text[17 + i] == line
    # Row 23 since issue #104, with the legend on 21 and 20 and 22 empty.
    assert text[23] == screens.START_PROMPT
    assert text[20] == "" and text[22] == ""
    assert screens.BADGE_LEGEND_ROW == 21


def test_the_start_prompt_still_flashes(title):
    """The only movement on the screen, and the one thing that has to be
    noticed. A layout shift is exactly the sort of edit that drops an argument.
    """
    from spotlight.core.screen import unpack_attr

    cx = screens.centre(screens.START_PROMPT)
    for i in range(len(screens.START_PROMPT)):
        _ink, _paper, _bright, flash = unpack_attr(title.get_attr(cx + i, 23))
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
    # `PRESS ANY KEY TO START` until issue #63: any key is what a tester
    # pressing `T` while reading the controls triggers by accident, and `S`
    # is not a game key. Moved with the string, in the same commit, as the
    # docstring above asks.
    assert screens.START_PROMPT == "PRESS S TO START"
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


# --- the pool in the title's corner (issue #104; the beam of #76 before it) ---

@pytest.fixture
def words():
    """The title without its pool: the words alone."""
    screen = Screen()
    screens.draw_words(screen)
    return screen


def text_cells(screen) -> set[tuple[int, int]]:
    """Every cell with a pixel in it -- the words, and nothing else."""
    from spotlight.core.constants import ROWS
    return {(cx, cy) for cy in range(ROWS) for cx in range(COLS)
            if any(glyph_at(screen, cx, cy))}


def test_the_pool_is_one_disc_in_the_corner_with_the_housing_above_it(words, title):
    """Issue #104, replacing the walked beam of #76: one disc of radius three
    centred on (28, 2), clipped to the screen, minus the housing's cell and
    minus every cell that holds text; the housing itself at (30, 0), bright
    white, drawn as the room draws it."""
    from spikes import sprites
    from spotlight.core.constants import BLACK, WHITE
    from spotlight.core.screen import unpack_attr
    pool = screens.pool_cells(words)
    cx0, cy0 = screens.POOL_CENTRE
    for cx, cy in pool:
        assert (cx - cx0) ** 2 + (cy - cy0) ** 2 <= 9
        assert (cx, cy) != screens.HOUSING_CELL
    assert 20 <= len(pool) <= 29, len(pool)
    hx, hy = screens.HOUSING_CELL
    assert unpack_attr(title.get_attr(hx, hy)) == (WHITE, BLACK, True, False)
    assert glyph_at(title, hx, hy) == list(sprites.HOUSING) \
        or tuple(glyph_at(title, hx, hy)) == tuple(sprites.HOUSING)
    assert not hasattr(screens, "draw_beam") and not hasattr(screens, "beam_cells")


def test_no_pool_cell_holds_text(words):
    """The one-ink rule, stated as sets: the beam and the words are disjoint,
    so no cell is ever asked to be white, cyan or bright yellow and also
    the beam's yellow."""
    assert not screens.pool_cells(words) & text_cells(words)


def test_the_words_are_not_touched_by_the_pool(words, title):
    """**Every text cell: the same pixels and the same attribute byte with the
    beam as without it.** This is the acceptance criterion the issue leads
    with, and it is the pin that lets the beam be added at all: the words
    were read cold by two people and found working, and the beam is not
    allowed to have been near them."""
    cells = text_cells(words)
    assert len(cells) > 100, "the words are there to be pinned"
    for cx, cy in cells:
        assert glyph_at(title, cx, cy) == glyph_at(words, cx, cy), (cx, cy)
        assert title.get_attr(cx, cy) == words.get_attr(cx, cy), (cx, cy)


def test_the_pool_changes_nothing_but_its_own_cells_and_the_housing(words, title):
    """The stronger form: outside the beam set the two screens are identical,
    pixels and attributes, text or not. A beam that stippled a spare cell or
    recoloured one it did not dot would fail here and nowhere else."""
    from spotlight.core.constants import ROWS

    beam = screens.pool_cells(words) | {screens.HOUSING_CELL}
    for cy in range(ROWS):
        for cx in range(COLS):
            if (cx, cy) in beam:
                continue
            assert glyph_at(title, cx, cy) == glyph_at(words, cx, cy), (cx, cy)
            assert title.get_attr(cx, cy) == words.get_attr(cx, cy), (cx, cy)


def test_every_pool_cell_is_non_bright_yellow_on_black(words, title):
    """The same hue as the logo and the keys, a step dimmer, so it reads as
    light and not as more words. Not bright, not flashing."""
    from spotlight.core.constants import BLACK, YELLOW
    from spotlight.core.screen import unpack_attr

    beam = screens.pool_cells(words)
    assert beam
    for cx, cy in beam:
        assert unpack_attr(title.get_attr(cx, cy)) == \
            (YELLOW, BLACK, False, False), (cx, cy)
    logo = title.get_attr(screens.centre(screens.TITLE), screens.LOGO_TOP)
    assert title.get_attr(*next(iter(beam))) != logo, \
        "the beam is not the logo's bright yellow"


def test_the_pool_wears_the_lit_floor_tile_for_its_position(words, title):
    """The floor's own noise (issue #71), block by position: a beam cell at
    (cx, cy) wears `FLOOR_LIT[(cy & 3) * 4 + (cx & 3)]`, so the beam is the
    same gravel the play area's light falls on and not a private pattern.
    Both spellings of the index are checked against each other on purpose."""
    from spikes import floor

    for cx, cy in screens.pool_cells(words):
        glyph = glyph_at(title, cx, cy)
        assert glyph == floor.FLOOR_LIT[floor.tile_index(cx, cy)], (cx, cy)
        assert glyph == floor.FLOOR_LIT[(cy & 3) * 4 + (cx & 3)], (cx, cy)


def test_the_pool_is_found_before_it_is_drawn(title):
    """`beam_cells` is a set computed before a dot goes down, and drawing the
    beam again on a title that has one draws nothing more. The hazard it
    guards is specific: the beam is pixels, and a routine that tested cells as
    it walked would find its own earlier dots and call them text -- forty
    discs overlap heavily, so most of the beam would be holes. The set form
    cannot do that, and this is the pin on it: a second `draw_beam` finds
    every beam cell already dotted, lays the same block on it by OR and the
    same attribute over it, and the screen does not change."""
    again = Screen()
    again.pixels[:] = title.pixels
    again.attrs[:] = title.attrs
    screens.draw_pool(again)
    assert bytes(again.pixels) == bytes(title.pixels)
    assert bytes(again.attrs) == bytes(title.attrs)


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
    "ALL_OUT": ("746fe4030fb39827", "0858a6d8d12cb9f5"),
    "NOBODY_LEFT": ("f4f87834bec2f559", "69ac6f67a959edf9"),
    "NO_LIVES": ("027ac18327a92a43", "66eed8a575771ad6"),
}


@pytest.mark.parametrize("name", sorted(ENDING_BEFORE))
def test_the_ending_screen_is_untouched_to_the_pixel(name):
    """Issue #56 redrew the title and **nothing else**, and this pin held the
    ending to the pixel through two rounds; issue #104 (Look and feel 3 row
    12) put the logo on it deliberately -- the user's ruling, not symmetry --
    and moved everything below down two rows, and these digests were re-taken
    in that commit. The values still carry the colour and the labels are
    still white; the table is the same table under a logo.
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

    **Since issue #97 the session reaches it too**, on purpose: the opening
    holds two seconds of black with the logo centred on it, so a run draws
    the logo once before its first frame. That is a ruling and not a leak,
    and what the rule still keeps is that nothing that draws the *room* --
    the sprites, the tiles, the floor -- knows the logo exists.
    """
    assert _imports_logo("import spikes.screens")
    assert _imports_logo("import spikes.session"), "the opening draws the logo"
    assert not _imports_logo("import spikes.scene")
    assert not _imports_logo("import spikes.sprites, spikes.tiles, spikes.floor")
