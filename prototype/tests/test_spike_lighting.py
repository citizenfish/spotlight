"""The lighting model: levels, composition and the fade."""

from spikes import layout, lighting as L
from spotlight.core.constants import BLACK, COLS, CYAN, WHITE, YELLOW
from spotlight.core.screen import Screen, attr_byte, unpack_attr


def _lit_then_left(cx=5, cy=5, memory=L.CHARGE_LIT, level=L.LIT):
    f = L.LightField()
    f.begin(); f.add(cx, cy, level, memory); f.commit()
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
    dim, lit = (L.DIM, L.CHARGE_DIM), (L.LIT, L.CHARGE_LIT)
    for first, second in ((dim, lit), (lit, dim)):
        f = L.LightField()
        f.begin()
        f.add(3, 3, *first)
        f.add(3, 3, *second)
        f.commit()
        assert f.level_at(3, 3) == L.LIT


def test_levels_do_not_sum():
    """Two lit sources are not brighter than one -- there is nothing brighter."""
    one = L.LightField()
    one.begin(); one.add(3, 3, L.LIT, L.CHARGE_LIT); one.commit()

    many = L.LightField()
    many.begin()
    for _ in range(5):
        many.add(3, 3, L.LIT, L.CHARGE_LIT)
    many.commit()

    assert many.charge[3 * COLS + 3] == one.charge[3 * COLS + 3]


def test_a_dim_source_does_not_read_as_lit():
    f = L.LightField()
    f.begin(); f.add(3, 3, L.DIM, L.CHARGE_DIM); f.commit()
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
        f.begin(); f.add(5, 5, L.LIT, L.CHARGE_LIT); f.commit()
    assert f.level_at(5, 5) == L.LIT


def test_relighting_resets_the_fade():
    f = _lit_then_left()
    _idle(f, L.CHARGE_DIM + 5)
    assert f.level_at(5, 5) == L.DIM
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_LIT); f.commit()
    assert f.level_at(5, 5) == L.LIT


def test_the_fade_runs_everywhere_not_just_near_the_player():
    """Time passes in cells nobody is looking at."""
    f = L.LightField()
    f.begin()
    for cx, cy in ((0, 0), (31, 21), (16, 11)):
        f.add(cx, cy, L.LIT, L.CHARGE_LIT)
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
        f.add(cx, cy, L.LIT, L.CHARGE_LIT)
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


# --- the fade curve --------------------------------------------------------

def test_lit_is_a_short_head_and_dim_is_a_long_tail():
    """Bright must mean 'lit right now', not 'lit within the last 1.5s'."""
    f = _lit_then_left()
    levels = []
    for _ in range(L.FADE_FRAMES + 1):
        levels.append(f.level_at(5, 5))
        f.begin(); f.commit()
    lit, dim = levels.count(L.LIT), levels.count(L.DIM)
    assert lit == L.LIT_FRAMES
    assert dim > lit * 3, f"dim tail ({dim}) should dwarf the lit head ({lit})"
    assert lit + dim == L.FADE_FRAMES


def test_a_dim_source_never_reads_as_lit_however_long_it_shines():
    f = L.LightField()
    for _ in range(L.FADE_FRAMES * 2):
        f.begin(); f.add(5, 5, L.DIM, L.CHARGE_DIM); f.commit()
    assert f.level_at(5, 5) == L.DIM


def test_a_dim_source_still_leaves_a_memory():
    f = L.LightField()
    f.begin(); f.add(5, 5, L.DIM, L.CHARGE_DIM); f.commit()
    for _ in range(L.FADE_FRAMES // 2):
        f.begin(); f.commit()
    assert f.level_at(5, 5) == L.DIM, "dim light should linger, not snap off"


# --- charge per source (issue #12) -----------------------------------------

def test_a_sweep_reads_lit_while_the_beam_is_on_it():
    """Level is what is shining now, whatever the charge says."""
    f = L.LightField()
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_SWEEP); f.commit()
    assert f.level_at(5, 5) == L.LIT
    assert f.remembered_at(5, 5) == L.DIM, "the memory it leaves is only dim"


