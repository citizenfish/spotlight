"""Fourteen moments: a flash, a pause, and a sound id nothing plays yet.

Issue #52, from *Art Direction* section 8. About twenty-five kinds of thing
happen in a run and the screen mentioned none of them; fourteen of them get a
beat here, and **none of them makes a noise** -- the ids are fixed so that slice
F writes a voice rather than a table.

What this file is really guarding is the three ways this slice could have broken
the project rather than the game:

* **a pause reaching `Session`**, which would move every event log in the
  project by however long the game paused;
* **a new event kind reaching the log**, which is the same fault by another
  route -- `M_SPRAY` is raised from the call site precisely because there is no
  `SPRAY_FIRED` and this slice must not invent one;
* **a flash implemented as a light**, which would show up as a moved repaint
  figure and would hand the player a light that costs nothing.

Each of those has a test below with the fault named in it.
"""

import pygame
import pytest

from spikes import bots, building as building_mod, moments as M
from spikes import rescue as R, sources
from spikes import session as S, spike1, spike_driver
from spikes.session import Intent, Session
from spotlight.core.constants import CELL
from spotlight.core.screen import Screen, unpack_attr


# --- getting a moment to happen --------------------------------------------

def _raised(run, name: str) -> list:
    """The cells each raise of `name` carried, this frame."""
    return [cells for raised, cells in run.moments.raised if raised == name]


def _settle(run, frames: int = 20):
    """Enough ordinary frames that the room has been lit once and remembered.

    A moment tests the light **when it is raised**, and the field is built at
    the end of a step -- so on frame one nothing anywhere is lit and every
    flash in this file would be suppressed for the right reason at the wrong
    moment. The opening flash lights the room on entry; twenty frames later it
    is still remembered.
    """
    for _ in range(frames):
        run.step()
    return run


def _until_event(kind: str, bot: str = "listener", seed: int = 1,
                 limit: int = 30000, **kw) -> Session:
    """A run stopped on the frame `kind` was first logged.

    `run.moments.raised` is therefore what that frame raised, which is what
    "raised exactly once, on the frame its event fires" is asked of.
    """
    run = Session(seed=seed, **kw)
    playing = bots.make(bot, seed=seed, light=True)
    while run.over is None and run.frame < limit:
        run.step(playing.intent(run))
        if any(e.kind == kind for e in run.frame_events):
            return run
    raise AssertionError(f"no {kind} in {limit} frames of {bot} on seed {seed}")


def _stand_on(run, thing) -> None:
    """Put the player exactly where something else is standing.

    The same convenience the doorway tests and the gallery use. It moves the
    player and nothing else, so every rule about arriving somewhere still runs.
    """
    run.player.x, run.player.y = thing.x, thing.y


def _cross_a_doorway(run):
    """Walk the player through the first doorway out of the room they are in.

    Stood in the doorway and then *walked*, which is the same convenience the
    doorway tests and the gallery use: teleporting `here` would be one line and
    would be a crossing the game never made. No bot in the stable crosses a
    doorway -- the crosser walks a route inside one room -- so this is the only
    way to reach the event.
    """
    door = run.place.room.doorways[0]
    run.player.x = door.column * CELL
    run.player.y = (door.middle - 1) * CELL
    facing = 1 if door.side == building_mod.EAST else -1
    for _ in range(32):
        run.step(Intent(dx=facing))
        if [e for e in run.frame_events if e.kind == S.CROSSED]:
            return run
    raise AssertionError("the player would not walk through the doorway")


def _body_under_the_player(seed: int = 1):
    """A run with a fresh body, and the player standing on it in its room.

    Standing on it is what makes the body's cell lit -- the personal glow is
    enough, and a moment may only flash a cell the player is already being
    shown. Without it the nest's own turn is a moment over dark ground, which
    is the rule working and a useless test of the cells.

    Blood is set out of reach because the point of the fixture is the body's
    clock: a death would respawn the player at the entrance half way through
    and quietly move them off the cell being tested.
    """
    run = _until_event(S.WORKER_DIED, seed=seed, lives=99, blood=64000)
    body = run.rescue.bodies()[0]
    # The room the body is in, because a body two rooms away is not being
    # shown to anybody. This is the one teleport in the file and it moves the
    # camera, not the rules.
    run.here = body.room
    cx, cy = body.cell()
    run.player.x, run.player.y = cx * CELL, (cy - 1) * CELL
    run.step()
    return run, body


