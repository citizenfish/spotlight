"""The status strip: dim styling, and repainting only what changed."""

import pytest

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
    expected = sum(r.width + len(r.label or "")
                   for r in panel.REGIONS.values())
    assert len(touched) == expected, "the tally's word counts too"


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


# --- x of y rescued (issue #10) --------------------------------------------

def _tally():
    s, p = _fresh()
    p.set_total("rescued", 7)
    return s, p


def _cell_rows(screen, cx, cy):
    """The eight bytes of one 8x8 cell, read back off the bitmap."""
    from spotlight.core.constants import CELL, SCREEN_W
    rows = []
    for dy in range(CELL):
        base = (cy * CELL + dy) * SCREEN_W + cx * CELL
        bits = 0
        for dx in range(CELL):
            bits = (bits << 1) | (1 if screen.pixels[base + dx] else 0)
        rows.append(bits)
    return tuple(rows)


def _read(screen, region):
    """The characters drawn in a tally region, badge excluded."""
    out = []
    for i in range(region.width):
        drawn = _cell_rows(screen, region.col + i, region.row)
        for ch, glyph in font.GLYPHS.items():
            if tuple(glyph) == drawn:
                out.append(ch)
                break
        else:
            out.append("?")
    return "".join(out)


def test_the_tally_shows_found_against_the_total():
    s, p = _tally()
    p.set("rescued", 3)
    p.draw(s, force=True)
    assert _read(s, panel.REGIONS["rescued"]).rstrip() == "3/7"


def test_the_tally_starts_at_none_found():
    s, p = _tally()
    p.draw(s, force=True)
    assert _read(s, panel.REGIONS["rescued"]).rstrip() == "0/7"


def test_the_tally_does_not_move_as_the_numbers_change():
    """A readout that shifts is one the eye has to find again every time."""
    s, p = _tally()
    p.set("rescued", 0)
    p.draw(s, force=True)
    first = _read(s, panel.REGIONS["rescued"]).index("/")
    p.set("rescued", 7)
    p.draw(s)
    assert _read(s, panel.REGIONS["rescued"]).index("/") == first


def test_the_tally_cannot_exceed_its_total():
    s, p = _tally()
    p.set("rescued", 99)
    assert p.values["rescued"] == 7


def test_a_total_too_wide_to_fit_loses_the_denominator_not_the_digits():
    """Three cells and a quota of twelve: "10/" would be a different number.

    The tally was five cells wide until issue #31, which spent two of them on
    the word SAFE. Nothing in this building has a two-figure quota, and if one
    ever does the strip wants reflowing -- but a readout that silently rounds
    is worse than one that says less, so this one says less.
    """
    s, p = _fresh()
    p.set_total("rescued", 12)
    p.set("rescued", 10)
    p.draw(s, force=True)
    assert _read(s, panel.REGIONS["rescued"]).rstrip() == "10"


def test_changing_the_total_repaints_it():
    s, p = _tally()
    p.draw(s, force=True)
    p.set_total("rescued", 9)
    assert "rescued" in p.dirty


def test_the_tally_sits_in_the_gap_the_hearts_leave():
    lives, rescued = panel.REGIONS["lives"], panel.REGIONS["rescued"]
    assert rescued.row == lives.row
    assert rescued.label_col > lives.col + lives.width, "the word overlaps lives"
    assert rescued.col + rescued.width <= layout.ACTION_LEFT, "spills into the kit"


# --- the word that says what is being counted (issue #31) ------------------

def _word(screen, region):
    """The label drawn to the left of a tally, read back off the bitmap."""
    out = []
    for i in range(len(region.label)):
        drawn = _cell_rows(screen, region.label_col + i, region.row)
        for ch, glyph in font.GLYPHS.items():
            if tuple(glyph) == drawn:
                out.append(ch)
                break
        else:
            out.append("?")
    return "".join(out)


def test_the_tally_says_in_words_what_it_is_counting():
    """`*3/7` left a first-timer to guess. The testers do not know the game."""
    s, p = _tally()
    p.set("rescued", 3)
    p.draw(s, force=True)
    assert _word(s, panel.REGIONS["rescued"]) == "SAFE"
    assert _read(s, panel.REGIONS["rescued"]).rstrip() == "3/7"


def test_the_word_is_drawn_a_cell_clear_of_the_number():
    """A word butted against the digits reads as one string, not two things."""
    rescued = panel.REGIONS["rescued"]
    assert rescued.label_col + len(rescued.label) == rescued.col - 1


def test_the_word_repaints_with_the_number():
    s, p = _tally()
    p.draw(s, force=True)
    p.set("rescued", 1)
    touched = p.draw(s)
    rescued = panel.REGIONS["rescued"]
    assert (rescued.label_col, rescued.row) in touched


# --- alerts (issue #31) ----------------------------------------------------

def _flashing(screen, region):
    """Is the flash bit set on the readout's first cell?"""
    return unpack_attr(screen.get_attr(region.col, region.row))[3]


def test_an_alert_flashes_the_readout():
    s, p = _fresh()
    p.draw(s, force=True)
    assert not _flashing(s, panel.REGIONS["light"])
    p.alert("light")
    p.draw(s)
    assert _flashing(s, panel.REGIONS["light"])


def test_an_alert_repaints_a_readout_that_did_not_change():
    """Nothing about the light's value moves when the last frame of it goes."""
    s, p = _fresh()
    p.draw(s, force=True)
    p.alert("light")
    assert "light" in p.dirty


def test_an_alert_stops_of_its_own_accord():
    s, p = _fresh()
    p.alert("light", frames=3)
    p.draw(s, force=True)
    for _ in range(3):
        assert p.flashing("light")
        p.tick()
    assert not p.flashing("light")
    p.draw(s)
    assert not _flashing(s, panel.REGIONS["light"])


def test_an_alert_on_an_unknown_readout_is_a_mistake():
    p = panel.Panel()
    with pytest.raises(KeyError):
        p.alert("torch")
