"""The four light sources."""

from spikes import lighting as L, sources as S
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import COLS, YELLOW


def _field(*srcs) -> L.LightField:
    f = L.LightField()
    f.begin()
    for src in srcs:
        src.apply(f)
    f.commit()
    return f


def _lit_cells(field) -> set[tuple[int, int]]:
    return {(cx, cy) for cy in range(PLAY_ROWS) for cx in range(COLS)
            if field.level_at(cx, cy)}


# --- switching -------------------------------------------------------------

def test_every_source_can_be_switched_off():
    glow = S.Glow(); glow.x, glow.y = 5, 5
    room = S.RoomLight(1, 1, 3, 3)
    cone = S.Cone(); cone.x, cone.y = 8, 8; cone.enabled = True
    roam = S.Roaming(15, 15)
    for src in (glow, room, cone, roam):
        assert _lit_cells(_field(src)), f"{type(src).__name__} lit nothing"
        src.toggle()
        assert not _lit_cells(_field(src)), f"{type(src).__name__} still lit"


# --- glow ------------------------------------------------------------------

def test_glow_is_one_cell_in_every_direction_around_the_person():
    """Anchored on the feet, but a person is two cells tall."""
    glow = S.Glow(); glow.x, glow.y = 5, 5
    assert _lit_cells(_field(glow)) == {
        (5 + dx, 5 + dy) for dx in (-1, 0, 1) for dy in (-2, -1, 0, 1)
    }


def test_the_glow_clears_the_top_of_your_head():
    """Walking north into walls you cannot see is not darkness, it is a bug."""
    glow = S.Glow(); glow.x, glow.y = 5, 5
    lit = _lit_cells(_field(glow))
    head = 5 - 1
    assert (5, head) in lit, "your own head is in the dark"
    assert (5, head - 1) in lit, "the row above your head is dark"


def test_a_shorter_body_gets_a_shorter_glow():
    glow = S.Glow(tall=1); glow.x, glow.y = 5, 5
    assert (5, 3) not in _lit_cells(_field(glow))


def test_glow_is_dim_not_lit():
    """Enough to inch along a wall, never enough to plan."""
    glow = S.Glow(); glow.x, glow.y = 5, 5
    assert _field(glow).level_at(5, 5) == L.DIM


def test_glow_is_clipped_at_the_room_edge():
    glow = S.Glow(); glow.x, glow.y = 0, 0
    assert _lit_cells(_field(glow)) == {(0, 0), (1, 0), (0, 1), (1, 1)}


# --- room light ------------------------------------------------------------

def test_room_light_fills_its_authored_zone():
    room = S.RoomLight(2, 3, 4, 2)
    assert _lit_cells(_field(room)) == {
        (cx, cy) for cx in range(2, 6) for cy in range(3, 5)
    }


def test_room_light_does_not_move():
    room = S.RoomLight(2, 3, 4, 2)
    before = _lit_cells(_field(room))
    for _ in range(100):
        pass
    assert _lit_cells(_field(room)) == before


# --- cone ------------------------------------------------------------------

def test_cone_follows_the_facing_direction():
    seen = {}
    for facing, expected in ((S.RIGHT, (1, 0)), (S.LEFT, (-1, 0)),
                             (S.UP, (0, -1)), (S.DOWN, (0, 1))):
        cone = S.Cone(reach=4); cone.x, cone.y = 10, 10
        cone.facing, cone.enabled = facing, True
        cells = _lit_cells(_field(cone))
        # The cell immediately ahead is lit; the one behind is not.
        ahead = (10 + expected[0], 10 + expected[1])
        behind = (10 - expected[0], 10 - expected[1])
        assert ahead in cells, f"facing {facing}: {ahead} not lit"
        assert behind not in cells, f"facing {facing}: {behind} lit but is behind"
        seen[facing] = cells
    assert len({frozenset(c) for c in seen.values()}) == 4, "facings not distinct"


