"""The reveal bit and the prey bit are two bits, and the held view sets one.

Issue #64 split them: reveal and prey were one bit, and the opening flash --
the room lit for twelve frames on first entry -- needed to show the people
without handing them to the swarm. **Issue #79 removed the opening flash**:
no room is ever shown whole. What is left with the reveal bit and not the
prey bit is `sources.Floodlight`, the `F` debug view, the gallery's lit-room
sheets and the tests that light a room to measure something -- and the rule
that nothing in play sets it.

The tests below are what survives of the flash's file: the two bits in the
field, the sources that set both, the room lights that set neither, and the
held view that sets the first alone.
"""

from spikes import lighting, sources
from spikes.session import Intent, Session
from spotlight.core.constants import CELL, COLS, SCREEN_W
from spotlight.core.screen import Screen
from spikes.layout import PLAY_ROWS


def _ink_in(screen: Screen, x: int, y: int, height: int = 16) -> int:
    """Pixels set inside an 8-wide box at pixel (x, y)."""
    return sum(screen.pixels[(y + dy) * SCREEN_W + x + dx]
               for dy in range(height) for dx in range(CELL)
               if 0 <= y + dy < 22 * CELL and 0 <= x + dx < SCREEN_W)


# --- nothing in play lights a room whole ------------------------------------

def test_a_room_is_never_shown_whole_on_entry():
    """Issue #79. The first frames of a run light what the glow lights and
    what the room's own lights light, and nothing else."""
    run = Session(seed=1)
    for _ in range(3):
        run.step()
        assert not run.place.floodlight.enabled
        lit = {(cx, cy) for cx in range(COLS) for cy in range(PLAY_ROWS)
               if run.field.level_at(cx, cy) == lighting.LIT}
        assert len(lit) < COLS * PLAY_ROWS // 4, "most of the room is lit on entry"


def test_nobody_is_drawn_or_prey_in_the_dark_on_entry():
    """Where the flash used to show every worker on frame one, a worker well
    off in the dark is now neither drawn nor prey."""
    run = Session(seed=1)
    run.step()
    screen = Screen()
    run.draw(screen)
    here = [w for w in run.rescue.workers if w.room == run.here]
    in_the_dark = [w for w in here
                   if not any(run.field.reveals_at(*c) for c in w.cells())]
    assert in_the_dark, "every worker in the room is shown on frame one"
    for worker in in_the_dark:
        assert _ink_in(screen, worker.x, worker.y) == 0
        assert worker not in run._lit_people(run.place)


def test_the_same_worker_under_the_beam_is_both_drawn_and_prey():
    """The rule: under the beam, *if you can see them, so can the flies*.
    (It was the player's torch that lit them until issue #119.)"""
    run = Session(seed=1)
    run.step()
    worker = next(w for w in run.rescue.workers if w.room == run.here)
    beam = run.place.roaming
    beam.mode = beam.DRIFT
    beam.x, beam.y = worker.cell()
    beam.update = lambda: None
    run.step(Intent())
    assert any(run.field.reveals_at(*c) for c in worker.cells())
    assert worker in run._lit_people(run.place)


def test_the_same_worker_under_a_room_light_is_neither():
    """Room lights show the room and not who is in it, to the player and to
    the flies."""
    run = Session(seed=1)
    # The room's beam off: the claim is the room light's, and since issue
    # #116 each beam has its own entry, which on this seed opens on the
    # worker and would reveal them.
    run.place.roaming.enabled = False
    run.step()
    worker = next(w for w in run.rescue.workers if w.room == run.here)
    cx, cy = worker.cell()
    run.place.room_lights.append(sources.RoomLight(cx - 1, cy - 2, 3, 3))
    run.step()
    assert all(run.field.level_at(*c) == lighting.LIT for c in worker.cells())
    assert not any(run.field.reveals_at(*c) for c in worker.cells())
    assert worker not in run._lit_people(run.place)


def _prey_held(seed: int, frames: int, hold: bool, prey: bool = False):
    """Who is prey after `frames` steps, with the debug view held or not."""
    run = Session(seed=seed)
    run.step()
    run.place.floodlight.hold(hold)
    for _ in range(frames):
        run.place.floodlight.prey = prey
        run.step()
    return run, [run.rescue.workers.index(w)
                 for w in run._lit_people(run.place)]


def test_the_held_debug_view_reveals_and_makes_no_prey():
    """**The thing that had been wrong all along.** `F` held the room lit and
    everybody in it drawn, and made every one of them prey, because the reveal
    bit was the prey bit. Its docstring said the swarm behaved as it would in
    the dark. Now it does: the same frame with and without the hold has the
    same prey list, and with the old one-bit behaviour put back it has
    everybody in the room on it."""
    held, prey = _prey_held(1, 5, hold=True)
    here = [w for w in held.rescue.workers if w.room == held.here]
    for worker in here:
        assert all(held.field.reveals_at(*c) for c in worker.cells()), \
            "the held view shows nobody"
    _dark, in_the_dark = _prey_held(1, 5, hold=False)
    assert prey == in_the_dark, "the hold changed who is prey"
    _old, old_way = _prey_held(1, 5, hold=True, prey=True)
    assert set(old_way) == {held.rescue.workers.index(w) for w in here}, \
        "the prey bit is not what the hold used to set"


def test_the_prey_flag_is_cleared_every_frame_like_the_reveal_flag():
    """No state survives the frame. The fade is still one byte per cell."""
    f = lighting.LightField()
    f.begin(); f.add(5, 5, lighting.LIT, lighting.CHARGE_LIT); f.commit()
    assert f.prey_at(5, 5) and f.reveals_at(5, 5)
    f.begin(); f.commit()
    assert not f.prey_at(5, 5) and not f.reveals_at(5, 5)
    assert f.level_at(5, 5) == lighting.LIT, "the memory is the fade's"


def test_prey_reads_the_prey_flag_and_nothing_else():
    """A source that reveals and does not make prey, at full brightness, on
    a cell nobody else lights: revealed, not prey. And the other way round is
    not a thing -- a light cannot make prey of somebody it does not show."""
    f = lighting.LightField()
    f.begin()
    f.add(5, 5, lighting.LIT, lighting.CHARGE_LIT, reveals=True, prey=False)
    f.commit()
    assert f.reveals_at(5, 5) and not f.prey_at(5, 5)
    f.begin()
    f.add(5, 5, lighting.LIT, lighting.CHARGE_LIT, reveals=False, prey=True)
    f.commit()
    assert not f.reveals_at(5, 5)
    # `prey=True` on a hiding light is allowed by the signature and asked
    # for by nobody; it is recorded here as a combination no source uses.
    assert f.prey_at(5, 5)


def test_every_source_but_the_held_view_sets_both_bits():
    """The rule, source by source, so a new one cannot quietly split them."""
    assert sources.Glow().reveals and sources.Glow().prey
    roam = sources.Roaming(0, 0, radius=3)
    assert roam.reveals and roam.prey
    room = sources.RoomLight(0, 0, 3, 3)
    assert not room.reveals and not room.prey
    held = sources.Floodlight()
    held.hold(True)
    assert held.reveals and not held.prey
