"""The status strip: dim styling, and repainting only what changed."""

from spikes import font, layout, panel
from spotlight.core.constants import BLACK, COLS
from spotlight.core.screen import Screen, attr_byte, unpack_attr


def _fresh() -> tuple[Screen, panel.Panel]:
    s = Screen()
    p = panel.Panel()
    panel.blank_strip(s)
    p.draw_labels(s)
    p.draw(s, force=True)
    return s, p


# --- dim styling -----------------------------------------------------------

def test_nothing_in_the_strip_is_bright():
    """A bright panel would be the most eye-catching thing on a black screen."""
    s, _ = _fresh()
    for row in range(layout.STRIP_TOP, layout.STRIP_BOTTOM):
        for cx in range(COLS):
            _, _, bright, _ = unpack_attr(s.get_attr(cx, row))
            assert not bright, f"cell ({cx}, {row}) is bright"


def test_strip_paper_is_always_black():
    s, _ = _fresh()
    for row in range(layout.STRIP_TOP, layout.STRIP_BOTTOM):
        for cx in range(COLS):
            _, paper, _, _ = unpack_attr(s.get_attr(cx, row))
            assert paper == BLACK


def test_readouts_stay_inside_the_strip():
    for name, region in panel.REGIONS.items():
        assert layout.STRIP_TOP <= region.row < layout.STRIP_BOTTOM, name
        assert region.col + region.width <= COLS, name


def test_readouts_do_not_overlap_each_other_or_the_labels():
    occupied: dict[tuple[int, int], str] = {}
    for row, col, text in panel.LABELS:
        for i in range(len(text)):
            occupied[(col + i, row)] = "label"
    for name, region in panel.REGIONS.items():
        for i in range(region.width):
            cell = (region.col + i, region.row)
            assert cell not in occupied, f"{name} collides with {occupied[cell]}"
            occupied[cell] = name


# --- change tracking -------------------------------------------------------

def test_set_reports_whether_it_changed_anything():
    p = panel.Panel()
    p.set("blood", 4)
    assert p.set("blood", 5) is True
    assert p.set("blood", 5) is False


def test_only_the_changed_readout_repaints():
    s, p = _fresh()
    assert p.dirty == frozenset()
    p.set("blood", 3)
    touched = p.draw(s)
    blood = panel.REGIONS["blood"]
    assert touched == [(blood.col + i, blood.row) for i in range(blood.width)]


def test_an_unchanged_panel_repaints_nothing():
    s, p = _fresh()
    p.set("blood", p.values["blood"])
    assert p.draw(s) == []


def test_force_repaints_everything():
    s, p = _fresh()
    touched = p.draw(s, force=True)
    assert len(touched) == sum(r.width for r in panel.REGIONS.values())


# --- values ----------------------------------------------------------------

def test_values_are_clamped_to_the_readout_width():
    p = panel.Panel()
    p.set("blood", 99)
    assert p.values["blood"] == panel.REGIONS["blood"].width
    p.set("blood", -5)
    assert p.values["blood"] == 0


def test_flags_are_coerced_to_zero_or_one():
    p = panel.Panel()
    p.set("lit", 7)
    assert p.values["lit"] == 1


def test_unknown_readout_is_rejected():
    p = panel.Panel()
    try:
        p.set("nonsense", 1)
    except KeyError:
        return
    raise AssertionError("expected KeyError")


# --- the two regions are independent ---------------------------------------

def test_clearing_the_play_area_leaves_the_strip_intact():
    s, p = _fresh()
    before_pixels = bytes(s.pixels[layout.STRIP_TOP * 8 * 256:])
    before_attrs = bytes(s.attrs[layout.STRIP_TOP * COLS:])
    s.clear_rows(layout.PLAY_TOP, layout.PLAY_BOTTOM,
                 attr_byte(ink=7, paper=BLACK))
    assert bytes(s.pixels[layout.STRIP_TOP * 8 * 256:]) == before_pixels
    assert bytes(s.attrs[layout.STRIP_TOP * COLS:]) == before_attrs


def test_the_bar_fills_from_the_left():
    """Sample a pixel set in BAR_FULL but clear in BAR_EMPTY, or the test is
    vacuous -- both glyphs share their outline."""
    row, col = 3, 3
    assert font.BAR_FULL[row] & (0x80 >> col)
    assert not font.BAR_EMPTY[row] & (0x80 >> col)

    s, p = _fresh()
    p.set("blood", 3)
    p.draw(s)
    blood = panel.REGIONS["blood"]
    filled = [s.point(cx * 8 + col, blood.row * 8 + row)
              for cx in range(blood.col, blood.col + blood.width)]
    assert filled == [True, True, True, False, False, False, False, False]


# --- the power bar must not lie about being empty (issue #12) --------------

def test_a_bar_reads_empty_only_when_it_is_empty():
    """A carried spotlight with power left must never show a flat bar.

    Truncating showed the starting spotlight as flat for its last five seconds
    while it was still burning, which reads as the light failing rather than
    draining.
    """
    assert panel.bar_pips(0, 1500) == 0
    for power in (1, 100, 249, 250, 600):
        assert panel.bar_pips(power, 1500) >= 1, f"{power} showed empty"


def test_a_full_bar_is_full_and_never_overflows():
    assert panel.bar_pips(1500, 1500) == 6
    assert panel.bar_pips(9999, 1500) == 6


def test_the_bar_is_scaled_against_the_strongest_light_in_the_level():
    """So a weak spotlight visibly gives you less, which is the trap."""
    weak = panel.bar_pips(150, 1500)
    strong = panel.bar_pips(1500, 1500)
    assert weak < strong


def test_the_bar_falls_as_power_drains():
    readings = [panel.bar_pips(p, 1500) for p in range(1500, -1, -50)]
    assert readings == sorted(readings, reverse=True)
    assert readings[0] == 6 and readings[-1] == 0
