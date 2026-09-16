"""The searchlight magnet: caught in the beam, you are hunted for ten seconds.

Issue #82, from the vault's *The searchlight magnet*. The pins the note asks
for, one section each: the hit test, the counter, the steering, the moment
and its flash, the billing, and the switch that makes the rule off the tree
before it.
"""

import pytest

from spikes import clegs as C, lighting, moments as M, scene, session as S, sources
from spikes.session import Intent, Session
from spotlight.core.constants import CELL


def _fresh(seed: int = 1) -> Session:
    """A run one frame in, with the beam parked so it cannot drift."""
    run = Session(seed=seed)
    run.step()
    beam = run.place.roaming
    assert beam is not None, "the near room has no searchlight"
    beam.step_every = 10 ** 6
    return run


def _beam_at(run, dx: int, dy: int) -> None:
    """Park the beam so the player's feet cell is (dx, dy) from its centre."""
    beam = run.place.roaming
    beam.x, beam.y = run.player.cx - dx, run.player.cy - dy


def _beam_away(run) -> None:
    beam = run.place.roaming
    beam.x, beam.y = (run.player.cx + 20) % 30 + 1, (run.player.cy + 10) % 20 + 1
    assert not run.beam_on_player()


def _lone_fly(run, cx: int, cy: int, **attrs) -> C.Cleg:
    """The room's swarm replaced by one fly, hunting, with nothing in its head."""
    fly = C.Cleg(cx, cy, seed=5)
    fly.step_every = 1
    for name, value in attrs.items():
        setattr(fly, name, value)
    run.place.swarm.clegs[:] = [fly]
    return fly


# --- the hit test ------------------------------------------------------------

def test_the_feet_cell_on_the_discs_edge_is_a_hit_and_the_head_alone_is_not():
    run = _fresh()
    r = run.place.roaming.radius
    _beam_at(run, r, 0)
    assert run.beam_on_player(), "on the edge of the disc, where the floor is lit"
    _beam_at(run, r + 1, 0)
    assert not run.beam_on_player()
    # Straight up the screen by r + 1: the head cell (one above the feet) is
    # exactly r from the centre and inside; the feet are not. Not a hit.
    _beam_at(run, 0, r + 1)
    assert not run.beam_on_player(), "the head cell alone is a hit"
    _beam_at(run, 0, r)
    assert run.beam_on_player()


def test_a_switched_off_searchlight_hits_nobody():
    run = _fresh()
    _beam_at(run, 0, 0)
    assert run.beam_on_player()
    run.place.roaming.enabled = False
    assert not run.beam_on_player()


def test_no_other_light_is_a_hit():
    """The cone on, a room light and a floor lamp on the player's own cells,
    and the beam across the room: nothing gives you away but the beam."""
    from spikes.session import FloorLight
    run = _fresh()
    _beam_away(run)
    cx, cy = run.player.cx, run.player.cy
    run.place.room_lights.append(sources.RoomLight(cx - 1, cy - 2, 3, 3))
    run.kit.floor.append(FloorLight(cx, cy, power=9000, lit=True, room=run.here))
    run.step(Intent(torch=True))
    assert run.cone.lit
    assert run.field.level_at(cx, cy) == lighting.LIT, "the player is not even lit"
    assert not run.beam_on_player()
    assert run.magnet == 0


# --- the counter -------------------------------------------------------------

def test_a_hit_sets_the_counter_and_logs_once_on_the_rising_edge():
    run = _fresh()
    _beam_at(run, 0, 0)
    before = len(run.log)
    run.step()
    assert run.magnet == S.MAGNET_FRAMES == 500
    events = [e for e in run.log[before:] if e.kind == S.MAGNET]
    assert len(events) == 1 and events[0].frame == run.frame
    # Standing in the beam: hit every frame, set to 500 every frame, logged
    # never again.
    for _ in range(50):
        run.step()
        assert run.magnet == 500
    assert len([e for e in run.log if e.kind == S.MAGNET]) == 1


def test_a_second_hit_sets_the_counter_and_does_not_add_to_it():
    run = _fresh()
    _beam_at(run, 0, 0)
    run.step()
    _beam_away(run)
    for _ in range(100):
        run.step()
    assert run.magnet == 400
    _beam_at(run, 0, 0)
    run.step()
    assert run.magnet == 500, "a second hit added to the counter"


