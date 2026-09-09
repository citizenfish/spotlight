"""Nests: a body's window, the brood, and a lifecycle that ends (issue #33).

The last thing owed before the phase-1 list is complete, and deliberately last
in the queue: it needs #18's staggered clocks so a body is not created on the
frame the level ends, #20 so the run outlives the first death, and #21 so a
death in the other room is not silent.

What is tested here is the lifecycle and the arithmetic. **The whole of it is
integer arithmetic on one frame counter**, which is what makes it affordable to
run for seven people in two rooms on a Z80: a body's state is where it is in its
fifty seconds, plus one bit saying whether somebody spent a charge on it.
"""

from spikes import (
    buzz, clegs as C, rescue as R, scene, session as S, sources, spray,
)
from spikes.session import Intent, Session
from spotlight.core.constants import CELL
from spotlight.core.screen import Screen


def _dead_body(age: int = 0) -> R.Worker:
    """One worker, dead, with a body of the given age in frames."""
    w = R.Worker(80, 48, blood=1)
    for _ in range(R.BLEED_EVERY):
        w.tick()
    assert w.state == R.DEAD
    for _ in range(age):
        w.tick()
    return w


# --- the lifecycle, which ends ---------------------------------------------

def test_the_window_is_twenty_seconds_and_the_nest_is_thirty():
    """The numbers the vault argued, in frames at 50Hz.

    `BODY_FRAMES` was 500 until this issue and the discrepancy was pinned on
    purpose in `test_held_constants.py` so it would be found deliberately
    rather than by surprise. This is where it is found.
    """
    assert R.BODY_FRAMES == 20 * 50
    assert R.NEST_FRAMES == 30 * 50
    assert R.GONE_FRAMES == 50 * 50


def test_one_spray_charge_buys_exactly_one_spawn():
    """The spray economy already said the right thing and no number here was
    chosen to make it: a patch lasts five seconds and a nest spawns every five.

    Five charges against six spawns is what makes suppression *holding ground*
    rather than a way to destroy a nest -- and if you spent everything on one
    you would have nothing left for the doorway you then have to get a tail
    through.
    """
    from spikes import spray
    assert R.NEST_SPAWN_EVERY == spray.PATCH_FRAMES
    assert spray.Spray().charges < R.NEST_BROOD


def test_a_body_lies_there_its_window_and_then_turns():
    body = _dead_body()
    assert body.in_window and not body.turning and not body.gone
    for _ in range(R.BODY_FRAMES - 1):
        body.tick()
        assert body.in_window, f"turned early at {body.age}"
    body.tick()
    assert body.turning and body.nesting and not body.in_window


def test_a_nest_burns_out_and_then_there_is_nothing():
    body = _dead_body(R.BODY_FRAMES)
    assert body.nesting
    for _ in range(R.NEST_FRAMES - 1):
        body.tick()
        assert body.nesting, f"burnt out early at {body.age}"
    body.tick()
    assert body.gone and not body.nesting


def test_a_doused_body_never_turns_and_still_goes():
    """**Every body is temporary, whatever you do about it.** A doused body
    lingers for as long as the nest it prevented would have taken, so a body's
    whole life is the same fifty seconds however it ends -- which is the point:
    saving somebody's body must not leave it on screen longer than losing it.
    """
    body = _dead_body(100)
    assert body.douse()
    for _ in range(R.NEST_FRAMES + R.BODY_FRAMES - 101):
        body.tick()
        assert not body.turning, "a doused body turned"
        assert not body.gone
    body.tick()
    assert body.gone


def test_a_body_can_only_be_doused_inside_its_window():
    """One charge before it turns, against more than five after and still
    losing. A nest cannot be undone and a doused body cannot be doused twice."""
    early = _dead_body(R.BODY_FRAMES - 1)
    assert early.douse()
    assert not early.douse(), "a second charge was spent on the same body"

    late = _dead_body(R.BODY_FRAMES)
    assert not late.douse(), "a nest was undone by a spray charge"
    assert late.turning