def _free_somebody(run):
    """Free the first waiting worker by walking onto them. Returns them."""
    worker = run.rescue.alive_waiting(run.here)[0]
    _stand_on(run, worker)
    run.step()
    assert [e for e in run.frame_events if e.kind == S.FREED], "nobody freed"
    return worker


# --- the table --------------------------------------------------------------

def test_there_are_fourteen_moments_and_these_are_they():
    """The table, pinned. A fifteenth is a design decision and not a tidy-up.

    Each row is (moment, sound id, priority, flash frames, pause frames), which
    is *Art Direction*'s table with the flash column dropped -- what flashes is
    tested one moment at a time below, because it is the only column that
    cannot be checked without playing the game.
    """
    assert [(m.name, m.sound, m.priority, m.frames, m.pause)
            for m in M.MOMENTS.values()] == [
        ("freed",       M.SFX_FREED,       0, 16,  0),
        ("delivered",   M.SFX_DELIVERED,   0, 32,  0),
        ("bite",        M.SFX_BITE,        0,  0,  0),
        ("worker_died", M.SFX_WORKER_DIED, 1,  0,  0),
        ("player_died", M.SFX_PLAYER_DIED, 1, 16, 25),
        ("torch_out",   M.SFX_TORCH_OUT,   0, 96,  0),
        ("door",        M.SFX_DOOR,        0,  0,  0),
        ("spray",       M.SFX_SPRAY,       0,  0,  0),
        ("spray_kill",  M.SFX_SPRAY_KILL,  0,  8,  0),
        ("nest_turned", M.SFX_NEST_TURNED, 1, 32,  0),
        ("hatched",     M.SFX_HATCHED,     0, 100, 0),
        ("game_over",   M.SFX_GAME_OVER,   1,  0, 50),
        ("all_out",     M.SFX_ALL_OUT,     1,  0, 50),
        ("pickup",      M.SFX_PICKUP,      0, 32,  0),
    ]


def test_the_fourteen_sound_ids_are_the_list_the_next_slice_gets():
    """No more, no fewer, no renames.

    Slice F is entitled to assume this list is the list -- the whole point of
    fixing the ids before the waveforms is that the events could be raised
    before there was a voice. A rename here is a silent breakage there, so it
    is a failing test here instead.
    """
    assert len(M.SOUND_NAMES) == 14
    assert M.SOUND_NAMES == (
        "SFX_FREED", "SFX_DELIVERED", "SFX_BITE", "SFX_WORKER_DIED",
        "SFX_PLAYER_DIED", "SFX_TORCH_OUT", "SFX_DOOR", "SFX_SPRAY",
        "SFX_SPRAY_KILL", "SFX_NEST_TURNED", "SFX_HATCHED", "SFX_GAME_OVER",
        "SFX_ALL_OUT", "SFX_PICKUP")
    # Every name is a real constant, and its value is its index -- a sound id
    # is one byte and an index into the table slice F will write.
    for wanted, name in enumerate(M.SOUND_NAMES):
        assert getattr(M, name) == wanted
    # ...and every moment carries one of them, each exactly once.
    assert sorted(m.sound for m in M.MOMENTS.values()) == list(range(14))


