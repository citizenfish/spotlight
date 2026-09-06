from spotlight.core import screen
from spotlight.core.constants import BLACK, CYAN, RED, YELLOW


def test_attr_byte_matches_hardware_layout():
    # ink 6 (yellow), paper 1 (blue), bright set -> 0b0100_1110
    assert screen.attr_byte(ink=6, paper=1, bright=True) == 0b0100_1110


def test_attr_roundtrip():
    packed = screen.attr_byte(ink=RED, paper=CYAN, bright=True, flash=False)
    assert screen.unpack_attr(packed) == (RED, CYAN, True, False)


def test_rejects_out_of_range_colour():
    for bad in ({"ink": 8, "paper": 0}, {"ink": 0, "paper": 9}):
        try:
            screen.attr_byte(**bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")


def test_plot_and_point():
    s = screen.Screen()
    assert not s.point(10, 10)
    s.plot(10, 10)
    assert s.point(10, 10)
    s.plot(10, 10, False)
    assert not s.point(10, 10)


def test_plot_off_screen_is_ignored():
    s = screen.Screen()
    s.plot(-1, 0)
    s.plot(0, 999)
    assert not any(s.pixels)


def test_one_attribute_governs_a_whole_cell():
    """The clash constraint, stated as a test."""
    s = screen.Screen()
    s.set_attr(2, 3, screen.attr_byte(ink=YELLOW, paper=BLACK))
    # Every pixel in cell (2, 3) resolves to the same attribute.
    seen = {s.attr_at_pixel(x, y)
            for y in range(3 * 8, 4 * 8) for x in range(2 * 8, 3 * 8)}
    assert len(seen) == 1


def test_fill_cell_pixels():
    s = screen.Screen()
    s.fill_cell_pixels(1, 1)
    assert s.point(8, 8) and s.point(15, 15)
    assert not s.point(16, 16) and not s.point(7, 7)


def test_clear_resets_pixels_and_attrs():
    s = screen.Screen()
    s.plot(4, 4)
    s.set_attr(0, 0, screen.attr_byte(ink=RED, paper=RED))
    s.clear()
    assert not any(s.pixels)
    assert set(s.attrs) == {screen.DEFAULT_ATTR}


def test_clear_rows_leaves_other_rows_alone():
    s = screen.Screen()
    s.fill_cell_pixels(0, 0)          # row 0
    s.fill_cell_pixels(0, 23)         # row 23
    s.set_attr(0, 23, screen.attr_byte(ink=RED, paper=BLACK))
    s.clear_rows(0, 22)
    assert not s.point(0, 0), "row 0 should have been cleared"
    assert s.point(0, 23 * 8), "row 23 should have been left alone"
    assert s.get_attr(0, 23) == screen.attr_byte(ink=RED, paper=BLACK)


def test_clear_rows_clamps_and_ignores_empty_ranges():
    s = screen.Screen()
    s.fill_cell_pixels(0, 0)
    s.clear_rows(5, 5)                 # empty
    s.clear_rows(-10, 0)               # clamps to nothing
    assert s.point(0, 0)
    s.clear_rows(-10, 99)              # clamps to the whole screen
    assert not any(s.pixels)
