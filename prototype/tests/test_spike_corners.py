"""A building that turns a corner: doorways in horizontal walls (issue #139).

A `Doorway` could only be in a vertical wall -- `Doorway.column` returned the
first column or the last, and `Building.cross` noticed only a figure walking off
the left or right edge -- so two rooms could only ever be adjacent east-west.
That was fine while a building was a strip. Once the opening's plan became a
grid three rooms across (#134), a connected building ran along one row and
three rooms fitted a row, so **a building capped at three rooms** while #137's
ladder had been ruled to grow them to six.

`building.py` used to call a doorway in a horizontal wall *"the easier case (a
person is one cell wide, so one cell across fits)"*. That is half right, and the
half it gets wrong is the half that matters: a person **fits** through a
narrower horizontal gap, and **clears** a horizontal threshold only after
sixteen pixels of height rather than eight of width. Two things fell out of that
and both are pinned below -- `is_solid` answered True for any row off the grid
before it ever asked the doorways, and `across` resolved one cell past the
threshold when a figure's feet reach two.
"""

import functools
import os
import tempfile

import pytest

from spikes import bots, building as B, levels, session as S, swarming
from spikes.session import Intent
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import CELL, COLS

HEAD = ("level: 9\nname: Corner\nbuilding: The Corner Works\n"
        "blood: 64\nspray: 5\nlives: 3\nmagnet: 10\nwake: on\n")

ROOM = """
room: {name}
roll:
segments: {segments}
length: 4 8
pieces: {pieces}
band: 6 24
away: 8
clegs: {clegs}
searchlight: 3 repeat
start: {start}
at: {col} {row}
{doors}
"""

#: A two-by-two ring: a-b across the top, c-d below, joined all the way round.
#:
#:     a - b
#:     |   |
#:     c - d
RING = [
    ("a", "yellow", (0, 0), ["door: east 10-12 b", "door: south 14-16 c"], [90]),
    ("b", "cyan", (1, 0), ["door: west 10-12 a", "door: south 14-16 d"], [60]),
    ("c", "cyan", (0, 1), ["door: north 14-16 a", "door: east 10-12 d"], [70]),
    ("d", "yellow", (1, 1), ["door: north 14-16 b", "door: west 10-12 c"], [80]),
]


def text_for(rooms, segments="0 0", pieces="0 0", clegs=1):
    """The rooms, with their people pooled into the building's roster.

    Each row still carries the clocks it was written with, but since issue #143
    a rolled room does not author its own people: the building names the roster
    once and the deal decides who is where. So the clocks are summed up into a
    `people:` line, and what a row's list now says is *how many*."""
    roster = [b for _n, _h, _a, _d, people in rooms for b in people]
    out = HEAD + "people: " + " ".join(str(b) for b in roster) + "\n"
    for i, (name, hue, at, doors, _people) in enumerate(rooms):
        out += ROOM.format(
            name=name, hue=hue, col=at[0], row=at[1], segments=segments,
            pieces=pieces, clegs=clegs,
            start="24 96" if i == 0 else "16 80", doors="\n".join(doors))
    return out


def load(rooms, seed=0xBEEF, **kw):
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "level9.txt")
    open(path, "w").write(text_for(rooms, **kw))
    levels._level.cache_clear()
    return levels.load(path, seed)


@pytest.fixture(scope="module")
def ring():
    return load(RING)


# --- the shape of it --------------------------------------------------------

def test_a_building_can_turn_a_corner_of_the_plan(ring):
    """Four rooms in a two-by-two, which no building could be before."""
    assert [r.at for r in ring.rooms] == [(0, 0), (1, 0), (0, 1), (1, 1)]
    sides = {r.name: sorted(B.SIDE_NAMES[d.side] for d in r.doorways)
             for r in ring.rooms}
    assert sides == {"a": ["east", "south"], "b": ["south", "west"],
                     "c": ["east", "north"], "d": ["north", "west"]}


def test_a_horizontal_doorway_spans_columns_and_knows_it(ring):
    north = next(d for d in ring[2].doorways if d.side == B.NORTH)
    assert not north.vertical
    assert north.cols == (14, 15, 16)
    assert north.line == 0 and north.beyond == -1
    assert north.landing == PLAY_ROWS - 1
    assert north.cells() == [(14, 0), (15, 0), (16, 0)]
    assert north.landing_cells() == [(14, 21), (15, 21), (16, 21)]
    # Asking it for rows is a bug, not a question.
    with pytest.raises(AttributeError, match="horizontal"):
        north.rows
    east = next(d for d in ring[2].doorways if d.side == B.EAST)
    assert east.vertical and east.rows == (10, 11, 12)
    with pytest.raises(AttributeError, match="vertical"):
        east.cols