def test_cone_widens_with_distance():
    cone = S.Cone(reach=6); cone.x, cone.y = 5, 10
    cone.facing, cone.enabled = S.RIGHT, True
    cells = _lit_cells(_field(cone))
    widths = [len({c for c in cells if c[0] == 5 + d}) for d in range(1, 7)]
    assert widths == sorted(widths), f"cone should not narrow: {widths}"
    assert widths[0] == 1 and widths[-1] > widths[0]


def test_a_cone_with_no_power_lights_nothing():
    cone = S.Cone(reach=5, power=0); cone.x, cone.y = 10, 10
    cone.enabled = True
    assert not _lit_cells(_field(cone))
    assert not cone.lit


def test_power_drains_only_while_lit():
    cone = S.Cone(power=10); cone.enabled = False
    cone.drain(); cone.drain()
    assert cone.power == 10, "an unlit spotlight must not drain"
    cone.enabled = True
    cone.drain()
    assert cone.power == 9


def test_power_never_goes_negative():
    cone = S.Cone(power=1); cone.enabled = True
    for _ in range(10):
        cone.drain()
    assert cone.power == 0


# --- roaming ---------------------------------------------------------------

def test_roaming_moves_with_no_player_input():
    roam = S.Roaming(15, 10, step_every=1)
    start = (roam.x, roam.y)
    moved = False
    for _ in range(50):
        roam.update()
        if (roam.x, roam.y) != start:
            moved = True
            break
    assert moved


def test_drifting_stays_inside_the_room():
    roam = S.Roaming(0, 0, step_every=1)
    for _ in range(2000):
        roam.update()
        assert 0 <= roam.x < COLS and 0 <= roam.y < PLAY_ROWS


def test_a_path_is_followed_and_loops():
    path = [(5, 5), (10, 5), (10, 9)]
    roam = S.Roaming(5, 5, path=path, step_every=1)
    assert roam.mode == S.Roaming.PATH
    visited = set()
    for _ in range(200):
        roam.update()
        visited.add((roam.x, roam.y))
    assert set(path) <= visited, f"never reached every waypoint: {visited}"


def test_mode_falls_back_to_drift_without_a_path():
    roam = S.Roaming(5, 5)
    roam.set_mode(S.Roaming.PATH)
    assert roam.mode == S.Roaming.DRIFT


def test_roaming_pool_is_a_disc():
    # DRIFT, because a sweeping light owns its own position.
    roam = S.Roaming(15, 10, radius=2, mode=S.Roaming.DRIFT)
    cells = _lit_cells(_field(roam))
    assert (15, 10) in cells
    assert (17, 10) in cells and (15, 12) in cells      # on the radius
    assert (17, 12) not in cells                        # corner, outside it


def test_xorshift_never_returns_zero_and_does_not_stick():
    state, seen = 0xACE1, set()
    for _ in range(500):
        state = S.xorshift16(state)
        assert state != 0
        assert state <= 0xFFFF
        seen.add(state)
    assert len(seen) > 400, "PRNG is cycling far too early"


# --- composition -----------------------------------------------------------

def test_all_four_composite_brightest_wins():
    glow = S.Glow(); glow.x, glow.y = 10, 10
    cone = S.Cone(reach=4); cone.x, cone.y = 10, 10
    cone.facing, cone.enabled = S.RIGHT, True
    room = S.RoomLight(9, 9, 3, 3)
    roam = S.Roaming(10, 10, radius=1)
    f = _field(glow, room, cone, roam)
    # The glow alone would leave this cell dim; the others make it lit.
    assert f.level_at(10, 10) == L.LIT
    assert _field(glow).level_at(10, 10) == L.DIM


# --- the searchlight sweep -------------------------------------------------

def _covered_by(roam, circuits=1, limit=100000):
    """Every cell the beam touches until it has finished `circuits` circuits."""
    seen, frames = set(), 0
    r2 = roam.radius * roam.radius
    while roam.cycles < circuits and frames < limit:
        roam.update()
        frames += 1
        for dy in range(-roam.radius, roam.radius + 1):
            for dx in range(-roam.radius, roam.radius + 1):
                if dx * dx + dy * dy <= r2:
                    seen.add((roam.x + dx, roam.y + dy))
    assert frames < limit, "sweep never completed a circuit"
    return {c for c in seen
            if 0 <= c[0] < COLS and 0 <= c[1] < PLAY_ROWS}, frames


