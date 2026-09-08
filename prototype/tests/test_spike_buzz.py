"""The two speakers: the portable half, which is when each of them sounds."""

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


# --- the body's tick (issue #33) -------------------------------------------
#
# The same counter with the interval handed to it rather than worked out from a
# distance, because a body's tick period is a property of the body. What makes
# the two voices tell apart is timbre and not rate -- see `spike_buzz.tick_wave`
# -- because rate is already carrying the meaning in both of them.

def test_the_ticker_is_silent_when_there_is_nothing_to_hear():
    t = B.Ticker()
    assert not any(t.update(B.NEVER) for _ in range(200))


def test_the_ticker_fires_on_the_interval_it_is_given():
    t = B.Ticker()
    assert [t.update(4) for _ in range(12)].count(True) == 3
    assert t.ticks == 3


def test_a_quickening_interval_fires_sooner_rather_than_restarting():
    """The same property the sonar has: the tempo tightens the moment the body
    gets closer to turning, not after one more wait."""
    t = B.Ticker()
    for _ in range(6):
        assert not t.update(50)
    assert t.update(6), "the count restarted when the interval shortened"


def test_a_silence_resets_the_count():
    """A body that is doused, turns, or is left two rooms away stops ticking
    rather than pausing mid-beat."""
    t = B.Ticker()
    for _ in range(9):
        t.update(10)
    t.update(B.NEVER)
    assert [t.update(10) for _ in range(9)].count(True) == 0


# --- the host's two voices --------------------------------------------------
#
# `spike_buzz` is the Pygame layer and does not port, but the *shape* of what it
# plays is the design: a lower, doubled click against the sonar's single one.
# On a Spectrum both are OUTs to port 254 and the difference is the delay
# between the flips, so the shape is the part that survives.

def test_the_bodys_tick_is_doubled_and_lower_than_the_sonars():
    from spikes import spike_buzz as H
    click = H.click_wave(stereo=False)
    tick = H.tick_wave(stereo=False)
    assert len(tick) > 2 * len(H.click_wave(H._BODY_SAMPLES, H._BODY_HALF,
                                            stereo=False)) - 1, \
        "the tick is not two beats and a gap"
    assert H._BODY_HALF > H._HALF, "the body's tick is not the lower voice"
    assert click and tick