def test_the_voice_reads_the_sound_ids_and_the_seam_is_closed():
    """The seam slice D left open, closed by slice F (issue #54).

    This test used to say the opposite: *nothing reads a sound id yet, and that
    is the seam* -- the ids and the priorities were argued next to the events
    they belong to, before there was a waveform to argue them next to, so the
    events could be raised while the game was still silent. `sounds.Voice` now
    reads exactly this list, and the ids and priorities it was handed are the
    ones that were written down here a slice earlier and have not moved.
    """
    from spikes import sounds

    run = _settle(Session(seed=1))
    _free_somebody(run)
    assert run.moments.sounds() == [(M.SFX_FREED, 0)]
    # Raised on this frame, and the speaker takes it: the moment is the only
    # thing asking, so nothing is in its way.
    assert run.voice.kind == sounds.EFFECT and run.voice.sound == M.SFX_FREED


# --- one test per moment ----------------------------------------------------

def test_freed_flashes_the_two_cells_they_were_standing_in():
    run = _settle(Session(seed=1))
    worker = _free_somebody(run)
    # `Worker.cells` is the figure's whole box: the design says "the worker's
    # two cells" and means the cells the person occupies, which is two when
    # they are column-aligned and four when they straddle a column boundary.
    assert _raised(run, M.M_FREED) == [tuple(sorted(worker.cells()))]
    assert run.moments.cells(run.here) == worker.cells()


def test_a_flash_marks_where_it_happened_and_follows_nobody():
    """The freed worker walks away and the flash stays where they were freed.

    That is what a moment *is*, and it is also why it costs nothing per frame:
    a fixed list of cells captured once, not a thing that has to be recomputed
    because somebody moved.
    """
    run = _settle(Session(seed=1))
    _free_somebody(run)
    where = run.moments.cells(run.here)
    for _ in range(15):
        run.step(Intent(dx=1))
    assert run.player.occupied_cells() != where, "nobody moved off the cells"
    assert run.moments.cells(run.here) == where


def test_delivered_flashes_the_door_and_not_the_person():
    """What the player is looking at when somebody is banked is the way out."""
    run = _settle(Session(seed=1))
    _free_somebody(run)
    ex, ey = run.place.room.exit_cell()
    run.player.x, run.player.y = ex * CELL, ey * CELL
    run.step()
    assert [e for e in run.frame_events if e.kind == S.DELIVERED]
    assert _raised(run, M.M_DELIVERED) == [((ex, ey), (ex, ey + 1))]


def test_a_bite_is_raised_once_and_flashes_nothing():
    """Bites are frequent, and a bar that alerts constantly is furniture.

    Not an oversight and not to be tidied up: the design argues it, and the
    bite is a sound.
    """
    run = _until_event(S.BITTEN)
    assert len(_raised(run, M.M_BITE)) == 1
    assert not run.moments.flashes
    assert M.MOMENTS[M.M_BITE].frames == 0


def test_a_workers_death_has_no_flash_and_must_not_gain_one():
    """They are usually not on lit ground, so there would be nothing to flash,
    and the death already has its own channel in the shout."""
    run = _until_event(S.WORKER_DIED, seed=1, lives=99)
    assert len(_raised(run, M.M_WORKER_DIED)) == 1
    assert not run.moments.flashes


def test_the_player_dying_flashes_where_they_died_and_asks_for_a_pause():
    """Raised **before** the respawn, or it would flash the entrance instead."""
    run = _settle(Session(seed=1))
    # Away from the entrance, so that the respawn is a move and the test can
    # tell the cells they died in from the cells they came back to.
    for _ in range(40):
        run.step(Intent(dx=1))
    where = tuple(sorted(run.player.occupied_cells()))
    run.blood = 0
    run.step()
    assert [e for e in run.frame_events if e.kind == S.LIFE_LOST]
    assert _raised(run, M.M_PLAYER_DIED) == [where]
    assert run.player.occupied_cells() != set(where), "no respawn happened"
    assert run.moments.pause == 25


def test_the_torch_going_out_alerts_the_bar_and_its_flag():
    """Two regions, because the readout is *how much light and whether it is
    burning* and the flag is the half that says it has gone out.

    It replaced a bare `panel.alert("light")`, which flashed the bar only.
    """
    run = _settle(Session(seed=1))
    run.step(Intent(torch=True))
    run.cone.power = 1
    run.step()
    assert [e for e in run.frame_events if e.kind == S.TORCH_OUT]
    assert _raised(run, M.M_TORCH_OUT) == [()]
    assert run.panel.flashing("light") and run.panel.flashing("lit")
    # The strip is where this flash lives, so nothing in the play area moved.
    assert not run.moments.flashes


