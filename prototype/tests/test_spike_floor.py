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