def _whole_room():
    return {(x, y) for x in range(COLS) for y in range(PLAY_ROWS)}


def test_one_circuit_lights_the_entire_room():
    """The point of a searchlight: nowhere is permanently safe."""
    covered, _ = _covered_by(S.Roaming(0, 0, radius=3, step_every=1))
    assert covered == _whole_room()


def test_coverage_holds_at_other_beam_sizes():
    for radius in (2, 3, 4, 5):
        covered, _ = _covered_by(S.Roaming(0, 0, radius=radius, step_every=1))
        missed = _whole_room() - covered
        assert not missed, f"radius {radius} missed {sorted(missed)[:4]}"


def test_repeating_sweeps_run_the_same_route_every_circuit():
    """Easy mode: learnable, so you can time your crossing."""
    roam = S.Roaming(0, 0, radius=3, step_every=1, vary=False)
    routes = []
    for _ in range(3):      # includes the first circuit, which must match too
        target = roam.cycles + 1
        path = []
        while roam.cycles < target:
            roam.update()
            path.append((roam.x, roam.y))
        routes.append(path)
    assert routes[0] == routes[1] == routes[2]


def test_varying_sweeps_change_between_circuits():
    """Hard mode: still total coverage, but you cannot plan around it."""
    roam = S.Roaming(0, 0, radius=3, step_every=1, vary=True)
    routes = []
    for _ in range(4):
        target = roam.cycles + 1
        path = []
        while roam.cycles < target:
            roam.update()
            path.append((roam.x, roam.y))
        routes.append(tuple(path))
    assert len(set(routes)) > 1, "vary mode repeated itself every circuit"


def test_a_varying_sweep_still_covers_everything_each_circuit():
    """Varying must not mean leaving gaps."""
    roam = S.Roaming(0, 0, radius=3, step_every=1, vary=True)
    for circuit in range(4):
        target = roam.cycles + 1
        seen = set()
        while roam.cycles < target:
            roam.update()
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    if dx * dx + dy * dy <= 9:
                        seen.add((roam.x + dx, roam.y + dy))
        missed = _whole_room() - seen
        assert not missed, f"circuit {circuit} missed {sorted(missed)[:4]}"


def test_sweep_waypoints_span_the_full_width():
    points = S.sweep_waypoints(3)
    assert min(x for x, _ in points) == 0
    assert max(x for x, _ in points) == COLS - 1


def test_sweep_rows_are_spaced_by_the_beam_diameter():
    rows = sorted({y for _, y in S.sweep_waypoints(3)})
    gaps = {b - a for a, b in zip(rows, rows[1:])}
    assert gaps <= {6}, f"uneven row spacing: {sorted(gaps)}"


def test_a_circuit_takes_a_sensible_number_of_frames():
    """Slow enough to be a threat you can see coming, fast enough to matter.

    A narrow beam takes longer, because covering the room with a thin arc means
    more of them. That is the trade and not a fault.
    """
    for radius, limit in ((3, 40), (2, 60)):
        roam = S.Roaming(0, 0, radius=radius)
        _, frames = _covered_by(roam)      # frames, not steps
        seconds = frames / 50
        assert 10 <= seconds <= limit, \
            f"radius {radius}: a full sweep takes {seconds:.1f}s"


def test_the_beam_crosses_the_room_at_a_watchable_pace():
    """Fast enough to matter, slow enough to time a crossing behind it.

    The speed is what a player reacts to; the circuit length is what they wait
    out. They are different numbers and this is the one that is felt.
    """
    roam = S.Roaming(0, 0, radius=3)
    cells_per_second = 50 / roam.step_every
    assert 5 <= cells_per_second <= 12, f"{cells_per_second:.1f} cells/sec"
    room_crossing = COLS / cells_per_second
    assert 3 <= room_crossing <= 7, f"crosses the room in {room_crossing:.1f}s"