def test_a_body_that_has_gone_is_not_a_body_or_a_nest_any_more():
    """Bodies no longer accumulate, and this is the query that says so: what
    the drawing asks for is what is still there."""
    rescue = R.Rescue([(80, 48, 1)])
    body = rescue.workers[0]
    rescue.tick()
    while body.age < R.GONE_FRAMES:
        rescue.tick()
    assert body.state == R.DEAD, "the tally forgot them"
    assert rescue.lost == 1, "a lifecycle that ends is not a death undone"
    assert rescue.bodies() == [] and rescue.nests() == []


# --- what hatches ----------------------------------------------------------

def test_a_nest_owes_six_one_every_five_seconds():
    """The first the frame it turns, the sixth five seconds before it burns
    out. Six spawns over thirty seconds, from a clock rather than a countdown.
    """
    body = _dead_body(R.BODY_FRAMES)
    owed = []
    for _ in range(R.NEST_FRAMES):
        if body.owed:
            owed.append(body.age - R.BODY_FRAMES)
            body.hatched += 1
        body.tick()
    assert len(owed) == R.NEST_BROOD
    assert owed == [i * R.NEST_SPAWN_EVERY for i in range(R.NEST_BROOD)]


def test_a_held_spawn_is_delayed_and_never_dropped():
    """**A busy room delays a brood; it never cancels one.** `owed` is earned
    from the clock rather than counted down, so a nest that could not place its
    second still owes it when the room clears."""
    body = _dead_body(R.BODY_FRAMES)
    for _ in range(R.NEST_SPAWN_EVERY * 3):
        body.tick()                       # nothing hatches: the valve holds
    assert body.owed == 4, "the held spawns were dropped"


def test_a_nest_spends_its_thirty_seconds_however_much_it_held():
    """Holding must not buy the nest more time. It burns out on the frame it
    would have burnt out on if every spawn had been placed."""
    held = _dead_body(R.BODY_FRAMES)
    for _ in range(R.NEST_FRAMES - 1):
        held.tick()
    assert held.nesting and held.hatched == 0
    held.tick()
    assert held.gone, "a held-up nest outlived its thirty seconds"


# --- the body's tick -------------------------------------------------------

def test_a_body_ticks_from_the_moment_of_death():
    body = _dead_body()
    assert body.ticking
    assert body.tick_period == R.TICK_SLOWEST


def test_the_tick_quickens_as_the_window_runs_out():
    """The sonar's own idiom, deliberately: in Spotlight a quickening tick
    always means you have less time than you did. Three speakers, one
    sentence."""
    body = _dead_body()
    periods = []
    while body.in_window:
        periods.append(body.tick_period)
        body.tick()
    assert periods[0] == R.TICK_SLOWEST
    assert periods[-1] <= R.TICK_FASTEST + 1
    assert periods == sorted(periods, reverse=True), "the tick slowed down"


def test_the_tick_stops_on_dousing_and_on_turning():
    doused = _dead_body(200)
    doused.douse()
    assert not doused.ticking

    turned = _dead_body(R.BODY_FRAMES)
    assert not turned.ticking


def test_only_one_body_ticks_and_it_is_the_one_nearest_turning():
    """At most one body ticks at a time -- with twenty-second clocks and a
    twenty-second window that is nearly always literally true. When a bite
    makes it false, the tick is about the one with the least time left."""
    rescue = R.Rescue([(80, 48, 1), (160, 48, 1)])
    fresh, older = rescue.workers
    older.bitten(older.blood)
    rescue.tick()
    for _ in range(300):
        rescue.tick()
    fresh.bitten(fresh.blood)
    rescue.tick()
    assert fresh.ticking and older.ticking
    assert rescue.ticking() is older


def test_the_ticker_drops_a_beat_rather_than_holding_a_note():
    t = buzz.Ticker()
    fired = [t.update(10) for _ in range(30)]
    assert fired.count(True) == 3
    assert not t.update(buzz.NEVER)


