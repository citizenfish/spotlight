"""The doorway: crossing it, what stops at it, and what carries through it.

Issue #21's own acceptance criteria, in the loop, through the game's own code.

**What was wrong before, and must not come back.** The prototype had one room,
and the far side of every wall in it was on screen. That made three of the
design's sharpest claims untestable and one of them quietly false:

* A tail could not be strung out somewhere the player cannot cover, so *Trapped
  Workers*' central claim -- that the instinct to turn and check on people is
  what gets them eaten -- had nowhere to happen.
* A worker being eaten a few cells away was always visible, so nothing depended
  on hearing it. With two rooms it is invisible **and** inaudible, because the
  sonar reports the room you are in and it skips attached flies -- once one has
  landed there is nothing left to hear. That is a number going down for no
  reason, which is the failure mode the playtest is most worried about, and the
  shouts through a doorway are the whole answer to it.
* And a light field that stops at a wall had never been asked for.
"""

import pytest

from spikes import (
    clegs as clegs_mod, lighting, rescue as rescue_mod, scene, session,
)
from spikes.session import Intent, Session
from spotlight.core.constants import CELL, COLS
from spotlight.core.screen import Screen

DOOR_ROW = scene.DOOR_ROWS[1]


def at_door(run, room=scene.NEAR, offset=0):
    """Stand the player in a doorway cell, feet on the middle row.

    Teleporting is a test convenience for getting the *player* somewhere;
    everything the tests then assert goes through the real loop.
    """
    run.here = room
    column = COLS - 1 if room == scene.NEAR else 0
    run.player.x = (column + offset) * CELL
    run.player.y = (DOOR_ROW - 1) * CELL
    return run


def walk(run, dx, frames, dy=0):
    for _ in range(frames):
        run.step(Intent(dx=dx, dy=dy))
    return run


# --- stepping through flicks the view, and preserves position ---------------

def test_walking_east_out_of_the_near_room_arrives_in_the_far_one():
    """**The world is continuous; only the view jumps.**

    The player is not re-placed, paused or snapped: they walk off one room's
    last column and onto the next room's first, which is the same walk they
    were already doing. The row is preserved exactly, because the doorway is at
    the same rows on both sides.
    """
    run = at_door(Session(seed=1))
    before = run.player.y
    walk(run, 1, 16)
    assert run.here == scene.FAR
    assert run.room == scene.FAR_NAME
    assert run.player.y == before, "the crossing moved them up or down"
    assert run.player.x < CELL * 2, "they did not come out of the doorway"


def test_walking_back_west_returns_to_the_near_room_at_the_same_row():
    run = at_door(Session(seed=1))
    y = run.player.y
    walk(run, 1, 16)
    assert run.here == scene.FAR
    walk(run, -1, 24)
    assert run.here == scene.NEAR
    assert run.player.y == y
    assert run.player.x > (COLS - 3) * CELL


def test_a_crossing_is_logged_with_the_room_left_and_the_room_reached():
    """A second room that nobody goes into bought walking and nothing else, so
    the run report has to be able to say whether anybody ever went."""
    run = at_door(Session(seed=1))
    walk(run, 1, 16)
    crossed = [e for e in run.log if e.kind == session.CROSSED]
    assert len(crossed) == 1
    assert crossed[0].room == scene.NEAR_NAME, "it does not say where from"
    assert crossed[0].count == scene.FAR, "it does not say where to"
    assert run.crossings == 1


def test_the_wall_beside_the_doorway_still_stops_you():
    """Three rows out of twenty-two are a way through. The rest are masonry."""
    run = Session(seed=1)
    run.player.x = (COLS - 1) * CELL
    run.player.y = 3 * CELL
    walk(run, 1, 40)
    assert run.here == scene.NEAR, "walked through a wall into the far room"


def test_only_the_room_the_player_is_in_is_drawn():
    """The screen flick, at the level of pixels. The room behind you is *gone*
    rather than dark, and that is the moment the second room exists for."""
    near = Session(seed=1)
    near.place.opening.hold(True)          # show the whole room, both times
    screen = Screen()
    near.step()
    near.draw(screen)
    before = bytes(screen.pixels)

    far = at_door(Session(seed=1))
    walk(far, 1, 16)
    far.place.opening.hold(True)
    far.step()
    far.draw(screen)
    assert bytes(screen.pixels) != before, "both rooms drew the same picture"


