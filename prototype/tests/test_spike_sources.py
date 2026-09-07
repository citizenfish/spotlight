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
    """Radius two is excluded, and by arithmetic rather than oversight: the
    station grid is spaced for a beam of three, and a narrower one cannot reach
    between the stations. A narrower beam would want a denser grid and its own
    tour."""
    for radius in (3, 4, 5):
        covered, _ = _covered_by(S.Roaming(0, 0, radius=radius, step_every=1))
        missed = _whole_room() - covered
        assert not missed, f"radius {radius} missed {sorted(missed)[:4]}"


def test_a_narrow_beam_cannot_use_this_station_grid():
    """Stated as a known limit so it is not rediscovered as a bug."""
    xs = [S.station(c, 0)[0] for c in range(S.STATION_COLS)]
    ys = [S.station(0, r)[1] for r in range(S.STATION_ROWS)]
    sx = max(b - a for a, b in zip(xs, xs[1:]))
    sy = max(b - a for a, b in zip(ys, ys[1:]))
    assert sx * sx + sy * sy > 4 * 2 * 2, "radius two would in fact reach"


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
    """Slow enough to be a threat you can see coming, fast enough to matter."""
    roam = S.Roaming(0, 0, radius=3)
    _, frames = _covered_by(roam)          # frames, not steps
    seconds = frames / 50
    assert 20 <= seconds <= 70, f"a full circuit takes {seconds:.1f}s"


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


def test_reshape_rebuilds_the_route_for_the_new_radius():
    roam = S.Roaming(0, 0, radius=3, step_every=1)
    roam.reshape(radius=4)
    covered, _ = _covered_by(roam)
    assert covered == _whole_room()


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


def test_one_circuit_still_lights_the_entire_room():
    """Covering everywhere is the point of a searchlight and is not negotiable."""
    for radius in (3, 4, 5):
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


# --- the beam moves like a knight (issue #10) ------------------------------

def _tour_circuit(radius=3, step_every=6, **kw):
    """Run one circuit and report where the beam went."""
    route, dwells = S.tour_route(radius, **kw)
    roam = S.Roaming(0, 0, radius=radius, step_every=step_every)
    roam._sweep, roam._dwells = route, dwells
    roam._leg = 0
    roam._snap_to_route_start()
    seen, path, frames = set(), [], 0
    while roam.cycles < 1 and frames < 300000:
        roam.update()
        frames += 1
        path.append((roam.x, roam.y))
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    seen.add((roam.x + dx, roam.y + dy))
    return seen, path, frames


def test_the_tour_is_closed_and_every_step_is_a_knight_move():
    """Closed is what lets the start be random without breaking coverage."""
    tour = S.KNIGHT_TOUR
    assert len(tour) == S.STATION_COLS * S.STATION_ROWS
    assert len(set(tour)) == len(tour), "a station is visited twice"
    for a, b in zip(tour, tour[1:] + tour[:1]):
        step = (abs(a[0] - b[0]), abs(a[1] - b[1]))
        assert sorted(step) == [1, 2], f"{a} to {b} is not a knight move"


def test_the_stations_are_spaced_closely_enough_to_cover():
    """The worst-lit point of a grid is the middle of a station rectangle."""
    xs = [S.station(c, 0)[0] for c in range(S.STATION_COLS)]
    ys = [S.station(0, r)[1] for r in range(S.STATION_ROWS)]
    sx = max(b - a for a, b in zip(xs, xs[1:]))
    sy = max(b - a for a, b in zip(ys, ys[1:]))
    assert sx * sx + sy * sy <= 4 * 3 * 3, f"gaps {sx}x{sy} too wide for radius 3"


def test_the_stations_keep_clear_of_the_walls():
    for col in range(S.STATION_COLS):
        for row in range(S.STATION_ROWS):
            x, y = S.station(col, row)
            assert S.STATION_INSET <= x <= COLS - 1 - S.STATION_INSET
            assert S.STATION_INSET <= y <= PLAY_ROWS - 1 - S.STATION_INSET


def test_the_beam_never_touches_a_wall():
    """Three complaints about it tracking them. Now it cannot."""
    _, path, _ = _tour_circuit()
    on_ring = [p for p in path
               if p[0] in (0, COLS - 1) or p[1] in (0, PLAY_ROWS - 1)]
    assert not on_ring, f"beam reached the wall at {on_ring[:3]}"


def test_one_circuit_still_lights_every_cell():
    for radius in (3, 4, 5):
        seen, _, _ = _tour_circuit(radius)
        assert not _whole_room() - seen, f"radius {radius} left gaps"


def test_it_covers_from_any_start_and_either_way_round():
    """The point of a closed tour: entering it anywhere is still a full tour."""
    for start in range(0, len(S.KNIGHT_TOUR), 7):
        for reverse in (False, True):
            for flip_x in (False, True):
                seen, _, _ = _tour_circuit(start=start, reverse=reverse,
                                           flip_x=flip_x)
                assert not _whole_room() - seen, \
                    f"start {start} reverse {reverse} flip {flip_x} left gaps"


