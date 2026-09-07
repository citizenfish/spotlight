"""The hand-built playtest building: two rooms and the doorway between them."""

import pytest

from spikes import building as B, lighting as L, scene, sources as S, sprites as SP
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import CELL, COLS
from spotlight.core.screen import Screen

ROOMS = scene.BUILDING.rooms
NAMES = [r.name for r in ROOMS]


def _room(name):
    return scene.BUILDING[scene.BUILDING.index_of(name)]


@pytest.fixture(params=NAMES)
def room(request):
    """Every test that is about *a room* is run against both of them.

    Room B is new and room A moved, so a test that only ever looked at the room
    it was written for would go on passing while the other one was broken.
    """
    return _room(request.param)


def test_the_building_is_exactly_the_play_area(room):
    scene.validate()          # raises if not
    assert len(room.rows) == PLAY_ROWS
    assert all(len(line) == COLS for line in room.rows)


def test_every_cell_kind_has_a_hue(room):
    for line in room.rows:
        for c in line:
            assert c in scene.INK, f"cell {c!r} has no ink"


def test_the_building_is_walled_all_the_way_round_except_at_its_doors(room):
    """The only holes in a room's outer wall are ways through it."""
    assert set(room.rows[0]) == {scene.WALL}
    assert set(room.rows[-1]) == {scene.WALL}
    doors = {c for d in room.doorways for c in d.cells()}
    doors |= set(room.cells_of(scene.EXIT))
    for cy, line in enumerate(room.rows):
        for cx in (0, COLS - 1):
            assert line[cx] == scene.WALL or (cx, cy) in doors, \
                f"{room.name} has a hole at {cx},{cy} that is not a door"


def test_ink_map_covers_every_cell(room):
    assert len(room.ink_map()) == COLS * PLAY_ROWS


def test_keys_and_doors_have_hues_of_their_own():
    """Light sets brightness; contents set hue. Both single-valued per cell,
    so this does not reintroduce clash."""
    assert scene.INK[scene.KEY] != scene.INK[scene.FLOOR]
    assert scene.INK[scene.DOOR] != scene.INK[scene.FLOOR]
    assert scene.INK[scene.KEY] != scene.INK[scene.DOOR]


def test_this_building_places_no_key(room):
    """It did nothing: doors and keys are not built, so it was a glyph that
    could not be picked up and opened nothing."""
    assert room.cells_of(scene.KEY) == []


def test_walls_are_solid_and_floor_is_not(room):
    wall = next((cx, cy) for cy, line in enumerate(room.rows)
                for cx, c in enumerate(line) if c == scene.WALL)
    floor = next((cx, cy) for cy, line in enumerate(room.rows)
                 for cx, c in enumerate(line) if c == scene.FLOOR)
    assert room.is_solid(*wall)
    assert not room.is_solid(*floor)


def test_outside_a_room_counts_as_solid(room):
    assert room.is_solid(0, PLAY_ROWS)
    assert room.is_solid(0, -1)
    assert room.is_solid(-COLS, 5)


# --- the threshold (issue #21) ----------------------------------------------

def test_the_two_rooms_are_joined_at_a_shared_wall():
    near, far = _room(scene.NEAR_NAME), _room(scene.FAR_NAME)
    assert [d.to for d in near.doorways] == [far.index]
    assert [d.to for d in far.doorways] == [near.index]
    assert near.doorways[0].side == B.EAST
    assert far.doorways[0].side == B.WEST


def test_the_doorway_is_at_the_same_rows_on_both_sides():
    """The world is continuous and only the view jumps, which is only true if
    the two sides line up. A doorway that landed you somewhere else would
    teleport a tail."""
    near, far = _room(scene.NEAR_NAME), _room(scene.FAR_NAME)
    assert near.doorways[0].rows == far.doorways[0].rows == scene.DOOR_ROWS


def test_the_connecting_doorway_is_three_cells_tall():
    """Two would fit a person. Three is an authoring kindness: the movement
    assist nudges by up to a cell, and a door the player bounces off is the
    first thing this audience reads as broken."""
    for r in ROOMS:
        for door in r.doorways:
            assert len(door.rows) == 3


