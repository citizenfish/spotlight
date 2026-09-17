"""A run takes a building, and every room can be run on its own
(issue #108, The rooms AL).

`Session(building=..., start_room=...)` plays whatever it is handed;
`Building.solo(i)` makes a one-room building out of room `i` with its
doorways bricked up and one of them made the way out; and the bots read the
building from the run, never from `scene`, so the same bot plays any of them.
"""

import pytest

from spikes import bots, building as B, scene, session
from spikes.session import Session


LEVEL = scene.BUILDING


# --- Session takes a building -----------------------------------------------

def test_a_session_left_to_itself_plays_the_scene():
    run = Session(seed=1)
    assert run.building is scene.BUILDING
    assert (run.here, (run.player.x, run.player.y)) == scene.BUILDING.start


def test_a_session_plays_the_building_it_is_given():
    alone = LEVEL.solo(scene.FAR)
    run = Session(seed=1, building=alone)
    assert run.building is alone
    assert len(run.places) == 1
    assert run.here == 0
    assert (run.player.x, run.player.y) == LEVEL[scene.FAR].player_start
    assert len(run.rescue.workers) == len(LEVEL[scene.FAR].workers)


def test_start_room_starts_the_player_in_that_room_at_its_own_start():
    run = Session(seed=1, start_room=scene.FAR)
    assert run.here == scene.FAR and run.start_room == scene.FAR
    assert (run.player.x, run.player.y) == LEVEL[scene.FAR].player_start
    assert len(run.places) == 2, "the rest of the building is still there"


def test_a_death_puts_you_back_at_the_start_room_you_asked_for():
    run = Session(seed=1, start_room=scene.FAR, lives=99)
    # Walk into the far room's swarm until the blood runs out.
    while run.lives == 99:
        run.step()
        assert run.frame < 20000, "nobody bit"
    assert run.here == scene.FAR
    assert (run.player.x, run.player.y) == LEVEL[scene.FAR].player_start


def test_a_room_with_no_start_cannot_be_the_start_room():
    rooms = [B.Room("a", LEVEL[0].rows, ink=LEVEL[0].ink, clegs=LEVEL[0].clegs,
                    player_start=(140, 72), doorways=LEVEL[0].doorways),
             B.Room("b", LEVEL[1].rows, ink=LEVEL[1].ink, clegs=LEVEL[1].clegs,
                    workers=LEVEL[1].workers, doorways=LEVEL[1].doorways)]
    building = B.Building(rooms)
    with pytest.raises(ValueError, match="no start"):
        Session(seed=1, building=building, start_room=1)


# --- Building.solo ------------------------------------------------------------

def test_solo_of_a_room_with_the_exit_only_walls_its_doorways():
    alone = LEVEL.solo(scene.NEAR)
    room = alone[0]
    assert len(alone) == 1 and room.doorways == ()
    assert room.has_exit and alone.exit == (0, LEVEL[scene.NEAR].exit_cell())
    door = LEVEL[scene.NEAR].doorways[0]
    assert all(room.rows[cy][door.column] == B.WALL for cy in door.rows)
    # And nothing else moved.
    for cy, (was, now) in enumerate(zip(LEVEL[scene.NEAR].rows, room.rows)):
        if cy not in door.rows:
            assert was == now, f"row {cy} changed"


def test_solo_of_an_inner_room_makes_its_west_doorway_the_way_out():
    alone = LEVEL.solo(scene.FAR)
    room = alone[0]
    door = LEVEL[scene.FAR].doorway_to(scene.NEAR)
    assert door.side == B.WEST
    top, middle, bottom = sorted(door.rows)
    assert room.rows[top][0] == B.DOOR
    assert room.rows[middle][0] == B.DOOR
    assert room.rows[bottom][0] == B.WALL
    assert room.doorways == ()
    assert alone.exit == (0, (0, top))
    assert alone.exit_facing == (-1, 0)
    assert alone.start == (0, LEVEL[scene.FAR].player_start)


def test_solo_keeps_the_room_as_authored():
    for i, room in enumerate(LEVEL.rooms):
        alone = LEVEL.solo(i)[0]
        assert alone.name == room.name
        assert alone.workers == room.workers
        assert alone.clegs == room.clegs
        assert alone.spotlights == room.spotlights
        assert alone.lights == room.lights
        assert alone.searchlight is room.searchlight
        assert alone.ink == room.ink


def test_solo_is_a_building_the_level_is_not_changed_by():
    before = [r.rows for r in LEVEL.rooms]
    LEVEL.solo(scene.FAR)
    assert [r.rows for r in LEVEL.rooms] == before
    assert LEVEL[scene.FAR].doorways != ()


def test_solo_refuses_a_room_with_no_start():
    rooms = [B.Room("a", LEVEL[0].rows, ink=LEVEL[0].ink, clegs=LEVEL[0].clegs,
                    player_start=(140, 72), doorways=LEVEL[0].doorways),
             B.Room("b", LEVEL[1].rows, ink=LEVEL[1].ink, clegs=LEVEL[1].clegs,
                    workers=LEVEL[1].workers, doorways=LEVEL[1].doorways)]
    with pytest.raises(ValueError, match="no start"):
        B.Building(rooms).solo(1)


# --- the bots read the run ---------------------------------------------------

@pytest.mark.parametrize("name", ["listener", "scout", "statue", "wanderer"])
def test_every_bot_plays_a_room_on_its_own_without_reading_the_scene(
        name, monkeypatch):
    """Take the scene's building away and the bots must not notice."""
    alone = LEVEL.solo(scene.FAR)
    run = Session(seed=3, building=alone)
    monkeypatch.setattr(scene, "BUILDING", None)
    monkeypatch.setattr(scene, "NEAR", None)
    monkeypatch.setattr(scene, "FAR", None)
    bot = bots.BOTS[name](seed=3)
    for _ in range(600):
        run.step(bot.intent(run))
        if run.over is not None:
            break
    assert run.frame > 0


def test_the_listener_walks_out_of_a_room_on_its_own():
    """The far room alone: four people, three flies, and the way out at the
    west wall where the doorway was. The Listener, which knows the building
    it is given, delivers and leaves."""
    run = Session(seed=1, building=LEVEL.solo(scene.FAR), lives=99)
    bot = bots.Listener(seed=1)
    while run.over is None:
        run.step(bot.intent(run))
        assert run.frame < 20000, "the listener never got out"
    assert run.over in (session.ALL_OUT, session.NOBODY_LEFT)
    assert run.rescue.saved > 0, "nobody was walked out"


def test_the_bot_helpers_take_the_building():
    alone = LEVEL.solo(scene.FAR)
    ex, ey = alone.exit[1]
    cells = bots.stand_cells(alone, 0, ex, ey)
    assert cells and all(bots.standable(alone, *c) for c in cells)
    start = (0, alone.start[1][0] // 8, (alone.start[1][1] + 15) // 8)
    assert bots.route(alone, start, cells), "no route to the way out"
    # The doorway was bricked up: nothing steps across into a room that is
    # not there.
    for place in bots.neighbours(alone, (0, 31, 11)):
        assert place[0] == 0