# --- light does not cross the threshold -------------------------------------

def test_you_cannot_see_into_the_far_room_from_the_near_rooms_doorway():
    """**A light source belongs to a room and its field stops at the wall.**

    A real cost and the right one: compositing two rooms' lighting is exactly
    what the room model exists to avoid, and a threshold you cannot see past is
    what makes stepping through it a commitment rather than a glance.

    Asked with the torch on and pointing straight at the doorway, which is the
    hardest case: the cone reaches seven cells, so without the rule the player
    would be looking a quarter of the way into the room next door.
    """
    run = at_door(Session(seed=1))
    run.step(Intent(dx=1, torch=True))
    for _ in range(4):
        run.step(Intent(dx=1))
    assert run.here == scene.NEAR, "walked through before the light was asked"
    assert run.cone.lit
    near, far = run.places[scene.NEAR], run.places[scene.FAR]
    assert near.field.level_at(COLS - 1, DOOR_ROW) == lighting.LIT, \
        "the player is not even lighting the doorway they are standing in"
    for cy in scene.DOOR_ROWS:
        for cx in range(0, 7):
            assert far.field.level_at(cx, cy) in (lighting.DARK, lighting.LIT), \
                "unexpected level"
    # The far room's only light is its own: the authored room light over the
    # doorway. Nothing the player carries reaches past the wall.
    lit_by_the_room = {c for z in far.room.light_zones()
                       for c in _zone_cells(z)}
    for cy in range(22):
        for cx in range(COLS):
            if (cx, cy) in lit_by_the_room:
                continue
            assert far.field.level_at(cx, cy) == lighting.DARK, \
                f"the player's torch lit {cx},{cy} in the room next door"


def _zone_cells(zone):
    left, top, width, height = zone
    return [(left + dx, top + dy)
            for dy in range(height) for dx in range(width)]


def test_the_exit_sign_burns_in_its_own_room_and_nowhere_else():
    """It has its own battery, so it is always lit -- in the near room. The far
    room has no way out and must not show one."""
    run = Session(seed=1)
    run.step()
    near, far = run.places[scene.NEAR], run.places[scene.FAR]
    assert near.sign_cells
    assert far.sign_cells == []
    # The far room's own room light sits over its side of the threshold, which
    # is the same corner of the grid, so only the cells it does not cover can
    # say anything about the sign.
    lit_by_the_room = {c for z in far.room.light_zones() for c in _zone_cells(z)}
    for cx, cy in near.sign_cells:
        assert near.field.level_at(cx, cy) == lighting.LIT
        if (cx, cy) not in lit_by_the_room:
            assert far.field.level_at(cx, cy) == lighting.DARK


# --- the far room's authored light ------------------------------------------

def test_the_far_room_is_lit_at_its_doorway_from_the_first_frame():
    """The centrepiece. From anywhere in the far room you can see the way home,
    so it is navigable without being safe -- and because it is permanent, it is
    a permanent lure on the one route you have to use."""
    run = Session(seed=1)
    run.step()
    far = run.places[scene.FAR]
    for cy in scene.DOOR_ROWS:
        assert far.field.level_at(0, cy) == lighting.LIT


def test_the_far_rooms_light_does_not_make_the_tail_prey():
    """*Light and Darkness* is explicit that room lights reveal nobody, to
    Clegs exactly as to the player, and `prey_at` enforces it.

    **This contradicts the vault's worked example for this room light**, which
    says the tail files through it lit and is therefore guaranteed prey at the
    one moment the whole line is in one place. The agreed rule wins here and the
    contradiction is the designer's to settle -- recorded as a test rather than
    as a comment so that whichever way it is settled, somebody has to come here
    and say so.
    """
    run = Session(seed=1)
    run.step()
    far = run.places[scene.FAR]
    for cy in scene.DOOR_ROWS:
        assert far.field.level_at(0, cy) == lighting.LIT
        assert not far.field.prey_at(0, cy)


def test_the_far_room_has_no_searchlight_and_the_near_room_does():
    run = Session(seed=1)
    assert run.places[scene.NEAR].roaming is not None
    assert run.places[scene.FAR].roaming is None
    assert len(run.searchlights) == 1


# --- the opening flash, and the fade across a room change -------------------

