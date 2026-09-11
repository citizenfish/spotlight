"""The mains surge: the whole building, for a second, once a minute.

Issue #53, from *Art Direction* section 9 and *Light and Darkness#The mains*.
This is the beat the whole memorisation premise rests on and it had never been
built.

What this file is really guarding is the four ways the slice could have broken
the project rather than the game, and each has a test below with the fault
named in it:

* **the surge's seed derived anywhere but the end of the chain**, which would
  shift the Cleg, beam and brood seeds, change what every fly in the building
  does, and move every event log in the project;
* **a surge implemented as a light**, which would lure the swarm to a light
  that is everywhere, and would show up as a moved repaint figure;
* **a freeze inside the session** rather than frames the shell declines to
  step, which is the same fault by another route: the frame counter would
  advance through it and every event after it would be stamped differently;
* **a surge dropped rather than deferred** when it comes due mid-crossing,
  which is a beat the player simply never gets and which nothing else would
  notice.
"""

import pygame
import pytest

from spikes import (
    bots, clegs as clegs_mod, lighting, report, scene, session as S, sources,
    spike1, spike_driver, surge,
)
from spikes.layout import PLAY_ROWS, STRIP_TOP
from spikes.session import Intent, Session
from spotlight.core.constants import (
    BLACK, CELL, COLS, GREEN, MAGENTA, RED, SCREEN_W, WHITE, YELLOW,
)
from spotlight.core.screen import Screen, unpack_attr


def _chain(seed: int) -> tuple:
    """The run's whole seed chain, in the order `Session` derives it."""
    cleg = sources.xorshift16(seed)
    beam = sources.xorshift16(cleg)
    brood = sources.xorshift16(beam)
    return cleg, beam, brood, sources.xorshift16(brood)


#: Tests that need a surge without playing a minute of game set `run.surge.due`
#: forward, which pokes the schedule and nothing else: a surge decides nothing,
#: so making one happen sooner cannot change a run.

# --- the seed is the last link in the chain ---------------------------------

@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_the_cleg_beam_and_brood_seeds_are_untouched(seed):
    """**The criterion that proves the logs cannot have moved.**

    Every random thing in a run is derived from the one seed by a chain of
    `xorshift16` calls, and the surge joins the *end* of it. Deriving it
    anywhere else would shift every seed downstream and change what every fly
    in the building does -- so "the event log is byte-identical" would be
    something discovered rather than designed. This asserts the three seeds
    that were already there are the three links they always were.
    """
    cleg, beam, brood, _surge = _chain(seed)
    run = Session(seed=seed)
    first = run.places[0].swarm.clegs[0]
    assert first._seed == clegs_mod.Cleg(0, 0, seed=cleg)._seed
    assert run.searchlights[0]._seed == beam
    assert run._brood_seed == brood


def test_the_surge_seed_is_the_fourth_link_and_the_numbers_are_pinned():
    """Pinned as integers, so inserting a link anywhere fails loudly.

    A future slice that wants a random stream of its own has to add it after
    this one, and this test is what tells whoever writes it. The first due is
    checked as well as the seed, because the seed is only half of the
    derivation -- the draw off it is the other half.
    """
    assert _chain(1) == (33153, 24609, 59801, 11787)
    run = Session(seed=1)
    expected = surge.FIRST_MIN + \
        sources.xorshift16(_chain(1)[3]) % surge.INTERVAL_SPREAD
    assert run.surge.due == expected == 2964


def test_a_run_with_no_surge_would_still_be_the_same_run():
    """The strongest form of the byte-identical claim that a test can make.

    A surge steps nothing, so it can decide nothing: a run played with the
    schedule disabled entirely logs exactly what the same seed logs with it
    running. This is the whole of why the round's baseline logs did not move.
    """
    def log_of(run):
        return [(e.frame, e.kind, e.who, e.count, e.room) for e in run.log]

    played = spike_driver.drive(bots.make("listener", seed=3), seed=3,
                                frames=4000)
    quiet = Session(seed=3)
    # Due past the end of the run, which is the only way to have a run of this
    # length with no surge in it at all.
    quiet.surge.due = 1 << 30
    playing = bots.make("listener", seed=3)
    while quiet.over is None and quiet.frame < 4000:
        quiet.step(playing.intent(quiet))
    if quiet.over is None:
        quiet.finish(S.FRAME_LIMIT)

    assert played.surge.count > 0, "no surge fired, so this proves nothing"
    assert quiet.surge.count == 0
    assert log_of(played) == log_of(quiet)


