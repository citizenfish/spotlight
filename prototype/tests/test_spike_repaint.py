"""What a frame costs to draw: cells changing light level, counted inside.

Issue #46. The look-and-feel round changes what is drawn in eight slices and
every one of them has to be priced against the port model before the next
starts. The number that prices them is **how many cells change light level in a
frame**, because that is the class of work a dirty-cell port does.

**The thing that was wrong before** is what most of these tests hold down. The
figure could only be got by differencing consecutive frames from outside the
game: about four minutes of Python a suite, code nobody kept, and a number that
could not be compared slice to slice without re-running everything. So there is
a test here that runs the differ from outside and requires the counter inside to
agree with it frame for frame, and a test that the three whole-field frames per
room entry -- the ones the port cannot afford -- are visible in the data rather
than hidden in an average.

And it must cost nothing when nobody is asking, because a port carries no
metrics counter. That is pinned by making the counting path raise and then
playing the game.
"""

import pygame
import pytest

from spotlight.core.constants import COLS
from spotlight.core.screen import Screen

from spikes import (bots, lighting, report, session as session_mod, spike1,
                    spike_driver as driver)
from spikes.layout import PLAY_ROWS

CELLS = COLS * PLAY_ROWS
NO_WALLS = bytes(CELLS)
ALL_WALL = bytes([1]) * CELLS


def _levels(*lit_cells) -> bytes:
    out = bytearray(CELLS)
    for cx, cy in lit_cells:
        out[cy * COLS + cx] = lighting.LIT
    return bytes(out)


# --- what it counts --------------------------------------------------------

def test_it_counts_every_cell_whose_level_changed():
    counter = lighting.Repaint()
    assert counter.frame(_levels((3, 3)), NO_WALLS) == 1
    assert counter.frame(_levels((3, 3), (4, 3)), NO_WALLS) == 1
    # One went out as another came on: two cells to redraw, not none.
    assert counter.frame(_levels((5, 3), (4, 3)), NO_WALLS) == 2


def test_a_frame_that_changes_nothing_counts_nothing():
    """Three frames in four, in a real run. The player moves a pixel a frame,
    so change arrives in bursts when something crosses a cell boundary."""
    counter = lighting.Repaint()
    counter.frame(_levels((3, 3)), NO_WALLS)
    for _ in range(9):
        assert counter.frame(_levels((3, 3)), NO_WALLS) == 0
    assert counter.stats()["frames_unchanged_percent"] == 90


def test_a_dim_cell_is_a_change_and_a_dimmer_hue_is_not():
    """The level is the whole of it. DIM is not DARK and it is not LIT."""
    counter = lighting.Repaint()
    lit = bytearray(CELLS)
    lit[10] = lighting.LIT
    assert counter.frame(bytes(lit), NO_WALLS) == 1
    lit[10] = lighting.DIM
    assert counter.frame(bytes(lit), NO_WALLS) == 1
    lit[10] = lighting.DARK
    assert counter.frame(bytes(lit), NO_WALLS) == 1


def test_the_wall_split_counts_only_solid_cells():
    """The wall figure prices wall texture: a wall's pixels only need
    redrawing when its tile variant changes, so it is the cheaper class of
    work and it has to be separable from the floor."""
    walls = bytearray(CELLS)
    walls[3 * COLS + 3] = 1
    counter = lighting.Repaint()
    counter.frame(_levels((3, 3), (4, 3)), bytes(walls))
    assert counter.total == 2
    assert counter.wall_total == 1
    stats = counter.stats()
    assert stats["cells_changed_max"] == 2
    assert stats["wall_cells_changed_max"] == 1


def test_the_first_frame_is_counted_against_a_dark_screen():
    """A display holds nothing before the first frame is drawn, so the opening
    flash is 704 cells changed and not a baseline nobody sees. It is the single
    most expensive frame in the game and it must not be free by accounting."""
    counter = lighting.Repaint()
    assert counter.frame(bytes([lighting.LIT]) * CELLS, NO_WALLS) == CELLS
    assert counter.stats()["cells_changed_max"] == 704


def test_a_cleared_screen_is_priced_from_black_again():
    counter = lighting.Repaint()
    counter.frame(_levels((3, 3)), NO_WALLS)
    counter.crossed()
    assert counter.frame(_levels((3, 3)), NO_WALLS) == 1