def test_the_connecting_doorway_is_a_gap_and_not_a_coloured_door():
    """The hue rule is for *locked* doors, which have to announce that a key
    exists. This one is unlocked and announces itself through the shouts.

    Floor or lit floor -- the far room authors its room light over its side of
    the threshold, which is the level's centrepiece. What it must never be is a
    `D`: that is the way *out of the building* and it carries the exit's hue.
    """
    for r in ROOMS:
        for door in r.doorways:
            for cx, cy in door.cells():
                assert r.rows[cy][cx] in (scene.FLOOR, scene.ROOM_LIGHT)


def test_the_cell_past_a_doorway_is_the_next_rooms_first_cell():
    """The whole of the crossing mechanism, and the reason nothing else in the
    game knows a doorway exists."""
    near, far = _room(scene.NEAR_NAME), _room(scene.FAR_NAME)
    row = near.doorways[0].middle
    assert near.across(COLS, row) == (far, 0, row)
    assert far.across(-1, row) == (near, COLS - 1, row)
    assert not near.is_solid(COLS, row), "the doorway does not lead anywhere"
    assert not far.is_solid(-1, row)


def test_the_wall_beside_a_doorway_is_still_solid():
    """A doorway is three rows out of twenty-two, and the other nineteen have
    to stop you exactly as they did before."""
    near = _room(scene.NEAR_NAME)
    for row in range(PLAY_ROWS):
        if row not in scene.DOOR_ROWS:
            assert near.is_solid(COLS, row), f"row {row} leaks into the far room"
            assert near.across(COLS, row) is None


def test_a_doorway_in_a_vertical_wall_must_be_two_cells_tall():
    """A person is two cells tall and one wide, so a one-cell gap in a vertical
    wall is a gap nobody fits through. The old rule was written when the only
    doorway in the prototype was in a horizontal wall."""
    thin = B.Room("thin", ROOMS[0].rows,
                  doorways=(B.Doorway(B.EAST, (10,), to=0),))
    B.Building((thin,))
    with pytest.raises(ValueError, match="at least two"):
        thin.validate()


def test_a_doorway_must_not_be_walled_up():
    walled = B.Room("walled", ROOMS[0].rows,
                    doorways=(B.Doorway(B.EAST, (2, 3, 4), to=0),))
    B.Building((walled,))
    with pytest.raises(ValueError, match="walled up"):
        walled.validate()


def test_a_doorway_must_have_one_back_again_at_the_same_rows():
    a = B.Room("a", ROOMS[0].rows, doorways=(B.Doorway(B.EAST, (10, 11, 12), 1),))
    b = B.Room("b", ROOMS[1].rows, doorways=(B.Doorway(B.WEST, (10, 11), 0),))
    with pytest.raises(ValueError, match="line up"):
        B.Building((a, b)).validate()


def test_a_person_who_walks_off_the_edge_arrives_next_door():
    """The transition fires when the figure has cleared the threshold entirely.
    At x=255 you straddle the two rooms; at x=256 you are wholly in the next
    one, which is x=0 there. Nothing jumps but the view."""
    near = _room(scene.NEAR_NAME)
    y = scene.DOOR_ROWS[1] * CELL
    assert scene.BUILDING.cross(near.index, 255, y) is None
    assert scene.BUILDING.cross(near.index, COLS * CELL, y) == (1, 0)
    assert scene.BUILDING.cross(1, -8, y) == (near.index, (COLS - 1) * CELL)


def test_walking_off_an_edge_with_no_doorway_goes_nowhere():
    near = _room(scene.NEAR_NAME)
    assert scene.BUILDING.cross(near.index, COLS * CELL, 2 * CELL) is None


# --- what each room authors -------------------------------------------------

def test_the_way_out_is_in_the_near_rooms_west_wall():
    """The exit and the way deeper are at opposite ends, so the distance from
    the far room's far corner to the way out is the width of two rooms. How far
    a worker is from the way out is the size of the bet you take fetching
    them."""
    near = _room(scene.NEAR_NAME)
    assert near.has_exit
    assert near.exit_cell()[0] == 0
    assert not _room(scene.FAR_NAME).has_exit
    assert scene.BUILDING.exit[0] == near.index


