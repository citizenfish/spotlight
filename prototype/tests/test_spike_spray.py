"""Flyspray: lingering patches, charges, and what they kill."""

from types import SimpleNamespace

from spikes import scene
from spikes import sources as S
from spikes.layout import PLAY_ROWS
from spikes.session import Intent, Session
from spikes.spray import PATCH_FRAMES, Spray, patch_cells
from spotlight.core.constants import CELL, COLS


def _cleg(cx, cy):
    return SimpleNamespace(cx=cx, cy=cy)


# --- laying a patch --------------------------------------------------------

def test_the_patch_lands_ahead_in_the_facing_direction():
    for facing, (fx, fy) in ((S.RIGHT, (1, 0)), (S.LEFT, (-1, 0)),
                             (S.UP, (0, -1)), (S.DOWN, (0, 1))):
        cells = set(patch_cells(10, 10, facing))
        assert (10 + fx, 10 + fy) in cells, f"nothing ahead facing {facing}"
        assert (10 - fx, 10 - fy) not in cells, f"sprayed behind, facing {facing}"


def test_you_do_not_spray_your_own_cell():
    for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
        assert (10, 10) not in set(patch_cells(10, 10, facing))


def test_the_patch_is_clipped_at_the_room_edge():
    for cells in (patch_cells(0, 0, S.LEFT), patch_cells(COLS - 1, PLAY_ROWS - 1,
                                                         S.DOWN)):
        for cx, cy in cells:
            assert 0 <= cx < COLS and 0 <= cy < PLAY_ROWS


def test_firing_lays_ground_that_covers():
    sp = Spray(charges=3)
    assert sp.fire(10, 10, S.RIGHT) is True
    assert sp.covers(11, 10)
    assert not sp.covers(9, 10)


# --- charges ---------------------------------------------------------------

def test_charges_run_out():
    sp = Spray(charges=2)
    assert sp.fire(5, 5, S.UP) is True
    assert sp.fire(5, 5, S.UP) is True
    assert sp.empty
    assert sp.fire(5, 5, S.UP) is False


def test_a_failed_shot_lays_nothing():
    sp = Spray(charges=0)
    sp.fire(5, 5, S.UP)
    assert not sp.patches


# --- lingering -------------------------------------------------------------

def test_a_patch_expires():
    sp = Spray()
    sp.fire(10, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES - 1):
        sp.tick()
    assert sp.covers(11, 10), "cleared too early"
    sp.tick()
    assert not sp.covers(11, 10)