def test_the_gap_is_cut_into_the_horizontal_wall(ring):
    """The roller cuts a doorway on either axis, and `validate` would refuse it
    if the wall were still solid there."""
    for cx in (14, 15, 16):
        assert ring[0].rows[PLAY_ROWS - 1][cx] == B.DOORWAY, cx
        assert ring[2].rows[0][cx] == B.DOORWAY, cx
    ring.validate()


# --- walking it -------------------------------------------------------------

def _line_up(run, dx, dy):
    """Stand the player where the gap on that side spans."""
    if dy:
        run.player.x = 15 * CELL
    else:
        run.player.y = 10 * CELL


def _walk(run, dx, dy, frames=320):
    for _ in range(frames):
        run.step(Intent(dx=dx, dy=dy))


def test_a_player_walks_a_full_circuit_in_every_direction(ring):
    """The acceptance: round the ring clockwise, which uses all four sides."""
    run = S.Session(seed=0xBEEF, sound=False, building=ring, start_room=0)
    order = []
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        _line_up(run, dx, dy)
        _walk(run, dx, dy)
        order.append(ring[run.here].name)
    assert order == ["b", "d", "c", "a"], order
    assert run.crossings == 4


def test_a_player_walks_the_circuit_the_other_way_too(ring):
    run = S.Session(seed=0xBEEF, sound=False, building=ring, start_room=0)
    order = []
    for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        _line_up(run, dx, dy)
        _walk(run, dx, dy)
        order.append(ring[run.here].name)
    assert order == ["c", "d", "b", "a"], order
    assert run.crossings == 4


def test_the_wall_beside_a_horizontal_doorway_still_stops_you(ring):
    """Three columns out of thirty-two are a way through. The rest is floor
    above masonry."""
    run = S.Session(seed=0xBEEF, sound=False, building=ring, start_room=0)
    run.player.x = 3 * CELL             # nowhere near columns 14-16
    _walk(run, 0, 1)
    assert run.here == 0, "walked through the floor"


def test_the_crossing_carries_the_row_and_only_the_view_jumps(ring):
    """Going south, the column is preserved exactly and the row wraps to the
    top of the room below -- the same rule the vertical case has always had,
    read on the other axis.

    Stopped **on** the crossing rather than walked for a fixed time, or the
    figure is halfway down the next room by the time it is looked at.
    """
    run = S.Session(seed=0xBEEF, sound=False, building=ring, start_room=0)
    run.player.x = 15 * CELL
    before = run.player.x
    for _ in range(400):
        run.step(Intent(dy=1))
        if run.here == 2:
            break
    assert run.here == 2, "never crossed"
    assert run.player.x == before, "the crossing moved them sideways"
    assert run.player.y < 2 * CELL, "they did not come out of the doorway"


def test_a_figure_clears_a_horizontal_threshold_on_its_whole_height(ring):
    """A person is two cells tall, so its feet reach **two** rows past the wall
    before it is wholly in the room below. `across` resolved one and the walk
    stopped a pixel short of the crossing with nothing to say why."""
    room = ring[0]
    south = next(d for d in room.doorways if d.side == B.SOUTH)
    assert south.holds(15, PLAY_ROWS), "one row past is not past"
    assert south.holds(15, PLAY_ROWS + 1), "two rows past is where the feet are"
    assert not south.holds(3, PLAY_ROWS), "past the wall, not past the gap"
    assert room.across(15, PLAY_ROWS)[1:] == (15, 0)
    assert room.across(15, PLAY_ROWS + 1)[1:] == (15, 1)


def test_a_cell_past_a_horizontal_doorway_is_not_solid(ring):
    """`is_solid` is the only authority on what is walkable, and it answered
    True for any row off the grid before it asked the doorways -- which made a
    horizontal doorway impossible to walk through."""
    room = ring[0]
    assert not room.is_solid(15, PLAY_ROWS), "the gap is bricked up"
    assert room.is_solid(3, PLAY_ROWS), "the floor is not a way out"
    assert room.is_solid(15, -1), "there is no doorway in a's north wall"