# --- when it fires ----------------------------------------------------------

@pytest.mark.parametrize("seed", range(1, 41))
def test_the_interval_is_forty_to_seventy_seconds_and_the_first_is_not_early(
        seed):
    """The design's numbers, over a sweep of seeds rather than one.

    Seeded rather than fixed so that a sweep of runs samples the distribution
    instead of the same surge -- the lesson the searchlight's entry station
    taught the hard way. So the sweep is the test: any one seed proves nothing
    about a distribution.
    """
    schedule = surge.Schedule(_chain(seed)[3])
    assert schedule.due >= surge.FIRST_MIN
    last = schedule.due
    for frame in range(surge.FIRST_MIN, 200000):
        if schedule.update(frame):
            gap = schedule.due - frame
            assert surge.INTERVAL_MIN <= gap <= 3500, gap
            last = frame
    assert schedule.count > 50, "not enough surges to say anything"
    assert last > 0


def test_the_spread_is_the_forty_to_seventy_seconds_the_design_asks_for():
    """2,000 to 3,500 frames inclusive, at 50Hz, and both ends reachable."""
    assert surge.INTERVAL_MIN == 2000
    assert surge.INTERVAL_MIN + surge.INTERVAL_SPREAD - 1 == 3500
    seen = {surge.INTERVAL_MIN + surge.Schedule(seed).state
            % surge.INTERVAL_SPREAD for seed in range(1, 5000)}
    assert min(seen) == 2000 and max(seen) == 3500


def test_the_first_surge_can_come_before_the_shortest_interval():
    """1,500 frames is a floor and not a synonym for the interval.

    If the first surge were simply the first interval it would never be earlier
    than 2,000 and the design's "no earlier than 1,500" would be a dead
    sentence. Half a minute matters here: the surge is the game's rhythm, and a
    player who has not met it yet is playing a different game.
    """
    firsts = {surge.Schedule(seed).due for seed in range(1, 2000)}
    assert surge.FIRST_MIN <= min(firsts) < surge.INTERVAL_MIN
    assert max(firsts) < surge.INTERVAL_MIN + surge.INTERVAL_SPREAD


# --- never mid-threshold ----------------------------------------------------

def test_a_surge_due_mid_threshold_is_deferred_and_not_dropped():
    """**The fault nothing else would have noticed.**

    A screen that changes twice in two frames is a glitch, not a beat: the
    player halfway through a doorway is a frame or two from the view flicking
    to the next room. So the due frame stands and the surge fires on the first
    frame the player is wholly in one room. Dropping it instead would cost the
    player a whole beat and would leave no trace anywhere.
    """
    schedule = surge.Schedule(1)
    due = schedule.due
    for frame in range(due, due + 8):
        assert not schedule.update(frame, mid_threshold=True)
        assert schedule.count == 0
    assert schedule.deferred == 8
    assert schedule.update(due + 8), "the surge was dropped rather than held"
    assert schedule.count == 1
    # And the gap that follows is measured from the frame it *fired*, so a
    # deferral does not silently shorten the next one.
    assert schedule.due - (due + 8) >= surge.INTERVAL_MIN


def test_the_player_reads_as_mid_threshold_only_while_crossing():
    """Walked in the real loop, because this is a fact about the doorway.

    True from the frame the sprite first touches the doorway column to the
    frame it has cleared it. **The whole sprite, not its centre**: an 8-wide
    figure overlaps the column for fifteen frames at a pixel a frame, and the
    wider window is the safer one -- what it costs is a surge held back for
    three tenths of a second and what it buys is that no frame of a crossing
    can ever have a plan dropped on it.
    """
    run = Session(seed=1)
    run.player.x = (COLS - 3) * CELL
    run.player.y = (scene.DOOR_ROWS[1] - 1) * CELL
    assert not run._mid_threshold(), "standing in the room read as crossing"
    straddling = 0
    for _ in range(32):
        run.step(Intent(dx=1))
        if run.here == scene.FAR:
            break
        straddling += run._mid_threshold()
    assert run.here == scene.FAR, "the player never got through the door"
    assert 0 < straddling <= 2 * CELL, straddling
    # **And it is still true on the far side**, because the player has landed
    # on the far room's own doorway column: the view has just flicked, which is
    # the very frame a plan must not be dropped on. It goes false once they
    # have walked out of the opening.
    assert run._mid_threshold()
    for _ in range(CELL):
        run.step(Intent(dx=1))
    assert not run._mid_threshold(), "still crossing well into the room"