def test_path_and_drift_modes_still_work():
    roam = S.Roaming(5, 5, path=[(5, 5), (10, 5)], step_every=1)
    assert roam.mode == S.Roaming.PATH
    roam.set_mode(S.Roaming.DRIFT)
    assert roam.mode == S.Roaming.DRIFT
    roam.set_mode(S.Roaming.SWEEP)
    assert roam.mode == S.Roaming.SWEEP


# --- issue #12: the searchlight is its own kind of light --------------------

def test_the_searchlight_tops_up_to_the_sweep_charge_not_full():
    roam = S.Roaming(15, 10, radius=1, mode=S.Roaming.DRIFT)
    f = _field(roam)
    assert f.charge[10 * COLS + 15] == L.CHARGE_SWEEP
    assert L.CHARGE_SWEEP < L.CHARGE_LIT


def test_the_searchlight_is_yellow_and_the_others_are_not():
    roam = S.Roaming(15, 10, radius=1, mode=S.Roaming.DRIFT)
    assert _field(roam).hue[10 * COLS + 15] == YELLOW
    cone = S.Cone(reach=2); cone.x, cone.y = 10, 10
    cone.facing, cone.enabled = S.RIGHT, True
    assert _field(cone).hue[10 * COLS + 11] == L.UNCOLOURED
    glow = S.Glow(); glow.x, glow.y = 5, 5
    assert _field(glow).hue[5 * COLS + 5] == L.UNCOLOURED


def test_the_cone_still_leaves_its_long_bright_trail():
    """Change 1 must not touch the walked trail that spike 1 settled on."""
    cone = S.Cone(reach=2); cone.x, cone.y = 10, 10
    cone.facing, cone.enabled = S.RIGHT, True
    f = _field(cone)
    for _ in range(L.LIT_FRAMES - 1):
        f.begin(); f.commit()
    assert f.level_at(11, 10) == L.LIT


def test_an_inset_sweep_keeps_the_whole_disc_on_the_room():
    roam = S.Roaming(0, 0, radius=3, step_every=1, inset=3,
                     mode=S.Roaming.SWEEP)
    r = roam.radius
    seen = set()
    while roam.cycles < 1:
        roam.update()
        seen.add((roam.x, roam.y))
    assert all(r <= x <= COLS - 1 - r and r <= y <= PLAY_ROWS - 1 - r
               for x, y in seen), "beam centre strayed within a radius of a wall"


def test_an_inset_sweep_still_covers_everything_inside_the_outer_ring():
    """A round beam kept a radius in from the wall only touches the outer ring
    at its own row, so ring cells between passes are the price of the inset.
    In a room the ring is wall, so nothing that matters is missed."""
    ring = {c for c in _whole_room()
            if c[0] in (0, COLS - 1) or c[1] in (0, PLAY_ROWS - 1)}
    for radius in (2, 3):
        roam = S.Roaming(0, 0, radius=radius, step_every=1, inset=radius,
                         mode=S.Roaming.SWEEP)
        covered, _ = _covered_by(roam)
        missed = _whole_room() - covered
        assert missed <= ring, (f"radius {radius}: inset sweep missed inside "
                                f"the ring: {sorted(missed - ring)[:6]}")
        assert (0, 0) in missed, "the corners are the known cost"


def test_reshape_rebuilds_the_sweep_for_the_new_radius():
    roam = S.Roaming(0, 0, radius=3, step_every=1)
    roam.reshape(radius=2)
    covered, _ = _covered_by(roam)
    assert covered == _whole_room()
    rows = sorted({y for _, y in S.sweep_waypoints(2)})
    gaps = {b - a for a, b in zip(rows, rows[1:])}
    assert gaps <= {4}


# --- room lights show the room, not who is in it (issue #12) ---------------

def test_a_room_light_lights_the_ground_without_revealing_people():
    room = S.RoomLight(2, 3, 4, 2)
    f = _field(room)
    assert f.level_at(3, 3) == L.LIT, "the ground is lit"
    assert not f.reveals_at(3, 3), "but it does not show who is standing there"


