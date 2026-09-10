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
    drawing still colours it -- the wall took the spray's stipple and hue.

    Since issue #44 a refused cell is not simply lost: it falls back one step
    toward the player. So the assertion here is the one the fault was about --
    **no cell the room calls solid is ever laid** -- and not the stronger
    "lays nothing at all", which the rebound deliberately withdrew.
    """
    ahead = set(patch_cells(10, 10, S.RIGHT))
    wall = _wall(*ahead)
    walled = set(patch_cells(10, 10, S.RIGHT, wall))
    assert not any(wall(*c) for c in walled), "sprayed the wall"
    assert walled == {(10, 9), (10, 11)}, \
        "a burst into solid wall should fall back level with the player"

    part = _wall((11, 9), (12, 9))
    cells = set(patch_cells(10, 10, S.RIGHT, part))
    assert (11, 9) not in cells and (12, 9) not in cells
    assert (11, 10) in cells, "dropped floor along with the wall"


def test_a_blocked_cell_is_replaced_by_the_cell_one_step_nearer():
    """**Superseded.** Until issue #44 this test read *dropping wall cells only
    ever shrinks a patch*: a blocked cell was removed and nothing took its
    place. The rebound is the design decision that withdrew that, so the
    invariant is now the weaker and exact one -- a blocked cell is replaced by
    `(d - 1, k)` and **nothing else in the burst moves**.

    What has not changed is that the replacement is never further away, which
    is the half of the old rule that was about power rather than shape.
    """
    for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
        open_ground = _offsets(10, 10, facing)
        for d, k in open_ground:
            wall = _at(10, 10, facing, d, k)
            got = _offsets(10, 10, facing, _wall(wall))
            fallback = {(d - 1, k)} - {(0, 0)}   # the own cell is refused
            assert got == (open_ground - {(d, k)}) | fallback, \
                f"facing {facing}: blocking {(d, k)} changed the rest"
            for fd, _fk in got:
                assert fd <= d or (fd, _fk) in open_ground, \
                    f"facing {facing}: blocking {(d, k)} laid further away"


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
    """Main room, (2, 1), facing left: four of the six cells were wall.

    The six are written out because they are the block the fault was reported
    against, and the patch is no longer that shape (issue #42) -- the reported
    number has to stay checkable against the thing that was measured.
    """
    room = scene.BUILDING.rooms[0]
    reported = {(1, 0), (1, 1), (1, 2), (0, 0), (0, 1), (0, 2)}
    assert sum(room.is_solid(*c) for c in reported) == 4, \
        "the room changed; re-measure before trusting this test"
    laid = set(patch_cells(2, 1, S.LEFT, room.is_solid))
    assert not any(room.is_solid(*c) for c in laid)
    assert laid <= set(patch_cells(2, 1, S.LEFT)), "the patch grew or moved"


def test_a_charge_fired_at_a_wall_rebounds_and_is_still_spent():
    """**Superseded.** This read *lays nothing and is still spent* until issue
    #44: the charge bought a stain before #41 and nothing at all after it, and
    the rebound is the design decision that gave it something to buy.

    Backed against the west wall facing into it, all three near cells are wall.
    `(1, 0)` aims its fallback at the player's own cell and is refused; the two
    outer ones fall back level with the player. So the charge is spent and buys
    two cells of ground it could never have laid before -- and none of them is
    the cell the player is standing in.
    """
    run = Session(seed=1)
    run.player.x, run.player.y = 1 * CELL, 12 * CELL
    run.player.facing = S.LEFT
    assert (run.player.cx, run.player.cy) == (1, 13)
    charges = run.spray.charges
    run.step(Intent(spray=True))
    assert run.spray.charges == charges - 1, "the charge was refunded"
    laid = set(run.spray.cells_in(run.here))
    assert laid == {(1, 12), (1, 14)}, "the rebound did not land"
    assert not any(run.is_solid(*c) for c in laid), "poison inside the wall"
    assert (1, 13) not in laid, "sprayed the player's own cell"


def test_a_charge_can_still_buy_nothing_and_is_still_spent():
    """**The rebound does not claim to buy something every time.** Over the
    playtest building 5 of 3,920 standing-cell-by-facing combinations still lay
    nothing, all of them with the player against the building's outer wall,
    where the fallback is off-screen or is the player's own cell. There the
    charge is spent and the mistake is the player's -- whether that should
    refund or warn is a design question and is deliberately not settled here.
    """
    run = Session(seed=1)
    # (0, 11) in the main room, facing left: hard against the outer wall, so
    # the whole burst is off-screen and off-screen cells do not rebound.
    run.player.x, run.player.y = 0 * CELL, 10 * CELL
    run.player.facing = S.LEFT
    assert (run.player.cx, run.player.cy) == (0, 11)
    charges = run.spray.charges
    run.step(Intent(spray=True))
    assert run.spray.charges == charges - 1, "the charge was refunded"
    assert run.spray.cells_in(run.here) == [], "something was laid off-screen"


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


# --- a charge rebounds off a wall (issue #44) -------------------------------
#
# The rule, in the burst's own terms: a cell the room calls solid falls back to
# (d - 1, k) -- one decrement along the axis already loaded, sideways offset
# unchanged, one per blocked cell, each independently. It replaced "a blocked
# cell is lost", which is what the three playtest sessions were played on.

def test_a_blocked_cell_falls_back_one_step_toward_the_player():
    """The rule itself, stated once and checked in all four facings.

    `(1, +/-1)` falls back to `(0, +/-1)`, which is ground level with the
    player -- the cell no burst had ever laid, and the whole cost of the
    change.
    """
    for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
        for k in (-1, 1):
            wall = _at(10, 10, facing, 1, k)
            offs = _offsets(10, 10, facing, _wall(wall))
            assert (1, k) not in offs, f"facing {facing}: laid on the wall"
            assert (0, k) in offs, f"facing {facing}: {(1, k)} did not rebound"
            assert offs == {(1, -1), (1, 0), (1, 1), (2, 0), (0, k)} - {(1, k)}


def test_the_far_cell_rebounds_into_the_near_row_without_widening():
    """`(2, 0)` falls back onto `(1, 0)`, which the near row already holds, so
    it dedupes rather than adding a cell. A burst that meets a wall at arm's
    length gets smaller, not wider."""
    for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
        cells = patch_cells(10, 10, facing, _wall(_at(10, 10, facing, 2, 0)))
        assert len(cells) == len(set(cells)) == 3, f"facing {facing}: {cells}"
        assert _offsets(10, 10, facing, _wall(_at(10, 10, facing, 2, 0))) == \
            {(1, -1), (1, 0), (1, 1)}


def test_the_rebound_never_lays_the_players_own_cell():
    """`(1, 0)` would fall back to `(0, 0)`, and it is refused -- that poison
    is lost.

    *Your own cell is never sprayed* is what keeps the spray area denial rather
    than a weapon, so the rebound does not get to buy an exception to it. This
    is `test_you_do_not_spray_your_own_cell` again with a room that refuses
    everything, which is the only way the fallback can aim there.
    """
    for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
        straight = patch_cells(10, 10, facing, _wall(_at(10, 10, facing, 1, 0)))
        assert (10, 10) not in set(straight), f"facing {facing}: sprayed self"
        everything = patch_cells(10, 10, facing, lambda x, y: True)
        assert everything == [], f"facing {facing}: {everything}"
        ahead = set(patch_cells(10, 10, facing))
        walled = set(patch_cells(10, 10, facing, _wall(*ahead)))
        assert (10, 10) not in walled, f"facing {facing}: sprayed self"


def test_a_cell_clipped_by_the_screen_bounds_does_not_rebound():
    """**Only a cell refused by the room rebounds.**

    The bounds clip sits ahead of the solid check because `Room.is_solid` will
    happily answer for the column past a doorway by asking the room next door,
    and a patch is keyed by room -- so a cell off this room's screen is not
    this room's to fall back from. Standing in column 0 facing left, all four
    cells are off-screen and every one of their fallbacks would be legal floor
    in this room; none of them may be laid.
    """
    on_floor = lambda x, y: False           # the room refuses nothing at all
    assert patch_cells(0, 10, S.LEFT, on_floor) == []
    assert patch_cells(0, 10, S.LEFT) == []
    assert patch_cells(10, 0, S.UP, on_floor) == []
    assert patch_cells(COLS - 1, 10, S.RIGHT, on_floor) == []


def test_a_rebound_onto_wall_loses_the_poison_and_does_not_chain():
    """One step and no second fallback.

    Chaining has no per-burst worst case, it would walk poison through a
    wall's thickness, and a chain from `(2, 0)` would arrive at `(0, 0)` -- the
    player's own cell -- by a route the rule refuses directly.
    """
    for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
        # (2, 0) blocked, and (1, 0) blocked behind it: nothing lands on the
        # centre line at all, and certainly not on the player.
        wall = _wall(_at(10, 10, facing, 2, 0), _at(10, 10, facing, 1, 0))
        offs = _offsets(10, 10, facing, wall)
        assert offs == {(1, -1), (1, 1)}, f"facing {facing}: {offs}"

        # (1, 1) blocked, and its fallback (0, 1) blocked too: the poison is
        # lost rather than carried on to (-1, 1), behind the player.
        wall = _wall(_at(10, 10, facing, 1, 1), _at(10, 10, facing, 0, 1))
        offs = _offsets(10, 10, facing, wall)
        assert offs == {(1, -1), (1, 0), (2, 0)}, f"facing {facing}: {offs}"


def test_the_rebound_is_one_rule_in_all_four_facings():
    """No new table and no per-facing case: the same wall at the same `(d, k)`
    gives the same shape whichever way the player is pointing, and the shape
    stays symmetric about the facing when the wall is."""
    for d, k in ((1, -1), (1, 0), (1, 1), (2, 0)):
        shapes = {facing: _offsets(10, 10, facing,
                                   _wall(_at(10, 10, facing, d, k)))
                  for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT)}
        one = shapes[S.UP]
        for facing, offs in shapes.items():
            assert offs == one, f"blocking {(d, k)}: facing {facing} differs"
    for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
        both = _wall(_at(10, 10, facing, 1, -1), _at(10, 10, facing, 1, 1))
        offs = _offsets(10, 10, facing, both)
        assert offs == {(d, -k) for d, k in offs}, "not symmetric any more"


def _standing_cells():
    """Every cell a two-cell-tall person can stand in, by room and facing.

    3,920 combinations over the playtest building, which is the population
    every measured figure about the burst is quoted over.
    """
    for room in scene.BUILDING.rooms:
        for cy in range(1, PLAY_ROWS):
            for cx in range(COLS):
                if room.is_solid(cx, cy) or room.is_solid(cx, cy - 1):
                    continue
                for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
                    yield room, cx, cy, facing


def test_no_burst_anywhere_ever_exceeds_four_cells():
    """**The rebound never widens the burst**, over every standing cell and
    facing in the building. A corner blocks more cells and so drops more, and
    each drop lands on a cell nearer the player -- so a corner rebounds less,
    not more."""
    for room, cx, cy, facing in _standing_cells():
        cells = patch_cells(cx, cy, facing, room.is_solid)
        assert len(cells) <= 4, f"{room.name} ({cx},{cy}) {facing}: {cells}"
        assert len(cells) == len(set(cells)), \
            f"{room.name} ({cx},{cy}) {facing}: duplicate cells {cells}"


def test_no_two_rebounds_ever_stack_on_one_floor_cell():
    """The design says the fallback map is one to one; this checks it rather
    than assuming it.

    The fallbacks are recomputed here as a **list**, because a set would hide
    exactly the thing being asked -- and it is what a future variant of the
    rule would break: anything mapping two blocked cells onto the same floor
    cell would concentrate a corner's losses instead of spending them.
    """
    for room, cx, cy, facing in _standing_cells():
        landed = []
        for d, k in ((1, -1), (1, 0), (1, 1), (2, 0)):
            x, y = _at(cx, cy, facing, d, k)
            if not (0 <= x < COLS and 0 <= y < PLAY_ROWS):
                continue
            if not room.is_solid(x, y) or (d - 1, k) == (0, 0):
                continue
            x, y = _at(cx, cy, facing, d - 1, k)
            if 0 <= x < COLS and 0 <= y < PLAY_ROWS and not room.is_solid(x, y):
                landed.append((x, y))
        assert len(landed) == len(set(landed)), \
            f"{room.name} ({cx},{cy}) {facing}: two rebounds on {landed}"


def test_the_rebound_never_lays_a_cell_further_away():
    """**Reach is unchanged.** The fallback only ever moves a cell toward the
    player, so no burst reaches past `REACH` and, on open floor, the shape is
    exactly the taper it always was. Reach is power, and this change was not
    supposed to buy any."""
    from spikes.spray import REACH
    for room, cx, cy, facing in _standing_cells():
        for x, y in patch_cells(cx, cy, facing, room.is_solid):
            fx, fy, sx, sy = S._AXES[facing]
            d = (x - cx) * fx + (y - cy) * fy
            k = (x - cx) * sx + (y - cy) * sy
            assert d <= REACH, f"{room.name} ({cx},{cy}) {facing}: ({d},{k})"
            assert (d, k) in {(1, -1), (1, 0), (1, 1), (2, 0), (0, -1), (0, 1)}


def test_the_rebound_reproduces_the_measured_footprint():
    """The figures the decision was taken on, over all 3,920 combinations --
    `measurements/spray_footprint.py` in the vault, which is the read-only
    harness this was checked against.

    These are geometry over one building and a fact about the shape of these
    two rooms, not about anybody's play. **A width table moving in `spray.py`
    or a room changing in `scene.py` is a reason to re-measure, not a reason to
    edit the numbers** -- the point of pinning them is that the design decision
    was taken on them and a silent drift would take it away again.
    """
    n = laid_taper = laid_rebound = nothing = 0
    residual = []
    for room, cx, cy, facing in _standing_cells():
        n += 1
        taper = patch_cells(cx, cy, facing)
        taper = [c for c in taper if not room.is_solid(*c)]
        cells = patch_cells(cx, cy, facing, room.is_solid)
        laid_taper += len(taper)
        laid_rebound += len(cells)
        if not taper:
            nothing += 1
            if not cells:
                residual.append((room.name, cx, cy))
    assert n == 3920
    # Means, kept in integers: 13800/3920 = 3.52 and 14373/3920 = 3.67.
    assert laid_taper == 13800, f"the taper measured {laid_taper / n}"
    assert laid_rebound == 14373, f"the rebound measured {laid_rebound / n}"
    assert nothing == 127, "bursts laying nothing before the rebound"
    assert len(residual) == 5, f"bursts still laying nothing: {residual}"
    assert set(residual) == {("the main room", 0, 11), ("the main room", 31, 11),
                             ("the main room", 31, 12), ("the far room", 0, 11),
                             ("the far room", 0, 12)}, \
        "the five are all hard against the building's outer wall"


# --- shape: a cloud, not a stamped block (issue #42) ------------------------

def _old_block(cx, cy, facing, reach=2, half=1):
    """The 3x2 rectangle the patch used to be, corners and all."""
    fx, fy, sx, sy = S._AXES[facing]
    return {(cx + fx * d + sx * k, cy + fy * d + sy * k)
            for d in range(1, reach + 1)
            for k in range(-half, half + 1)}


def _at(cx, cy, facing, d, k):
    """The cell at forward `d`, sideways `k` -- the burst's own terms."""
    fx, fy, sx, sy = S._AXES[facing]
    return cx + fx * d + sx * k, cy + fy * d + sy * k


def _offsets(cx, cy, facing, is_solid=None):
    """The patch in forward/sideways terms, which is how it is authored.

    `(d, k)` is the only frame in which the rebound is one rule rather than
    four, so the rebound tests are written in it too.
    """
    fx, fy, sx, sy = S._AXES[facing]
    out = set()
    for x, y in patch_cells(cx, cy, facing, is_solid):
        dx, dy = x - cx, y - cy
        out.add((dx * fx + dy * fy, dx * sx + dy * sy))
    return out


def test_the_patch_has_no_square_corners():
    """It used to be `REACH=2, HALF_WIDTH=1` with every combination filled --
    a 3x2 block that read as a stamp rather than something sprayed."""
    for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
        offs = _offsets(10, 10, facing)
        assert (2, -1) not in offs and (2, 1) not in offs, \
            f"facing {facing} still has square far corners"
        assert offs == {(1, -1), (1, 0), (1, 1), (2, 0)}


def test_the_patch_never_grew():
    """A shape change, not a power change: the new patch is a **strict subset**
    of the old block. Same reach, same near row, two far corners gone."""
    for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
        cells = set(patch_cells(10, 10, facing))
        assert cells < _old_block(10, 10, facing), f"facing {facing} widened"
        assert len(cells) == 4


def test_the_width_only_ever_shrinks_with_distance():
    """The taper is the shape. A width table that grew with distance would put
    the corners back one row further out."""
    from spikes.spray import HALF_WIDTH
    assert list(HALF_WIDTH) == sorted(HALF_WIDTH, reverse=True)
    assert HALF_WIDTH[0] >= 1, "no width at all one cell ahead"


def test_the_four_facings_are_reflections_of_one_another():
    """One shape, turned by `_AXES` -- not four hand-authored blobs."""
    shapes = {facing: _offsets(10, 10, facing)
              for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT)}
    one = shapes[S.UP]
    for facing, offs in shapes.items():
        assert offs == one, f"facing {facing} is a different shape"
    assert one == {(d, -k) for d, k in one}, "not symmetric about the facing"