def test_the_way_out_is_two_cells_tall_so_somebody_fits_in_it():
    near = _room(scene.NEAR_NAME)
    doors = near.cells_of(scene.EXIT)
    assert len(doors) >= 2
    assert {c[0] for c in doors} == {0}
    rows = sorted(c[1] for c in doors)
    assert rows == list(range(rows[0], rows[0] + len(rows))), "not one doorway"


def test_the_exit_sign_hangs_beside_the_door_and_inside_the_room():
    """Beside rather than above: the door is in a wall now, and above a door in
    the top wall is masonry. A way out you cannot find is not a way out."""
    near = _room(scene.NEAR_NAME)
    cells = near.exit_sign_cells(scene.EXIT_SIGN)
    assert len(cells) == len(scene.EXIT_SIGN)
    ex, ey = near.exit_cell()
    assert all(cy == ey for _cx, cy in cells)
    assert all(cx > ex for cx, _cy in cells), "the sign is in the masonry"
    assert not any(near.is_solid(*c) for c in cells)


def test_only_the_near_room_has_a_searchlight():
    """Room B is the dark room. Nothing sweeps it, and that is the dial the
    author has turned furthest."""
    assert _room(scene.NEAR_NAME).searchlight is not None
    assert _room(scene.FAR_NAME).searchlight is None


def test_only_the_far_room_authors_a_room_light():
    """The room light is the level author's sharpest tool and no room in the
    prototype had ever used one."""
    assert _room(scene.NEAR_NAME).light_zones() == []
    assert _room(scene.FAR_NAME).light_zones()


def test_the_far_rooms_light_sits_on_the_doorway_home():
    """The centrepiece: from anywhere in B you can see the way home, so B is
    navigable without being safe -- and because Clegs go to lit ground, the one
    route you have to use is the one place the swarm reliably gathers."""
    far = _room(scene.FAR_NAME)
    lit = set(far.cells_of(scene.ROOM_LIGHT))
    door = set(far.doorways[0].cells())
    assert door <= lit, "the room light is not on the doorway"


def test_the_room_light_is_one_zone_and_not_one_per_row():
    """A block of `L` cells is one light. Three stacked one-row zones would put
    three lures a cell apart, which is not what the author drew."""
    assert len(_room(scene.FAR_NAME).light_zones()) == 1


def test_light_zones_cover_every_authored_light_cell(room):
    covered = set()
    for left, top, width, height in room.light_zones():
        for cy in range(top, top + height):
            for cx in range(left, left + width):
                covered.add((cx, cy))
    assert covered == set(room.cells_of(scene.ROOM_LIGHT))


def test_the_player_starts_in_the_near_room():
    assert scene.BUILDING.start[0] == _room(scene.NEAR_NAME).index
    assert scene.BUILDING.start[1] == scene.PLAYER_START