# --- in a run --------------------------------------------------------------

def _run_until(run, test, limit=30000):
    while run.frame < limit and run.over is None:
        run.step()
        if test():
            return True
    return False


def test_a_body_in_a_run_turns_hatches_and_leaves_nothing_behind():
    """The whole lifecycle on a live building, which is the only place the
    valve, the swarm and the drawing all have an opinion at once."""
    run = Session(seed=1, lives=99)
    assert _run_until(run, lambda: bool(run.rescue.bodies()))
    body = run.rescue.bodies()[0]
    started = len(run.swarm.clegs)

    assert _run_until(run, lambda: body.nesting), "no body ever turned"
    assert [e for e in run.log if e.kind == S.NEST_TURNED]

    assert _run_until(run, lambda: body.hatched > 0), "a nest spawned nothing"
    assert len(run.swarm.clegs) > started

    assert _run_until(run, lambda: body.gone), "a nest never burnt out"
    assert body not in run.rescue.bodies() and body not in run.rescue.nests()


def test_a_burnt_out_nest_leaves_nothing_on_screen():
    """*Screen Layout*: anything drawn is a claim that it matters, because the
    player paid light to see it. Measured after #20, bodies accumulated and
    never left -- seven on screen at once in a losing room's last minute."""
    run = Session(seed=1, lives=99)
    assert _run_until(run, lambda: bool(run.rescue.bodies(run.here)))
    body = run.rescue.bodies(run.here)[0]
    where = (body.x, body.y)

    screen = Screen()
    run.draw(screen)
    lit = [(dx, dy) for dy in range(2 * CELL) for dx in range(CELL)
           if screen.point(where[0] + dx, where[1] + dy)]
    assert lit, "a body in its window was not drawn at all"

    assert _run_until(run, lambda: body.gone)
    run.draw(screen)
    still = [(dx, dy) for dy in range(2 * CELL) for dx in range(CELL)
             if screen.point(where[0] + dx, where[1] + dy)]
    assert not still, f"a burnt-out nest left {len(still)} pixels on screen"


def test_no_run_ends_with_a_screen_of_bodies():
    """The fix for the thing that was measured: **bodies no longer
    accumulate.** Seven people can die and the room still has to be readable.

    Before this, a losing room's last minute had up to seven bodies on it and
    none of them ever left. Now a run in which everybody dies ends with an empty
    floor, and at no point in it are there more than four bodies and nests
    together -- which is what a fifty-second lifecycle allows given how close
    together these deaths actually land. See the test below for that number,
    because it is not the one the design assumed.
    """
    for seed in (1, 2, 3):
        run = Session(seed=seed, lives=99)
        most = 0
        for _ in range(20000):
            run.step()
            if run.over is not None:
                break
            most = max(most, len(run.rescue.bodies()) + len(run.rescue.nests()))
        assert run.lost == run.total, f"seed {seed} did not lose everybody"
        assert most <= 4, f"seed {seed} had {most} bodies and nests at once"
        assert most < run.total, "a screen of them is still a screen of them"
        assert not run.rescue.bodies() and not run.rescue.nests(), \
            f"seed {seed} ended with bodies still lying there"


def test_three_nests_are_live_at_once_because_the_deaths_are_not_spaced():
    """**The two-nest ceiling is a property of the clock ladder, and the ladder
    is no longer what decides when people die.**

    The arithmetic the design states is right: a body's lifecycle is fifty
    seconds and the authored clocks are twenty apart, so a nest turns while the
    previous one has ten seconds to run and the one before it has gone. Two
    overlap and three never do -- *if the deaths are twenty seconds apart*.

    They are not. Since issue #19 a Cleg can drink a worker dry, so the spacing
    became distributional: on an idle run these seeds land consecutive deaths
    **four to eight seconds** apart, and three nests are live together. That is
    the exact reason the hold-the-spawn valve was promoted back from a backstop
    to the budget's guarantee -- a guarantee cannot survive a randomising
    accelerator -- and it is why the valve rather than the spacing is what this
    build relies on.

    Recorded as a measurement of what the prototype does, not as an approval of
    it. Whether the ladder, the bite or the ceiling should move is a decision
    for the vault; target T13 is asked of bot runs, and this is the bot-less
    floor under it.
    """
    run = Session(seed=1, lives=99)
    while run.frame < 20000 and run.over is None:
        run.step()
    assert run.most_nests == 3, \
        f"the idle run held {run.most_nests} nests at once, not three"