def test_the_patch_still_plugs_the_connecting_doorway():
    """**Protect a doorway** is one of the two uses the design leans on. The
    doorway is three rows and the near row is three across, so one burst still
    covers all of it -- the trim came off the far row, which nothing has to
    pass through."""
    door_rows = (10, 11, 12)
    cells = set(patch_cells(30, 11, S.RIGHT))
    for row in door_rows:
        assert (31, row) in cells, f"doorway row {row} left open"


def test_a_body_one_step_ahead_is_still_wholly_covered():
    """**Douse a fresh body** is the other. A person is two cells tall, so a
    body ahead of you occupies two cells and both must be poisoned."""
    for facing, body in ((S.RIGHT, ((11, 10), (11, 9))),
                         (S.LEFT, ((9, 10), (9, 9))),
                         (S.DOWN, ((10, 12), (10, 11))),
                         (S.UP, ((10, 9), (10, 8)))):
        cells = set(patch_cells(10, 10, facing))
        assert set(body) <= cells, f"facing {facing} missed part of the body"


# --- the droplets ----------------------------------------------------------

def _dots(pattern):
    """Where the pixels are, as (row, column) pairs, bit 7 leftmost."""
    return [(y, x) for y, bits in enumerate(pattern)
            for x in range(8) if bits & (0x80 >> x)]