def test_a_surge_that_comes_due_in_a_doorway_waits_for_the_room():
    """The same rule, in the real loop rather than against the schedule."""
    run = Session(seed=1)
    run.player.x = (COLS - 1) * CELL
    run.player.y = (scene.DOOR_ROWS[1] - 1) * CELL
    run.surge.due = run.frame + 1
    run.step(Intent(dx=1))
    assert run._mid_threshold() or run.here == scene.FAR
    if run.surge.count == 0:
        assert run.surge.deferred > 0
        while run.surge.count == 0 and run.frame < 100:
            run.step(Intent(dx=1))
    assert run.surge.count == 1, "the surge never arrived"
    assert not run._mid_threshold()


# --- it is not a light ------------------------------------------------------

def test_a_surge_touches_no_field_no_charge_and_no_source():
    """**A surge is not a light and must never become one.**

    It draws no Clegs toward it, and that falls out rather than being an
    exception: a fly climbs toward light, and a light that is everywhere offers
    nothing to climb toward. What makes it fall out is exactly this -- the
    surge adds no charge to any field, is in no room's list of sources, and
    writes pixels and attributes and stops.
    """
    run = Session(seed=1, metrics=True)
    for _ in range(200):
        run.step()
    charges = [bytes(place.field.charge) for place in run.places]
    levels = [place.field.levels() for place in run.places]
    fixed = [list(place.fixed) for place in run.places]
    lights = list(run.kit.floor), list(run.room_lights)
    counted = run.repaint.stats()

    screen = Screen()
    run.draw(screen)
    written = run.draw_surge(screen)

    assert written == surge.cells_written() == COLS * PLAY_ROWS
    assert [bytes(p.field.charge) for p in run.places] == charges
    assert [p.field.levels() for p in run.places] == levels
    assert [list(p.fixed) for p in run.places] == fixed
    assert (list(run.kit.floor), list(run.room_lights)) == lights
    assert run.repaint.stats() == counted


def test_the_swarm_does_not_notice_a_surge():
    """The claim in the form a player would feel it: same flies, same places.

    Two runs on the same seed, one of them surging every other frame, and the
    swarm is in the same cells at the end. If a surge ever lured anything this
    is the test that fails, and it fails by position rather than by an
    assertion about the implementation.
    """
    def swarm_of(run):
        return [(place.index, c.cx, c.cy, c.state, c.kind)
                for place in run.places for c in place.swarm.clegs]

    quiet, surging = Session(seed=2), Session(seed=2)
    screen = Screen()
    for frame in range(400):
        quiet.step()
        surging.step()
        if frame % 2:
            surging.draw(screen)
            surging.draw_surge(screen)
    assert swarm_of(quiet) == swarm_of(surging)


def test_a_surge_adds_no_kind_to_the_run_log():
    """A surge is not an event and must never become one: a new kind in the log
    is a changed log, and every baseline in this round rests on it not moving.
    """
    kinds = {value for name, value in vars(S).items()
             if name.isupper() and isinstance(value, str)}
    run = spike_driver.drive(bots.make("listener", seed=1, light=True),
                             seed=1, frames=4000)
    assert run.surge.count > 0, "no surge fired, so this proves nothing"
    assert {e.kind for e in run.log} <= kinds


# --- the freeze is the shell's ----------------------------------------------

def test_the_freeze_does_not_reach_the_session():
    """**The same mechanism as a moment's pause, and deliberately not a second
    one.**

    If the session held instead -- a flag that made `step` do nothing -- its
    frame counter would go on advancing through the freeze, every event after
    it would carry a different frame number, and every run log in the project
    would move. So the shell simply does not step, and the session never hears
    about it.
    """
    shell = spike1.Shell(Screen())
    shell.key(pygame.K_j)
    run = shell.run
    run.surge.due = run.frame + 1
    while run.surge.count == 0 and run.frame < 100:
        shell.frame()
    assert shell.surging == surge.SURGE_FRAMES - 1, "the surge did not hold"

    frame, log = run.frame, list(run.log)
    for held in range(surge.SURGE_FRAMES - 1, 0, -1):
        assert shell.surging == held
        shell.frame(dx=1)
    assert shell.surging == 0
    assert run.frame == frame, "the session was stepped during a surge"
    assert run.log == log, "the log moved during a surge"

    shell.frame()
    assert run.frame == frame + 1, "play did not resume"