def test_the_opening_flash_fires_on_first_entry_and_not_on_re_entry():
    """You cannot play a room you have never seen the shape of. Re-entry is
    precisely the case where you are supposed to be living off what you held in
    your head, so flashing every time would make the fade pointless and hand
    the building over for free."""
    run = at_door(Session(seed=1))
    far = run.places[scene.FAR]
    assert not far.seen
    walk(run, 1, 16)
    assert far.seen
    assert far.opening.left > 0, "the far room did not open with a flash"
    for _ in range(far.opening.frames + 2):
        run.step()
    assert far.opening.left == 0
    walk(run, -1, 24)                       # back to the near room
    assert run.here == scene.NEAR
    walk(run, 1, 24)                        # and in again
    assert run.here == scene.FAR
    assert far.opening.left == 0, "the flash fired again on re-entry"


def test_the_fade_keeps_running_in_the_room_you_have_left():
    """Time passes everywhere. Duck out and back and your memory is still warm;
    come back much later and it has gone."""
    run = at_door(Session(seed=1))
    near = run.places[scene.NEAR]
    # The near room's searchlight is switched off for this test and only this
    # test. It is the one light in the building that keeps writing into a room
    # nobody is looking at, so leaving it on would be measuring the beam rather
    # than the fade. Everything else here is the real loop.
    near.roaming.toggle()
    run.step(Intent(torch=True))
    for _ in range(10):
        run.step()
    sign = set(near.sign_cells)
    remembered = [(cx, cy) for cy in range(22) for cx in range(COLS)
                  if near.field.remembered_at(cx, cy) != lighting.DARK
                  and (cx, cy) not in sign]
    assert remembered, "the torch left no memory to decay"
    walk(run, 1, 16)
    assert run.here == scene.FAR
    warm = sum(near.field.charge[cy * COLS + cx] for cx, cy in remembered)
    for _ in range(40):
        run.step()
    assert sum(near.field.charge[cy * COLS + cx]
               for cx, cy in remembered) < warm, \
        "the room behind you stopped fading"
    for _ in range(lighting.FADE_FRAMES + 40):
        run.step()
    assert all(near.field.remembered_at(cx, cy) == lighting.DARK
               for cx, cy in remembered), "the memory never went out"


def test_catching_a_field_up_is_the_same_as_having_decayed_it():
    """The port keeps a light field for the room you are in and the one you
    just left and no others -- 1,408 bytes whatever the building's size --
    stamped with the frame you left and caught up in one pass on re-entry.

    It is exact because the fade is a monotone countdown, and this is the test
    that says so. It is not yet on the live path: with two rooms both fields
    are resident, so nothing is ever behind. The equivalence is what the whole
    argument rests on, and a rule that is only true in a comment is a rule
    nobody can check.
    """
    frame_by_frame = lighting.LightField()
    in_one_pass = lighting.LightField()
    for field in (frame_by_frame, in_one_pass):
        field.begin()
        for cx in range(10):
            field.add(cx, 5, lighting.LIT, lighting.CHARGE_LIT - cx * 7)
        field.commit()
    for _ in range(37):
        frame_by_frame.begin()
        frame_by_frame.commit()
    in_one_pass.catch_up(37)
    assert bytes(frame_by_frame.charge) == bytes(in_one_pass.charge)
    assert bytes(frame_by_frame.display) == bytes(in_one_pass.display)

    in_one_pass.catch_up(lighting.FADE_FRAMES * 2)
    assert not any(in_one_pass.charge), "a long absence should leave it black"


# --- Clegs cross doorways in pursuit of light -------------------------------

def _put_flies(run, room, cells):
    """Move a room's swarm to known cells, so a steering claim can be watched."""
    flies = run.places[room].swarm.clegs
    for cleg, cell in zip(flies, cells):
        cleg.cx, cleg.cy = cell
        cleg.goal = None
    return flies[:len(cells)]


def test_a_cleg_beside_a_doorway_walks_through_it_to_the_light_beyond():
    """**No pathfinding, ever.** The fly is offered a lure standing on the
    threshold and takes the ordinary greedy step towards it; the cell it walks
    into turns out to belong to the room next door, and the session hands it
    over. Nothing in the swarm knows a doorway exists.
    """
    run = Session(seed=1)
    fly = _put_flies(run, scene.NEAR, [(COLS - 3, DOOR_ROW)])[0]
    for _ in range(200):
        run.step()
        if fly in run.places[scene.FAR].swarm.clegs:
            break
    assert fly in run.places[scene.FAR].swarm.clegs, \
        "the fly never crossed to the far room's permanent light"
    assert fly not in run.places[scene.NEAR].swarm.clegs, \
        "the fly is in two rooms at once"
    assert 0 <= fly.cx < COLS