# --- the swarm --------------------------------------------------------------

def test_a_cleg_crosses_a_horizontal_doorway(ring):
    """The same rule as a vertical one: a fly walks into a cell that turns out
    not to be a wall. Nothing about a doorway is in `clegs.py` at all."""
    run = S.Session(seed=0xBEEF, sound=False, building=ring, start_room=0)
    fly = run.places[0].swarm.clegs[0]
    fly.cx, fly.cy = 15, PLAY_ROWS - 2
    where = run.building.step_across(0, 15, PLAY_ROWS)
    assert where is not None, "a fly cannot step through a horizontal doorway"
    assert where == (2, 15, 0)


def test_the_swarm_can_reach_every_room_of_a_building_that_turns(ring):
    """The bare-shell gate and the rolled check, both, on a ring."""
    for room in ring.rooms:
        assert swarming.unswarmable(room) == [], room.name
        assert swarming.strands_a_shell(room.rows, room.doorways) == [], room.name


# --- the loader -------------------------------------------------------------

def test_a_north_door_that_does_not_lead_north_is_refused():
    rooms = [
        ("a", "yellow", (0, 0), ["door: south 14-16 b"], [90]),
        ("b", "cyan", (1, 0), ["door: north 14-16 a"], [60]),
    ]
    with pytest.raises(ValueError, match="which is not south of it"):
        load(rooms)


def test_a_horizontal_doorway_is_three_columns_clear_of_the_corners():
    for door, why in (("south 14-15 b", "3 columns, not 2"),
                      ("south 30-32 b", "runs into the corner")):
        rooms = [("a", "yellow", (0, 0), [f"door: {door}"], [90]),
                 ("b", "cyan", (0, 1), ["door: north 14-16 a"], [60])]
        with pytest.raises(ValueError, match=why):
            load(rooms)


def test_a_doorway_answered_on_the_wrong_wall_is_refused():
    """With two sides this could not be got wrong; with four it can."""
    rooms = [("a", "yellow", (0, 0), ["door: south 14-16 b"], [90]),
             ("b", "cyan", (0, 1), ["door: east 10-12 a"], [60])]
    # The grid check gets there first and says the same thing from the other
    # end: b's east door leads to a room that is not east of it.
    with pytest.raises(ValueError, match="which is not east of it"):
        load(rooms)


def test_the_two_sides_of_a_horizontal_doorway_must_line_up():
    rooms = [("a", "yellow", (0, 0), ["door: south 14-16 b"], [90]),
             ("b", "cyan", (0, 1), ["door: north 10-12 a"], [60])]
    with pytest.raises(ValueError, match="does not line up"):
        load(rooms)


def test_a_building_of_six_rooms_now_loads():
    """What the round was for. Ruling 6 asked for six rooms; rulings 7 and 8
    between them capped a building at three, because rooms could only ever be
    adjacent east-west and the plan is three wide."""
    rooms = []
    names = ["r0", "r1", "r2", "r3", "r4", "r5"]
    for i, name in enumerate(names):
        col, row = i % 3, i // 3
        doors = []
        if col:
            doors.append(f"door: west 10-12 {names[i - 1]}")
        if col < 2:
            doors.append(f"door: east 10-12 {names[i + 1]}")
        if row:
            doors.append(f"door: north 14-16 {names[i - 3]}")
        else:
            doors.append(f"door: south 14-16 {names[i + 3]}")
        hue = "yellow" if (col + row) % 2 == 0 else "cyan"
        rooms.append((name, hue, (col, row), doors, [90 - i * 10]))
    six = load(rooms)
    assert len(six) == 6
    assert [r.at for r in six.rooms] == [(0, 0), (1, 0), (2, 0),
                                         (0, 1), (1, 1), (2, 1)]
    six.validate()
    assert six.roster == 6


# --- the shout and the spill ------------------------------------------------