def test_the_plan_stays_on_screen_for_the_whole_freeze():
    """Nothing is drawn during the held frames because nothing changes, which
    is why the other forty-eight frames of a surge cost the port nothing."""
    shell = spike1.Shell(Screen())
    shell.key(pygame.K_j)
    shell.run.surge.due = shell.run.frame + 1
    while shell.run.surge.count == 0:
        shell.frame()
    plan = bytes(shell.screen.attrs), bytes(shell.screen.pixels)
    # The frame it was drawn on is the first of the fifty, so forty-nine are
    # held after it and the fiftieth frame of plan is the last.
    assert shell.surging == surge.SURGE_FRAMES - 1
    for _ in range(surge.SURGE_FRAMES - 1):
        shell.frame(dx=1)
        assert (bytes(shell.screen.attrs),
                bytes(shell.screen.pixels)) == plan
    shell.frame()
    assert bytes(shell.screen.attrs) != plan[0], "the play area never came back"


def test_the_headless_driver_never_waits_for_a_surge():
    """Its frames are frames of simulation. A hold here would mean the same
    `--frames` bought fewer stepped frames, every bot run would end somewhere
    new, and the tail of every event log in the project would shift."""
    run = spike_driver.drive(bots.make("listener", seed=1, light=True),
                             seed=1, frames=3000, draw=True)
    assert run.frame == 3000, "the driver lost frames to a surge"
    assert run.surge.count > 0, "no surge fired, so this proves nothing"


def test_a_death_and_a_surge_on_one_frame_do_not_fight():
    """The death is the beat that frame; the surge is owed and follows it.

    Two screens back to back would read as the game hanging twice, and a surge
    dropped because somebody happened to die on its frame would be a beat lost
    for a reason nobody could ever have found.
    """
    shell = spike1.Shell(Screen())
    shell.key(pygame.K_j)
    run = shell.run
    for _ in range(20):
        shell.frame()
    run.blood = 0
    run.surge.due = run.frame + 1
    shell.frame()
    assert shell.held, "the death did not ask the shell to hold"
    assert not shell.surging, "the surge took the death's frame"
    assert run.surge.owed == surge.SURGE_FRAMES, "the surge was dropped"
    for _ in range(shell.held):
        shell.frame()
    shell.frame()
    assert shell.surging == surge.SURGE_FRAMES - 1


# --- what is drawn ----------------------------------------------------------

def _plan(seed: int = 1, frames: int = 200) -> tuple:
    run = Session(seed=seed)
    for _ in range(frames):
        run.step()
    screen = Screen()
    run.draw(screen)
    run.draw_surge(screen)
    return run, screen


def _lit(screen, cx: int, cy: int) -> bool:
    return any(screen.pixels[y * SCREEN_W + x]
               for y in range(cy * CELL, cy * CELL + CELL)
               for x in range(cx * CELL, cx * CELL + CELL))


def test_the_plan_is_four_pixels_a_cell_and_two_rooms_wide():
    """A room is 32x22 cells, so a plan is 128x88 pixels -- sixteen attribute
    cells by eleven -- and two rooms fill the width exactly. One pixel a cell
    would put a room in four attribute cells and colour would mean nothing;
    eight would fit one room."""
    assert surge.SCALE == 4
    assert surge.ROOM_COLS == 16 and surge.ROOMS_ACROSS == 2
    assert surge.PLAN_ROWS == 11
    assert surge.PLAN_TOP == 6
    assert surge.PLAN_TOP + surge.PLAN_ROWS - 1 == 16
    assert len(scene.BUILDING.rooms) == surge.ROOMS_ACROSS
    # The far corner of the far room is the last pixel of the plan and is on
    # screen, which is what "fits exactly" means.
    px, py = surge.origin(1, COLS - 1, PLAY_ROWS - 1)
    assert (px + surge.SCALE, py + surge.SCALE) == (SCREEN_W, 17 * CELL)


def test_the_rows_above_and_below_the_plan_are_left_empty():
    """**Reserved, not free.** The design parks score and time remaining there,
    both are unbuilt mechanics, and building them here would be the gameplay
    change this round forbids. Rescued-of-quota is on the strip already and
    there is no clock in this game at all, so there is nothing to leave out."""
    _run, screen = _plan()
    for cy in list(range(0, surge.PLAN_TOP)) + list(range(17, PLAY_ROWS)):
        for cx in range(COLS):
            assert screen.attrs[cy * COLS + cx] == surge.BLANK
            assert not _lit(screen, cx, cy), f"something drew at {(cx, cy)}"


