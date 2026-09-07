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

from spotlight.core.screen import Screen

from spikes import screens, session
from screenreader import read, rows


@pytest.fixture
def title():
    screen = Screen()
    screens.draw_title(screen)
    return screen


def test_the_title_names_the_game(title):
    assert "SPOTLIGHT" in "".join(rows(title)).replace(" ", "")


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