def test_the_ground_behind_the_beam_goes_out_quickly():
    """The point of the change: a swept cell is dim at once and dark soon."""
    f = _lit_then_left(memory=L.CHARGE_SWEEP)
    assert f.level_at(5, 5) == L.LIT, "bright while the beam is on it"
    _idle(f, 1)
    assert f.level_at(5, 5) == L.DIM, "dim the very frame after it leaves"
    _idle(f, L.CHARGE_SWEEP - 2)
    assert f.level_at(5, 5) == L.DIM
    _idle(f, 1)
    assert f.level_at(5, 5) == L.DARK
    assert L.CHARGE_SWEEP < L.FADE_FRAMES // 2, "the wake must be brief"


def test_a_sweep_is_forgotten_far_sooner_than_the_cone():
    swept = _lit_then_left(memory=L.CHARGE_SWEEP)
    coned = _lit_then_left(memory=L.CHARGE_LIT)
    _idle(swept, L.CHARGE_SWEEP)
    _idle(coned, L.CHARGE_SWEEP)
    assert swept.level_at(5, 5) == L.DARK
    assert coned.level_at(5, 5) != L.DARK
    assert L.CHARGE_SWEEP < L.LIT_THRESHOLD, "a sweep never leaves a lit memory"


def test_brightness_now_does_not_extend_the_memory():
    """A source shining on a cell shows bright without topping up the fade."""
    f = L.LightField()
    for _ in range(20):
        f.begin(); f.add(5, 5, L.LIT, L.CHARGE_SWEEP); f.commit()
        assert f.level_at(5, 5) == L.LIT
    assert f.charge[5 * COLS + 5] == L.CHARGE_SWEEP, "memory must not accumulate"


def test_a_brighter_memory_is_not_dimmed_by_a_weaker_light():
    """The cone has just left; the beam passing over must not shorten its trail."""
    f = _lit_then_left(memory=L.CHARGE_LIT)
    _idle(f, L.LIT_FRAMES + 20)          # well into the cone's dim tail
    before = f.charge[5 * COLS + 5]
    assert before > L.CHARGE_SWEEP
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_SWEEP); f.commit()
    assert f.charge[5 * COLS + 5] == before - 1, "decayed one frame, not topped"
    assert f.level_at(5, 5) == L.LIT, "but the beam on it still reads bright"


# --- hue per cell (issue #12) ----------------------------------------------

def _paint_with_map(field, ink_map=None):
    s = Screen()
    ink = bytearray([L.UNCOLOURED]) * (COLS * layout.PLAY_ROWS)
    if ink_map:
        for (cx, cy), hue in ink_map.items():
            ink[cy * COLS + cx] = hue
    field.paint(s, ink)
    return s


def test_hue_rides_with_the_memory_that_wins():
    f = L.LightField(light_hue=True)
    f.begin()
    f.add(5, 5, L.LIT, L.CHARGE_SWEEP, YELLOW)
    f.add(5, 5, L.LIT, L.CHARGE_LIT, WHITE)
    f.commit()
    assert f.hue[5 * COLS + 5] == WHITE, "the cone is brighter, so it colours"

    f = L.LightField(light_hue=True)
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_SWEEP, YELLOW); f.commit()
    assert f.hue[5 * COLS + 5] == YELLOW


def test_uncoloured_contents_take_the_light_hue_and_coloured_keep_theirs():
    f = L.LightField(light_hue=True)
    f.begin()
    f.add(5, 5, L.LIT, L.CHARGE_SWEEP, YELLOW)
    f.add(6, 5, L.LIT, L.CHARGE_SWEEP, YELLOW)
    f.commit()
    s = _paint_with_map(f, {(6, 5): CYAN})
    assert s.get_attr(5, 5) == L.attr_for(L.LIT, YELLOW), "floor goes yellow"
    assert s.get_attr(6, 5) == L.attr_for(L.LIT, CYAN), "a key stays cyan"


def test_light_hue_is_off_by_default():
    f = L.LightField()
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_SWEEP, YELLOW); f.commit()
    s = _paint_with_map(f)
    assert s.get_attr(5, 5) == L.attr_for(L.LIT, L.UNCOLOURED)