def test_respraying_refreshes_rather_than_stacking():
    """There is no such thing as doubly-poisoned ground."""
    sp = Spray(charges=5)
    sp.fire(10, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES // 2):
        sp.tick()
    sp.fire(10, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES - 1):
        sp.tick()
    assert sp.covers(11, 10), "refresh did not reset the clock"


def test_patches_expire_independently():
    sp = Spray(charges=5)
    sp.fire(10, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES // 2):
        sp.tick()
    sp.fire(20, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES // 2 + 1):
        sp.tick()
    assert not sp.covers(11, 10), "the older patch should have gone"
    assert sp.covers(21, 10), "the newer patch should remain"


# --- killing ---------------------------------------------------------------

def test_clegs_standing_in_spray_die():
    sp = Spray()
    sp.fire(10, 10, S.RIGHT)
    inside, outside = _cleg(11, 10), _cleg(2, 2)
    assert sp.kills([inside, outside]) == [inside]


def test_nothing_dies_once_the_patch_has_cleared():
    sp = Spray()
    sp.fire(10, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES):
        sp.tick()
    assert sp.kills([_cleg(11, 10)]) == []


def test_an_empty_sprayer_kills_nothing():
    sp = Spray(charges=0)
    sp.fire(10, 10, S.RIGHT)
    assert sp.kills([_cleg(11, 10)]) == []


# --- poison lies on floor, not on wall (issue #41) --------------------------

def _wall(*cells):
    """An `is_solid` that calls exactly the named cells wall."""
    solid = set(cells)
    return lambda x, y: (x, y) in solid


def test_a_burst_lays_no_poison_inside_a_wall():
    """Nothing can stand in a wall, so poison there kills nothing and the
    drawing still colours it -- the wall took the spray's stipple and hue."""
    ahead = set(patch_cells(10, 10, S.RIGHT))
    walled = set(patch_cells(10, 10, S.RIGHT, _wall(*ahead)))
    assert walled == set(), "sprayed the whole wall"

    part = _wall((11, 9), (12, 9))
    cells = set(patch_cells(10, 10, S.RIGHT, part))
    assert (11, 9) not in cells and (12, 9) not in cells
    assert (11, 10) in cells, "dropped floor along with the wall"


def test_dropping_wall_cells_only_ever_shrinks_a_patch():
    """A shape change would move cells; this one may only remove them."""
    for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
        open_ground = set(patch_cells(10, 10, facing))
        for wall in open_ground:
            got = set(patch_cells(10, 10, facing, _wall(wall)))
            assert got == open_ground - {wall}, \
                f"facing {facing}: dropping {wall} changed the rest"


def test_no_burst_anywhere_in_the_building_lands_on_wall():
    """The measurement in issue #41, generalised over every room, every cell a
    person can stand in and every facing.

    The reported case was the main room from (2, 1) -- four of six cells wall.
    Issue #41 names the facing as **down**, which is wrong: from (2, 1) facing
    down every cell is clear floor. It is facing **left** that lands four of
    six on the west wall, and facing up that lands three of three.
    """
    for room in scene.BUILDING.rooms:
        for cy in range(1, PLAY_ROWS):
            for cx in range(COLS):
                if room.is_solid(cx, cy) or room.is_solid(cx, cy - 1):
                    continue  # nobody two cells tall can stand here
                for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
                    for cell in patch_cells(cx, cy, facing, room.is_solid):
                        assert not room.is_solid(*cell), \
                            f"{room.name}: ({cx},{cy}) facing {facing} " \
                            f"sprayed wall at {cell}"


def test_the_reported_wall_case_is_now_clean():
    """Main room, (2, 1), facing left: four of six cells were wall."""
    room = scene.BUILDING.rooms[0]
    before = patch_cells(2, 1, S.LEFT)
    assert sum(room.is_solid(*c) for c in before) == 4, \
        "the fault this fixes has moved; re-measure before trusting the test"
    after = patch_cells(2, 1, S.LEFT, room.is_solid)
    assert len(after) == 2
    assert set(after) < set(before), "the patch grew or moved"


def test_a_charge_fired_at_a_wall_lays_nothing_and_is_still_spent():
    """The player's mistake stands. Whether firing into a wall should refund
    or warn is a design question and is deliberately not settled here."""
    run = Session(seed=1)
    # Backed against the west wall of the main room, facing into it.
    run.player.x, run.player.y = 1 * CELL, 12 * CELL
    run.player.facing = S.LEFT
    assert (run.player.cx, run.player.cy) == (1, 13)
    charges = run.spray.charges
    run.step(Intent(spray=True))
    assert run.spray.charges == charges - 1, "the charge was refunded"
    assert run.spray.cells_in(run.here) == [], "poison laid inside the wall"


def test_a_patch_laid_in_a_room_never_covers_a_solid_cell():
    """Whatever route a patch takes into `patches`, it is on floor."""
    run = Session(seed=1)
    room = run.place.room
    for cy, cx, facing in ((13, 1, S.LEFT), (1, 5, S.RIGHT), (2, 2, S.UP),
                           (10, 20, S.DOWN)):
        if room.is_solid(cx, cy) or room.is_solid(cx, cy - 1):
            continue
        run.spray.charges = 5
        run.player.x, run.player.y = cx * CELL, (cy - 1) * CELL
        run.player.facing = facing
        run.spray.fire(run.player.cx, run.player.cy, facing, run.here,
                       run.is_solid)
        for cell in run.spray.cells_in(run.here):
            assert not room.is_solid(*cell), f"({cx},{cy}) {facing}: {cell}"
