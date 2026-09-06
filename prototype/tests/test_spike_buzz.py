"""The proximity sonar: the portable half, which is when it clicks."""

from spikes import buzz as B


def _clicks_over(distance, frames=1000):
    s = B.Sonar()
    return sum(1 for _ in range(frames) if s.update(distance))


# --- silence ---------------------------------------------------------------

def test_silent_when_there_is_nothing_to_hear():
    assert B.interval_for(None) == B.NEVER
    assert B.interval_for(B.REACH) == B.NEVER
    assert B.interval_for(B.REACH + 9) == B.NEVER
    assert _clicks_over(None) == 0
    assert _clicks_over(B.REACH) == 0


# --- the rate carries the urgency ------------------------------------------

def test_it_clicks_faster_the_closer_they_are():
    """Tempo is the whole cue, so it must never go the wrong way."""
    intervals = [B.interval_for(d) for d in range(0, B.REACH)]
    assert intervals == sorted(intervals), f"not monotonic: {intervals}"
    assert intervals[0] == B.FASTEST


def test_the_slowest_tick_is_a_rumour_and_the_fastest_is_a_problem():
    far = _clicks_over(B.REACH - 1, frames=500)
    near = _clicks_over(0, frames=500)
    assert near >= far * 3, f"contact ({near}) barely beats distant ({far})"


def test_the_edge_of_hearing_still_ticks():
    """The first step out of silence must not be silence."""
    assert B.interval_for(B.REACH - 1) != B.NEVER
    assert _clicks_over(B.REACH - 1, frames=200) >= 1


def test_you_hear_them_before_you_could_see_them():
    """The carried cone reaches seven cells; the warning must beat it."""
    assert B.REACH > 7
    assert B.interval_for(8) != B.NEVER


def test_intervals_are_whole_frames():
    assert all(isinstance(B.interval_for(d), int) for d in range(B.REACH + 2))


# --- the counter -----------------------------------------------------------

def test_a_click_is_a_single_frame_not_a_held_note():
    s = B.Sonar()
    fired = [s.update(0) for _ in range(B.FASTEST * 3)]
    assert fired.count(True) == 3, "should tick three times, not sound for all"


def test_closing_the_distance_tightens_the_tempo_at_once():
    """Not after one more wait at the old rate."""
    slow, fast = B.Sonar(), B.Sonar()
    for _ in range(B.FASTEST):
        slow.update(B.REACH - 1)
    for _ in range(B.FASTEST):
        fast.update(0)
    assert fast.clicks > slow.clicks


def test_going_quiet_resets_the_count():
    s = B.Sonar()
    for _ in range(B.FASTEST - 1):
        s.update(0)
    s.update(None)
    assert not s.update(0), "a click left over from before the silence"


def test_the_sonar_reports_the_interval_it_chose():
    s = B.Sonar()
    s.update(0)
    assert s.interval == B.FASTEST
    s.update(None)
    assert s.interval == B.NEVER