def test_nest_born_clegs_start_at_the_top_of_the_hunger_curve():
    """**Ordinary Clegs in every respect but one: they have never fed.** That
    is not a second rule -- it is the existing hunger rule read honestly for a
    fly that has never eaten, so it can notice the faintest light in the room
    from the moment it hatches and comes straight for you wherever you are."""
    run = Session(seed=1, lives=99)
    was = {id(c) for c in run.swarm.clegs}
    assert _run_until(run, lambda: any(id(c) not in was
                                       for c in run.swarm.clegs))
    born = [c for c in run.swarm.clegs if id(c) not in was]
    assert born
    for fly in born:
        assert fly.keenness == C.KEEN_MAX, "a hatchling was born fed"


def test_a_hatchling_is_only_exceptional_until_its_first_meal():
    """That is what makes a nest a spike rather than a climate, and it needed
    no code: `Swarm._sate` already zeroes hunger when a fly feeds."""
    fly = C.Cleg(4, 4, seed=7)
    fly.hunger = C.KEEN_MAX * C.HUNGER_STEP
    assert fly.keenness == C.KEEN_MAX
    C.Swarm._sate(fly)
    assert fly.keenness == 0


# --- the spray, and the window it is for -----------------------------------

def test_a_charge_on_a_fresh_body_saves_it_from_turning():
    """Dousing is not a new verb: it is sprayed ground, which is what
    `spray.py` has said the spray is for since it was written."""
    run = Session(seed=1, lives=99)
    assert _run_until(run, lambda: bool(run.rescue.bodies(run.here)))
    body = run.rescue.bodies(run.here)[0]
    charges = run.spray.charges

    # Stand a couple of cells west of the body, face it, and fire -- which is
    # what walking up to one and pressing the button is. The patch is laid
    # *ahead* of the player, and this is that route into a douse. Standing on
    # the body is the other one, and has its own tests below (issue #39).
    cx, cy = body.cell()
    run.player.x, run.player.y = (cx - 2) * CELL, (cy - 1) * CELL
    run.player.facing = sources.RIGHT
    run.step(Intent(spray=True))
    assert run.spray.charges == charges - 1
    assert body.doused, "a patch over a body in its window did not douse it"
    assert [e for e in run.log if e.kind == S.DOUSED]

    for _ in range(R.BODY_FRAMES):
        run.step()
    assert not body.turning, "a doused body turned anyway"


# --- a body under your feet (issue #39) ------------------------------------

def _body_underfoot(facing):
    """A run with a fresh body in the player's room, stood on, facing `facing`.

    The body is made by bleeding somebody out rather than by waiting for the
    authored clock, because four facings' worth of waiting is thousands of
    frames per assertion and none of them are testing the clock.
    """
    run = Session(seed=1, lives=99)
    victim = next(w for w in run.rescue.workers if w.room == run.here)
    victim.blood = 1
    assert _run_until(run, lambda: bool(run.rescue.bodies(run.here)), 500)
    body = run.rescue.bodies(run.here)[0]

    cx, cy = body.cell()
    # Feet on the body's feet cell: the player's two cells are then exactly
    # the body's two, which is what walking onto one in the dark leaves you in.
    run.player.x, run.player.y = cx * CELL, (cy - 1) * CELL
    run.player.facing = facing
    assert run.player.cx == cx and run.player.cy == cy
    return run, body