def test_the_ten_seconds_run_from_the_last_sighting():
    run = _fresh()
    _beam_at(run, 0, 0)
    for _ in range(200):
        run.step()
    _beam_away(run)
    frames = 0
    while run.magnet:
        run.step()
        frames += 1
    assert frames == 500
    # And the end is not a new event.
    assert len([e for e in run.log if e.kind == S.MAGNET]) == 1


def test_death_clears_the_counter_and_a_doorway_keeps_it():
    run = _fresh()
    _beam_at(run, 0, 0)
    run.step()
    assert run.magnet == 500
    run.blood = 0
    run.step()
    assert run.lives == S.LIVES - 1
    assert run.magnet == 0, "a death did not clear the magnet"

    from test_spike_doorway import at_door, walk
    run = at_door(Session(seed=1))
    run.magnet = 400
    walk(run, 1, 16)
    assert run.here == scene.FAR
    assert 380 <= run.magnet < 400, "the doorway lost the magnet"


# --- the steering ------------------------------------------------------------

def test_a_hunting_fly_in_the_dark_beyond_its_notice_comes_for_the_player():
    """Across the room, torch off, outside its own notice range: the frame
    after the magnet is on, its goal is the player's cell and it is billed to
    the magnet; a few frames on it is closer than it was."""
    run = _fresh()
    _beam_away(run)
    px, py = run.player.cx, run.player.cy
    fx, fy = (2 if px > 15 else 29), (2 if py > 10 else 19)
    fly = _lone_fly(run, fx, fy, notice=2)
    run.step()
    assert fly.goal is None, "the fly can see the player in the dark"
    run.magnet = 500
    run.step()
    assert fly.goal == (px, py)
    assert fly.goal_source == sources.LURE_MAGNET
    d0 = abs(fly.cx - px) + abs(fly.cy - py)
    for _ in range(12):
        run.step()
    assert abs(fly.cx - px) + abs(fly.cy - py) < d0, "it did not come"


def test_a_sated_fly_and_an_attached_fly_are_left_alone():
    run = _fresh()
    _beam_away(run)
    px, py = run.player.cx, run.player.cy
    sated = C.Cleg(2, 2, seed=7)
    sated.state, sated._timer = C.SATED, 10 ** 6
    riding = C.Cleg(px, py, seed=9)
    riding.state = C.ATTACHED
    run.place.swarm.clegs[:] = [sated, riding]
    run.magnet = 500
    for _ in range(5):
        run.step()
    assert sated.state == C.SATED and sated.goal is None
    assert riding.state == C.ATTACHED and riding.goal is None


def test_the_magnet_is_offered_next_door_as_door_spill_only():
    """The room next door sees the magnet as light through the doorway --
    a lure standing on the threshold, of the magnet's kind -- and as nothing
    else; with the magnet off the doorway carries no such thing."""
    run = _fresh()
    far = run.places[scene.FAR]

    def spill_kinds():
        own = [run._own_lures(place) for place in run.places]
        return {lure[3] for lure in run._doors(far, own)}

    assert sources.LURE_MAGNET not in spill_kinds()
    run.magnet = 500
    assert sources.LURE_MAGNET in spill_kinds() or run._own_lures(run.place)[-1][3] == sources.LURE_MAGNET
    # The far room's own list never carries it: the magnet is the player's
    # room's, and the player is not there.
    assert all(lure[3] != sources.LURE_MAGNET for lure in run._own_lures(far))


# --- the moment and its flash ------------------------------------------------

def test_the_moment_is_raised_once_per_rising_edge_with_no_cells_and_no_pause():
    run = _fresh()
    _beam_at(run, 0, 0)
    run.step()
    raised = [cells for name, cells in run.moments.raised if name == M.M_MAGNET]
    assert raised == [()], raised
    assert M.MOMENTS[M.M_MAGNET].pause == 0 and M.MOMENTS[M.M_MAGNET].frames == 0
    assert M.MOMENTS[M.M_MAGNET].strip == () and M.MOMENTS[M.M_MAGNET].priority == 1
    assert not M.MOMENTS[M.M_MAGNET].state_flash, "the tell is not a flash (#84)"
    for _ in range(20):
        run.step()
        assert not [n for n, _c in run.moments.raised if n == M.M_MAGNET]
    # Off, and on again: a second rising edge, a second moment.
    _beam_away(run)
    run.magnet = 0
    run.step()
    _beam_at(run, 0, 0)
    run.step()
    assert [n for n, _c in run.moments.raised if n == M.M_MAGNET] == [M.M_MAGNET]