def test_no_axis_dominates_how_the_beam_travels():
    """The complaint, three times over, was that it travelled one way. A
    serpentine is parallel passes, so it always will; a knight's tour has no
    parallel passes at all."""
    from collections import Counter
    roam = S.Roaming(0, 0, radius=3, vary=True)
    last, axes = (roam.x, roam.y), Counter()
    for _ in range(50 * 60 * 6):
        roam.update()
        if (roam.x, roam.y) != last:
            dx, dy = roam.x - last[0], roam.y - last[1]
            axes["flat" if dy == 0 else "upright" if dx == 0 else "slant"] += 1
            last = (roam.x, roam.y)
    total = sum(axes.values())
    assert 100 * axes["flat"] // total <= 40, "still mostly sideways"
    assert 100 * axes["slant"] // total >= 35, "hardly ever moves diagonally"
    assert axes["upright"] > 0


def test_the_beam_walks_the_line_rather_than_dog_legging():
    """Diagonally until one axis lines up, then straight, bunches every leg's
    odd steps into a run at the end -- five cells of pure sideways travel on a
    knight's move, which is a third of the journey."""
    roam = S.Roaming(0, 0, radius=3, step_every=1)
    route = roam._sweep
    target = route[1]
    path = [(roam.x, roam.y)]
    for _ in range(200):
        roam.update()
        if (roam.x, roam.y) != path[-1]:
            path.append((roam.x, roam.y))
        if (roam.x, roam.y) == target:
            break
    longest, run, last = 0, 0, None
    for a, b in zip(path, path[1:]):
        step = (b[0] - a[0], b[1] - a[1])
        run = run + 1 if step == last else 1
        last = step
        longest = max(longest, run)
    assert longest <= 3, f"a run of {longest} identical steps in one move"


def test_a_circuit_is_something_you_can_wait_out():
    _, _, frames = _tour_circuit()
    assert 20 <= frames / 50 <= 70, f"a circuit takes {frames/50:.0f}s"


def test_it_pauses_at_the_stations_and_the_pauses_vary():
    dwells = [d for d in S.tour_route(3)[1] if d]
    assert dwells, "never pauses"
    assert len(set(dwells)) > 1, "pauses are metronomic"


# --- smoothing the motion (issue #10) --------------------------------------

def _step_intervals(roam, seconds=180):
    """How many frames apart consecutive moves are, and how far each moved."""
    last, last_f, out = (roam.x, roam.y), 0, []
    for f in range(1, seconds * 50 + 1):
        roam.update()
        if (roam.x, roam.y) != last:
            far = abs(roam.x - last[0]) + abs(roam.y - last[1])
            out.append((f - last_f, far))
            last, last_f = (roam.x, roam.y), f
    return out


def test_a_diagonal_step_waits_longer_because_it_goes_further():
    """Otherwise the beam speeds up by 41% whenever it moves diagonally, which
    on a knight's tour is a constant stutter rather than a sweep."""
    roam = S.Roaming(0, 0, radius=3)
    steps = [(t, far) for t, far in _step_intervals(roam) if t <= 12]
    flat = [t for t, far in steps if far == 1]
    slant = [t for t, far in steps if far == 2]
    assert flat and slant, "expected both kinds of step"
    assert sum(slant) / len(slant) > sum(flat) / len(flat), \
        "a diagonal step is given no longer than an orthogonal one"


