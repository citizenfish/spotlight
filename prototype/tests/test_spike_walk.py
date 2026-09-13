"""The stride counter on its own: four pixels of travel, either axis, once.

Issue #72. The figures' own tests (`test_spike_player`, `test_spike_rescue`)
pin the counter where it is stepped; this pins the counter's rule with no
figure in the way, so that a change to the rule fails here with the rule
named rather than there with a walk described.
"""

from spikes import walk
from spikes.walk import STRIDE_PIXELS, STRIDES, Stride


def test_the_cadence_is_four_pixels_and_the_cycle_is_four_steps():
    """The two numbers the drawing and the sheet are built on."""
    assert STRIDE_PIXELS == 4
    assert STRIDES == 4


def test_four_pixels_along_either_axis_is_a_stride_and_three_is_not():
    s = Stride(100, 100)
    assert not s.moved_to(103, 100) and s.index == 0
    assert s.moved_to(104, 100) and s.index == 1
    assert not s.moved_to(104, 103) and s.index == 1
    assert s.moved_to(104, 104) and s.index == 2


def test_the_anchor_moves_to_where_the_stride_happened():
    """Four pixels *since the last advance*, not since the start."""
    s = Stride(0, 0)
    s.moved_to(4, 0)
    assert not s.moved_to(7, 0), "counted from the start, not the stride"
    assert s.moved_to(8, 0)


def test_a_jump_of_more_than_four_is_one_stride():
    """*Four or more*, not *how many fours*: a nudge of a whole cell, or the
    wrap of x across a doorway, is one stride. An accumulator that counted
    every pixel strode twice on a nudge and the cycle skipped a frame."""
    s = Stride(0, 0)
    assert s.moved_to(8, 0) and s.index == 1
    assert s.moved_to(255, 0) and s.index == 2


def test_both_axes_at_once_is_one_stride():
    s = Stride(0, 0)
    assert s.moved_to(4, 4) and s.index == 1


def test_the_index_wraps_and_never_leaves_the_cycle():
    s = Stride(0, 0)
    seen = []
    for x in range(4, 4 * 10, 4):
        s.moved_to(x, 0)
        seen.append(s.index)
    assert seen == [1, 2, 3, 0, 1, 2, 3, 0, 1]
    assert all(0 <= i < walk.STRIDES for i in seen)


def test_standing_still_and_shuffling_hold_the_stride():
    s = Stride(50, 50)
    s.moved_to(54, 50)
    for _ in range(20):
        assert not s.moved_to(54, 50)
    for x in (55, 56, 57, 56, 55, 54, 53, 52, 51, 52, 53, 54):
        assert not s.moved_to(x, 50), f"a shuffle to {x} strode"
    assert s.index == 1


def test_the_counter_is_integers_only():
    """Portable code: three integers in the figure's record and nothing else,
    so the port stores three bytes and compares two of them."""
    s = Stride(3, 7)
    assert Stride.__slots__ == ("index", "_x", "_y")
    assert all(isinstance(getattr(s, slot), int) for slot in Stride.__slots__)