def test_the_status_strip_is_not_part_of_the_surge():
    """It stays exactly where it is and keeps its bytes: the plan replaces the
    play area and nothing else."""
    run, screen = _plan()
    before = bytes(screen.attrs[STRIP_TOP * COLS:])
    pixels = bytes(screen.pixels[STRIP_TOP * CELL * SCREEN_W:])
    run.draw_surge(screen)
    assert bytes(screen.attrs[STRIP_TOP * COLS:]) == before
    assert bytes(screen.pixels[STRIP_TOP * CELL * SCREEN_W:]) == pixels
    assert any(before), "the strip was blank, so this proved nothing"


def test_a_wall_is_a_filled_block_and_a_floor_is_nothing():
    """The two that make the plan a plan. A cell with nothing but floor in it
    draws nothing and keeps black paper, which is what makes the walls read as
    lines rather than as a grid."""
    _run, screen = _plan()
    room = scene.BUILDING[scene.NEAR]
    wall = next((cx, cy) for cy in range(PLAY_ROWS) for cx in range(COLS)
                if room.is_wall(cx, cy))
    px, py = surge.origin(scene.NEAR, *wall)
    for y in range(py, py + surge.SCALE):
        for x in range(px, px + surge.SCALE):
            assert screen.pixels[y * SCREEN_W + x], f"wall {wall} has a hole"

    # A floor cell with nothing standing in it, in the middle of the room.
    marks = {(r, cx, cy) for r, cx, cy, _kind in _run.surge_marks()}
    floor = next((cx, cy) for cy in range(2, PLAY_ROWS - 2)
                 for cx in range(2, COLS - 2)
                 if not room.is_wall(cx, cy)
                 and (scene.NEAR, cx, cy) not in marks)
    px, py = surge.origin(scene.NEAR, *floor)
    assert not any(screen.pixels[y * SCREEN_W + x]
                   for y in range(py, py + surge.SCALE)
                   for x in range(px, px + surge.SCALE))


def test_the_way_out_is_drawn_and_is_magenta():
    """A door is a filled block in the door's own hue, which is the hue a key
    to it would take. It is the one coloured landmark on the plan and it is how
    you work out which way you are facing."""
    _run, screen = _plan()
    room = scene.BUILDING[scene.NEAR]
    ex, ey = room.exit_cell()
    acx, acy = surge.attr_cell(scene.NEAR, ex, ey)
    assert unpack_attr(screen.attrs[acy * COLS + acx])[0] == MAGENTA
    assert _lit(screen, acx, acy)


def test_the_player_the_people_and_the_flies_are_all_on_it():
    """**The surge shows everything, people included**, which is what makes it
    the memorisation beat rather than a floor plan -- and it shows the room you
    are not standing in, which is the whole of what it hands over."""
    run, screen = _plan(seed=1, frames=200)
    marks = run.surge_marks()
    kinds = [kind for _r, _cx, _cy, kind in marks]
    assert kinds.count(surge.P_PLAYER) == 1
    assert kinds.count(surge.P_WORKER) == len(run.rescue.workers)
    assert kinds.count(surge.P_CLEG) == len(run.swarm.clegs)
    assert {room for room, _cx, _cy, _k in marks} == {scene.NEAR, scene.FAR}, \
        "the plan only shows the room the player is standing in"
    for room, cx, cy, _kind in marks:
        acx, acy = surge.attr_cell(room, cx, cy)
        assert _lit(screen, acx, acy), f"nothing drawn for {(room, cx, cy)}"


def test_a_worker_is_green_and_a_fly_is_a_single_red_pixel():
    """The plan *shows* Clegs and the surge *attracts* none: both are true and
    this slice carries both. A fly is one pixel because four are a cell and a
    cell is a wall."""
    run, screen = _plan()
    worker = run.rescue.alive_waiting()[0]
    acx, acy = surge.attr_cell(worker.room, *worker.cell())
    assert unpack_attr(screen.attrs[acy * COLS + acx])[0] == GREEN

    place = run.places[scene.NEAR]
    fly = place.swarm.clegs[0]
    px, py = surge.origin(scene.NEAR, fly.cx, fly.cy)
    on = [(x - px, y - py) for y in range(py, py + surge.SCALE)
          for x in range(px, px + surge.SCALE)
          if screen.pixels[y * SCREEN_W + x]]
    assert (1, 1) in on, "the fly is not the middle pixel of its cell"