def test_the_building_never_loses_or_duplicates_a_fly():
    """The counters are the building's, because a fly that walked through a
    doorway is the same fly. Handing one between two lists is exactly where one
    would get dropped."""
    run = Session(seed=3)
    total = len(run.swarm.clegs)
    for _ in range(3000):
        run.step()
        assert len(run.swarm.clegs) == total
        assert len({id(c) for c in run.swarm.clegs}) == total


def test_a_fly_looks_round_its_own_room_before_it_looks_at_a_doorway():
    """**The thing that was wrong.**

    With one list of lures the far room's permanent light -- one cell from its
    side of the threshold -- was the nearest thing a fly anywhere near the near
    room's east wall could notice, nearer than the player's torch across the
    room. They crossed, the room light held them, and over five minutes the
    near room went from three flies to none with a lit player standing in it. A
    still, lit player's blood loss fell by about four times.

    **A building that converges away from the player inverts the level**: the
    far room becomes lethal, which is intended, and the near room becomes free,
    which is not. So light in the next room is the faintest thing a fly can be
    offered, and anything lit on this side of the wall beats it.
    """
    run = Session(seed=1)
    fly = _put_flies(run, scene.NEAR, [(COLS - 3, DOOR_ROW)])[0]
    run.player.x, run.player.y = (COLS - 6) * CELL, (DOOR_ROW - 1) * CELL
    run.step(Intent(torch=True))
    assert run.cone.lit
    for _ in range(120):
        run.step()
        assert fly in run.places[scene.NEAR].swarm.clegs, \
            "a fly left a lit room for the glow round a doorway"


def test_a_fly_carried_across_a_doorway_stays_on_the_player():
    """A fly rides its host. Leaving it behind in the room you walked out of
    would heal you every time you used a door."""
    run = at_door(Session(seed=1))
    run.step()
    fly = run.places[scene.NEAR].swarm.clegs[0]
    fly.cx, fly.cy = run.player.cx, run.player.cy
    run.places[scene.NEAR].swarm._attach(fly)
    blood = run.blood
    walk(run, 1, 16)
    assert run.here == scene.FAR
    assert fly in run.places[scene.FAR].swarm.clegs, "the fly was left behind"
    assert fly.state == clegs_mod.ATTACHED
    walk(run, 1, clegs_mod.DRAIN_EVERY + 2)
    assert run.blood < blood, "it stopped draining when the room changed"


# --- the tail at a doorway ---------------------------------------------------

def _tail_of(run, count):
    """Free `count` people by standing on them, then bring them to the doorway.

    They are collected where they are and then the *player* is teleported to the
    doorway; the tail follows through the game's own `follow`, walking the trail
    the player walked, which is what the doorway tests are about.
    """
    from tests.test_session import touch
    for worker in list(run.rescue.workers)[:count]:
        touch(run, worker)
        run.step()
    assert len(run.rescue.tail) == count
    return run.rescue.tail


def test_a_tail_follows_the_player_through_a_doorway_one_at_a_time():
    """**The reason the second room is in scope.**

    Before you cross, the tail is a line strung along your own path. As you
    cross, the room behind you is gone and people come out of the doorway one
    at a time into your glow. Nothing pulls them: the trail carries the room
    each step was taken in, so a follower crosses at the point the player
    crossed, when they get there.
    """
    run = Session(seed=1)
    tail = _tail_of(run, 3)
    at_door(run, scene.NEAR, offset=-6)
    arrived = []
    for _ in range(400):
        run.step(Intent(dx=1))
        here = [w for w in tail if w.room == scene.FAR]
        if len(here) > len(arrived):
            arrived = here[:]
        if len(arrived) == len(tail):
            break
    assert run.here == scene.FAR
    assert len(arrived) == len(tail), "not everybody came through"
    assert arrived == tail, "they arrived out of order"