def test_crossing_a_doorway_needs_no_flash():
    """The screen has just flicked to a different room, which is already the
    largest visual event in the game."""
    run = _cross_a_doorway(_settle(Session(seed=1)))
    assert len(_raised(run, M.M_DOOR)) == 1
    assert not run.moments.flashes


def test_firing_the_spray_raises_a_moment_and_no_event():
    """**The trap this slice had to avoid.** There is no `SPRAY_FIRED` in the
    run log and there must not be one: a new kind in the log is a changed log,
    and every acceptance criterion in this round rests on the log not moving.
    """
    run = _settle(Session(seed=1))
    before = len(run.log)
    run.step(Intent(spray=True))
    assert _raised(run, M.M_SPRAY) == [()]
    assert len(run.log) == before, "firing the spray put something in the log"
    assert not hasattr(S, "SPRAY_FIRED")


def test_a_spray_kill_flashes_the_cell_the_fly_died_in():
    run = _settle(Session(seed=1))
    fly = run.place.swarm.clegs[0]
    run.player.x, run.player.y = (fly.cx - 2) * CELL, (fly.cy - 1) * CELL
    run.player.facing = sources.RIGHT
    run.step(Intent(spray=True, torch=True))
    for _ in range(250):
        if [e for e in run.frame_events if e.kind == S.SPRAY_KILL]:
            break
        run.step()
    else:
        pytest.skip("no fly walked into the patch")
    cells = _raised(run, M.M_SPRAY_KILL)
    assert len(cells) == 1 and cells[0], "the kill flashed nowhere"
    assert set(cells[0]) <= run.moments.cells(run.here)


def test_a_body_turning_flashes_the_nests_cell():
    run, body = _body_under_the_player()
    where = body.cell()
    while body.age < R.BODY_FRAMES:
        run.step()
    assert [e for e in run.frame_events if e.kind == S.NEST_TURNED]
    assert _raised(run, M.M_NEST_TURNED) == [(where,)]


def test_a_hatch_raises_its_moment_and_starts_no_new_flash():
    """The flash was already running: it is a tell, not a report.

    A hatch is announced two seconds *before* it happens, so it cannot be
    driven by the `HATCHED` event -- see `hatch_is_near`. The moment is still
    raised, because it still has a sound.
    """
    run, body = _body_under_the_player()
    where = body.cell()
    # The tell runs for the hundred frames before the spawn, and a nest is owed
    # its first the instant it turns -- so the flash is already on when the
    # body is still a body.
    while body.age < R.BODY_FRAMES:
        run.step()
        if body.age >= R.BODY_FRAMES - M.TELL_FRAMES:
            assert where in run.flash_cells()
    assert [e for e in run.frame_events if e.kind == S.HATCHED]
    assert _raised(run, M.M_HATCHED) == [(where,)]
    assert M.MOMENTS[M.M_HATCHED].state_flash
    # ...and the event started no flash of its own. The only flash running is
    # the thirty-two frames the *turn* raised on the same frame; the tell is
    # the nest's state, which stops when the spawn lands rather than a hundred
    # frames after it.
    assert [f.frames for f in run.moments.flashes] == [
        M.MOMENTS[M.M_NEST_TURNED].frames]


def test_the_two_endings_pause_and_flash_nothing():
    for reason, moment in ((S.NO_LIVES, M.M_GAME_OVER),
                           (S.ALL_OUT, M.M_ALL_OUT)):
        run = _settle(Session(seed=1))
        run.finish(reason)
        assert _raised(run, moment) == [()]
        assert run.moments.pause == 50
        assert not run.moments.flashes