# --- the arithmetic, which is all integer ----------------------------------

def test_mean_p95_p99_and_max_come_out_of_the_histogram():
    """Nearest rank, no interpolation, no floats -- 256 counters is what the
    Z80 would keep and percentiles between two counts would invent a cell that
    never changed."""
    counter = lighting.Repaint()
    shown = bytearray(CELLS)
    for i, count in enumerate([0] * 90 + [10] * 5 + [20] * 4 + [700]):
        # Force exactly `count` cells to differ from the last frame.
        nxt = bytearray(shown)
        for cell in range(count):
            nxt[cell] = (shown[cell] + 1) % 3
        assert counter.frame(bytes(nxt), NO_WALLS) == count
        shown = nxt
    stats = counter.stats()
    total = 5 * 10 + 4 * 20 + 700
    assert counter.frames == 100
    # The mean is per hundred frames, so that the metrics block stays integer:
    # 830 here is 8.30 cells a frame.
    assert stats["cells_changed_per_100f"] == 100 * total // 100 == 830
    # Ranks 1-90 are 0, 91-95 are 10, 96-99 are 20, and rank 100 is the 700.
    # p95 is the 95th of those, so the one whole-field frame sits outside both
    # percentiles and is only visible in the max -- which is exactly why the
    # max is reported.
    assert stats["cells_changed_p95"] == 10
    assert stats["cells_changed_p99"] == 20
    assert stats["cells_changed_max"] == 700
    assert stats["frames_unchanged_percent"] == 90


def test_a_run_with_no_frames_says_so_rather_than_zero():
    """`None` is an answer. A row of zeroes would claim nothing ever changed."""
    assert lighting.Repaint().stats() == {
        key: None for key in lighting.REPAINT_METRICS}


def test_the_stats_are_all_integers():
    counter = lighting.Repaint()
    counter.frame(_levels((1, 1)), ALL_WALL)
    assert all(isinstance(v, int) for v in counter.stats().values())


# --- the same number an external differ takes ------------------------------

def test_it_agrees_with_a_differ_run_from_outside_the_game():
    """The point of the whole issue: the same figure, for free.

    The differ below is the four-minute one, written out: keep the levels the
    screen is showing, compare them with next frame's, count what moved. Six
    hundred frames of the listener takes it past the first crossing, which is
    the frame the two could most easily disagree on -- see
    `test_a_crossing_is_a_whole_screen_of_work`.
    """
    run = session_mod.Session(metrics=True)
    bot = bots.make("listener", seed=run.seed)
    shown = bytes(CELLS)
    outside = []
    inside = []
    real = lighting.Repaint.frame

    def watched(self, levels, solid):
        count = real(self, levels, solid)
        inside.append(count)
        return count

    lighting.Repaint.frame = watched
    try:
        for _ in range(600):
            run.step(bot.intent(run))
            levels = run.place.field.levels()
            outside.append(sum(1 for a, b in zip(shown, levels) if a != b))
            shown = levels
    finally:
        lighting.Repaint.frame = real

    assert inside == outside
    assert sum(inside) > 0, "a listener that never sees anything proves nothing"