def test_a_follower_who_has_not_crossed_yet_is_still_in_the_room_behind_you():
    """The moment the whole thing exists for: part of your line is somewhere you
    cannot see, and there is nothing on screen to tell you how many.

    Shown as an A/B on the real drawing path. The straggler is put in the cell
    the player is standing in, so your own glow is on them and there is no
    question of their being invisible for some other reason -- and they are
    still not drawn, because they are in the room next door. Move them to this
    room without moving them a pixel and the picture changes.
    """
    run = Session(seed=1)
    tail = _tail_of(run, 3)
    at_door(run, scene.NEAR, offset=-1)
    for _ in range(40):
        run.step(Intent(dx=1))
        if run.here == scene.FAR:
            break
    assert run.here == scene.FAR
    behind = [w for w in tail if w.room == scene.NEAR]
    assert behind, "the whole tail teleported across with the player"

    straggler = behind[0]
    straggler.x, straggler.y = run.player.x, run.player.y
    screen = Screen()
    run.draw(screen)
    without = bytes(screen.pixels)

    straggler.room = run.here
    run.draw(screen)
    assert bytes(screen.pixels) != without, \
        "somebody in the room behind you was drawn in this one"


def test_the_tail_spacing_is_not_decided_here():
    """A tail of four spans six cells at this spacing and clears a doorway in
    under a second, where the design wants half a room and two to three seconds.

    That is a **tuning number** and it is tracked in *Resource budgets* for
    phase 2; the second room is what finally makes it measurable. Pinned so that
    nobody quietly widens it while building a doorway, which would be a number
    chosen by the person who built the door rather than by the person measuring
    it.
    """
    assert rescue_mod.TAIL_SPACING == 12


def test_a_follower_dying_mid_tail_closes_the_line_and_leaves_the_body():
    """Settled in the vault: the line closes up and **the body stays where it
    fell, in the room it fell in**.

    It needs no code of its own and that is the point -- the tail is a path and
    a set of people walking it, not a set of slots, so taking somebody out moves
    everybody behind them one place up the trail and nothing shuffles. The
    consequence is the interesting part: the body is in the room behind you, and
    going back for it is a second journey against the same clock.
    """
    run = Session(seed=1)
    tail = _tail_of(run, 3)
    at_door(run, scene.NEAR, offset=-2)
    for _ in range(40):
        run.step(Intent(dx=1))
        if run.here == scene.FAR:
            break
    assert run.here == scene.FAR
    victim = next(w for w in tail if w.room == scene.NEAR)
    behind = [w for w in tail if w is not victim]

    # Standing still while they bleed, so that "the body stays where it fell"
    # is a claim about the body and not about the walk: a follower who is still
    # being led is supposed to move.
    victim.blood = 1
    where = None
    for _ in range(rescue_mod.BLEED_EVERY + 2):
        where = (victim.room, victim.x, victim.y)
        run.step()
        assert run.tally_adds_up(), run.frame
        if victim.state == rescue_mod.DEAD:
            break

    assert victim.state == rescue_mod.DEAD
    assert victim not in run.rescue.tail, "a body was still being dragged along"
    assert (victim.room, victim.x, victim.y) == where, \
        "the body moved after they died"
    assert victim.room == scene.NEAR, "the body did not stay in the room behind"
    assert victim in run.rescue.bodies(scene.NEAR), \
        "the body is not in the room it fell in"
    assert run.rescue.tail == behind, "the line did not close up"
    for _ in range(60):
        run.step(Intent(dx=1))
        assert (victim.room, victim.x, victim.y) == where, \
            "the body followed the player"
    died = [e for e in run.log if e.kind == session.WORKER_DIED]
    assert [e.room for e in died] == [scene.NEAR_NAME], \
        "the report cannot say which room they were lost in"


def test_the_tally_adds_up_with_people_in_both_rooms():
    """Out + died + still inside = seven, whichever side of the wall they are
    on. It is the number a tester reads off the ending screen."""
    run = Session(seed=1)
    _tail_of(run, 4)
    at_door(run, scene.NEAR, offset=-4)
    rooms = set()
    for _ in range(600):
        run.step(Intent(dx=1))
        rooms.add(run.here)
        assert run.tally_adds_up(), run.frame
        if run.over is not None:
            break
    assert rooms == {scene.NEAR, scene.FAR}, "the run never used both rooms"
    assert run.rescued + run.lost + run.inside == run.total == 7


# --- shouts carry through a doorway -----------------------------------------