def test_picking_up_a_spotlight_alerts_the_bar_underneath_the_player():
    """The one readout whose *value* changes without the player asking, in the
    same instant as something they did ask for.

    `spotlight_swaps` is 0 in every run any bot has ever made, so this is set
    up the way the gallery sets it up: the game's own swap rule, fired by the
    game's own code.
    """
    run = _settle(Session(seed=1))
    light = [l for l in run.kit.floor if l.room == run.here][0]
    run.player.x = light.cx * CELL
    run.player.y = (light.cy + 1) * CELL - 16
    run.step(Intent(torch=True))
    assert [e for e in run.frame_events if e.kind == S.SWAPPED]
    assert _raised(run, M.M_PICKUP) == [()]
    assert run.panel.flashing("light")
    assert not run.panel.flashing("lit"), "the bar, not the flag"


# --- the two rules ----------------------------------------------------------

def test_a_moment_over_a_dark_cell_raises_no_flash():
    """Flashing something in the dark is a light that costs nothing, and this
    game does not have one of those.

    On frame zero nothing has been lit at all, which is the cheapest dark cell
    to get hold of. The moment is still raised: it has a sound, it simply has
    nothing to flash.
    """
    run = Session(seed=1)
    run._moment(M.M_FREED, [(5, 5), (5, 6)])
    assert run.moments.flashes == []
    assert _raised(run, M.M_FREED) == [()]
    assert run.moments.sounds() == [(M.SFX_FREED, 0)]


def test_a_moment_flashes_only_the_lit_half_of_what_it_is_given():
    """Cell by cell, not all or nothing."""
    # Long enough that the opening flash has faded out of the room's memory,
    # so that there is a dark cell to be had at all.
    run = _settle(Session(seed=1), 400)
    lit = run.player.cx, run.player.cy
    assert run.field.level_at(*lit), "the player's own glow went out"
    dark = [(cx, cy) for cy in range(20) for cx in range(30)
            if run.field.level_at(cx, cy) == 0][0]
    run._moment(M.M_FREED, [lit, dark])
    assert run.moments.cells(run.here) == {lit}