def _box_pixels(run) -> set:
    """Where the box's line would be for the player's figure right now."""
    from spotlight.core.screen import Screen
    from spikes import sprites
    blank = Screen()
    sprites.draw_box(blank, sprites.PLAYER_FRAMES[run.player.stride],
                     run.player.x, run.player.y)
    return {i for i, p in enumerate(blank.pixels) if p}


def _drawn(run):
    """The screen as the run draws it, and how many of the figure's own
    pixels and of its box's line are set on it."""
    from spotlight.core.screen import Screen
    from spikes import sprites
    screen = Screen()
    run.draw(screen)
    figure = sprites.PLAYER_FRAMES[run.player.stride]
    x, y = run.player.x, run.player.y
    own = sum(1 for dy, row in enumerate(figure) for dx in range(8)
              if row & (0x80 >> dx) and screen.point(x + dx, y + dy))
    box = _box_pixels(run)
    return screen, own, sum(bin(r).count("1") for r in figure), \
        sum(1 for i in box if screen.pixels[i]), len(box)


def test_the_figure_is_boxed_on_the_on_frames_while_the_counter_runs():
    """**The tell is shape, not colour** (issues #84, #100). On an on-phase
    frame a closed box is set round the figure and the figure is intact; on
    an off-phase frame it is not there; after the counter ends it is not
    there on any frame. No attribute changes for it."""
    run = _fresh()
    _beam_at(run, 0, 0)
    run.step(Intent(torch=True))
    assert run.magnet == 500
    seen = {0: [], 1: []}
    for _ in range(2 * S.MAGNET_PULSE):
        _screen, own, own_all, on, total = _drawn(run)
        assert own == own_all, "the figure lost pixels to its box"
        phase = (run.frame // S.MAGNET_PULSE) % 2
        seen[phase].append(on == total if phase == 0 else on < total // 2)
        run.step(Intent(torch=True))
    assert seen[0] and all(seen[0]), seen
    assert seen[1] and all(seen[1]), seen
    assert not (set(run.player.body_cells()) & run.flash_cells())
    _beam_away(run)
    run.magnet = 1
    run.step()
    assert run.magnet == 0
    for _ in range(2 * S.MAGNET_PULSE):
        _screen, _own, _all, on, total = _drawn(run)
        assert on < total // 2, "still boxed after it ended"
        run.step()


def test_the_box_sits_two_clear_of_the_drawn_figure_with_its_margin_cleared():
    """The line two pixels clear of the figure's extent on every side, the
    pixel either side of it cleared, and nothing inside the margin touched
    -- which is what makes it read on a lit stipple pool."""
    from spikes import sprites
    from spotlight.core.screen import Screen
    frame = sprites.PLAYER_FRAMES[0]
    top, bottom = sprites.extent(frame)
    x, y = 80, 80
    screen = Screen()
    # A stippled ground: every pixel set, so what the box clears shows.
    for py in range(60, 110):
        for px in range(60, 110):
            screen.pixels[py * 256 + px] = 1
    sprites.draw_box(screen, frame, x, y)
    left, right = x - sprites.BOX_GAP - 1, x + 8 + sprites.BOX_GAP
    t, b = y + top - sprites.BOX_GAP - 1, y + bottom + sprites.BOX_GAP + 1
    for px in range(left, right + 1):
        assert screen.point(px, t) and screen.point(px, b), "the line is broken"
        assert not screen.point(px, t - 1) and not screen.point(px, b + 1)
    for py in range(t, b + 1):
        assert screen.point(left, py) and screen.point(right, py)
        assert not screen.point(left - 1, py) and not screen.point(right + 1, py)
    # The inner margin, clear of the corners where the two lines meet.
    for px in range(left + 2, right - 1):
        assert not screen.point(px, t + 1) and not screen.point(px, b - 1)
    for py in range(t + 2, b - 1):
        assert not screen.point(left + 1, py) and not screen.point(right - 1, py)
    # Inside the margin: untouched stipple.
    assert screen.point(x + 3, y + top + 2)
    assert not hasattr(sprites, "draw_brackets"), "the brackets were kept"


# --- billing -----------------------------------------------------------------

def _fed_under_magnet(journey_source=None) -> Session:
    run = _fresh()
    _beam_away(run)
    px, py = run.player.cx, run.player.cy
    fly = _lone_fly(run, px - 2, py)
    if journey_source is not None:
        fly.goal, fly.goal_source = (px - 4, py), journey_source
    run.magnet = 500
    for _ in range(40):
        run.step()
        if run.swarm.attachments:
            break
    assert run.swarm.attachments == 1, "the fly never reached the player"
    return run


def test_a_bite_under_the_magnet_is_billed_to_the_magnet():
    run = _fed_under_magnet()
    assert run.swarm.bites_by_source[sources.LURE_MAGNET] == 1
    assert sources.LURE_NAMES[sources.LURE_MAGNET] == "magnet"
    assert len(sources.LURE_NAMES) == sources.LURE_KINDS == 7


def test_a_fly_on_a_beam_journey_is_rebilled_to_the_magnet():
    run = _fed_under_magnet(journey_source=sources.LURE_BEAM)
    assert run.swarm.bites_by_source[sources.LURE_MAGNET] == 1
    assert run.swarm.bites_by_source[sources.LURE_BEAM] == 0


# --- the switch ----------------------------------------------------------------

def test_with_the_rule_off_the_beam_gives_nobody_away():
    run = Session(seed=1, magnet=False)
    run.step()
    run.place.roaming.step_every = 10 ** 6
    _beam_at(run, 0, 0)
    assert run.beam_on_player(), "the geometry still says so"
    for _ in range(50):
        run.step()
    assert run.magnet == 0
    assert not [e for e in run.log if e.kind == S.MAGNET]
    assert not [n for n, _c in run.moments.raised if n == M.M_MAGNET]


# --- the whole building, and the sated wake (issue #88) ----------------------

def test_a_fly_in_the_far_room_is_handed_the_doorway_and_comes_through():
    """Building scope: with the player magnetised in the near room, a hunting
    fly deep in the far room has the far room's threshold to the near room
    as its goal, walks to it, and is handed over."""
    run = _fresh()
    _beam_away(run)
    far = run.places[scene.FAR]
    door = next(d for d in far.room.doorways if d.to == scene.NEAR)
    fly = C.Cleg(20, 4, seed=5)
    fly.step_every = 1
    far.swarm.clegs[:] = [fly]
    run.step()
    assert fly.goal is None, "the far room's fly can see the player from next door"
    run.magnet = 500
    run.step()
    assert fly.goal == (door.beyond, door.middle)
    assert fly.goal_source == sources.LURE_MAGNET
    for _ in range(300):
        run.step()
        if fly in run.place.swarm.clegs:
            break
    assert fly in run.place.swarm.clegs, "it never crossed into the player's room"
    run.step()                     # its first tick in the player's room
    assert fly.goal == (run.player.cx, run.player.cy)


def test_a_hit_wakes_every_sated_fly_in_the_building_once():
    run = _fresh()
    _beam_away(run)
    near = C.Cleg(3, 3, seed=7)
    far = C.Cleg(20, 4, seed=9)
    for fly in (near, far):
        fly.state, fly._timer = C.SATED, 10 ** 6
    run.place.swarm.clegs[:] = [near]
    run.places[scene.FAR].swarm.clegs[:] = [far]
    run.step()
    assert near.state == C.SATED and far.state == C.SATED
    _beam_at(run, 0, 0)
    run.step()                                    # the rising edge
    assert near.state == C.HUNTING and far.state == C.HUNTING, "nobody woke"
    # Sated again during the magnet -- a bite, say -- and the beam still on
    # the player: not woken again until the magnet has ended and a new hit
    # comes.
    near.state, near._timer = C.SATED, 10 ** 6
    for _ in range(20):
        run.step()
        assert run.magnet == 500
    assert near.state == C.SATED, "a hit frame woke a fly that had just fed"
    _beam_away(run)
    run.magnet = 0
    run.step()
    _beam_at(run, 0, 0)
    run.step()
    assert near.state == C.HUNTING, "a second rising edge did not wake it"


def test_a_fly_sated_by_a_bite_under_the_magnet_keeps_its_ten_seconds():
    run = _fed_under_magnet()
    fly = run.place.swarm.clegs[0]
    for _ in range(200):
        run.step()
        if fly.state == C.SATED:
            break
    assert fly.state == C.SATED, "it never finished feeding"
    for _ in range(100):
        run.step()
    assert fly.state == C.SATED, "the running magnet woke it"
