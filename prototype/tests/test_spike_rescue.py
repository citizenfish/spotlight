"""Trapped workers, and reaching them: the objective at its smallest."""

from spikes import rescue as R, scene
from spikes.tally import Tally


def _one(x=80, y=48):
    return R.Rescue([(x, y)])


# --- finding ---------------------------------------------------------------

def test_a_worker_occupies_the_two_cells_a_person_stands_in():
    assert R.Worker(80, 48).cells() == {(10, 6), (10, 7)}


def test_a_worker_at_an_awkward_offset_straddles_six_cells():
    """Two columns and three rows: a 16-tall figure off the grid spans three."""
    assert len(R.Worker(83, 50).cells()) == 6


def test_walking_onto_any_cell_of_a_worker_reaches_them():
    """A person is a person wherever you touch them."""
    for cell in R.Worker(80, 48).cells():
        rescue = _one()
        assert rescue.reach({cell}) is not None, f"missed them at {cell}"


def test_bodies_that_overlap_are_touching():
    """Two 8x16 figures chest to chest, whose feet cells differ."""
    from spikes.player import Player
    worker = R.Worker(80, 48)                 # cells (10, 6) and (10, 7)
    rescue = R.Rescue([(80, 48)])
    player = Player(80, 48 + 8)               # standing through them
    assert player.occupied_cells() & worker.cells()
    assert rescue.reach(player.occupied_cells()) is not None


def test_the_player_standing_clear_reaches_nobody():
    from spikes.player import Player
    rescue = R.Rescue([(80, 48)])
    player = Player(80 + 24, 48)
    assert not player.occupied_cells() & R.Worker(80, 48).cells()
    assert rescue.reach(player.occupied_cells()) is None


def test_standing_beside_a_worker_does_not_reach_them():
    rescue = _one()
    assert rescue.reach({(9, 6)}) is None
    assert rescue.reach({(11, 6)}) is None
    assert rescue.remaining == 1


def test_a_worker_is_only_found_once():
    rescue = _one()
    assert rescue.reach({(10, 6)}) is not None
    assert rescue.reach({(10, 6)}) is None, "found the same person twice"
    assert rescue.found == 1


def test_the_room_is_cleared_when_everybody_is_found():
    rescue = R.Rescue([(80, 48), (160, 96)])
    assert not rescue.all_found
    rescue.reach({(10, 6)})
    assert not rescue.all_found
    rescue.reach({(20, 12)})
    assert rescue.all_found and rescue.remaining == 0


def test_those_already_found_stop_being_waiting():
    rescue = R.Rescue([(80, 48), (160, 96)])
    rescue.reach({(10, 6)})
    assert len(rescue.waiting()) == 1


def test_the_scene_gives_the_player_something_to_look_for():
    """Spike 2 could not answer its own question with an empty room."""
    rescue = R.Rescue(scene.WORKERS)
    assert rescue.remaining == len(scene.WORKERS) >= 5


# --- what a run cost -------------------------------------------------------

def test_a_tally_counts_only_the_frames_the_light_was_burning():
    t = Tally()
    for _ in range(100):
        t.frame(True, 0)
    for _ in range(300):
        t.frame(False, 0)
    assert t.lit_frames == 100
    assert t.lit_percent == 25


def test_blood_per_rescue_is_the_number_the_bargain_turns_on():
    t = Tally()
    t.found, t.blood_lost = 4, 10
    assert t.blood_per_worker == 25, "tenths, to stay integer"


def test_blood_per_rescue_survives_finding_nobody():
    t = Tally()
    t.blood_lost = 8
    assert t.blood_per_worker == 80, "no divide by zero"


def test_the_report_says_what_the_run_cost():
    t = Tally()
    t.frame(True, 2)
    lines = " ".join(t.report())
    for wanted in ("time", "workers found", "light on", "blood lost",
                   "attachments", "blood per rescue"):
        assert wanted in lines


# --- calling out (issue #10) ------------------------------------------------

def test_a_waiting_worker_calls_periodically():
    w = R.Worker(80, 48)
    calls = [f for f in range(R.CALL_PERIOD * 3) if w.calling(f)]
    assert calls, "never calls at all"
    assert len(calls) == R.CALL_FRAMES * 3


def test_a_call_is_brief_against_the_silence():
    """Often enough to give a bearing if you are watching, rare enough that
    you have to be."""
    assert R.CALL_FRAMES * 4 < R.CALL_PERIOD


def test_somebody_already_found_stops_calling():
    w = R.Worker(80, 48)
    assert any(w.calling(f) for f in range(R.CALL_PERIOD))
    w.found = True
    assert not any(w.calling(f) for f in range(R.CALL_PERIOD))


def test_the_room_does_not_shout_in_chorus():
    """Each call should be a separate piece of news."""
    rescue = R.Rescue(scene.WORKERS)
    at_once = [len(rescue.calling(f)) for f in range(R.CALL_PERIOD)]
    assert max(at_once) == 1, f"up to {max(at_once)} shouting together"


def test_the_room_is_quiet_most_of_the_time():
    """A call is a bearing you have to be watching for, not a map."""
    rescue = R.Rescue(scene.WORKERS)
    noisy = sum(1 for f in range(R.CALL_PERIOD) if rescue.calling(f))
    assert noisy * 3 < R.CALL_PERIOD, \
        f"somebody is shouting {100 * noisy // R.CALL_PERIOD}% of the time"


def test_the_word_sits_above_their_head():
    cells = R.Worker(80, 48).call_cells()
    assert len(cells) == len(R.CALL)
    assert all(cy == 5 for _, cy in cells), "should be the row above the head"
    assert [cx for cx, _ in cells] == [9, 10, 11, 12]


def test_a_worker_at_the_top_of_the_room_calls_from_below_instead():
    cells = R.Worker(80, 0).call_cells()
    assert all(cy > 1 for _, cy in cells), "the shout ran off the top"


def test_a_call_never_runs_off_the_side_of_the_room():
    from spotlight.core.constants import COLS
    for x in (0, 8, (COLS - 1) * 8, (COLS - 2) * 8):
        for cx, cy in R.Worker(x, 48).call_cells():
            assert 0 <= cx < COLS, f"shout at x={x} left the room"


def test_every_scene_worker_can_be_heard_inside_the_room():
    from spikes.layout import PLAY_ROWS
    from spotlight.core.constants import COLS
    for w in R.Rescue(scene.WORKERS).workers:
        for cx, cy in w.call_cells():
            assert 0 <= cx < COLS and 0 <= cy < PLAY_ROWS
