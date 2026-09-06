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
    assert rescue.waiting == 1


def test_a_worker_is_only_found_once():
    rescue = _one()
    assert rescue.reach({(10, 6)}) is not None
    assert rescue.reach({(10, 6)}) is None, "found the same person twice"
    assert len(rescue.tail) == 1


def test_the_room_is_cleared_when_everybody_is_found():
    rescue = R.Rescue([(80, 48), (160, 96)])
    assert rescue.waiting
    rescue.reach({(10, 6)})
    assert rescue.waiting
    rescue.reach({(20, 12)})
    assert rescue.waiting == 0


def test_those_already_found_stop_being_waiting():
    rescue = R.Rescue([(80, 48), (160, 96)])
    rescue.reach({(10, 6)})
    assert rescue.waiting == 1


def test_the_scene_gives_the_player_something_to_look_for():
    """Spike 2 could not answer its own question with an empty room."""
    rescue = R.Rescue(scene.WORKERS)
    assert rescue.waiting == len(scene.WORKERS) >= 5


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
    w.state = R.FOLLOWING
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


# --- the clock (issue #13) -------------------------------------------------

def test_a_worker_bleeds_from_the_moment_the_level_starts():
    """This is the clock. Without it the best play is dark and methodical,
    which is safe, correct and dull."""
    w = R.Worker(80, 48)
    assert w.blood == R.WORKER_BLOOD
    for _ in range(R.BLEED_EVERY):
        w.tick()
    assert w.blood == R.WORKER_BLOOD - 1


def test_a_worker_left_alone_dies_and_leaves_a_body():
    rescue = R.Rescue([(80, 48)])
    w = rescue.workers[0]
    died = []
    for _ in range(R.BLEED_EVERY * R.WORKER_BLOOD):
        died += rescue.tick()
    assert died == [w]
    assert w.state == R.DEAD and not w.alive
    assert rescue.lost == 1 and rescue.waiting == 0
    assert rescue.bodies() == [w]


def test_a_body_lies_there_before_it_would_turn():
    """The window the flyspray exists for, even before nests are built."""
    w = R.Worker(80, 48, blood=1)
    for _ in range(R.BLEED_EVERY):
        w.tick()
    assert w.state == R.DEAD and not w.turning
    for _ in range(R.BODY_FRAMES):
        w.tick()
    assert w.turning


def test_a_dead_worker_stops_calling_and_cannot_be_freed():
    rescue = R.Rescue([(80, 48)])
    w = rescue.workers[0]
    w.bleed(R.WORKER_BLOOD)
    assert w.state == R.DEAD
    assert not any(w.calling(f) for f in range(R.CALL_PERIOD))
    assert rescue.reach(w.cells()) is None


# --- the tail --------------------------------------------------------------

def test_freeing_somebody_puts_them_in_the_tail_in_order():
    rescue = R.Rescue([(80, 48), (160, 96), (40, 24)])
    first, second = rescue.workers[1], rescue.workers[0]
    rescue.reach(first.cells())
    rescue.reach(second.cells())
    assert rescue.tail == [first, second], "the tail is not in collection order"
    assert all(w.state == R.FOLLOWING for w in rescue.tail)


def test_the_tail_walks_the_path_the_player_walked():
    """Followers step where the player stepped, not toward where they are --
    which is what makes a line string out round a corner instead of clumping."""
    rescue = R.Rescue([(80, 48)])
    rescue.reach(rescue.workers[0].cells())
    follower = rescue.tail[0]
    for x in range(200, 260):          # walk east
        rescue.follow(x, 48)
    assert follower.y == 48
    assert 0 < 259 - follower.x <= R.TAIL_SPACING + 1, \
        "the follower is not trailing at the right distance"


def test_a_longer_tail_strings_out_rather_than_stacking_up():
    rescue = R.Rescue([(80, 48), (81, 48), (82, 48)])
    for w in list(rescue.workers):
        rescue.reach(w.cells())
    for x in range(100, 300):
        rescue.follow(x, 48)
    xs = [w.x for w in rescue.tail]
    assert xs == sorted(xs, reverse=True), "the tail is out of order"
    assert len(set(xs)) == len(xs), "followers are standing on each other"


