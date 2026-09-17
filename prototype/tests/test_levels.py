"""Levels are loaded from text, and Level 3 is the playtest building
byte for byte (issue #107, The rooms AK)."""

import pytest

from spikes import building as B, levels, scene
from spotlight.core.constants import CYAN, YELLOW


#: The playtest building as `scene._rooms()` authored it before the file
#: existed: the pinned copy the loaded level is held to, field for field.
PINNED_ROOM_A = (
    "################################",
    "#......#.......................#",
    "#......#.......................#",
    "#......#....########...........#",
    "#......#....#......#...........#",
    "#......#....#......#...........#",
    "#...........#......#...........#",
    "#...........###d####...........#",
    "#..............................#",
    "#####.#####....................#",
    "D..............................d",
    "D.........xx[]x................d",
    "#..............................d",
    "#..............................#",
    "#..............................#",
    "#..........========............#",
    "#..............................#",
    "#.......................|......#",
    "#.......................|......#",
    "#.......................|......#",
    "#.......................|......#",
    "################################",
)
PINNED_ROOM_B = (
    "################################",
    "#..............................#",
    "#..............................#",
    "#....|........|........|.......#",
    "#....|........|........|.......#",
    "#....|........|........|.......#",
    "#....|........|........|.......#",
    "#..............................#",
    "#..............................#",
    "#........[][]........[][]......#",
    "d........[][]........[][]......#",
    "d..............................#",
    "d........cxxc........cxxc......#",
    "#........cxxc........cxxc......#",
    "#..............................#",
    "#..............................#",
    "#.......|........|........|....#",
    "#.......|........|........|....#",
    "#.......|........|........|....#",
    "#.......|........|........|....#",
    "#..............................#",
    "################################",
)
PINNED_WORKERS_A = ((141, 128, 90), (115, 34, 40), (232, 152, 30))
PINNED_WORKERS_B = ((40, 144, 50), (131, 40, 60), (224, 24, 70), (232, 152, 80))
PINNED_CLEGS_A = ((2, 3), (29, 8), (6, 20))
PINNED_CLEGS_B = ((16, 2), (28, 11), (10, 19))
PINNED_SPOTLIGHTS_A = ((4, 16, 900), (26, 3, 150))
PINNED_SPOTLIGHTS_B = ((27, 11, 1500),)
PINNED_LIGHTS_B = ((0, 10, 3, 3),)
PINNED_START = (140, 72)
PINNED_DOOR_ROWS = (10, 11, 12)


def test_level_three_is_the_playtest_building_field_for_field():
    b = levels.level(3)
    assert [r.name for r in b.rooms] == ["the main room", "the far room"]
    near, far = b.rooms
    assert near.rows == PINNED_ROOM_A and far.rows == PINNED_ROOM_B
    assert near.workers == PINNED_WORKERS_A and far.workers == PINNED_WORKERS_B
    assert near.clegs == PINNED_CLEGS_A and far.clegs == PINNED_CLEGS_B
    assert near.spotlights == PINNED_SPOTLIGHTS_A and far.spotlights == PINNED_SPOTLIGHTS_B
    assert near.lights == () and far.lights == PINNED_LIGHTS_B
    assert near.ink == B.palette(YELLOW) and far.ink == B.palette(CYAN)
    assert near.searchlight.radius == 3 and near.searchlight.vary is False
    assert far.searchlight is None
    assert near.player_start == PINNED_START
    assert b.start == (0, PINNED_START)
    assert [(d.side, d.rows, d.to) for d in near.doorways] == [(B.EAST, PINNED_DOOR_ROWS, 1)]
    assert [(d.side, d.rows, d.to) for d in far.doorways] == [(B.WEST, PINNED_DOOR_ROWS, 0)]
    assert b.level == 3 and b.title == "Rescue"


def test_scene_is_a_view_of_the_loaded_level():
    assert scene.BUILDING is levels.level(3)
    assert scene.ROOM_A == PINNED_ROOM_A and scene.ROOM_B == PINNED_ROOM_B
    assert scene.WORKERS_A == PINNED_WORKERS_A and scene.CLEGS_B == PINNED_CLEGS_B
    assert scene.PLAYER_START == PINNED_START and scene.LIGHTS_B == PINNED_LIGHTS_B
    assert scene.SEARCHLIGHT_RADIUS == 3 and scene.SEARCHLIGHT_VARY is False
    assert scene.ROOM_NEAR is scene.BUILDING[0] and scene.ROOM_FAR is scene.BUILDING[1]


def test_the_source_file_is_the_one_the_loader_reads():
    path = levels.LEVELS_DIR / "level3.txt"
    assert path.exists()
    assert levels.load(path).rooms[0].rows == PINNED_ROOM_A
    assert levels.levels() == [3] or 3 in levels.levels()


def _lines(text: str) -> str:
    return text


MINIMAL = """level: 9
name: Test

room: one
floor: yellow
map:
""" + "\n".join(["#" * 32] + ["#" + "." * 30 + "#"] * 20 + ["#" * 32]) + """
worker: 40 40 60
cleg: 20 10
start: 40 40
"""


