from spotlight.core.constants import COLS, ROWS
from spotlight.core.game import DARK, Game
from spotlight.core.screen import Screen


def test_starts_centred():
    g = Game()
    assert (g.x, g.y) == (COLS // 2, ROWS // 2)


def test_movement_is_clamped_to_the_grid():
    g = Game()
    for _ in range(COLS * 2):
        g.update(-1, -1)
    assert (g.x, g.y) == (0, 0)
    for _ in range(COLS * 2):
        g.update(1, 1)
    assert (g.x, g.y) == (COLS - 1, ROWS - 1)


def test_light_leaves_distant_cells_dark():
    g = Game()
    s = Screen()
    g.draw(s)
    assert s.get_attr(0, 0) == DARK
    assert s.get_attr(g.x, g.y) != DARK


def test_lit_area_is_bounded_by_radius():
    g = Game()
    s = Screen()
    g.draw(s)
    lit = sum(1 for a in s.attrs if a != DARK)
    r = g.light_radius
    assert 0 < lit <= (2 * r + 1) ** 2
