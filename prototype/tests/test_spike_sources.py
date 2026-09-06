"""The four light sources."""

from spikes import lighting as L, sources as S
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import COLS


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

def test_glow_is_one_cell_in_every_direction():
    glow = S.Glow(); glow.x, glow.y = 5, 5
    assert _lit_cells(_field(glow)) == {
        (5 + dx, 5 + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
    }


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
    roam = S.Roaming(15, 10, radius=2)
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