def test_the_player_starts_somewhere_walkable():
    """The whole 8x16 box must clear the walls, not just the cell the
    coordinates land in. Checking one cell let a start position through that
    had the player's shoulder inside a wall, unable to move at all."""
    from spikes.player import HEIGHT, WIDTH
    px, py = scene.PLAYER_START
    solid = ROOMS[scene.BUILDING.start[0]].is_solid
    blocked = [(cx, cy)
               for cx in range(px // 8, (px + WIDTH - 1) // 8 + 1)
               for cy in range(py // 8, (py + HEIGHT - 1) // 8 + 1)
               if solid(cx, cy)]
    assert not blocked, f"player starts inside walls at {blocked}"


def test_the_player_can_actually_move_from_the_start():
    from spikes.player import Player
    solid = ROOMS[scene.BUILDING.start[0]].is_solid
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        p = Player(*scene.PLAYER_START)
        assert p.move(dx, dy, solid), f"cannot move ({dx}, {dy})"


def test_the_player_does_not_start_on_the_way_out():
    """*Building Structure* wants the start on the exit and issue #21 does not
    move it there, deliberately: a Wanderer already ends its run in under two
    seconds on three seeds in twelve by walking into the exit by accident, and
    the designer is ruling on that. Pinned so the omission reads as a decision
    rather than as something forgotten."""
    from spikes.player import Player
    player = Player(*scene.PLAYER_START)
    assert scene.BUILDING.exit[1] not in player.occupied_cells()


def test_workers_are_placed_off_the_cell_grid():
    """They must straddle cells, or the two-tone question cannot be judged."""
    placed = ([(x, y) for _, x, y in scene.ENTITIES]
              + [(x, y) for x, y, _b in scene.WORKERS_A + scene.WORKERS_B])
    off_grid = [p for p in placed if p[0] % 8 or p[1] % 8]
    assert len(off_grid) >= 3, "most things should sit at awkward offsets"
    assert len(off_grid) < len(placed), "a couple aligned makes the contrast"


def test_the_swarm_starts_on_floor_and_spread_out(room):
    """Clegs are cell-dwellers, and they start where they have to travel."""
    from spikes.player import Player
    player = Player(*scene.PLAYER_START)
    assert len(room.clegs) >= 3
    for cx, cy in room.clegs:
        assert not room.is_solid(cx, cy), f"Cleg in a wall at {cx},{cy}"
        if room.player_start is None:
            continue
        reach = max(abs(cx - player.cx), abs(cy - player.cy))
        assert reach >= 5, f"Cleg at {cx},{cy} starts on top of the player"


def test_the_swarm_is_the_buildings_and_is_split_between_the_rooms():
    """Six, which is what the entity budget allows for two concurrent nests, a
    tail and the player -- and it is what the prototype has always had. Issue
    #21 makes the split the vault asked for and #23 deferred: three each.

    The counts are the **building's**. Clegs cross doorways and go to light, so
    a room's authored population is not its worst case: six flies and a tail of
    four in one room is 6 + (5 x 1.75) = 14.75 Cleg-equivalents against a
    ceiling of eighteen.
    """
    assert len(scene.CLEGS_A) == 3
    assert len(scene.CLEGS_B) == 3
    assert sum(len(r.clegs) for r in ROOMS) == 6


def test_a_cleg_starts_against_a_wall_and_another_does_not():
    flies = scene.CLEGS_A + scene.CLEGS_B
    touching = [c for r in ROOMS for c in r.clegs
                if any(r.is_solid(c[0] + dx, c[1] + dy)
                       for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)))]
    assert touching, "no Cleg is against a wall"
    assert len(touching) < len(flies), "every Cleg is against a wall"


def test_the_near_room_is_worth_three_people_and_the_far_room_four():
    """A first-timer who never finds the doorway ends on three of seven, which
    is the top of the target band. The near room is worth three by
    construction."""
    assert len(scene.WORKERS_A) == 3
    assert len(scene.WORKERS_B) == 4


def test_the_strongest_light_in_the_building_is_in_the_far_room():
    """Taking it means leaving what you carry behind, which puts a burning lure
    in the far room at exactly the moment you want the swarm elsewhere."""
    best = max((p, r.name) for r in ROOMS for _cx, _cy, p in r.spotlights)
    assert best[1] == scene.FAR_NAME


def test_the_near_room_offers_one_decent_light_and_one_nearly_dead():
    """A weak light is a trap, and it should be available where it costs a walk
    rather than a life."""
    powers = sorted(p for _cx, _cy, p in scene.SPOTLIGHTS_A)
    assert len(powers) == 2
    assert powers[0] * 4 < powers[1], "the weak one is not weak enough to trap"


def test_every_spotlight_lies_on_floor(room):
    for cx, cy, _power in room.spotlights:
        assert not room.is_solid(cx, cy)


# --- a worker under a room light (issue #12) -------------------------------