def test_every_other_source_reveals():
    glow = S.Glow(); glow.x, glow.y = 5, 5
    cone = S.Cone(reach=2); cone.x, cone.y = 10, 10
    cone.facing, cone.enabled = S.RIGHT, True
    roam = S.Roaming(15, 10, radius=1, mode=S.Roaming.DRIFT)
    assert _field(glow).reveals_at(5, 5)
    assert _field(cone).reveals_at(11, 10)
    assert _field(roam).reveals_at(15, 10)


def test_whether_a_room_light_reveals_is_switchable():
    """So it can be judged by eye rather than argued about."""
    room = S.RoomLight(2, 3, 4, 2)
    assert not _field(room).reveals_at(3, 3)
    room.reveals = True
    assert _field(room).reveals_at(3, 3)


# --- the opening flash (issue #9) ------------------------------------------

def test_the_flash_lights_the_whole_room():
    """You cannot play a room you have never seen the shape of."""
    flash = S.Flash()
    flash.fire()
    assert _lit_cells(_field(flash)) == {
        (cx, cy) for cx in range(COLS) for cy in range(PLAY_ROWS)
    }


def test_the_flash_is_brief_and_then_stops_by_itself():
    flash = S.Flash(frames=5)
    flash.fire()
    for _ in range(5):
        assert flash.enabled
        flash.update()
    assert not flash.enabled
    assert not _lit_cells(_field(flash))


def test_the_room_fades_after_the_flash_rather_than_snapping_back():
    """What the player keeps is what they held in their head."""
    field = L.LightField()
    flash = S.Flash(frames=2)
    flash.fire()
    for _ in range(2):
        field.begin(); flash.apply(field); field.commit(); flash.update()
    assert field.level_at(5, 5) == L.LIT
    for _ in range(L.LIT_FRAMES + 1):
        field.begin(); field.commit()
    assert field.level_at(5, 5) == L.DIM, "should linger, not snap off"


def test_the_flash_shows_the_building_not_who_is_in_it():
    """Same rule as the room lights. Finding people stays the player's job."""
    flash = S.Flash()
    flash.fire()
    field = _field(flash)
    assert field.level_at(9, 9) == L.LIT
    assert not field.reveals_at(9, 9)


def test_the_flash_draws_the_swarm_nowhere():
    """A light that is everywhere has no *toward* for a Cleg to climb."""
    flash = S.Flash()
    flash.fire()
    assert flash.lure() is None


def test_firing_again_restarts_it():
    flash = S.Flash(frames=4)
    flash.fire()
    flash.update(); flash.update()
    flash.fire()
    assert flash.left == 4


# --- the lamp lights its bearer (issue #10) --------------------------------

def test_a_burning_spotlight_lights_the_person_holding_it():
    """Otherwise switching it on draws the swarm and leaves you untouchable."""
    cone = S.Cone(reach=5, power=100)
    cone.x, cone.y, cone.facing = 10, 10, S.RIGHT
    cone.enabled = True
    field = _field(cone)
    assert field.level_at(10, 10) == L.LIT
    assert field.prey_at(10, 10), "carrying a lit lamp must make you prey"


def test_switching_it_off_takes_you_out_of_the_light():
    cone = S.Cone(reach=5, power=100)
    cone.x, cone.y, cone.facing = 10, 10, S.RIGHT
    assert not _field(cone).prey_at(10, 10)


def test_the_glow_alone_never_makes_you_prey():
    """The dark is a refuge, and the glow must not spoil it."""
    glow = S.Glow()
    glow.x, glow.y = 10, 10
    field = _field(glow)
    assert field.reveals_at(10, 10), "you can still see your own feet"
    assert not field.prey_at(10, 10)


def test_the_cone_still_points_where_you_face():
    """Lighting yourself must not have turned the cone into a radius."""
    cone = S.Cone(reach=4, power=100)
    cone.x, cone.y, cone.facing = 10, 10, S.RIGHT
    cone.enabled = True
    cells = _lit_cells(_field(cone))
    assert (11, 10) in cells and (9, 10) not in cells