def test_a_charge_douses_a_body_underfoot_whatever_the_facing():
    """The one place you can find a body without spending light was the one
    place you could not save it from.

    `patch_cells` starts one cell ahead of the player, so a burst never covers
    where they stand. A person is two cells tall, so facing **up** landed the
    patch on the player's own upper cell and the douse worked -- in that one
    facing out of four, with no facing indicator on screen once the torch is
    off. Walking onto a body in the dark is exactly how one is found when the
    death shout gives a direction rather than a position.
    """
    for facing in (sources.UP, sources.DOWN, sources.LEFT, sources.RIGHT):
        run, body = _body_underfoot(facing)
        charges = run.spray.charges
        run.step(Intent(spray=True))
        assert body.doused, f"facing {facing} did not douse a body underfoot"
        assert run.spray.charges == charges - 1
        assert [e for e in run.log if e.kind == S.DOUSED], \
            f"facing {facing} doused without saying so"


def test_dousing_underfoot_lays_no_ground_under_the_player():
    """**The patch is not widened.** The spray is area denial, not a weapon:
    poisoning the cell the player stands in would let them kill the fly that
    is already on them, which is the one thing the spray must never do. The
    body is saved and the ground the player is on is still clean."""
    run, body = _body_underfoot(sources.RIGHT)
    run.step(Intent(spray=True))
    assert body.doused
    for cx, cy in run.player.body_cells():
        assert not run.spray.covers(cx, cy, run.here), \
            "the burst sprayed the player's own cell"


def test_the_patch_ahead_is_unchanged_by_the_underfoot_rule():
    """Everywhere else the burst lands exactly where it always did."""
    run, _ = _body_underfoot(sources.RIGHT)
    cx, cy = run.player.cx, run.player.cy
    run.step(Intent(spray=True))
    laid = {cell for (room, cell) in run.spray.patches if room == run.here}
    assert laid == set(spray.patch_cells(cx, cy, sources.RIGHT))


def test_an_empty_sprayer_douses_nothing_underfoot():
    """It is the charge that douses, not the standing there."""
    run, body = _body_underfoot(sources.DOWN)
    run.spray.charges = 0
    run.step(Intent(spray=True))
    assert not body.doused
    assert not [e for e in run.log if e.kind == S.DOUSED]


def test_a_charge_spent_beside_a_body_still_does_not_douse_it():
    """The fix reaches the body under your feet and no further. Standing one
    cell to the side and firing away from it is a miss, as it always was."""
    run, body = _body_underfoot(sources.LEFT)
    run.player.x -= 3 * CELL          # three cells west, facing further west
    run.step(Intent(spray=True))
    assert not body.doused


def test_a_patch_over_a_nest_kills_what_it_hatches():
    """**Suppression, not destruction.** A hatchling arrives on the nest's own
    cell, which is sprayed ground, so a charge buys exactly the one spawn its
    five seconds cover -- and a nest's life is six of them."""
    run = Session(seed=1, lives=99)
    assert _run_until(run, lambda: bool(run.rescue.nests(run.here)), 40000)
    nest = run.rescue.nests(run.here)[0]
    cx, cy = nest.cell()
    run.spray.patches[(nest.room, (cx, cy))] = R.NEST_SPAWN_EVERY
    before = len(run.swarm.clegs)
    hatched = nest.hatched
    for _ in range(R.NEST_SPAWN_EVERY):
        run.step()
        if nest.hatched > hatched:
            break
    assert nest.hatched > hatched, "the nest never spawned"
    assert len(run.swarm.clegs) <= before, \
        "a hatchling walked out of a sprayed nest alive"


# --- the speaker -----------------------------------------------------------

def test_the_sonar_wins_the_speaker():
    """One beeper, and the fly about to land on you outranks the body twenty
    cells away. The body's tick drops the beat and the player still hears that
    something is wrong."""
    run = Session(seed=1, lives=99)
    both = 0
    for _ in range(20000):
        run.step()
        if run.over is not None:
            break
        assert not (run.click and run.tick), "two voices on one speaker"
        both += 1 if run.ticking is not None else 0
    assert both, "no body ever ticked in the whole run"


