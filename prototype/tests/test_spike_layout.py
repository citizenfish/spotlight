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


def test_strip_splits_down_the_middle():
    assert layout.STATUS_LEFT == 0
    assert layout.ACTION_LEFT == COLS // 2