def test_followers_keep_bleeding():
    """Escorting is against the same clock as searching, so gathering everybody
    before heading out is a gamble rather than the obvious play."""
    rescue = R.Rescue([(80, 48)])
    rescue.reach(rescue.workers[0].cells())
    follower = rescue.tail[0]
    before = follower.blood
    for _ in range(R.BLEED_EVERY * 2):
        rescue.tick()
    assert follower.blood < before


def test_a_follower_who_bleeds_out_leaves_the_tail():
    rescue = R.Rescue([(80, 48)])
    rescue.reach(rescue.workers[0].cells())
    for _ in range(R.BLEED_EVERY * R.WORKER_BLOOD):
        rescue.tick()
    assert rescue.tail == []
    assert rescue.lost == 1


# --- the way out -----------------------------------------------------------

def test_the_exit_banks_everybody_following():
    rescue = R.Rescue([(80, 48), (160, 96)], exit_cell=(10, 3))
    for w in list(rescue.workers):
        rescue.reach(w.cells())
    saved = rescue.deliver({(10, 3), (10, 4)})
    assert len(saved) == 2
    assert rescue.saved == 2 and rescue.tail == []
    assert rescue.settled


def test_the_exit_is_reached_by_touching_it_not_standing_on_it():
    """The way out is a door in a wall, and a person is two cells tall -- the
    feet-cell test made it unreachable."""
    rescue = R.Rescue([(80, 48)], exit_cell=(10, 1))
    rescue.reach(rescue.workers[0].cells())
    assert rescue.deliver({(10, 2), (10, 3)}) == []
    assert len(rescue.deliver({(10, 1), (10, 2)})) == 1


def test_arriving_at_the_exit_with_nobody_does_nothing():
    rescue = R.Rescue([(80, 48)], exit_cell=(10, 3))
    assert rescue.deliver({(10, 3)}) == []
    assert rescue.saved == 0


def test_a_run_is_settled_when_everybody_is_out_or_dead():
    rescue = R.Rescue([(80, 48), (160, 96)], exit_cell=(10, 3))
    assert not rescue.settled
    rescue.workers[0].bleed(R.WORKER_BLOOD)
    assert not rescue.settled
    rescue.reach(rescue.workers[1].cells())
    rescue.deliver({(10, 3)})
    assert rescue.settled and rescue.saved == 1 and rescue.lost == 1


# --- the clock you can hear (issue #13) ------------------------------------

def test_a_worker_shouts_more_often_as_they_weaken():
    """The clock, and the only form it takes. A number counting down is not
    something a person in a dark building would know."""
    w = R.Worker(80, 48)
    fresh = w.call_period
    w.blood = R.WORKER_BLOOD // 4
    assert w.call_period < fresh
    w.blood = 1
    assert w.call_period < R.CALL_PERIOD // 4


def test_the_most_frantic_call_is_still_a_call_not_a_siren():
    w = R.Worker(80, 48, blood=1)
    assert w.call_period >= R.CALL_PERIOD_URGENT
    assert w.call_period > R.CALL_FRAMES * 2, "shouting more than it is silent"


# --- the room (issue #13) --------------------------------------------------

def test_no_worker_starts_within_reach_of_the_exit():
    """A worker beside the door is not a rescue: no journey, no decision about
    when to leave, and nothing for the clock to bite on."""
    ex = scene.exit_cell()
    for x, y in scene.WORKERS:
        cell = (x // 8, (y + 15) // 8)
        assert max(abs(cell[0] - ex[0]), abs(cell[1] - ex[1])) > 8, \
            f"the worker at {cell} is on the doorstep"


def test_the_exit_carries_a_sign_beside_it():
    ex = scene.exit_cell()
    sign = scene.exit_sign_cells()
    assert len(sign) == len(scene.EXIT_SIGN)
    assert all(not scene.is_solid(cx, cy) for cx, cy in sign)
    assert all(cy == ex[1] for _, cy in sign), "the sign is not beside the door"
    assert max(abs(cx - ex[0]) for cx, _ in sign) <= len(scene.EXIT_SIGN)


def test_the_room_holds_nothing_that_cannot_be_touched():
    """Anything drawn is a claim that it matters; the player paid light to see
    it. A body and a nest sat here long after they meant anything."""
    assert scene.ENTITIES == ()