def test_the_tick_carries_from_the_room_next_door():
    """Unlike the sonar, which reports only the room you are in -- and this is
    the only reason going back for a body behind you is a decision rather than
    a guess."""
    run = Session(seed=1, lives=99)
    assert _run_until(run, lambda: bool(run.rescue.bodies(scene.FAR)))
    body = run.rescue.bodies(scene.FAR)[0]
    assert run.here == scene.NEAR, "the player wandered into the far room"
    heard = run.rescue.ticking({scene.NEAR, scene.FAR})
    assert heard is body
    assert run.rescue.ticking({scene.NEAR}) is None, \
        "a body two rooms away would have been heard"


def test_a_body_two_rooms_away_would_not_carry():
    """Only the adjacent room. There is no path, no search and no propagation
    -- the same three limits the shout through a doorway is held to."""
    rescue = R.Rescue([(4, 8, 8, 1)])           # room four, blood of one
    for _ in range(R.BLEED_EVERY):
        rescue.tick()
    body = rescue.workers[0]
    assert body.room == 4 and body.ticking
    assert rescue.ticking({0, 1}) is None
    assert rescue.ticking({4}) is body


# --- the budget ------------------------------------------------------------

def test_the_level_budget_is_sized_for_its_worst_plausible_failure():
    """**Not its opening state** -- this is the first mechanic that manufactures
    entities, so the question a level answers is no longer "what did you draw"
    but "what can this become".
    """
    from spikes import building as B
    b = scene.BUILDING
    assert b.population == 6
    assert b.largest_tail == 6, "everybody but the one who made the nest"
    assert b.worst_case() == B.cost(clegs=6 + R.NEST_BROOD, people=7, nests=1)
    assert b.worst_case() > B.cost(clegs=6, people=7), \
        "the count did not grow when nests arrived"


def test_the_valve_holds_a_spawn_rather_than_dropping_it():
    """**The budget's only guarantee** now that the game manufactures entities.
    A nest over the ceiling delays its brood and burns out on time regardless.
    """
    run = Session(seed=1, lives=99)
    assert _run_until(run, lambda: run.valve_holds > 0, 40000), \
        "the valve never fired in a run that loses everybody"
    held = [e for e in run.log if e.kind == S.VALVE_HELD]
    nest = run.rescue.workers[held[0].who]
    assert nest.owed > 0, "the valve dropped the spawn instead of holding it"


# --- the valve counts what the port pays (issue #34) ------------------------

def _drawn(run) -> int:
    """What the port would have to draw this frame, in the room on screen."""
    from spikes import building as B
    here = run.here
    people = 1 + sum(1 for w in run.rescue.workers
                     if w.room == here and w.alive)
    return B.cost(clegs=len(run.places[here].swarm.clegs), people=people)


def test_the_budget_is_counted_in_t_states_not_cleg_equivalents():
    """**A ceiling denominated in one entity's cost moves whenever that
    entity's sprite format moves**, and it has now done so once: eighteen
    Cleg-equivalents was the pixel-positioned figure, and cell-aligned Clegs
    halved a fly. *Nests* wrote down that trap and then fell into it.

    The figures are quoted from *The 48K cycle budget* rather than re-derived,
    so there is one place to change them when the port measures a real routine.
    """
    from spikes import building as B
    assert B.ENTITY_CEILING == 32832
    assert B.PERSON_COST == 2902
    assert B.CLEG_COST == 830
    assert B.CLEG_COST * 2 < 1654 * 2, "a cell-aligned fly is not the cheap one"
    # A body and a nest do not move, so they are drawn from remembered ground
    # and belong to the frame's dirty-cell accounting rather than to this bill.
    assert B.FIXTURE_COST == 0