def _make_them_shout(run, room):
    """Wind a room's workers to the frame their call is on.

    Calls are rate-limited by blood, so a room of fresh workers is nearly
    silent; the test needs a frame where somebody is definitely calling and
    steps to it rather than waiting a fortnight for one.
    """
    for _ in range(9000):
        run.step()
        if run.rescue.calling(run.frame, room):
            return True
        if run.over is not None:
            break
    return False


def test_a_call_from_the_next_room_is_drawn_over_the_connecting_doorway():
    """**The one genuinely new rule.**

    The sonar reports the nearest Cleg in the room you are in, so without this
    the room behind you falls silent the moment you leave it. It is also how the
    door is found: a first-timer sees `HELP` appear over a gap in the east wall
    and understands there are people through there, which is why the door needs
    no colour of its own.
    """
    run = Session(seed=1)
    assert _make_them_shout(run, scene.FAR), "nobody in the far room called"
    assert run.door_calls, "the call did not carry through the doorway"
    door = run.place.room.doorways[0]
    cells = run.door_calls[0]
    assert len(cells) == len(rescue_mod.CALL)
    assert all(cy == door.middle for _cx, cy in cells)
    assert (door.column, door.middle) in cells, \
        "the word is not over the doorway"
    # ...and it lifts its own cells out of the dark, like any other shout.
    for cx, cy in cells:
        assert run.field.level_at(cx, cy) == lighting.LIT


def test_the_call_says_the_door_and_not_the_person():
    """Where in the far room they are shouting from is not in it and must never
    be. A shout is a bearing, not a map -- carried too far this turns a dark
    building into something read by ear.

    So the word over the doorway sits where the doorway is and nowhere else,
    and it is the *same* four cells whoever is calling and wherever in the far
    room they are standing.
    """
    door = None
    seen = set()
    for seed in range(1, 8):
        run = Session(seed=seed)
        if not _make_them_shout(run, scene.FAR):
            continue
        who = run.rescue.calling(run.frame, scene.FAR)
        assert who
        assert run.door_calls
        cells = tuple(run.door_calls[0])
        if door is None:
            door = cells
        assert cells == door, "the word moved with the person shouting"
        seen |= {id(w) for w in who}
        # Their own call cells belong to the far room's field. Nothing about
        # where they are standing reaches this room.
        for cx, cy in {cell for w in who for cell in w.call_cells()}:
            assert run.places[scene.FAR].field.level_at(cx, cy) == lighting.LIT
            if cx < COLS - len(rescue_mod.CALL):
                assert run.field.level_at(cx, cy) != lighting.LIT, \
                    "a far-room caller lit a cell in the near room"
    assert door is not None
    assert len(seen) > 1, "only ever heard the same person, so nothing is shown"


def _three_rooms():
    """A -- B -- C in a line, with everybody trapped in C.

    Room `a` is the one the player starts in and the one with the way out; the
    only people in the building are two doors away.
    """
    from spikes import building as B
    empty = tuple("#" * COLS if cy in (0, 21) else
                  ("#" if cy not in scene.DOOR_ROWS else ".")
                  + "." * (COLS - 2)
                  + ("#" if cy not in scene.DOOR_ROWS else ".")
                  for cy in range(22))
    with_exit = tuple(("D" + line[1:]) if cy in (10, 11) else line
                      for cy, line in enumerate(empty))
    a = B.Room("a", with_exit, player_start=(16 * CELL, 5 * CELL),
               doorways=(B.Doorway(B.EAST, scene.DOOR_ROWS, 1),))
    b = B.Room("b", empty,
               doorways=(B.Doorway(B.WEST, scene.DOOR_ROWS, 0),
                         B.Doorway(B.EAST, scene.DOOR_ROWS, 2)))
    c = B.Room("c", empty, workers=((16 * CELL, 5 * CELL, 30),),
               doorways=(B.Doorway(B.WEST, scene.DOOR_ROWS, 1),))
    return B.Building((a, b, c))


def test_only_the_adjacent_room_carries(monkeypatch):
    """One of the three limits that keep the rule honest, and the one that
    stops a dark building becoming a map read by ear.

    A third room is two doors away and says nothing. It falls out of how the
    rule is written rather than being enforced: the session walks **this**
    room's own doorways and asks about the room on the other side of each, so
    there is no path, no search and nothing to propagate.
    """
    house = _three_rooms()
    monkeypatch.setattr(scene, "BUILDING", house)
    a, b, c = 0, 1, 2

    run = Session(seed=1)
    assert run.here == a
    assert run.total == 1
    heard_in_a = False
    for _ in range(4000):
        run.step()
        heard_in_a = heard_in_a or bool(run.door_calls)
        if run.over is not None:
            break
    assert not heard_in_a, "a call carried two doors"

    # Standing one room closer, the same call arrives.
    run = Session(seed=1)
    run.here = b
    run.place.enter()
    heard_in_b = False
    for _ in range(4000):
        run.step()
        if run.door_calls:
            heard_in_b = True
            break
        if run.over is not None:
            break
    assert heard_in_b, "a call did not carry through the one door it should"