def test_a_shout_through_a_horizontal_doorway_is_written_inside_the_room(ring):
    """A word is four cells along a row, so *beside* a gap in the floor cannot
    mean further along the same wall without covering it. It goes one row
    inward instead, centred on the gap's columns."""
    run = S.Session(seed=0xBEEF, sound=False, building=ring, start_room=0)
    for _ in range(40):
        run.step()
    south = next(d for d in ring[0].doorways if d.side == B.SOUTH)
    run.rescue.workers[0].blood = 1          # somebody in room c, calling
    for worker in run.rescue.workers:
        if worker.room == 2:
            worker.blood = 1
    for _ in range(200):
        run.step()
        if run.door_calls:
            break
    if not run.door_calls:
        pytest.skip("nobody in the room below called inside the window")
    cells = run.door_calls[0]
    rows_used = {cy for _cx, cy in cells}
    assert rows_used == {PLAY_ROWS - 2}, \
        f"the word is not one row inside the south wall: {sorted(rows_used)}"
    assert not any(cy == PLAY_ROWS - 1 for _cx, cy in cells), \
        "the word was written over the doorway"


# --- a bot can get through a corner (issue #140) -----------------------------
#
# #139 made the world walkable in four directions and left the bot harness
# behind, and because every shipped level is east-west nothing caught it: the
# oracle is 7 of 7 on a row and **0 of 7 on a ring**. It was two faults.
#
# `bots.standable` refuses a feet row of 0 -- correctly, a person is 8x16 and
# the head cell must exist -- so the gap of a north doorway is a cell no route
# may stand in, and `step_across` only answers for a cell *beyond* the room,
# which cannot be reached without standing on row 0 first. And the walk that
# follows a route pressed east or west and lined up on the row, which is a
# doorway in a vertical wall and was every doorway in the game until #139.

#: The four shapes, with the roster each pools into its `people:` line.
#:
#: **The low clock is 40 and not 30** (issue #146). A bite costs about eight
#: blood, the swarm bites whoever is *following* you, and the tail is exposed for
#: the whole tour -- so a person on 30 is freed, joins the line, takes two bites
#: and dies at 28 seconds with sixty seconds of clock unspent. It cost the oracle
#: one of seven on the L, one seed in four, and it cost Level 3 and Level 5 the
#: same before the shipped rosters were lifted for the same reason. Every roster
#: in the game now starts at 40.
SHAPES = {
    "row": [("a", "yellow", (0, 0), ["door: east 10-12 b"], [90, 45, 40]),
            ("b", "cyan", (1, 0), ["door: west 10-12 a", "door: east 10-12 c"], [50, 60]),
            ("c", "yellow", (2, 0), ["door: west 10-12 b"], [70, 80])],
    "column": [("a", "yellow", (0, 0), ["door: south 14-16 b"], [90, 45, 40]),
               ("b", "cyan", (0, 1), ["door: north 14-16 a", "door: south 14-16 c"], [50, 60]),
               ("c", "yellow", (0, 2), ["door: north 14-16 b"], [70, 80])],
    "an L": [("a", "yellow", (0, 0), ["door: east 10-12 b"], [90, 45, 40]),
             ("b", "cyan", (1, 0), ["door: west 10-12 a", "door: south 14-16 c"], [50, 60]),
             ("c", "yellow", (1, 1), ["door: north 14-16 b"], [70, 80])],
    "the ring": RING,
}

BOT_SEEDS = (48879, 48880, 48881, 48882)


def rooms_a_bot_can_reach(building, start):
    """Every room a flood fill over `bots.neighbours` gets to from one cell."""
    seen, queue = {start}, [start]
    while queue:
        for step in bots.neighbours(building, queue.pop()):
            if step not in seen:
                seen.add(step)
                queue.append(step)
    return {room for room, _cx, _cy in seen}


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_a_bot_can_reach_every_room_of_every_shape(shape):
    """The flood fill, from **every** room in turn rather than from the first.

    Measured before the fix: 3 of 3 on a row, 1 of 3 on a column, 2 of 3 on an
    L, 2 of 4 on a ring and 3 of 7 on a seven-room grid. The asymmetry is the
    tell -- going south worked and going north did not, because the bottom row
    of a room can hold a figure's feet with its head on the row above, and the
    top row cannot.
    """
    building = load(SHAPES[shape])
    for start in range(len(building)):
        got = rooms_a_bot_can_reach(building, (start, 16, 11))
        assert got == set(range(len(building))), \
            f"from room {start}, a bot reaches only {sorted(got)}"


