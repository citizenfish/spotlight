"""The hand-built static room."""

from spikes import scene
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import COLS


def test_the_room_is_exactly_the_play_area():
    scene.validate()          # raises if not
    assert len(scene.ROOM) == PLAY_ROWS
    assert all(len(row) == COLS for row in scene.ROOM)


def test_every_cell_kind_has_a_hue():
    for row in scene.ROOM:
        for c in row:
            assert c in scene.INK, f"cell {c!r} has no ink"


def test_the_room_is_walled_all_the_way_round():
    assert set(scene.ROOM[0]) == {scene.WALL}
    assert set(scene.ROOM[-1]) == {scene.WALL}
    for row in scene.ROOM:
        assert row[0] == scene.WALL and row[-1] == scene.WALL


def test_ink_map_covers_every_cell():
    inks = scene.ink_map()
    assert len(inks) == COLS * PLAY_ROWS


def test_keys_and_doors_have_hues_of_their_own():
    """Light sets brightness; contents set hue. Both single-valued per cell,
    so this does not reintroduce clash."""
    assert scene.INK[scene.KEY] != scene.INK[scene.FLOOR]
    assert scene.INK[scene.DOOR] != scene.INK[scene.FLOOR]
    assert scene.INK[scene.KEY] != scene.INK[scene.DOOR]


def test_walls_are_solid_and_floor_is_not():
    wall = next(iter([(cx, cy) for cy, row in enumerate(scene.ROOM)
                      for cx, c in enumerate(row) if c == scene.WALL]))
    floor = next(iter([(cx, cy) for cy, row in enumerate(scene.ROOM)
                       for cx, c in enumerate(row) if c == scene.FLOOR]))
    assert scene.is_solid(*wall)
    assert not scene.is_solid(*floor)


def test_outside_the_room_counts_as_solid():
    assert scene.is_solid(-1, 0)
    assert scene.is_solid(0, PLAY_ROWS)


def test_light_zones_cover_every_authored_light_cell():
    covered = set()
    for left, top, width, height in scene.light_zones():
        for cy in range(top, top + height):
            for cx in range(left, left + width):
                covered.add((cx, cy))
    assert covered == set(scene.cells_of(scene.ROOM_LIGHT))


def test_the_player_starts_somewhere_walkable():
    """The whole 8x16 box must clear the walls, not just the cell the
    coordinates land in. Checking one cell let a start position through that
    had the player's shoulder inside a wall, unable to move at all."""
    from spikes.player import HEIGHT, WIDTH
    px, py = scene.PLAYER_START
    blocked = [(cx, cy)
               for cx in range(px // 8, (px + WIDTH - 1) // 8 + 1)
               for cy in range(py // 8, (py + HEIGHT - 1) // 8 + 1)
               if scene.is_solid(cx, cy)]
    assert not blocked, f"player starts inside walls at {blocked}"


def test_the_player_can_actually_move_from_the_start():
    from spikes.player import Player
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        p = Player(*scene.PLAYER_START)
        assert p.move(dx, dy, scene.is_solid), f"cannot move ({dx}, {dy})"


def test_entities_are_placed_off_the_cell_grid():
    """They must straddle cells, or the two-tone question cannot be judged."""
    off_grid = [(n, x, y) for n, x, y in scene.ENTITIES
                if x % 8 or y % 8]
    assert len(off_grid) >= 4, "most entities should sit at awkward offsets"


def test_a_cleg_sits_against_a_wall_and_another_does_not():
    clegs = [(x, y) for n, x, y in scene.ENTITIES if n == "cleg"]
    assert len(clegs) >= 2
    touching = [c for c in clegs
                if any(scene.is_solid(c[0] // 8 + dx, c[1] // 8 + dy)
                       for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))]
    assert touching, "no Cleg is against a wall"
    assert len(touching) < len(clegs), "every Cleg is against a wall"
