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


def _whole_run(rescue, frames=9000):
    """Every frame of a full room's clock, as (frame, who is shouting)."""
    for f in range(frames):
        rescue.tick()
        yield f, rescue.calling(f)


def test_the_room_does_not_shout_in_chorus():
    """Each call should be a separate piece of news.

    Measured over a whole run rather than over one call period, which is what
    the old version of this test did and why it never saw the problem: at full
    blood everybody is at their slowest, and the room is at its quietest.

    With the flat clock all seven workers converged on the same two-second
    period and the last seconds of a run were **seven voices shouting on 95% of
    frames**. The staggered ladder never gets there, because the urgent ones
    have died before the slow ones become urgent.
    """
    worst = max(len(who) for _, who in _whole_run(R.Rescue(scene.WORKERS)))
    assert worst <= 3, f"up to {worst} of seven shouting together"


def test_the_room_is_quiet_most_of_the_time():
    """A call is a bearing you have to be watching for, not a map.

    Over the whole run, not over the first call period. The flat clock managed
    41% and finished on a solid wall of shouting; the ladder is a third.
    """
    frames = 9000
    noisy = sum(1 for _, who in _whole_run(R.Rescue(scene.WORKERS), frames)
                if who)
    assert noisy * 2 < frames, \
        f"somebody is shouting {100 * noisy // frames}% of the time"


def test_two_people_shouting_at_once_do_not_garble_each_other():
    """Staggered clocks mean the calls can overlap in time, so they must not
    overlap in space -- two HELPs sharing a cell would draw as neither word.

    This is a property of where this room puts its workers, so it is a test of
    the room as much as of the mechanism, and it is the reason the chorus test
    above can be relaxed at all.
    """
    for f, who in _whole_run(R.Rescue(scene.WORKERS)):
        taken = set()
        for worker in who:
            cells = set(worker.call_cells())
            assert not (cells & taken), f"two calls share a cell on frame {f}"
            taken |= cells


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


def test_a_dead_worker_calls_once_and_then_never_again():
    """**The death beat.** A death has to be announced or, as far as the player
    is concerned, it did not happen: an absence is not a signal, and a
    first-timer with six other voices in the building will not notice that one
    of them stopped. One shout, at the moment they die, from where they fell --
    and then silence for good.
    """
    rescue = R.Rescue([(80, 48)])
    w = rescue.workers[0]
    w.bleed(R.WORKER_BLOOD)
    assert w.state == R.DEAD

    shouted = 0
    for f in range(R.CALL_PERIOD * 3):
        if w.calling(f):
            shouted += 1
        rescue.tick()
    assert shouted == R.CALL_FRAMES, "the last call is one call, no more"
    assert not any(w.calling(f) for f in range(R.CALL_PERIOD))
    assert rescue.reach(w.cells()) is None


def test_the_death_call_comes_from_where_they_fell():
    """A follower who bleeds out on the walk to the exit has died too, and that
    is the loss the player most needs to be told about. The bearing is the cell
    they fell in, not the one they were trapped in."""
    rescue = R.Rescue([(80, 48)])
    w = rescue.workers[0]
    rescue.reach(w.cells())
    assert w.state == R.FOLLOWING
    w.x, w.y = 200, 96                       # dragged along behind the player
    assert w.bleed(R.WORKER_BLOOD)
    assert w.calling(0), "a follower's death is not announced"
    assert w.call_cells() == R.Worker(200, 96).call_cells()


def test_a_worker_who_dies_is_out_of_the_tail_but_still_shouts():
    rescue = R.Rescue([(80, 48), (160, 96)])
    first, second = rescue.workers
    rescue.reach(first.cells())
    assert rescue.tail == [first]
    first.blood = 1
    for _ in range(R.BLEED_EVERY):
        rescue.tick()
    assert first.state == R.DEAD and rescue.tail == []
    assert first in rescue.calling(0)
    assert second.state == R.WAITING


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
    w.blood = w.reference // 4
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
    for x, y, _blood in scene.WORKERS:
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


# --- the staggered clocks (issue #18, values from issue #23) ---------------

#: Lives in seconds, in the order the vault authors them. Not derived from the
#: code: written out, so that a change to `BLEED_EVERY` or to the ladder has to
#: be a change to an agreed number rather than an accident.
LADDER_SECONDS = (60, 80, 100, 120, 140, 160, 180)


def test_the_room_authors_a_blood_ladder_and_does_not_compute_one():
    """**The thing that was wrong.** Every worker started on the same blood and
    bled on the same tick, so all seven died in the same frame -- measured, on
    every seed. There was no "who do I go to first", no death anybody could
    learn from, and no body was ever seen because the level ended on the frame
    the bodies appeared.
    """
    bloods = sorted(blood for _x, _y, blood in scene.WORKERS)
    assert bloods == [30, 40, 50, 60, 70, 80, 90]
    assert len(set(bloods)) == len(bloods), "two workers share a clock"