def _a_worker():
    x, y, _blood = scene.WORKERS_A[0]
    return x, y


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
    """Emergency lighting shows the room, not who is in it.

    Load-bearing now that a room actually authors one: the vault's worked
    example for room B's light says the tail files through it *lit*, and this
    rule says it does not. The agreed rule wins and the contradiction is the
    designer's to settle -- see `scene.ROOM_B`.
    """
    x, y = _a_worker()
    field = _field_of(_light_over(x, y))
    assert field.level_at(x // CELL, y // CELL) == L.LIT, "the ground is lit"
    assert not _drawn(x, y, field), "but the worker should not be drawn"


def test_the_authored_room_light_reveals_nobody_either():
    """Asked of the real one rather than of a fixture, because the real one is
    the first any room has ever had."""
    far = _room(scene.FAR_NAME)
    lights = [S.RoomLight(*z) for z in far.light_zones()]
    field = _field_of(*lights)
    cx, cy = far.doorways[0].cells()[1]
    assert field.level_at(cx, cy) == L.LIT
    assert not field.prey_at(cx, cy), "the room light makes the tail prey"


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


# --- the building has to be walkable (issue #9) ----------------------------

def _reachable_from(room, start):
    seen, stack = set(), [start]
    while stack:
        c = stack.pop()
        if c in seen or room.is_solid(*c) or not (0 <= c[0] < COLS):
            continue
        seen.add(c)
        stack += [(c[0] + dx, c[1] + dy)
                  for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    return seen


def _floor(room):
    return {(x, y) for y in range(PLAY_ROWS) for x in range(COLS)
            if not room.is_solid(x, y)}


def test_every_floor_cell_is_reachable_from_the_door(room):
    """The inner room was a sealed box with a worker in it.

    Nobody noticed while sprites were the question, because nobody had tried to
    walk in. Found by playing, and this is what stops it coming back -- in both
    rooms, which is what makes it a check on the building rather than on one
    picture somebody happened to draw.
    """
    if room.player_start is not None:
        from spikes.player import Player
        start = (Player(*room.player_start).cx, Player(*room.player_start).cy)
    else:
        start = room.doorways[0].cells()[1]
    cut_off = _floor(room) - _reachable_from(room, start)
    assert not cut_off, f"{room.name}: walled-off floor: {sorted(cut_off)}"


def test_every_worker_can_actually_be_reached(room):
    """The objective has to be completable, or the evaluation asks nothing."""
    from spikes.rescue import Worker
    if room.player_start is not None:
        from spikes.player import Player
        start = (Player(*room.player_start).cx, Player(*room.player_start).cy)
    else:
        start = room.doorways[0].cells()[1]
    reachable = _reachable_from(room, start)
    for x, y, _blood in room.workers:
        standing = Worker(x, y).cells()
        assert standing & reachable, f"{room.name}: {x},{y} cannot be got to"
        assert not any(room.is_solid(*c) for c in standing), \
            f"{room.name}: worker at {x},{y} is inside a wall"


def test_there_are_seven_people_in_the_building():
    assert sum(len(r.workers) for r in ROOMS) == 7


def test_the_workers_are_spread_out():
    """Clustered workers would be one search, not seven. Measured from the
    start, across the whole building: everybody in the far room is a journey by
    construction, so the question is whether the near room's three are."""
    from spikes.player import Player
    player = Player(*scene.PLAYER_START)
    far = [1 for x, y, _b in scene.WORKERS_A
           if max(abs(x // CELL - player.cx), abs(y // CELL - player.cy)) > 5]
    assert len(far) >= 2, "the near room's workers are all beside the start"


def test_the_inner_room_is_entered_through_a_one_cell_doorway():
    """One cell wide on purpose -- it is the case the corner assist exists for,
    and *Building Structure* keeps one-cell doorways legal in horizontal
    walls."""
    near = _room(scene.NEAR_NAME)
    cx, cy = scene.INNER_DOOR
    assert not near.is_solid(cx, cy)
    assert near.is_solid(cx - 1, cy) and near.is_solid(cx + 1, cy)


# --- no floor may be somewhere the swarm cannot get to ---------------------
#
# The dual of the rule above, and it needs a different instrument. A flood fill
# asks whether a path *exists*, which is the wrong question about something that
# cannot find one: Clegs steer greedily at a light and slide along whatever they
# hit, so a concave pocket is a place the beam sweeps, the flies approach, and
# nothing ever arrives. That is a permanent refuge and the design says there are
# none.
#
# Measured in room A before this issue: the bottom-right corner cost **1.6 blood
# in a hundred and fifty seconds against 146.2 in the middle** -- ninety-one
# times safer, and the strongest play in Spotlight was to find it and work from
# there. A flood fill said it was fine, because it was: you could walk in. The
# flies could not.
#
# #26 will make this a general check with a proper measurement behind it. What
# is here is the check issue #21 needed to draw two rooms with.

def _arrives(room):
    """cell -> how many of the room's floor cells a Cleg steering at it arrives
    from, using `Cleg._toward` exactly: greedy, longest axis first, slide to the
    other axis if blocked, stand still if both are.

    Because that step is a function of the cell and the goal alone, the room is
    one functional graph per goal, so "which cells reach here" is a backward
    walk over it and costs one pass per goal rather than a simulation per pair.
    """
    free = _floor(room)
    counts = {}
    for goal in free:
        gx, gy = goal
        back = {}
        for cell in free:
            if cell == goal:
                continue
            cx, cy = cell
            dx = (gx > cx) - (gx < cx)
            dy = (gy > cy) - (gy < cy)
            if abs(gx - cx) >= abs(gy - cy):
                order = ((dx, 0), (0, dy))
            else:
                order = ((0, dy), (dx, 0))
            for sx, sy in order:
                if (sx, sy) == (0, 0):
                    continue
                step = (cx + sx, cy + sy)
                if step in free:
                    back.setdefault(step, []).append(cell)
                    break
        seen, stack = {goal}, [goal]
        while stack:
            for prev in back.get(stack.pop(), ()):
                if prev not in seen:
                    seen.add(prev)
                    stack.append(prev)
        counts[goal] = len(seen) - 1
    return counts


@pytest.fixture(scope="module")
def arrivals():
    return {r.name: _arrives(r) for r in ROOMS}


def test_no_floor_is_somewhere_the_swarm_cannot_get_to_at_all(room, arrivals):
    stranded = [c for c, n in arrivals[room.name].items() if n == 0]
    assert not stranded, f"{room.name}: the swarm can never reach {stranded}"


def test_the_bottom_right_corner_of_the_near_room_is_no_longer_a_refuge(arrivals):
    """The pocket this issue exists to remove. The wall across row 18 sealed it
    and has been turned on its side, so the corner is approached from the north
    instead of only from along a two-row channel."""
    counts = arrivals[scene.NEAR_NAME]
    total = len(counts)
    corner = [n for (cx, cy), n in counts.items() if cx >= 25 and cy >= 18]
    assert corner, "the corner has no floor in it"
    assert min(corner) * 5 >= total, (
        f"the bottom-right corner is still a pocket: reachable from "
        f"{min(corner)} of {total} cells")


def test_the_far_room_did_not_inherit_a_pocket(arrivals):
    """Room B is new, so it is the room most likely to have been drawn with one
    by accident. Alcoves and three-sided bays were tried and measured at 3-9%,
    worse than the corner above; partitions open at both ends measure at 21%.
    """
    counts = arrivals[scene.FAR_NAME]
    total = len(counts)
    worst = min(counts.items(), key=lambda kv: kv[1])
    assert worst[1] * 5 >= total, (
        f"{worst[0]} is reachable from only {worst[1]} of {total} cells")


def test_the_inner_box_is_the_one_known_pocket_and_is_kept_on_purpose(arrivals):
    """Recorded rather than fixed, so it reads as a decision.

    By the same measurement the inner box's interior is reachable from about 3%
    of room A's floor -- a stronger refuge than the corner this issue opens. The
    vault keeps the inner box and its one-cell door deliberately (it is the case
    the movement assist exists for, and it holds a worker), so removing it is a
    design decision and not a bug fix. This test asserts the shape of the
    problem so that #26 finds it waiting rather than discovering it.
    """
    counts = arrivals[scene.NEAR_NAME]
    total = len(counts)
    inside = [n for (cx, cy), n in counts.items()
              if 13 <= cx <= 18 and 4 <= cy <= 6]
    assert inside
    assert min(inside) < total // 10, (
        "the inner box is no longer a pocket -- good, but the vault has not "
        "been told, and this test is the record that it was one")


# --- a person is two cells tall (issue #13) --------------------------------

def _standable(room, cx, cy):
    return not room.is_solid(cx, cy) and not room.is_solid(cx, cy - 1)


def _reachable_by_a_person(room, start):
    seen, stack = set(), [start]
    while stack:
        c = stack.pop()
        if c in seen or not (0 <= c[0] < COLS) or not _standable(room, *c):
            continue
        seen.add(c)
        stack += [(c[0] + dx, c[1] + dy)
                  for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    return seen


def test_every_worker_can_be_reached_by_something_person_shaped(room):
    """A single-cell flood fill is not the same question. The player is two
    cells tall, so a cell can be walkable and still not standable -- their head
    goes into the wall above."""
    from spikes.rescue import Worker
    if room.player_start is not None:
        from spikes.player import Player
        p = Player(*room.player_start)
        start = (p.cx, p.cy)
    else:
        start = (room.doorways[0].cells()[-1])
    reachable = _reachable_by_a_person(room, start)
    for x, y, _blood in room.workers:
        assert Worker(x, y).cells() & reachable, \
            f"{room.name}: nobody person-shaped can get to {x},{y}"


def test_the_exit_can_be_reached_by_something_person_shaped():
    from spikes.player import Player
    near = _room(scene.NEAR_NAME)
    player = Player(*scene.PLAYER_START)
    reachable = _reachable_by_a_person(near, (player.cx, player.cy))
    ex = near.exit_cell()
    touching = [c for c in reachable
                if abs(c[0] - ex[0]) <= 1 and abs(c[1] - ex[1]) <= 1]
    assert touching, f"the way out at {ex} cannot be reached"


def test_the_doorway_can_be_walked_through_by_something_person_shaped():
    """The one that would make the second room pointless if it failed."""
    from spikes.player import Player
    near = _room(scene.NEAR_NAME)
    player = Player(*scene.PLAYER_START)
    reachable = _reachable_by_a_person(near, (player.cx, player.cy))
    assert set(near.doorways[0].cells()) & reachable


def test_a_person_reaches_less_than_a_single_cell_would():
    """Stated so the difference is not mistaken for a bug later."""
    from spikes.player import Player
    near = _room(scene.NEAR_NAME)
    player = Player(*scene.PLAYER_START)
    loose = _reachable_from(near, (player.cx, player.cy))
    body = _reachable_by_a_person(near, (player.cx, player.cy))
    assert body < loose, "the two checks happen to agree; they need not"


# --- what this building authors about its light (issue #23) ----------------

def test_the_playtest_building_repeats_its_searchlight():
    """Repeating makes the beam a puzzle you can watch, time and cross behind;
    varying is weather. The beam delivers about three quarters of the swarm, so
    the dominant threat should be the one a first-timer can learn."""
    assert scene.SEARCHLIGHT_VARY is False
    assert _room(scene.NEAR_NAME).searchlight.vary is False


def test_the_beam_radius_is_untouched():
    """Held, and holding it is a decision: settled by a person at a keyboard --
    at twice this it was over you before you could do anything about it -- and
    nothing measured implicates it."""
    assert scene.SEARCHLIGHT_RADIUS == 3


def test_the_room_uses_what_it_authors():
    """A constant in the level data that the session ignores is a lie."""
    from spikes.session import Session
    run = Session(seed=1)
    assert run.roaming.vary is scene.SEARCHLIGHT_VARY
    assert run.roaming.radius == scene.SEARCHLIGHT_RADIUS
    assert len(run.searchlights) == 1, "the building has one searchlight"


def test_two_runs_of_the_same_seed_start_the_beam_in_the_same_place():
    """Learnable within a run is half of the deal; the other half is that a
    seed still names a run."""
    from spikes.session import Session
    assert Session(seed=9).roaming.origin() == Session(seed=9).roaming.origin()


def test_different_seeds_start_the_beam_in_different_places():
    from spikes.session import Session
    starts = {Session(seed=s).roaming.origin() for s in range(1, 40)}
    assert len(starts) > 4, f"the beam starts in only {len(starts)} places"