def test_a_flash_sets_bit_seven_and_changes_nothing_else():
    """Same ink, same paper, same bright.

    A flash is the hardware FLASH bit and it is not a light: the cell's colour
    is chosen by exactly what chose it before -- light sets the level, contents
    set the hue -- and the moment sets one bit on top.
    """
    run = _settle(Session(seed=1))
    _free_somebody(run)
    flashing = run.flash_cells()
    assert flashing, "nothing was flashing, so this proves nothing"

    with_flash, without = Screen(), Screen()
    run.draw(with_flash)
    run.moments.flashes = []
    run.draw(without)

    # The play area only: the strip is painted once and then only where it
    # changes, so a second draw onto a second screen leaves it blank there --
    # which is a fact about the panel and nothing to do with a flash.
    play = 32 * 22
    for i, (was, now) in enumerate(zip(without.attrs[:play],
                                       with_flash.attrs[:play])):
        cell = (i % 32, i // 32)
        if cell in flashing:
            assert now == was | M.FLASH_BIT
            ink, paper, bright, flash = unpack_attr(now)
            assert (ink, paper, bright) == unpack_attr(was)[:3]
            assert flash and not unpack_attr(was)[3]
        else:
            assert now == was, f"a flash reached {cell}"


def test_raising_a_moment_never_touches_the_light_field():
    """**The criterion the repaint figures make mechanically checkable.**

    If a moment ever moved the count of cells changing light level, it has been
    implemented as a light and it is wrong. Here that is asserted directly: the
    charge, the displayed levels and the repaint histogram are all untouched by
    raising every flashing moment in the table over the player's own cells.
    """
    run = _settle(Session(seed=1, metrics=True))
    charge = bytes(run.field.charge)
    levels = run.field.levels()
    counted = run.repaint.stats()

    cells = sorted(run.player.occupied_cells())
    for name, moment in M.MOMENTS.items():
        if moment.frames and not moment.state_flash:
            run._moment(name, cells)
    assert run.moments.flashes, "nothing was raised, so this proves nothing"

    assert bytes(run.field.charge) == charge
    assert run.field.levels() == levels
    assert run.repaint.stats() == counted


def test_only_endings_and_deaths_may_stop_the_clock():
    """A pause during play is a change to the pace of the game, which this
    round forbids. A bite may not pause; the last life going may."""
    pausing = {name for name, m in M.MOMENTS.items() if m.pause}
    assert pausing == {M.M_PLAYER_DIED, M.M_GAME_OVER, M.M_ALL_OUT}


# --- the pause is the shell's ----------------------------------------------

def test_a_pause_does_not_reach_the_session():
    """**The fault this slice could most easily have introduced.**

    If the session honoured a pause, its frame counter would go on advancing
    through it, every event after it would carry a different frame number, and
    every run log in the project would move. So the shell holds and the session
    is simply not stepped: `run.frame` does not move and `run.log` does not
    grow.
    """
    shell = spike1.Shell(Screen())
    shell.key(pygame.K_j)
    run = shell.run
    for _ in range(20):
        shell.frame()
    run.blood = 0
    shell.frame()
    assert shell.held == 25, "the death did not ask the shell to hold"

    frame, log = run.frame, list(run.log)
    for held in range(25, 0, -1):
        assert shell.held == held
        shell.frame(dx=1)
    assert shell.held == 0
    assert run.frame == frame, "the session was stepped during a pause"
    assert run.log == log, "the log moved during a pause"

    shell.frame()
    assert run.frame == frame + 1, "play did not resume"


def test_the_pause_holds_the_frame_the_moment_happened_on():
    """It holds the ending screen *off*, which is the whole of what it is for:
    a beat on the last frame of play before the screen that explains it."""
    shell = spike1.Shell(Screen())
    shell.key(pygame.K_j)
    for _ in range(20):
        shell.frame()
    shell.run.finish(S.NO_LIVES)
    shell.frame()
    assert shell.state == spike1.PLAY and shell.held == 50
    for _ in range(49):
        shell.frame()
    assert shell.state == spike1.PLAY, "the ending screen came up early"
    shell.frame()
    assert shell.state == spike1.ENDED


def test_a_pause_is_taken_once_and_the_session_never_takes_it():
    run = _settle(Session(seed=1))
    run.finish(S.NO_LIVES)
    assert run.moments.take_pause() == 50
    assert run.moments.take_pause() == 0
    # And stepping the session neither takes it nor honours it.
    run = _settle(Session(seed=1))
    run.blood = 0
    run.step()
    frame = run.frame
    run.step()
    assert run.frame == frame + 1 and run.moments.pause == 25


def test_two_pauses_on_one_frame_are_one_beat():
    """The last life going raises a death and an ending on the same frame. Two
    holds back to back would read as the game hanging twice."""
    run = _settle(Session(seed=1))
    run._moment(M.M_PLAYER_DIED)
    run._moment(M.M_GAME_OVER)
    assert run.moments.pause == 50


def test_the_headless_driver_ignores_pauses_entirely():
    """A hold in the driver would mean the same `--frames` bought fewer stepped
    frames, and the tail of every event log in the project would shift.

    Two things are asserted: the run stepped every frame it was given, and the
    pause it is owed is still sitting there untaken.
    """
    run = spike_driver.drive(bots.make("listener", seed=1, light=True),
                             seed=1, frames=600)
    assert run.frame == 600, "the driver lost frames to a pause"
    assert run.over == S.FRAME_LIMIT
    # `finish` raised `M_GAME_OVER`, which asks for fifty frames. Nobody took
    # them, which is the whole point.
    assert run.moments.pause == 50


def test_no_moment_adds_a_kind_to_the_run_log():
    """Every kind a driven run logs is one the session declared before this
    slice existed. A moment is not an event and must never become one."""
    kinds = {value for name, value in vars(S).items()
             if name.isupper() and isinstance(value, str)}
    run = spike_driver.drive(bots.make("listener", seed=1, light=True),
                             seed=1, frames=2000)
    logged = {e.kind for e in run.log}
    assert logged <= kinds
    assert not logged & set(M.MOMENTS) - kinds


# --- the two flashes that are states ---------------------------------------

def test_a_body_flashes_for_its_whole_window():
    """The visual half of the tick, which had never been built.

    Same predicate as the tick, deliberately: a body you can hear is a body you
    can see if you are looking at it, and two predicates meant to agree would
    eventually not.
    """
    body = R.Worker(80, 48, blood=1)
    for _ in range(R.BLEED_EVERY):
        body.tick()
    assert body.state == R.DEAD
    for age in range(R.BODY_FRAMES):
        assert M.body_is_flashing(body) is body.ticking
        assert M.body_is_flashing(body), f"a body stopped flashing at {age}"
        body.tick()
    assert not M.body_is_flashing(body), "a nest is not a body"


def test_a_doused_body_stops_flashing():
    """There is nothing left to decide about it, which is why it stops ticking
    too."""
    body = R.Worker(80, 48, blood=1)
    for _ in range(R.BLEED_EVERY):
        body.tick()
    assert M.body_is_flashing(body)
    body.douse()
    assert not M.body_is_flashing(body)


def test_a_nest_tells_you_two_seconds_before_it_places_one():
    """A nest earns a spawn every 250 frames, so the tell is arithmetic on the
    clock it already keeps and nothing new is stored."""
    # Freshly turned: it is owed its first straight away.
    assert M.hatch_is_near(age=0, hatched=0, owed=1)
    # Placed, and the next one is five seconds off.
    assert not M.hatch_is_near(age=1, hatched=1, owed=0)
    assert not M.hatch_is_near(age=149, hatched=1, owed=0)
    # Two seconds out, and on until it lands.
    assert M.hatch_is_near(age=150, hatched=1, owed=0)
    assert M.hatch_is_near(age=249, hatched=1, owed=0)
    assert M.hatch_is_near(age=250, hatched=1, owed=1)
    # ...and a nest with its whole brood placed has nothing left to tell.
    assert not M.hatch_is_near(age=R.NEST_FRAMES, hatched=R.NEST_BROOD, owed=0)


def test_a_spawn_the_valve_holds_leaves_the_nest_flashing():
    """True rather than a bug: it is still owed one. The valve delays a brood
    and can never cancel one, so the tell stays on until the spawn lands."""
    assert M.hatch_is_near(age=600, hatched=1, owed=2)


def test_the_tell_is_a_hundred_frames_and_so_is_the_moment():
    """Same number because it is the same flash."""
    assert M.TELL_FRAMES == 100
    assert M.MOMENTS[M.M_HATCHED].frames == M.TELL_FRAMES


def test_a_body_on_lit_ground_wears_the_flash_bit():
    """The state, on a drawn frame. It fires only where the player can already
    see the ground, so it hands over nothing a lit floor was not handing over
    anyway."""
    run = _until_event(S.WORKER_DIED, seed=1, lives=99)
    body = run.rescue.bodies()[0]
    run.here = body.room
    cx, cy = body.cell()
    # Stand beside them with the torch on, so the ground is lit and the body is
    # inside the light rather than merely remembered.
    run.player.x, run.player.y = (cx + 1) * CELL, (cy - 1) * CELL
    run.step(Intent(torch=True))
    run.step()
    assert body.ticking, "the body's window closed before the picture"
    assert (cx, cy) in run.flash_cells()

    screen = Screen()
    run.draw(screen)
    assert screen.get_attr(cx, cy) & M.FLASH_BIT


def test_a_body_in_the_dark_flashes_nothing():
    """A flash is not a light, so a body nobody can see stays invisible."""
    run = _until_event(S.WORKER_DIED, seed=1, lives=99)
    body = run.rescue.bodies()[0]
    run.here = body.room
    for place in run.places:
        place.field.charge[:] = bytes(len(place.field.charge))
        place.field.begin()
        place.field.commit()
    assert body.cell() not in run.flash_cells()
