"""The lighting model: levels, composition and the fade."""

from spikes import layout, lighting as L
from spotlight.core.constants import BLACK, COLS, YELLOW
from spotlight.core.screen import Screen, attr_byte, unpack_attr


def _lit_then_left(cx=5, cy=5, level=L.LIT):
    f = L.LightField()
    f.begin(); f.add(cx, cy, level); f.commit()
    return f


def _idle(field, frames):
    for _ in range(frames):
        field.begin()
        field.commit()


# --- levels and attributes -------------------------------------------------

def test_three_levels_map_onto_the_hardware():
    """Bright ink, normal ink, black. That is all the Spectrum gives free."""
    ink, paper, bright, _ = unpack_attr(L.attr_for(L.LIT, YELLOW))
    assert (ink, paper, bright) == (YELLOW, BLACK, True)

    ink, paper, bright, _ = unpack_attr(L.attr_for(L.DIM, YELLOW))
    assert (ink, paper, bright) == (YELLOW, BLACK, False)

    ink, paper, bright, _ = unpack_attr(L.attr_for(L.DARK, YELLOW))
    assert (ink, paper, bright) == (BLACK, BLACK, False), "dark is invisible, not dim"


# --- composition -----------------------------------------------------------

def test_brightest_wins_whichever_order_sources_arrive():
    for first, second in ((L.DIM, L.LIT), (L.LIT, L.DIM)):
        f = L.LightField()
        f.begin(); f.add(3, 3, first); f.add(3, 3, second); f.commit()
        assert f.level_at(3, 3) == L.LIT


def test_levels_do_not_sum():
    """Two lit sources are not brighter than one -- there is nothing brighter."""
    one = L.LightField()
    one.begin(); one.add(3, 3, L.LIT); one.commit()

    many = L.LightField()
    many.begin()
    for _ in range(5):
        many.add(3, 3, L.LIT)
    many.commit()

    assert many.charge[3 * COLS + 3] == one.charge[3 * COLS + 3]


def test_a_dim_source_does_not_read_as_lit():
    f = L.LightField()
    f.begin(); f.add(3, 3, L.DIM); f.commit()
    assert f.level_at(3, 3) == L.DIM


# --- the fade --------------------------------------------------------------

def test_a_lit_cell_decays_through_dim_to_dark():
    f = _lit_then_left()
    assert f.level_at(5, 5) == L.LIT

    _idle(f, L.CHARGE_DIM)
    assert f.level_at(5, 5) == L.DIM, "should be dim by half the fade"

    _idle(f, L.FADE_FRAMES)
    assert f.level_at(5, 5) == L.DARK


def test_fade_duration_follows_the_single_constant():
    """Timing is tunable from FADE_FRAMES alone, not scattered magic numbers."""
    f = _lit_then_left()
    _idle(f, L.FADE_FRAMES - 1)
    assert f.level_at(5, 5) != L.DARK, "should not be black yet"
    _idle(f, 1)
    assert f.level_at(5, 5) == L.DARK


def test_staying_lit_holds_a_cell_at_full_brightness():
    f = L.LightField()
    for _ in range(L.FADE_FRAMES * 2):
        f.begin(); f.add(5, 5, L.LIT); f.commit()
    assert f.level_at(5, 5) == L.LIT


def test_relighting_resets_the_fade():
    f = _lit_then_left()
    _idle(f, L.CHARGE_DIM + 5)
    assert f.level_at(5, 5) == L.DIM
    f.begin(); f.add(5, 5, L.LIT); f.commit()
    assert f.level_at(5, 5) == L.LIT


def test_the_fade_runs_everywhere_not_just_near_the_player():
    """Time passes in cells nobody is looking at."""
    f = L.LightField()
    f.begin()
    for cx, cy in ((0, 0), (31, 21), (16, 11)):
        f.add(cx, cy, L.LIT)
    f.commit()
    _idle(f, L.FADE_FRAMES)
    assert all(f.level_at(cx, cy) == L.DARK
               for cx, cy in ((0, 0), (31, 21), (16, 11)))


# --- shape and bounds ------------------------------------------------------

def test_state_is_one_byte_per_cell_not_per_pixel():
    f = L.LightField()
    assert len(f.charge) == COLS * layout.PLAY_ROWS == 704


def test_out_of_bounds_sources_are_ignored():
    f = L.LightField()
    f.begin()
    for cx, cy in ((-1, 0), (COLS, 0), (0, -1), (0, layout.PLAY_ROWS)):
        f.add(cx, cy, L.LIT)
    f.commit()
    assert not any(f.charge)


def test_reading_outside_the_play_area_is_dark():
    f = L.LightField()
    assert f.level_at(-1, 0) == L.DARK
    assert f.level_at(0, layout.PLAY_ROWS) == L.DARK


def test_a_source_only_lights_its_own_cell():
    f = _lit_then_left(5, 5)
    lit = [i for i, c in enumerate(f.charge) if c]
    assert lit == [5 * COLS + 5]


# --- painting --------------------------------------------------------------

def test_paint_writes_the_play_area_and_leaves_the_strip_alone():
    s = Screen()
    strip_marker = attr_byte(ink=YELLOW, paper=BLACK)
    for cx in range(COLS):
        for cy in range(layout.STRIP_TOP, layout.STRIP_BOTTOM):
            s.set_attr(cx, cy, strip_marker)

    f = _lit_then_left(5, 5)
    f.paint(s, YELLOW)

    assert s.get_attr(5, 5) == L.attr_for(L.LIT, YELLOW)
    assert s.get_attr(0, 0) == L.attr_for(L.DARK, YELLOW)
    for cx in range(COLS):
        for cy in range(layout.STRIP_TOP, layout.STRIP_BOTTOM):
            assert s.get_attr(cx, cy) == strip_marker, "strip was overwritten"


def test_levels_returns_one_entry_per_cell():
    f = _lit_then_left(5, 5)
    levels = f.levels()
    assert len(levels) == COLS * layout.PLAY_ROWS
    assert levels[5 * COLS + 5] == L.LIT