def test_memory_keeps_or_reverts_the_hue_as_asked():
    for keeps in (True, False):
        f = L.LightField(light_hue=True, hue_memory=keeps)
        f.begin(); f.add(5, 5, L.LIT, L.CHARGE_SWEEP, YELLOW); f.commit()
        _idle(f, 1)
        assert f.level_at(5, 5) == L.DIM
        s = _paint_with_map(f)
        expected = YELLOW if keeps else L.UNCOLOURED
        assert s.get_attr(5, 5) == L.attr_for(L.DIM, expected), f"keeps={keeps}"


def test_a_brighter_light_keeps_its_hue_against_a_weaker_one():
    f = L.LightField(light_hue=True)
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_LIT, WHITE); f.commit()
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_SWEEP, YELLOW); f.commit()
    assert f.hue[5 * COLS + 5] == WHITE


def test_hue_state_is_one_byte_per_cell():
    f = L.LightField()
    assert len(f.hue) == COLS * layout.PLAY_ROWS == 704


def test_a_passing_beam_does_not_recolour_ground_you_lit_yourself():
    """The hue follows the memory, and the cone's memory outlasts the beam's."""
    f = L.LightField(light_hue=True)
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_LIT, WHITE); f.commit()
    _idle(f, L.LIT_FRAMES + 20)
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_SWEEP, YELLOW); f.commit()
    assert f.hue[5 * COLS + 5] == WHITE


# --- what the fade may remember (issue #12) --------------------------------

def test_a_light_reveals_only_while_it_is_on_the_cell():
    """Memory is of the building, never of who was standing in it."""
    f = _lit_then_left(memory=L.CHARGE_LIT)
    assert f.reveals_at(5, 5), "revealed while the light is on it"
    _idle(f, 1)
    assert f.level_at(5, 5) == L.LIT, "still brightly remembered"
    assert not f.reveals_at(5, 5), "but no longer revealing"


def test_a_light_that_does_not_reveal_still_lights_the_ground():
    f = L.LightField()
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_LIT, reveals=False); f.commit()
    assert f.level_at(5, 5) == L.LIT
    assert not f.reveals_at(5, 5)


def test_one_revealing_source_is_enough():
    """A worker under a room light and in your glow is visible."""
    f = L.LightField()
    f.begin()
    f.add(5, 5, L.LIT, L.CHARGE_LIT, reveals=False)
    f.add(5, 5, L.DIM, L.CHARGE_DIM, reveals=True)
    f.commit()
    assert f.reveals_at(5, 5)


def test_revealing_is_cleared_between_frames():
    f = L.LightField()
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_LIT); f.commit()
    assert f.reveals_at(5, 5)
    f.begin(); f.commit()
    assert not f.reveals_at(5, 5)


def test_reading_revealing_outside_the_play_area_is_false():
    f = L.LightField()
    assert not f.reveals_at(-1, 0)
    assert not f.reveals_at(0, layout.PLAY_ROWS)


def test_prey_is_lit_not_merely_glimpsed():
    """Your own glow shows a worker at arm's length but never makes you prey."""
    f = L.LightField()
    f.begin(); f.add(5, 5, L.DIM, L.CHARGE_DIM); f.commit()
    assert f.reveals_at(5, 5), "the glow does show them"
    assert not f.prey_at(5, 5), "but it must not mark them as prey"

    f = L.LightField()
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_LIT); f.commit()
    assert f.prey_at(5, 5)


def test_a_light_that_hides_people_does_not_mark_prey_either():
    """Room lights show the room and not who is in it -- to Clegs as well."""
    f = L.LightField()
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_LIT, reveals=False); f.commit()
    assert f.level_at(5, 5) == L.LIT
    assert not f.prey_at(5, 5)


def test_prey_is_never_remembered():
    f = L.LightField()
    f.begin(); f.add(5, 5, L.LIT, L.CHARGE_LIT); f.commit()
    assert f.prey_at(5, 5)
    f.begin(); f.commit()
    assert not f.prey_at(5, 5), "the light has gone; you are in the dark again"
    assert f.level_at(5, 5) == L.LIT, "even though the cell still looks lit"