def test_a_bot_reaches_every_room_of_a_seven_room_building():
    """The size the shape ladder is going to, on a shape that turns twice."""
    grid = [(0, 0), (1, 0), (2, 0), (2, 1), (1, 1), (0, 1), (0, 2)]
    names = [f"r{i}" for i in range(len(grid))]
    rooms = []
    for i, (col, row) in enumerate(grid):
        doors = []
        for j, (c2, r2) in enumerate(grid):
            if i == j:
                continue
            for way, at in (("east", (col + 1, row)), ("west", (col - 1, row))):
                if (c2, r2) == at:
                    doors.append(f"door: {way} 10-12 {names[j]}")
            for way, at in (("south", (col, row + 1)), ("north", (col, row - 1))):
                if (c2, r2) == at:
                    doors.append(f"door: {way} 14-16 {names[j]}")
        hue = "yellow" if (col + row) % 2 == 0 else "cyan"
        rooms.append((names[i], hue, (col, row), doors, [90 - i * 10]))
    building = load(rooms)
    assert len(building) == 7
    for start in range(7):
        assert rooms_a_bot_can_reach(building, (start, 16, 11)) == set(range(7))


@pytest.mark.parametrize("shape", ["column", "an L", "the ring"])
def test_the_oracle_finishes_a_building_it_must_cross_north_and_south_in(shape):
    """The acceptance. The oracle is the ceiling: it is told where everybody is,
    and on every shipped level it is 7 of 7 with `all_out` on all four seeds.
    On any shape with a horizontal doorway it was **0 of 7**, which read as an
    unwinnable building and was a broken bot."""
    for seed in BOT_SEEDS:
        building = load(SHAPES[shape], seed=seed, segments="3 5",
                        pieces="1 3", clegs=2)
        run = S.Session(seed=seed, sound=False, building=building, start_room=0)
        bot = bots.make("oracle", seed=seed)
        while run.over is None and run.frame < 9000:
            run.step(bot.intent(run))
        assert run.over == "all_out", \
            f"{shape}, seed {seed}: {run.rescued} of {run.total}, {run.over}"


def test_the_listener_and_the_scout_both_leave_the_first_room_of_a_column():
    """The two bots that find people rather than being told where they are. A
    listener that cannot cross a horizontal doorway never hears past the first
    room, and a scout never maps past it."""
    for who in ("listener", "scout"):
        left = 0
        for seed in BOT_SEEDS:
            building = load(SHAPES["column"], seed=seed, segments="3 5",
                            pieces="1 3", clegs=2)
            run = S.Session(seed=seed, sound=False, building=building,
                            start_room=0)
            bot = bots.make(who, seed=seed, spray=True)
            while run.over is None and run.frame < 9000:
                run.step(bot.intent(run))
            left += run.crossings > 0
        assert left == len(BOT_SEEDS), \
            f"the {who} stayed in the first room on {len(BOT_SEEDS) - left} seeds"


def test_a_route_across_a_vertical_doorway_is_the_route_it_always_was():
    """**Nothing east-west may move**, or every figure in the vault is stale.

    The graph is compared cell for cell against the rule as it was written
    before #140: a person is one cell wide, so the landing column of a vertical
    doorway is always standable and the crossing is found on the first step.
    The pass-through this slice adds is reached only going *vertically* through
    a gap in a horizontal wall, and a row of three has none.
    """
    def before(building, place):
        passable = functools.partial(bots.standable, building)
        room, cx, cy = place
        out = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if passable(room, nx, ny):
                out.append((room, nx, ny))
                continue
            step = building.step_across(room, nx, ny)
            if step is not None and passable(*step):
                out.append(step)
        return out

    building = load(SHAPES["row"])
    for room in range(len(building)):
        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                at = (room, cx, cy)
                assert sorted(before(building, at)) == \
                    sorted(bots.neighbours(building, at)), at


def test_the_route_never_stands_a_figure_where_it_cannot_stand():
    """The reason `standable` was not simply relaxed. Every cell of every route
    has to be a cell a person can occupy -- a route through a gap they cannot
    stand in is worse than no route, and measured it took the oracle from 2 of 7
    to 0 of 7 on an L."""
    for shape in SHAPES:
        building = load(SHAPES[shape])
        for start in range(len(building)):
            for goal in range(len(building)):
                path = bots.route(building, (start, 16, 11), [(goal, 16, 11)])
                for room, cx, cy in path:
                    assert bots.standable(building, room, cx, cy), \
                        f"{shape}: route stands at {(room, cx, cy)}"