def test_the_three_room_entry_frames_are_visible():
    """The fault the number exists to watch, and it is not this round's to fix.

    The opening flash lights all 704 cells to the same charge, so they cross
    both fade thresholds in lockstep: the whole field changes on the frame the
    flash lands, again when it drops to dim, and again when it goes out. In the
    port model the first is 102,620 T-states against 52,416 spendable. An
    average hides all three; this test is here so that a slice which makes them
    worse cannot do it quietly.
    """
    run = session_mod.Session(metrics=True)
    counts = []
    real = lighting.Repaint.frame
    lighting.Repaint.frame = (
        lambda self, levels, solid:
        counts.append(real(self, levels, solid)) or counts[-1])
    try:
        for _ in range(200):
            run.step(session_mod.IDLE)
    finally:
        lighting.Repaint.frame = real

    whole_field = [(i, c) for i, c in enumerate(counts, 1) if c > CELLS // 2]
    frames = [i for i, _c in whole_field]
    assert frames == [1, 41, 161], whole_field
    # The flash arrives on a screen that is still black, so its own frame is
    # every cell there is. The two fade frames are all but the handful the
    # player's own glow is holding up.
    assert whole_field[0][1] == 704
    assert run.repaint.stats()["cells_changed_max"] == 704


def test_a_crossing_is_a_whole_screen_of_work():
    """Walking through a doorway replaces the picture, and it is counted.

    This is the one place the implementation departs from what the issue
    sketched. A counter kept per `LightField` would compare each room with its
    own last frame and price a crossing at nearly nothing -- while the screen,
    which is the thing being redrawn, has just changed every cell where the two
    rooms differ. The previous levels are therefore kept beside the screen.
    """
    run = session_mod.Session(metrics=True)
    a, b = run.places[0], run.places[1]
    a.field.begin()
    for cx in range(COLS):
        a.field.add(cx, 5, lighting.LIT, lighting.CHARGE_LIT)
    a.field.commit()
    run.repaint.frame(a.field.display, a.room.solid_map())
    before = run.repaint.total
    # The same instant, in the other room, which is dark.
    changed = run.repaint.frame(b.field.display, b.room.solid_map())
    assert changed == COLS, "the room you left has to be wiped off the screen"
    assert run.repaint.total == before + COLS


# --- it costs nothing when nobody is asking --------------------------------

def test_the_game_does_not_count(monkeypatch):
    """A port carries no metrics counter, so neither does the game.

    Not merely "the numbers are not reported" -- the path is not entered. The
    counter is made to explode and then the game is played at it.
    """
    def explode(*args, **kwargs):
        raise AssertionError("the game must not enter the counting path")

    monkeypatch.setattr(lighting.Repaint, "frame", explode)
    shell = spike1.Shell(Screen())
    shell.key(pygame.K_SPACE)
    for _ in range(60):
        shell.frame(dx=1)
    assert shell.run is not None
    assert shell.run.repaint is None


def test_a_session_counts_nothing_unless_it_is_asked():
    quiet = session_mod.Session()
    assert quiet.repaint is None
    # Not even the wall maps, which are the only other thing counting needs.
    assert quiet._wall_maps is None
    counted = session_mod.Session(metrics=True)
    assert counted.repaint is not None


def test_a_run_that_did_not_count_reports_nothing_rather_than_zero():
    """Every key is present so the across-seeds table keeps its columns, and
    every one is `None`, because zero would read as "nothing ever changed"."""
    run = session_mod.Session()
    for _ in range(10):
        run.step(session_mod.IDLE)
    numbers = report.metrics(run)
    for key in lighting.REPAINT_METRICS:
        assert numbers[key] is None, key


# --- and it comes out in the report ----------------------------------------

def test_the_driver_turns_it_on_and_the_json_carries_it():
    run = driver.drive(bots.make("listener", seed=1), seed=1, frames=400)
    numbers = driver.report.results(run, bot="listener")["metrics"]
    for key in lighting.REPAINT_METRICS:
        assert isinstance(numbers[key], int), key
    assert numbers["cells_changed_max"] == 704, "the opening flash is in there"
    assert 0 <= numbers["cells_changed_p95"] <= numbers["cells_changed_p99"]
    assert numbers["wall_cells_changed_per_100f"] \
        <= numbers["cells_changed_per_100f"]


def test_the_across_seeds_table_shows_them():
    """`--seeds N` has to tabulate them like every other metric, or a slice
    cannot be compared with the one before it."""
    rows = [driver.report.results(
        driver.drive(bots.make("listener", seed=seed), seed=seed, frames=300),
        bot="listener") for seed in (1, 2)]
    lines = driver.summary_lines(rows)
    assert "chg/100f" in lines[0]
    assert "chgmax" in lines[0]
    assert "wall/100f" in lines[0]
    for line, row in zip(lines[2:], rows):
        assert str(row["metrics"]["cells_changed_max"]) in line


def test_the_columns_all_exist_as_metrics():
    """A column whose key nobody produces prints a dash for ever."""
    numbers = report.metrics(
        driver.drive(bots.make("statue", seed=1), seed=1, frames=100))
    for _title, key, _width in driver.SUMMARY:
        assert key in numbers or key in ("seed", "ending"), key