def test_the_player_and_the_nests_flash_and_nothing_else_does():
    """**You find yourself first**, and finding yourself on a plan is the
    precondition for using it. The FLASH bit is free -- the ULA blinks it in
    hardware -- and the nests get it because they are the thing you are trying
    not to walk into."""
    assert [i for i, flashes in enumerate(surge.FLASHES) if flashes] == \
        [surge.P_PLAYER, surge.P_NEST]
    run, screen = _plan()
    flashing = {(i % COLS, i // COLS)
                for i, attr in enumerate(screen.attrs[:STRIP_TOP * COLS])
                if attr & 0b1000_0000}
    assert flashing == {surge.attr_cell(run.here, run.player.cx,
                                        run.player.cy)}


def test_a_wall_sharing_the_players_cell_blinks_with_him():
    """**Accepted rather than fixed.** The FLASH bit is per attribute cell like
    the ink, so a wall in the player's cell flashes too. One blinking 8x8 patch
    is a small price for the only mark on the plan you have to find before the
    plan is any use at all -- and the alternative is per-pixel flash, which the
    hardware does not have.
    """
    room = scene.BUILDING[scene.NEAR]
    wall = next((cx, cy) for cy in range(PLAY_ROWS) for cx in range(COLS)
                if room.is_wall(cx, cy))
    screen = Screen()
    surge.draw(screen, scene.BUILDING.rooms,
               [(scene.NEAR, wall[0], wall[1], surge.P_PLAYER)])
    acx, acy = surge.attr_cell(scene.NEAR, *wall)
    ink, _paper, _bright, flash = unpack_attr(screen.attrs[acy * COLS + acx])
    # And the patch takes the player's ink, not the wall's -- which since issue
    # #59 is how you can tell it is the player's patch at all.
    assert flash and ink == YELLOW


# --- one chooser per cell, so clash is still impossible ---------------------

def test_the_priority_order_is_the_design_table():
    """player > worker > nest > Cleg > key > door > wall, and the hues with
    them. A key takes the hue of the door it opens, which is why it is magenta
    rather than a colour of its own."""
    assert (surge.P_PLAYER, surge.P_WORKER, surge.P_NEST, surge.P_CLEG,
            surge.P_KEY, surge.P_DOOR, surge.P_WALL) == (0, 1, 2, 3, 4, 5, 6)
    assert surge.HUE[:7] == (YELLOW, GREEN, RED, RED, MAGENTA, MAGENTA, WHITE)


def test_the_player_is_not_drawn_in_the_colour_the_walls_are_drawn_in():
    """**The mark you have to find first was the quietest thing on the plan**
    (issue #59).

    He was white, on a plan whose walls are white and are most of it, and the
    green and red marks are bigger and louder than a 2x2 patch. A reader given
    a still said they found themselves *by being the one that blinks*, which
    means the flash was carrying the whole load. It still flashes -- that is
    asserted above -- and now the colour is pulling with it rather than
    against it.

    **Yellow is the only ink free**, and it is free because the plan draws no
    floor: green is a person, red is a fly or a nest, magenta is the way out,
    white is the building, and cyan and yellow are the two rooms' floors.
    """
    assert surge.HUE[surge.P_PLAYER] == YELLOW
    assert surge.HUE[surge.P_PLAYER] != surge.HUE[surge.P_WALL], \
        "the player is drawn in the colour most of the plan is drawn in"
    assert surge.FLASHES[surge.P_PLAYER], "the mark lost its blink"
    # Every hue on the plan means one thing: no two kinds share an ink except
    # the pairs that are deliberately one meaning (fly and nest, key and door).
    assert len({surge.HUE[k] for k in
                (surge.P_PLAYER, surge.P_WORKER, surge.P_NEST, surge.P_DOOR,
                 surge.P_WALL)}) == 5


@pytest.mark.parametrize("kind", [surge.P_PLAYER, surge.P_WORKER,
                                  surge.P_NEST, surge.P_CLEG])
def test_the_most_important_thing_in_a_cell_chooses_its_hue(kind):
    """**The clash rule is kept by priority rather than by compromise.**

    Four map cells share one attribute cell at this scale, and there is still
    exactly one chooser per cell, so clash is still impossible. It degrades in
    the direction you want: a worker standing against a wall turns that patch
    green, which is the thing you needed to know.
    """
    room = scene.BUILDING[scene.NEAR]
    plain, marked = Screen(), Screen()
    surge.draw(plain, scene.BUILDING.rooms)
    # A wall cell, whose attribute cell therefore reads white with nothing
    # else on the plan. The room's walls are one cell thick, so an attribute
    # cell that is *all* wall does not exist to be found -- which is itself the
    # reason the priority rule is needed.
    wall = next((cx, cy) for cy in range(2, PLAY_ROWS - 2)
                for cx in range(2, COLS - 2) if room.is_wall(cx, cy))
    surge.draw(marked, scene.BUILDING.rooms,
               [(scene.NEAR, wall[0], wall[1], kind)])
    acx, acy = surge.attr_cell(scene.NEAR, *wall)
    index = acy * COLS + acx
    assert unpack_attr(plain.attrs[index])[0] == WHITE
    assert unpack_attr(marked.attrs[index])[0] == surge.HUE[kind]


def test_every_cell_of_the_plan_holds_one_ink_and_black_paper():
    """The whole point of drawing through `core.Screen`: there is one attribute
    per cell and nothing on the plan can ask for two."""
    _run, screen = _plan()
    for cy in range(surge.PLAN_TOP, surge.PLAN_TOP + surge.PLAN_ROWS):
        for cx in range(COLS):
            ink, paper, bright, _flash = unpack_attr(
                screen.attrs[cy * COLS + cx])
            assert paper == BLACK
            assert ink in surge.HUE
            assert bright or ink == BLACK


def test_a_third_room_is_refused_rather_than_cropped():
    """A plan that silently omitted a room would be worse than no plan: the
    player would memorise a building that is not there. When a building grows a
    third room this raises, and the scale decision gets made on purpose."""
    with pytest.raises(ValueError):
        surge.draw(Screen(), list(scene.BUILDING.rooms) * 2)


# --- the number the user has to settle --------------------------------------

def test_the_surge_length_is_one_constant_and_nothing_is_derived_from_it():
    """**`SURGE_FRAMES` is the user's number**, to be found at a keyboard, and
    nobody else moves it. It is written down once so that settling it is one
    edit, and nothing is computed from it so that settling it cannot move
    anything else. The moment something derives from it, changing it stops
    being safe and `--surge-frames` stops being enough -- so this walks the
    syntax rather than the text: every module-level assignment in the portable
    tree is checked for the name on its right-hand side.
    """
    import ast
    import pathlib

    assigned, derived = [], []
    for path in sorted(pathlib.Path(surge.__file__).parent.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            names = ([t.id for t in node.targets if isinstance(t, ast.Name)]
                     if isinstance(node, ast.Assign)
                     else [node.target.id]
                     if isinstance(node.target, ast.Name) else [])
            if "SURGE_FRAMES" in names:
                assigned.append(path.name)
            if node.value is not None and any(
                    isinstance(kid, ast.Name) and kid.id == "SURGE_FRAMES"
                    for kid in ast.walk(node.value)):
                derived.append(f"{path.name}:{node.lineno}")
    assert assigned == ["surge.py"], assigned
    assert derived == [], f"something is derived from SURGE_FRAMES: {derived}"
    assert surge.SURGE_FRAMES == 50


def test_forty_eight_frames_is_the_hardware_floor_the_default_stands_on():
    """The reason the default is 50 rather than a number somebody liked.

    The player's mark is drawn with the FLASH bit, which the ULA blinks sixteen
    frames on and sixteen off, free-running and synchronised with nothing. A
    window shorter than 48 frames can straddle two off-phases and show the mark
    as two part-blinks and never once whole -- and finding yourself on the plan
    is the precondition for using it. This is not a bound on the constant: the
    user may settle on anything. It is here so that whoever settles it knows
    which direction a wrong answer lies in.
    """
    from spotlight.frontend.display import FLASH_PERIOD
    assert FLASH_PERIOD == 16
    assert surge.SURGE_FRAMES >= 3 * FLASH_PERIOD


@pytest.mark.parametrize("frames", [1, 200])
def test_the_surge_frames_flag_overrides_it_at_both_extremes(frames):
    """The user will try both, so both are tested. One frame is a subliminal
    flicker and two hundred is four seconds of map; the answer is somewhere
    between and it is theirs to find."""
    assert spike1.main.__module__  # the flag is parsed in spike1
    shell = spike1.Shell(Screen(), surge_frames=frames)
    shell.key(pygame.K_j)
    run = shell.run
    assert run.surge.frames == frames
    run.surge.due = run.frame + 1
    while run.surge.count == 0 and run.frame < 100:
        shell.frame()
    assert shell.surging == frames - 1
    at = run.frame
    for _ in range(frames - 1):
        shell.frame()
    assert run.frame == at, "the game was stepped during the surge"
    shell.frame()
    assert run.frame == at + 1


def test_a_surge_of_no_frames_is_refused():
    """`take` returns 0 for "nothing owed", so a surge of no frames could not
    say it had happened. It is a mistake rather than a setting."""
    with pytest.raises(ValueError):
        surge.Schedule(1, frames=0)


def test_the_flag_reaches_the_session_through_the_shell():
    """Parsed in `main` and carried on the shell, because a restart builds a
    new `Session` and the setting belongs to the sitting rather than the run."""
    shell = spike1.Shell(Screen(), surge_frames=7)
    shell.key(pygame.K_j)
    assert shell.run.surge.frames == 7
    shell.start()
    assert shell.run.surge.frames == 7, "a restart lost the setting"


# --- what it costs ----------------------------------------------------------

def test_the_run_report_carries_the_surges_and_what_they_repaint():
    """**The figure the repaint counter cannot see, said out loud.**

    Two whole-screen repaints per surge -- one on the frame the plan appears,
    one on the frame the play area comes back -- at 704 cells each. The counter
    above them counts cells whose *light level* changed and a surge changes
    none, so those figures must not move; this is what replaces them.
    """
    run = spike_driver.drive(bots.make("listener", seed=1, light=True),
                             seed=1, frames=4000)
    metrics = report.metrics(run)
    assert metrics["surges"] == run.surge.count > 0
    assert metrics["surge_repaint_frames"] == 2 * run.surge.count
    assert metrics["surge_repaint_cells"] == COLS * PLAY_ROWS == 704
    assert metrics["surge_frames"] == surge.SURGE_FRAMES

    note = " ".join(report.note(run, bot="listener"))
    assert "Surges" in note
    assert "102,620" in note and "52,416" in note, \
        "the tester's note does not price a surge against the port"


def test_the_repaint_counter_does_not_move_for_a_surge():
    """**If it moves, the surge has touched the light field and it is wrong.**

    Stated as a criterion in the issue and asserted here directly rather than
    left to a comparison against the commit before: a surge changes no light
    level, so mean, p95, p99 and max of both counts are the same with the
    schedule running and with it switched off.
    """
    def figures(due):
        run = Session(seed=4, metrics=True)
        run.surge.due = due
        playing = bots.make("listener", seed=4, light=True)
        screen = Screen()
        while run.over is None and run.frame < 3500:
            run.step(playing.intent(run))
            run.draw(screen)
            if run.surge.take():
                run.draw_surge(screen)
        return run, run.repaint.stats()

    surging, with_surges = figures(1500)
    quiet, without = figures(1 << 30)
    assert surging.surge.count > 0 and quiet.surge.count == 0
    for key in lighting.REPAINT_METRICS:
        assert with_surges[key] == without[key], key


def test_the_debug_key_brings_a_surge_forward_and_nothing_else():
    """The other half of what somebody settling the number needs.

    `--surge-frames N` sets the length; a surge otherwise arrives once every
    forty to seventy seconds, so comparing five values by playing would be five
    minutes of waiting. `U` makes the next one due now and changes nothing
    else, and it is `--debug` only like every other developer key -- a tester
    who fidgets must not be able to conjure the plan.
    """
    shell = spike1.Shell(Screen(), debug=True)
    shell.key(pygame.K_j)
    run = shell.run
    for _ in range(10):
        shell.frame()
    assert run.surge.count == 0
    shell.key(pygame.K_u)
    shell.frame()
    assert run.surge.count == 1
    assert shell.surging == surge.SURGE_FRAMES - 1
    # And the schedule carries on from where it fired rather than being left
    # where the key found it.
    assert run.surge.due - run.frame >= surge.INTERVAL_MIN

    quiet = spike1.Shell(Screen())
    quiet.key(pygame.K_j)
    for _ in range(10):
        quiet.frame()
    quiet.key(pygame.K_u)
    quiet.frame()
    assert quiet.run.surge.count == 0, "the key worked without --debug"


@pytest.mark.parametrize("argv, want", [
    ([], surge.SURGE_FRAMES),
    (["--surge-frames", "1"], 1),
    (["--surge-frames", "200"], 200),
    (["--scale", "2", "--surge-frames", "24", "--debug"], 24),
])
def test_the_command_line_says_how_long_a_surge_lasts(argv, want):
    """What `--surge-frames N` means, asked without opening a window.

    The switch exists because settling the number is somebody sitting at a
    keyboard trying five values, and five rebuilds is not that.
    """
    assert spike1.surge_frames_from(argv) == want
