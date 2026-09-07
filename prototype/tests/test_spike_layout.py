"""Screen regions for spike 1."""

from spikes import layout
from spotlight.core.constants import COLS, ROWS


def test_play_area_is_32x22():
    assert layout.PLAY_ROWS == 22
    assert COLS == 32
    assert layout.PLAY_CELLS == 704


def test_play_rows_are_even_so_8x16_sprites_tile_whole():
    """People are two cells tall; an odd play area leaves a useless half-row."""
    assert layout.PLAY_ROWS % 2 == 0


def test_regions_tile_the_screen_without_overlap():
    assert layout.PLAY_TOP == 0
    assert layout.PLAY_BOTTOM == layout.STRIP_TOP
    assert layout.STRIP_BOTTOM == ROWS
    assert layout.PLAY_CELLS + layout.STRIP_CELLS == COLS * ROWS


def test_the_kit_half_is_exactly_as_wide_as_it_needs_to_be():
    """The split is not the middle, and the two cells it gave up are a word.

    Issue #31: the rescue tally had to say what it was counting, and the only
    cells left to say it in were the ones the kit half was not using. LIGHT is
    the widest thing on that side -- label, gap, six bar cells, gap, the lit
    flag -- and that is fourteen.
    """
    assert layout.STATUS_LEFT == 0
    assert layout.ACTION_LEFT == COLS - 13
    assert layout.ACTION_LEFT > COLS // 2, "the status half is the bigger one"
