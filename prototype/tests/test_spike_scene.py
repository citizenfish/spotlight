"""The hand-built static room."""

from spikes import lighting as L, scene, sources as S, sprites as SP
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import CELL, COLS
from spotlight.core.screen import Screen


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


def test_this_room_places_no_key():
    """It did nothing: doors and keys are not in this spike, so it was a glyph
    that could not be picked up and opened nothing."""
    assert scene.cells_of(scene.KEY) == []


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
    placed = ([(x, y) for _, x, y in scene.ENTITIES] + list(scene.WORKERS))
    off_grid = [p for p in placed if p[0] % 8 or p[1] % 8]
    assert len(off_grid) >= 4, "most things should sit at awkward offsets"
    assert len(off_grid) < len(placed), "a couple aligned makes the contrast"


def test_the_swarm_starts_on_floor_and_spread_out():
    """Clegs are cell-dwellers now, and they start where they have to travel.

    They were fixed scenery placed at pixel offsets while sprites were the
    question. They move under their own rule now, so what matters is that none
    starts inside a wall and none starts on top of the player.
    """
    from spikes.player import Player
    player = Player(*scene.PLAYER_START)
    assert len(scene.CLEGS) >= 4
    for cx, cy in scene.CLEGS:
        assert not scene.is_solid(cx, cy), f"Cleg starts in a wall at {cx},{cy}"
        reach = max(abs(cx - player.cx), abs(cy - player.cy))
        assert reach >= 5, f"Cleg at {cx},{cy} starts on top of the player"


def test_a_cleg_starts_against_a_wall_and_another_does_not():
    touching = [c for c in scene.CLEGS
                if any(scene.is_solid(c[0] + dx, c[1] + dy)
                       for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))]
    assert touching, "no Cleg is against a wall"
    assert len(touching) < len(scene.CLEGS), "every Cleg is against a wall"


# --- a worker under a room light (issue #12) -------------------------------
#
# This room authors no light zone any more, so these build one over a worker
# rather than looking for one -- which is what they should have done anyway.

def _a_worker():
    """A worker from the scene, at its awkward pixel offset."""
    assert scene.WORKERS, "the scene has no workers to find"
    return scene.WORKERS[0]


def _light_over(x, y):
    return S.RoomLight(x // CELL - 1, y // CELL - 1, 3, 4)


def _drawn(x, y, field):
    s = Screen()
    SP.draw(s, SP.WORKER, x, y, visible=field.reveals_at)
    return any(s.pixels)


def _field_of(*srcs):
    f = L.LightField()
    f.begin()
    for src in srcs:
        src.apply(f)
    f.commit()
    return f


def test_a_room_light_does_not_show_the_worker_standing_in_it():
    """Emergency lighting shows the room, not who is in it."""
    x, y = _a_worker()
    field = _field_of(_light_over(x, y))
    assert field.level_at(x // CELL, y // CELL) == L.LIT, "the ground is lit"
    assert not _drawn(x, y, field), "but the worker should not be drawn"


def test_the_worker_shows_when_the_player_gets_near():
    x, y = _a_worker()
    glow = S.Glow()
    glow.x, glow.y = x // CELL, y // CELL
    assert _drawn(x, y, _field_of(_light_over(x, y), glow)), \
        "your own glow should show them"


def test_the_worker_shows_when_a_searchlight_crosses_them():
    x, y = _a_worker()
    beam = S.Roaming(x // CELL, y // CELL, radius=2, mode=S.Roaming.DRIFT)
    assert _drawn(x, y, _field_of(beam))


def test_the_worker_does_not_linger_once_the_light_has_gone():
    """The fade remembers the room; it must not remember the person."""
    x, y = _a_worker()
    glow = S.Glow()
    glow.x, glow.y = x // CELL, y // CELL
    field = _field_of(glow)
    assert _drawn(x, y, field)
    field.begin(); field.commit()          # the player has stepped away
    assert field.level_at(x // CELL, y // CELL) != L.DARK, "ground remembered"
    assert not _drawn(x, y, field), "the worker should be gone"


def test_this_room_authors_no_light_zone():
    """It had one and it was removed -- a rectangle of dots that never changed."""
    assert scene.light_zones() == []
    assert not scene.cells_of(scene.ROOM_LIGHT)


# --- the room has to be walkable (issue #9) --------------------------------

def _reachable_from(start):
    seen, stack = set(), [start]
    while stack:
        c = stack.pop()
        if c in seen or scene.is_solid(*c):
            continue
        seen.add(c)
        stack += [(c[0] + dx, c[1] + dy)
                  for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    return seen


def test_every_floor_cell_is_reachable_from_the_start():
    """The inner room was a sealed box with a worker in it.

    Nobody noticed while sprites were the question, because nobody had tried to
    walk in. Found by playing, and this is what stops it coming back.
    """
    from spikes.player import Player
    player = Player(*scene.PLAYER_START)
    floor = {(x, y) for y in range(PLAY_ROWS) for x in range(COLS)
             if not scene.is_solid(x, y)}
    cut_off = floor - _reachable_from((player.cx, player.cy))
    assert not cut_off, f"walled-off floor: {sorted(cut_off)}"


def test_every_entity_stands_somewhere_reachable():
    from spikes.player import Player
    player = Player(*scene.PLAYER_START)
    reachable = _reachable_from((player.cx, player.cy))
    for name, x, y in scene.ENTITIES:
        assert (x // CELL, y // CELL) in reachable, f"{name} is walled in"


def test_every_worker_can_actually_be_reached():
    """The objective has to be completable, or the evaluation asks nothing."""
    from spikes.player import Player
    from spikes.rescue import Worker
    player = Player(*scene.PLAYER_START)
    reachable = _reachable_from((player.cx, player.cy))
    for x, y in scene.WORKERS:
        standing = Worker(x, y).cells()
        assert standing & reachable, f"worker at {x},{y} cannot be got to"
        assert not any(scene.is_solid(*c) for c in standing), \
            f"worker at {x},{y} is inside a wall"


def test_there_are_enough_workers_to_make_looking_worthwhile():
    assert len(scene.WORKERS) >= 5


def test_the_workers_are_spread_out():
    """Clustered workers would be one search, not seven."""
    from spikes.player import Player
    player = Player(*scene.PLAYER_START)
    far = [1 for x, y in scene.WORKERS
           if max(abs(x // CELL - player.cx), abs(y // CELL - player.cy)) > 9]
    assert len(far) >= 3, "most workers are within a stone's throw of the start"


def test_the_inner_room_is_entered_through_a_one_cell_doorway():
    """One cell wide on purpose -- it is the case the corner assist exists for."""
    cx, cy = scene.INNER_DOOR
    assert not scene.is_solid(cx, cy)
    assert scene.is_solid(cx - 1, cy) and scene.is_solid(cx + 1, cy)