def test_the_valve_never_fires_while_the_room_is_inside_the_ceiling():
    """The acceptance criterion of #34, and the thing #33 got wrong: it held
    spawns with the room at 27 to 61 per cent of the real budget."""
    from spikes import building as B
    run = Session(seed=1, lives=99)
    for _ in range(20000):
        run.step()
        if run.over is not None:
            break
        if any(e.kind == S.VALVE_HELD for e in run.frame_events):
            held = [e for e in run.frame_events if e.kind == S.VALVE_HELD][0]
            room = run.rescue.workers[held.who].room
            assert run._load(room) + B.CLEG_COST > B.ENTITY_CEILING, \
                "the valve refused a spawn the port could have drawn"


def test_a_brood_lands_where_the_room_can_hold_it():
    """**A busy room delays a brood; it never cancels one** -- and a room that
    is not busy does not delay it either, which is what #33 could not manage.

    Nine of a Statue's thirty-six spawns landed against the old ceiling. The
    number is asked of the mechanic rather than of a bot here: a nest in a room
    with space places all six.
    """
    run = Session(seed=1, lives=99)
    assert _run_until(run, lambda: bool(run.rescue.nests()), 40000)
    nest = run.rescue.nests()[0]
    while nest.nesting and run.over is None:
        run.step()
    assert nest.hatched >= R.NEST_BROOD - 1, \
        f"the first nest of the run placed {nest.hatched} of {R.NEST_BROOD}"


def test_no_frame_asks_the_port_to_draw_more_than_it_can():
    """The guarantee the valve exists to be, measured rather than asserted.

    It counts the **building's** flies against a room's people, and that is why
    this holds: counting only the room's lets a spawn through into a quiet room
    that the swarm then walks into. Measured, that reading reaches 44 flies and
    87% of the ceiling -- under it by luck. This one caps at 36 and 74%.
    """
    from spikes import bots, building as B
    for name in ("statue", "wanderer", "listener"):
        for seed in (1, 2, 3):
            bot, run = bots.make(name, seed=seed), Session(seed=seed)
            peak = 0
            while run.over is None and run.frame < 20000:
                run.step(bot.intent(run))
                peak = max(peak, _drawn(run))
            assert peak <= B.ENTITY_CEILING, \
                f"{name} seed {seed} peaked at {peak} of {B.ENTITY_CEILING}"


def test_no_run_holds_more_fixtures_than_the_bound_allows():
    """**Watched rather than asserted** (issue #36). The last time this number
    was wanted it was a comment quoting twenty runs, and the answer was twice
    what the comment said -- so it is a number the report emits now, and the
    bound is the thing it is checked against.
    """
    from spikes import bots, report
    bound = scene.BUILDING.most_fixtures
    peak = 0
    for name in ("statue", "wanderer", "listener"):
        for seed in (1, 2, 3):
            bot, run = bots.make(name, seed=seed), Session(seed=seed)
            while run.over is None and run.frame < 20000:
                run.step(bot.intent(run))
            got = report.metrics(run)["most_fixtures_at_once"]
            assert got <= bound, f"{name} seed {seed} held {got} of {bound}"
            peak = max(peak, got)
    assert peak >= 3, "no run held enough fixtures to be testing anything"


def test_the_worst_case_maximises_over_the_dead_rather_than_assuming_one():
    """**Dead and following are the same people**, so the two cannot both be at
    their maximum: every fixture on the floor is a person not in the line.

    Today the worst split is one death, because a body is free and a follower is
    not -- so the sum lands exactly where the hand-written version put it. The
    point of maximising is that the day `FIXTURE_COST` stops being zero, the
    worst case moves on its own instead of waiting for somebody to remember.
    """
    from spikes import building as B
    b = scene.BUILDING
    assert b.worst_case() == B.cost(
        clegs=b.population + R.NEST_BROOD, people=1 + b.largest_tail,
        fixtures=1), "the worst split is not one death"
    # ...and it is genuinely a maximum, not the first thing tried.
    for dead in range(1, b.roster + 1):
        assert b.worst_case() >= B.cost(
            clegs=b.population + R.NEST_BROOD,
            people=1 + b.roster - dead, fixtures=dead)
