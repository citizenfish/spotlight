"""Stippling lit floor."""

from spikes import floor, lighting as L
from spotlight.core.constants import CELL
from spotlight.core.screen import Screen


def _never_solid(cx, cy):
    return False


def _pixels_in_cell(s, cx, cy):
    return sum(1 for dy in range(CELL) for dx in range(CELL)
               if s.point(cx * CELL + dx, cy * CELL + dy))


def test_lit_floor_is_denser_than_dim_floor():
    """This is the contrast step the palette cannot give us."""
    s, f = Screen(), L.LightField()
    f.begin(); f.add(1, 1, L.LIT, L.CHARGE_LIT); f.add(3, 1, L.DIM, L.CHARGE_DIM); f.commit()
    floor.draw(s, f, _never_solid)
    assert _pixels_in_cell(s, 1, 1) > _pixels_in_cell(s, 3, 1) > 0


def test_dark_floor_is_left_bare():
    s, f = Screen(), L.LightField()
    floor.draw(s, f, _never_solid)
    assert not any(s.pixels)


def test_solid_cells_are_not_stippled():
    """A wall is already drawn; dotting it would only muddle the shape."""
    s, f = Screen(), L.LightField()
    f.begin(); f.add(2, 2, L.LIT, L.CHARGE_LIT); f.commit()
    floor.draw(s, f, lambda cx, cy: (cx, cy) == (2, 2))
    assert _pixels_in_cell(s, 2, 2) == 0


def test_stipple_stays_inside_its_own_cell():
    s, f = Screen(), L.LightField()
    f.begin(); f.add(4, 4, L.LIT, L.CHARGE_LIT); f.commit()
    floor.draw(s, f, _never_solid)
    assert _pixels_in_cell(s, 4, 4) > 0
    for cx, cy in ((3, 4), (5, 4), (4, 3), (4, 5)):
        assert _pixels_in_cell(s, cx, cy) == 0


def test_the_lit_pattern_has_four_dots():
    assert sum(bin(row).count("1") for row in floor.STIPPLE_LIT) == 4
    assert sum(bin(row).count("1") for row in floor.STIPPLE_DIM) == 1


def _dots(pattern):
    """Where the pixels are, as (row, column) pairs, bit 7 leftmost."""
    return [(y, x) for y, bits in enumerate(pattern)
            for x in range(8) if bits & (0x80 >> x)]


def test_the_stipple_moved_out_of_the_code_without_moving_a_dot():
    """The transcription that issue #51 was, pinned to the pixel.

    **What was wrong before**, and what this stops coming back: the stipples
    were declared as hex in `floor.py` while the asset-pipeline decision said
    they lived in `assets/tiles/floor.txt`, so the drift test that guards every
    other bitmap did not guard these and the Z80 had no `DEFB` for them. Moving
    them was pure transcription and **no pixel was allowed to change**; these
    are the exact positions they had beforehand, at `fb4d831`.

    They are also a **tuned decision, not a drawing**, which is why an exact
    pin is right here where it would be wrong for a sprite. The densities say
    how much of a room the player is told about, and the two levels are the
    contrast step the palette cannot give -- 255 against 215 on one channel is
    invisible on a moving figure. Two things elsewhere are measured against
    these positions: the player's five-pixel foot bar exists because the lit
    stipple's four-pixel spacing swallows anything narrower (issue #49), and
    the sign and doorway tests check the lit dots still show through what is
    painted over them.

    So this failing is not necessarily a bug -- it means somebody redrew a
    tuned pattern, and the fix is a design decision in the vault and then this
    test, in that order. Issue #51 forbade it outright.
    """
    assert _dots(floor.STIPPLE_LIT) == [(1, 1), (1, 5), (5, 1), (5, 5)], \
        "the lit stipple is four dots four pixels apart in both axes"
    assert _dots(floor.STIPPLE_DIM) == [(3, 3)], \
        "the dim stipple is one dot in sixty-four, near the middle of the cell"