def test_a_call_only_carries_while_somebody_is_actually_shouting():
    """It leaves no trace: the word is on screen for as long as a call lasts and
    then the doorway is dark again."""
    run = Session(seed=1)
    assert _make_them_shout(run, scene.FAR)
    assert run.door_calls
    for _ in range(rescue_mod.CALL_FRAMES + 2):
        run.step()
        if not run.rescue.calling(run.frame, scene.FAR):
            break
    assert not run.rescue.calling(run.frame, scene.FAR)
    assert not run.door_calls
    door = run.place.room.doorways[0]
    assert run.field.level_at(door.column, door.middle) != lighting.LIT \
        or run.cone.lit, "the doorway stayed lit after the shout"


def test_a_call_through_a_doorway_draws_no_clegs():
    """A shout is not a light. It reveals nobody and lures nothing, and that
    holds unchanged when the cells it lifts are a doorway's."""
    run = Session(seed=1)
    assert _make_them_shout(run, scene.FAR)
    assert run.door_calls
    door_cells = {c for cells in run.door_calls for c in cells}
    own = run._own_lures(run.place)
    assert not any((lx, ly) in door_cells for lx, ly, _r, _k in own), \
        "the shout became a lure"


def test_a_death_in_the_room_behind_you_is_heard_through_the_doorway():
    """The reason this rule got sharper than when it was written. A follower
    eaten in the dark is invisible **and** inaudible -- the sonar skips attached
    flies -- so the death beat carried over the doorway is the only thing left
    that says a number went down for a reason.
    """
    run = at_door(Session(seed=1))
    walk(run, 1, 16)
    assert run.here == scene.FAR
    run.calls_on = False                 # silence the living, so this is a death
    doomed = next(w for w in run.rescue.workers if w.room == scene.NEAR)
    doomed.blood = 1
    for _ in range(rescue_mod.BLEED_EVERY + 2):
        run.step()
        if doomed.state == rescue_mod.DEAD:
            break
    assert doomed.state == rescue_mod.DEAD
    run.calls_on = True
    run.step()
    assert run.door_calls, "a death in the room behind you said nothing"


def test_the_word_over_the_doorway_is_drawn_on_screen():
    """All the way to pixels, because a rule the player cannot see is not a
    rule they can learn."""
    run = Session(seed=1)
    assert _make_them_shout(run, scene.FAR)
    assert run.door_calls
    screen = Screen()
    run.draw(screen)
    for cx, cy in run.door_calls[0]:
        assert any(screen.point(cx * CELL + dx, cy * CELL + dy)
                   for dy in range(CELL) for dx in range(CELL)), \
            f"nothing was drawn at {cx},{cy}"


@pytest.mark.parametrize("calls_on", (True, False))
def test_the_debug_switch_silences_the_doorway_too(calls_on):
    """A switch labelled "workers call for help" that leaves one kind of
    shouting running is a liar -- the same argument the death beat is held to."""
    run = Session(seed=1)
    run.calls_on = calls_on
    heard = False
    for _ in range(3000):
        run.step()
        heard = heard or bool(run.door_calls)
        if heard:
            break
    assert heard is calls_on


# --- the population is the building's ----------------------------------------

def test_the_building_is_inside_the_entity_budget():
    """Six flies and a tail of four in one room with the player is
    6 + (5 x 1.75) = 14.75 Cleg-equivalents against a ceiling of eighteen,
    which leaves the three and a quarter a hatching nest needs.

    **The count is the building's, not a room's**: Clegs cross doorways and go
    to light, so a room's authored population is not its worst case.
    """
    run = Session(seed=1)
    flies = len(run.swarm.clegs)
    assert flies == 6
    worst = flies * 4 + (1 + 4) * 7          # quarters, to stay in integers
    assert worst <= 18 * 4, f"{worst / 4} Cleg-equivalents against 18"