def test_the_beam_travels_at_a_steady_speed():
    roam = S.Roaming(0, 0, radius=3)
    steps = [(t, far) for t, far in _step_intervals(roam) if t <= 12]
    # Cells covered per frame, counting a diagonal as the 1.41 it really is.
    speeds = [(1414 if far == 2 else 1000) // t for t, far in steps]
    assert max(speeds) - min(speeds) <= max(speeds) // 5, \
        f"speed swings from {min(speeds)} to {max(speeds)} per frame"


def test_it_does_not_stop_at_every_station():
    """Forty-eight pauses in a circuit is not a light being aimed, it is a
    stutter."""
    dwells = S.tour_route(3)[1]
    pauses = [d for d in dwells if d]
    assert 2 <= len(pauses) <= len(dwells) // 3, \
        f"{len(pauses)} pauses among {len(dwells)} stations"


def test_the_pauses_are_a_small_part_of_a_circuit():
    dwells = S.tour_route(3)[1]
    roam = S.Roaming(0, 0, radius=3)
    frames = 0
    while roam.cycles < 1 and frames < 300000:
        roam.update()
        frames += 1
    assert sum(dwells) * 5 < frames, "spends most of its time standing still"


# --- the station grid and the entry point (issue #23) ----------------------

def test_every_floor_cell_falls_inside_some_station_disc():
    """*Light and Darkness* claims total coverage and that **nowhere is
    permanently safe**. This is that claim, asserted rather than eyeballed.

    It is the weaker of the two coverage properties and it is the one that
    matters for the corner: `test_one_circuit_lights_the_entire_room` allows a
    cell to be reached only by the *tracks between* stations, and a cell that
    is only ever crossed in transit is lit for a fraction of the time a cell
    the beam stops on is. Standing where no station's disc reaches is standing
    somewhere the machine can only glance at.

    Written when the vault called for the station inset to move from 3 to 2 to
    restore this property. The constant was **already 2** and the property
    already held; the test is here so it cannot quietly stop holding, and so
    that the next person to reach for the inset can see it is not the dial.
    """
    from spikes import scene

    stations = [S.station(col, row)
                for col in range(S.STATION_COLS)
                for row in range(S.STATION_ROWS)]
    r2 = scene.SEARCHLIGHT_RADIUS * scene.SEARCHLIGHT_RADIUS
    missed = []
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            if scene.ROOM_NEAR.is_solid(cx, cy):
                continue
            if not any((cx - sx) ** 2 + (cy - sy) ** 2 <= r2
                       for sx, sy in stations):
                missed.append((cx, cy))
    assert not missed, f"{len(missed)} floor cells no station reaches: {missed[:6]}"


def test_the_station_grid_still_meets_its_own_spacing_rule():
    """The worst-lit point of a grid is the middle of a station rectangle, half
    a diagonal from the four around it, so `sx^2 + sy^2 <= 4r^2`. 3.86 and 3.4
    give 26.5 against 36."""
    xs = [S.station(c, 0)[0] for c in range(S.STATION_COLS)]
    ys = [S.station(0, r)[1] for r in range(S.STATION_ROWS)]
    sx = max(b - a for a, b in zip(xs, xs[1:]))
    sy = max(b - a for a, b in zip(ys, ys[1:]))
    assert sx * sx + sy * sy <= 4 * 3 * 3


def test_no_station_sits_against_a_wall():
    """The beam never touches a wall, which three previous attempts could not
    manage, and the inset is what buys it."""
    for col in range(S.STATION_COLS):
        for row in range(S.STATION_ROWS):
            cx, cy = S.station(col, row)
            assert 0 < cx < COLS - 1 and 0 < cy < PLAY_ROWS - 1


def test_the_entry_station_comes_from_the_seed():
    """**The first circuit was never seeded.** `_new_sweep(first=True)` laid it
    out with no seed at all, so every run began at the same station and walked
    the same route -- which is why the tester found the tour identical in every
    seed for the first fifty-eight seconds, and why five seeds were one sample
    of the term that dominates the first minute.
    """
    starts = {S.Roaming(0, 0, radius=3, seed=seed).origin()
              for seed in range(1, 200)}
    assert len(starts) > 8, f"the beam starts in only {len(starts)} places"


def test_the_first_circuit_of_a_repeating_beam_varies_with_the_seed():
    """Seeded across runs, identical within one. Both halves matter: a tester
    wants a sample, a player wants something learnable."""
    def first_circuit(seed):
        roam = S.Roaming(0, 0, radius=3, step_every=1, vary=False, seed=seed)
        path = []
        while roam.cycles < 1:
            roam.update()
            path.append((roam.x, roam.y))
        return path

    a, b = first_circuit(0x1234), first_circuit(0x5678)
    assert a != b, "two seeds walked the same first circuit"
    assert first_circuit(0x1234) == a, "a seed does not name a route"


def test_a_repeating_beam_covers_the_room_from_any_entry():
    """Entering the tour anywhere is only safe because the tour is closed. If
    some entry point left a gap, seeding the entry would be trading a coverage
    bug for a variety that nobody asked for."""
    for seed in (1, 7, 0x1234, 0xACE1, 0xBEEF):
        roam = S.Roaming(0, 0, radius=3, step_every=1, vary=False, seed=seed)
        covered, _ = _covered_by(roam)
        assert covered == _whole_room(), f"seed {seed} left gaps"


def test_the_beam_never_pays_for_a_step_it_does_not_take():
    """Every route here is closed, so its last waypoint is its first. Taking
    that leg as an ordinary step costs a whole interval in which the beam does
    not move -- a hitch at the start of the run and one at every wrap.

    It hid behind the unseeded entry: with the tour always entered at station
    zero the hitch landed on a waypoint the beam pauses at anyway.
    """
    for seed in (1, 7, 0x1234, 0xACE1):
        roam = S.Roaming(0, 0, radius=3, vary=False, seed=seed)
        steps = [(t, far) for t, far in _step_intervals(roam) if t <= 12]
        stalled = [t for t, far in steps if far == 1 and t > roam.step_every]
        assert not stalled, f"seed {seed} stalled for {stalled}"


def test_the_carried_torch_lasts_twenty_seconds():
    """On comprehension grounds, and low confidence: a first-timer switches it
    on to see, leaves it on, and at twelve seconds is dark again with no event
    and no explanation. Twenty seconds is four room-crossings -- enough to
    learn what light costs, nowhere near enough to play lit.

    Twenty and not more: this is not the tuning question, and what a torch buys
    cannot be measured until a bot's route depends on what it can see.
    """
    cone = S.Cone(reach=7)
    assert cone.power == 1000 == S.Cone.FULL
    cone.enabled = True
    for _ in range(20 * 50):
        assert cone.lit
        cone.drain()
    assert not cone.lit, "the torch outlasted its twenty seconds"