def test_the_droplets_moved_out_of_the_code_without_moving_a_dot():
    """The transcription that issue #51 was, pinned to the pixel.

    **What was wrong before:** the droplets were declared as hex in `spray.py`
    although the asset-pipeline decision put them in `assets/tiles/spray.txt`,
    so nothing checked them for drift and the port had no `DEFB` for them.
    Moving them changed no pixel, and these are the positions they had at
    `fb4d831`.

    The two properties underneath the exact list are what the pattern is for,
    and either of them going is a look regression rather than a tidy-up:

    * **twice the density of lit floor** -- eight dots against four -- so a
      sprayed cell reads as covered in something; and
    * **staggered, not columnar.** Lit floor puts its dots in columns 1 and 5
      on every row that has any; the spray alternates columns 2 and 6 with
      columns 0 and 4. That is what keeps poison distinguishable from lit floor
      **without relying on the cyan**, which matters because hue is per 8x8
      cell and a patch at the edge of the torch sits against every brightness
      there is.
    """
    from spikes import floor
    from spikes.spray import STIPPLE

    assert _dots(STIPPLE) == [(1, 2), (1, 6), (3, 0), (3, 4),
                              (5, 2), (5, 6), (7, 0), (7, 4)]
    assert len(_dots(STIPPLE)) == 2 * len(_dots(floor.STIPPLE_LIT))
    columns = {x for _, x in _dots(STIPPLE)}
    assert not columns & {x for _, x in _dots(floor.STIPPLE_LIT)}, \
        "the droplets landed in the floor stipple's columns and stopped " \
        "being distinguishable from it in mono"


def test_the_droplets_are_drawn_from_the_generated_table():
    """`spray.py` declares no bytes: the pattern comes through `bitmaps_gen`
    like every other bitmap, so a change to the asset reaches the screen and
    the Z80 from one edit (issue #51)."""
    from spikes import bitmaps_gen, spray as spray_mod

    assert spray_mod.STIPPLE is bitmaps_gen.BITMAPS["SPRAY"]