def test_the_ladder_is_the_lives_the_vault_agreed():
    lives = sorted(blood * R.BLEED_EVERY // 50 for _x, _y, blood in scene.WORKERS)
    assert tuple(lives) == LADDER_SECONDS


def test_no_two_deaths_land_within_twenty_seconds_of_each_other():
    """Target T7, as restated in *Difficulty targets*. Twenty seconds is one
    body window each, so the player attends to one loss at a time, and it holds
    concurrent nests to the two the entity budget can carry.

    First-to-last is not the quantity: seven deaths spread over sixty seconds
    are ten seconds apart, which is half a window.
    """
    rescue = R.Rescue(scene.WORKERS, scene.exit_cell())
    deaths = []
    for f in range(20000):
        for _ in rescue.tick():
            deaths.append(f)
        if rescue.settled:
            break
    assert len(deaths) == len(scene.WORKERS), "not everybody bled out"
    gaps = [b - a for a, b in zip(deaths, deaths[1:])]
    assert min(gaps) >= 20 * 50, f"two deaths {min(gaps) // 50}s apart"


def test_the_shortest_clock_is_already_urgent_on_the_first_frame():
    """Urgency is time left, not fraction left. Scaling each worker against
    their own capacity was tried and rejected: it makes everybody sound
    identical on frame one, which is exactly when the "who first" decision is
    taken, and turns the shout into a report of how much of themselves is left.
    """
    rescue = R.Rescue(scene.WORKERS, scene.exit_cell())
    periods = {w.start_blood: w.call_period for w in rescue.workers}
    assert periods[90] == R.CALL_PERIOD, "the longest clock is not the slowest"
    assert periods[30] < R.CALL_PERIOD // 2, "the shortest clock is not urgent"
    ordered = [periods[b] for b in sorted(periods)]
    assert ordered == sorted(ordered), "shouting does not follow the ladder"


def test_two_workers_with_the_same_blood_left_shout_at_the_same_rate():
    """One bleed tick for everybody means the same blood is the same number of
    seconds, so it has to sound the same however much they started with."""
    rescue = R.Rescue(((0, 0, 30), (8, 0, 90)))
    short, long_ = rescue.workers
    short.blood = long_.blood = 15
    assert short.call_period == long_.call_period


def test_a_body_lies_on_screen_for_its_whole_window():
    """Nobody had ever seen one: the run ended on the frame the body appeared.
    A body has to exist, stay put, and be walked up to."""
    rescue = R.Rescue(scene.WORKERS, scene.exit_cell())
    first = None
    for f in range(20000):
        gone = rescue.tick()
        if gone and first is None:
            first = (f, gone[0], (gone[0].x, gone[0].y))
            break
    assert first is not None
    frame, body, where = first
    for _ in range(R.BODY_FRAMES):
        rescue.tick()
        assert (body.x, body.y) == where, "the body moved"
        assert body in rescue.bodies()
    assert rescue.waiting > 0, "the room emptied before the window elapsed"


# --- a death can now come from two directions (issue #19) ------------------

def test_a_death_is_counted_once_whichever_way_it_arrives():
    """A Cleg kills in `Swarm.tick`; the clock kills in `Rescue.tick`, later in
    the same frame. `reap` is the one place that notices either, so a death
    cannot be counted twice or missed by whichever killer forgot to report it.
    """
    rescue = R.Rescue([(80, 48), (160, 96)])
    bitten, bled = rescue.workers
    bitten.bitten(bitten.blood)                  # a fly drank them dry
    assert bitten.state == R.DEAD
    assert rescue.tick() == [bitten]
    assert rescue.tick() == [], "the same death was counted twice"
    assert rescue.died == [bitten] and rescue.lost == 1

    bled.blood = 1
    for _ in range(R.BLEED_EVERY):
        rescue.tick()
    assert rescue.died == [bitten, bled] and rescue.lost == 2
    assert rescue.settled is False or rescue.saved == 0


def test_a_bite_death_and_a_clock_death_have_the_same_frame_zero():
    """One frame, and nobody could see it -- but the body's age is what the
    nest window will be measured in, so an off-by-one nobody can perceive today
    is one somebody builds on tomorrow.
    """
    bitten = R.Worker(80, 48, blood=1)
    bled = R.Worker(80, 48, blood=1)
    bitten.bitten(1)                    # killed before the frame's tick
    bitten.tick()                       # ...and then the frame ticks
    for _ in range(R.BLEED_EVERY):
        bled.tick()                     # killed by the tick itself
    assert bitten.state == bled.state == R.DEAD
    assert bitten.calling(0) and bled.calling(0)
    for _ in range(R.CALL_FRAMES - 1):
        bitten.tick()
        bled.tick()
    assert bitten.calling(0) == bled.calling(0) is True
    bitten.tick()
    bled.tick()
    assert bitten.calling(0) == bled.calling(0) is False


def test_the_exit_is_a_place_you_can_be_whether_or_not_you_have_anybody():
    """Issue #20 split "am I at the door" from "is there anybody to hand over".
    They were one question, and the run now ends on the first of them."""
    rescue = R.Rescue([(80, 48)], exit_cell=(4, 4))
    assert rescue.at_exit({(4, 4), (4, 5)})
    assert not rescue.at_exit({(9, 9)})
    assert rescue.deliver({(4, 4)}) == [], "nobody to deliver, and no error"

    worker = rescue.workers[0]
    rescue.reach(worker.cells())
    assert rescue.deliver({(4, 4)}) == [worker]