def test_a_minimal_level_loads():
    b = levels.build(levels.parse(MINIMAL)[2])
    assert len(b.rooms) == 1 and b.rooms[0].workers == ((40, 40, 60),)


@pytest.mark.parametrize("bad, why", [
    (MINIMAL.replace("worker: 40 40 60", "worker: 40 40"), "worker wants 3"),
    (MINIMAL.replace("floor: yellow", "floor: red"), "floor must be"),
    (MINIMAL.replace("start: 40 40\n", ""), "no `start:`"),
    (MINIMAL.replace("level: 9\n", ""), "no `level:`"),
    (MINIMAL.replace("worker: 40 40 60", "banana: 1"), "unknown key"),
])
def test_a_malformed_file_names_its_fault(bad, why):
    with pytest.raises(ValueError) as err:
        levels.build(levels.parse(bad, "bad.txt")[2], "bad.txt")
    assert why in str(err.value)


def _room(name, hue, doors, wall_east_gap=False):
    rows = ["#" * 32]
    for r in range(1, 21):
        east = "d" if (wall_east_gap and r in (10, 11, 12)) else "#"
        rows.append("#" + "." * 30 + east)
    rows.append("#" * 32)
    body = f"\nroom: {name}\nfloor: {hue}\nmap:\n" + "\n".join(rows) + "\nworker: 40 40 60\ncleg: 20 5\nstart: 40 40\n"
    for d in doors:
        body += f"door: {d}\n"
    return body


def test_the_loaders_own_refusals():
    head = "level: 9\nname: Test\n"
    # Two adjacent rooms sharing a floor hue: refused.
    same = head + _room("one", "yellow", ["east 10-12 two"], True) + _room("two", "yellow", ["west 10-12 one"])
    with pytest.raises(ValueError) as err:
        levels.build(levels.parse(same, "t.txt")[2], "t.txt")
    assert "share a floor hue" in str(err.value)
    # A door whose rows are not 10-12: refused.
    rows = head + _room("one", "yellow", ["east 5-7 two"], True) + _room("two", "cyan", ["west 5-7 one"])
    with pytest.raises(ValueError) as err:
        levels.build(levels.parse(rows, "t.txt")[2], "t.txt")
    assert "10-12" in str(err.value)
    # A door to a room that does not exist: refused, naming it.
    ghost = head + _room("one", "yellow", ["east 10-12 nowhere"], True)
    with pytest.raises(ValueError) as err:
        levels.build(levels.parse(ghost, "t.txt")[2], "t.txt")
    assert "nowhere" in str(err.value)


# --- the budget (issue #115, The rooms AS) -----------------------------------

def test_the_default_budget_is_the_constants_level_three_was_measured_with():
    from spikes import session, sources
    assert B.DEFAULT_BUDGET == (session.BLOOD_FULL, 5, sources.Cone.FULL,
                                session.LIVES)
    assert levels.level(3).budget == B.DEFAULT_BUDGET
    assert levels.level(2).budget == B.DEFAULT_BUDGET
    assert levels.level(1).budget == B.Budget(64, 0, 1000, 3)


def test_a_level_without_a_budget_gets_the_constants():
    text = "level: 9\nname: Bare\n" + _room("only", "yellow", [])
    number, name, specs, budget = levels.parse(text)
    assert budget == B.DEFAULT_BUDGET


def test_the_session_reads_the_budget_from_the_building():
    from spikes import session as S
    run = S.Session(seed=1, building=levels.level(1))
    assert run.blood == run.blood_full == 64
    assert run.lives == 3
    assert run.cone.power == run.cone_full == 1000
    assert run.spray.charges == 0
    # Given to the constructor, blood and lives still win.
    run = S.Session(seed=1, building=levels.level(1), lives=99, blood=10)
    assert run.lives == 99 and run.blood == 10


def test_a_level_with_no_spray_starts_with_no_charges_and_the_key_does_nothing():
    from spikes import session as S
    run = S.Session(seed=1, building=levels.level(1))
    assert run.spray.charges == 0
    before = len(run.log)
    for _ in range(5):
        run.step(S.Intent(spray=True))
    assert run.tally.sprays == 0
    assert run.spray.charges == 0
    assert not [e for e in run.log[before:] if "spray" in e.kind]
    # And the strip's readout draws no pip for it.
    from spotlight.core.screen import Screen
    from spikes import panel as panel_mod, font
    screen = Screen()
    run.draw(screen)
    region = panel_mod.REGIONS["spray"]
    from screenreader import glyph_at
    for i in range(region.width):
        assert glyph_at(screen, region.col + i, region.row) == \
            tuple(font.BLANK), "a spray pip drawn with no charges"


def test_a_budget_key_is_the_levels_and_negative_or_lifeless_is_refused():
    body = _room("only", "yellow", [])
    with pytest.raises(ValueError, match="goes before the first `room:`"):
        levels.parse("level: 9\nname: X\n" + body + "spray: 2\n")
    with pytest.raises(ValueError, match="cannot be negative"):
        levels.parse("level: 9\nname: X\nblood: -1\n" + body)
    with pytest.raises(ValueError, match="at least one life"):
        levels.parse("level: 9\nname: X\nlives: 0\n" + body)