# --- the beam swings; it does not march (issue #10) ------------------------

def test_the_default_sweep_is_arcs_not_rows():
    """A player called the straight version too predictable, and it was."""
    assert S.Roaming(0, 0).mode == S.Roaming.ARC


def test_the_table_is_the_whole_of_the_trigonometry():
    """Integers only. A Z80 keeps this in ROM and looks it up."""
    assert S.sin256(0) == 0 and S.sin256(S.TURN // 4) == 256
    assert S.cos256(0) == 256 and S.cos256(S.TURN // 4) == 0
    for step in range(S.TURN):
        assert isinstance(S.sin256(step), int)
        assert -256 <= S.sin256(step) <= 256


def test_sine_and_cosine_stay_a_quarter_turn_apart():
    for step in range(S.TURN):
        assert S.cos256(step) == S.sin256(step + S.TURN // 4)


def test_an_arc_curves_rather_than_running_straight():
    """Three points off a straight line is the whole of the difference."""
    pts = S.arc_waypoints(3, (0, 0), 20, 0, 16, step=4)
    (x0, y0), (x1, y1), (x2, y2) = pts[0], pts[len(pts) // 2], pts[-1]
    # Cross product of the end-to-end vector with the middle point's offset.
    bend = (x2 - x0) * (y1 - y0) - (y2 - y0) * (x1 - x0)
    assert bend != 0, f"the arc is a straight line: {pts}"


def test_one_arc_circuit_still_lights_the_entire_room():
    """Covering everywhere is the point of a searchlight and is not negotiable."""
    for radius in (2, 3, 4, 5):
        covered, _ = _covered_by(S.Roaming(0, 0, radius=radius, step_every=1))
        missed = _whole_room() - covered
        assert not missed, f"radius {radius} missed {sorted(missed)[:4]}"


def test_every_mount_covers_the_room():
    """Wherever it is bolted, it sweeps the whole of the room it faces."""
    for mount in range(4):
        roam = S.Roaming(0, 0, radius=3, step_every=1)
        roam.mount = mount
        roam.reshape()
        covered, _ = _covered_by(roam)
        assert _whole_room() - covered == set(), f"mount {mount} left gaps"


def test_a_varying_arc_sweep_moves_the_mount():
    """Random enough that you cannot learn where the next circuit starts."""
    roam = S.Roaming(0, 0, radius=3, step_every=1, vary=True)
    mounts = set()
    for _ in range(12):
        target = roam.cycles + 1
        while roam.cycles < target:
            roam.update()
        mounts.add(roam.mount)
    assert len(mounts) > 1, "the searchlight is bolted to the same corner"


def test_a_varying_arc_sweep_still_covers_everything_each_circuit():
    roam = S.Roaming(0, 0, radius=3, step_every=1, vary=True)
    for circuit in range(4):
        target = roam.cycles + 1
        seen = set()
        while roam.cycles < target:
            roam.update()
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    if dx * dx + dy * dy <= 9:
                        seen.add((roam.x + dx, roam.y + dy))
        missed = _whole_room() - seen
        assert not missed, f"circuit {circuit} missed {sorted(missed)[:4]}"


def test_the_straight_serpentine_is_still_there_for_the_editor():
    roam = S.Roaming(0, 0, radius=3, step_every=1, mode=S.Roaming.SWEEP)
    covered, _ = _covered_by(roam)
    assert _whole_room() - covered == set()


# --- the surge shows people; the opening flash does not (issue #10) --------

def test_the_opening_flash_shows_the_room_and_not_who_is_in_it():
    flash = S.Flash()
    flash.fire()
    field = _field(flash)
    assert field.level_at(9, 9) == L.LIT
    assert not field.reveals_at(9, 9)


def test_a_surge_shows_everything_people_included():
    """The memorisation beat. It is a different thing from the flash."""
    flash = S.Flash()
    flash.fire(surge=True)
    field = _field(flash)
    assert field.level_at(9, 9) == L.LIT
    assert field.reveals_at(9, 9)


def test_a_surge_does_not_leave_the_flash_revealing_afterwards():
    flash = S.Flash()
    flash.fire(surge=True)
    assert flash.reveals
    flash.fire()
    assert not flash.reveals


def test_neither_a_flash_nor_a_surge_lures_anything():
    flash = S.Flash()
    for surge in (False, True):
        flash.fire(surge=surge)
        assert flash.lure() is None


def test_a_held_flash_stays_on_until_let_go():
    """A real surge is a quarter of a second; this is for watching things in."""
    flash = S.Flash(frames=3)
    flash.hold(True)
    for _ in range(500):
        flash.update()
    assert flash.enabled and flash.reveals
    field = _field(flash)
    assert field.level_at(9, 9) == L.LIT and field.reveals_at(9, 9)

    flash.hold(False)
    assert not flash.enabled
    assert not _lit_cells(_field(flash))


def test_holding_it_does_not_change_what_the_clegs_do():
    """A light that is everywhere offers nothing to steer toward."""
    flash = S.Flash()
    flash.hold(True)
    assert flash.lure() is None


def test_a_timed_surge_still_counts_down_after_a_hold():
    flash = S.Flash(frames=4)
    flash.hold(True)
    flash.hold(False)
    flash.fire(surge=True)
    for _ in range(4):
        flash.update()
    assert not flash.enabled


# --- the beam is worked by hand, and keeps off the walls (issue #10) -------

def _circuit(radius=3, mount=0, step_every=6):
    """Run one circuit and report where the beam spent its time."""
    route, dwells = S.arc_sweep(radius, mount)
    roam = S.Roaming(0, 0, radius=radius, step_every=step_every)
    roam.mount = mount
    roam._sweep, roam._dwells = route, dwells
    roam._leg = 0
    roam._snap_to_route_start()
    seen, frames, ring = set(), 0, 0
    while roam.cycles < 1 and frames < 200000:
        roam.update()
        frames += 1
        if roam.x in (0, COLS - 1) or roam.y in (0, PLAY_ROWS - 1):
            ring += 1
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    seen.add((roam.x + dx, roam.y + dy))
    return seen, frames, ring


def test_the_beam_hardly_ever_touches_the_wall():
    """The complaint, twice over, was that it tracked them. It was doing it
    31% of a circuit; a light reaches its own radius, so it never had to."""
    for radius in (2, 3, 4, 5):
        _, frames, ring = _circuit(radius)
        assert 100 * ring // frames <= 8, \
            f"radius {radius}: {100 * ring // frames}% of a circuit on the ring"


def test_no_pass_runs_along_the_top_or_bottom_wall():
    for radius in (2, 3, 4, 5):
        rows = {y for _, y in S.arc_sweep(radius, 0)[0]}
        assert min(rows) >= radius, "a pass runs along the ceiling"
        assert max(rows) <= PLAY_ROWS - 1 - radius, "a pass runs along the floor"


def test_it_still_lights_every_cell_of_the_room():
    """Total coverage is the point of a searchlight and is not negotiable."""
    for radius in (2, 3, 4, 5):
        for mount in range(4):
            seen, _, _ = _circuit(radius, mount)
            missed = _whole_room() - seen
            assert not missed, (f"radius {radius} mount {mount} missed "
                                f"{sorted(missed)[:4]}")


def test_the_corners_are_why_the_passes_still_run_the_full_width():
    """A beam lights a disc, not a square. Held off both walls at once it sits
    too far from the corner to light it, so the passes reach the side walls."""
    for radius in (2, 3, 4, 5):
        inset = S.corner_inset(radius)
        assert 2 * inset * inset <= radius * radius, "would miss the corner"
        assert inset < radius, "no tighter than the radius, or it is pointless"


def test_every_pass_sweeps_the_same_way():
    """Alternating them puts the turn against a wall, and with the rows
    shuffled that turn is a long run straight up the edge column."""
    passes = [p for p in (S.arc_sweep(3, 0)[0][i:i + 3]
                          for i in range(0, len(S.arc_sweep(3, 0)[0]) - 1, 3))
              if len(p) == 3]
    directions = {p[2][0] > p[0][0] for p in passes}
    assert len(directions) == 1, "passes go in different directions"


def test_the_beam_holds_short_of_the_wall_rather_than_against_it():
    """A pause costs frames whether or not the beam is moving, so a hold on the
    wall was most of the time spent on it."""
    route, dwells = S.arc_sweep(3, 0)
    for (x, _), dwell in zip(route, dwells):
        if dwell:
            assert x not in (0, COLS - 1), "holds with its nose on the wall"


def test_it_pauses_at_all_and_the_pauses_vary():
    """An operator does not reverse a searchlight instantly."""
    dwells = [d for d in S.arc_sweep(3, 0)[1] if d]
    assert dwells, "never pauses"
    assert len(set(dwells)) > 1, "pauses are metronomic"
    assert all(S.DWELL <= d < S.DWELL + S.DWELL_SPREAD for d in dwells)


def test_a_varying_circuit_takes_the_passes_in_a_different_order():
    orders = {tuple(y for _, y in S.arc_sweep(3, m, seed=0xACE1 + m * 977)[0])
              for m in range(1, 4)}
    assert len(orders) > 1, "every circuit works down the room the same way"


def test_a_circuit_is_still_something_you_can_wait_out():
    for radius, limit in ((3, 40), (2, 60)):
        _, frames, _ = _circuit(radius)
        assert 10 <= frames / 50 <= limit, \
            f"radius {radius}: a circuit takes {frames/50:.0f}s"


def _passes(route):
    """The route as passes: each is three waypoints, start, ease and end."""
    return [route[i:i + 3] for i in range(0, len(route) - 1, 3)]


def test_a_circuit_sweeps_in_rows_or_in_columns():
    """Rows alone read as a beam that only ever travels sideways, because that
    is exactly what it does."""
    for a_pass in _passes(S.arc_sweep(3, 0, vertical=False)[0]):
        assert len({y for _, y in a_pass}) == 1, "a row pass changed row"
        assert len({x for x, _ in a_pass}) == 3, "a row pass did not travel"
    for a_pass in _passes(S.arc_sweep(3, 0, vertical=True)[0]):
        assert len({x for x, _ in a_pass}) == 1, "a column pass changed column"
        assert len({y for _, y in a_pass}) == 3, "a column pass did not travel"


def test_column_sweeps_cover_the_room_too():
    for radius in (2, 3, 4, 5):
        route, dwells = S.arc_sweep(radius, 0, vertical=True)
        roam = S.Roaming(0, 0, radius=radius, step_every=1)
        roam._sweep, roam._dwells = route, dwells
        roam._leg = 0
        roam._snap_to_route_start()
        covered, _ = _covered_by(roam)
        assert not _whole_room() - covered, f"radius {radius} left gaps"


def test_column_passes_keep_off_the_side_walls():
    for radius in (2, 3, 4, 5):
        xs = {x for x, _ in S.arc_sweep(radius, 0, vertical=True)[0]}
        assert min(xs) >= radius and max(xs) <= COLS - 1 - radius


def test_the_beam_does_not_predominantly_travel_one_way():
    """Measured over four minutes of varying circuits."""
    from collections import Counter
    roam = S.Roaming(0, 0, radius=3, vary=True)
    last, axes = (roam.x, roam.y), Counter()
    for _ in range(50 * 60 * 4):
        roam.update()
        if (roam.x, roam.y) != last:
            dx, dy = roam.x - last[0], roam.y - last[1]
            axes["flat" if dy == 0 else "upright" if dx == 0 else "slant"] += 1
            last = (roam.x, roam.y)
    total = sum(axes.values())
    for way in ("flat", "upright"):
        share = 100 * axes[way] // total
        assert 25 <= share <= 60, f"{way} travel is {share}% of the beam's motion"
