"""Levels are loaded from text, and Level 3 is the playtest building
byte for byte (issue #107, The rooms AK)."""

import pytest

from spikes import building as B, levels, scene
from spotlight.core.constants import CYAN, YELLOW


#: The playtest building's shell, which is what `level3.txt` authors since
#: its rooms began to roll (issue #121): the clocks, the counts, the beams,
#: the door light, the start and the doorways. The maps that were pinned
#: here byte for byte -- A's inner box, B's desks -- are the vault's *The
#: Playtest Building* now, and nothing else.
#: The clocks, room by room. Three rooms since issue #137: the main room keeps
#: its three people, because a first-timer who never finds the doorway ending
#: on three of seven is the top of a tuned band, and the third room took from
#: the far room's four.
#:
#: **The clocks are dealt, not authored, since issue #143.** `level3.txt` names
#: the roster once -- `people: 90 80 70 60 50 40 30` -- and the deal puts the
#: shortest nearest the way out, so nobody is asked to cross the building on the
#: shortest fuse in it. Which room each person is in used to be the author's and
#: is now the shape's, which is what lets a building have more rooms than the
#: file has people.
#:
#: **These are the default seed's, not the building's.** Every room gets one
#: person, and where the four left over go is the roll's, so the three rooms
#: read 3/2/2, 2/3/2 or 2/2/3 depending on the seed -- eight seeds from the
#: default give all three. What never moves is the order: no room holds a
#: shorter clock than a room nearer the way out. `test_the_roster.py` states
#: that as the property; this pins one building.
PINNED_CLOCKS_A = (30, 40, 50)
PINNED_CLOCKS_B = (60, 70)
PINNED_CLOCKS_C = (80, 90)
#: The far room's light sits on the way home, and the way home is in the north
#: wall since Level 3 became a column (issue #146) -- so the zone moved with it.
#: What it is *for* has not changed: the doorway cells are inside the light, which
#: is the collision issue #50 finished.
PINNED_LIGHTS_B = ((14, 0, 3, 3),)
PINNED_START = (24, 96)
PINNED_DOOR_SPAN = (14, 15, 16)


def test_level_three_is_the_playtest_buildings_shell():
    b = levels.level(3)
    assert [r.name for r in b.rooms] == [
        "the main room", "the far room", "the boiler room"]
    near, far, beyond = b.rooms
    assert tuple(w[2] for w in near.workers) == PINNED_CLOCKS_A
    assert tuple(w[2] for w in far.workers) == PINNED_CLOCKS_B
    assert tuple(w[2] for w in beyond.workers) == PINNED_CLOCKS_C
    assert [len(r.clegs) for r in b.rooms] == [2, 2, 2]
    assert near.lights == () and far.lights == PINNED_LIGHTS_B
    assert beyond.lights == ()
    assert near.has_exit and not far.has_exit and not beyond.has_exit
    assert near.ink == B.palette(YELLOW) and far.ink == B.palette(CYAN)
    assert beyond.ink == B.palette(YELLOW)
    assert near.searchlight.radius == 3 and near.searchlight.vary is False
    # The far room's beam varies (issue #118): every room has one now.
    assert far.searchlight.radius == 3 and far.searchlight.vary is True
    assert near.searchlight.pace == 6
    assert near.player_start == PINNED_START
    assert b.start == (0, PINNED_START)
    # Every room says where it is on the plan the opening flashes (issue #134).
    assert [r.at for r in b.rooms] == [(0, 0), (0, 1), (0, 2)]
    # **A column since issue #146**: the chain runs down, so every doorway is in
    # a horizontal wall and its span is columns.
    assert [(d.side, d.cols, d.to) for d in near.doorways] == [(B.SOUTH, PINNED_DOOR_SPAN, 1)]
    assert sorted((d.side, d.cols, d.to) for d in far.doorways) == [
        (B.NORTH, PINNED_DOOR_SPAN, 0), (B.SOUTH, PINNED_DOOR_SPAN, 2)]
    assert [(d.side, d.cols, d.to) for d in beyond.doorways] == [(B.NORTH, PINNED_DOOR_SPAN, 1)]
    assert b.level == 3 and b.title == "Rescue"


def test_scene_is_a_view_of_the_loaded_level():
    assert scene.BUILDING is levels.level(3)
    assert scene.ROOM_A == scene.BUILDING[0].rows
    assert scene.WORKERS_A == scene.BUILDING[0].workers
    assert scene.CLEGS_B == scene.BUILDING[1].clegs
    assert scene.PLAYER_START == PINNED_START and scene.LIGHTS_B == PINNED_LIGHTS_B
    assert scene.SEARCHLIGHT_RADIUS == 3 and scene.SEARCHLIGHT_VARY is False
    assert scene.ROOM_NEAR is scene.BUILDING[0] and scene.ROOM_FAR is scene.BUILDING[1]


def test_the_source_file_is_the_one_the_loader_reads():
    path = levels.LEVELS_DIR / "level3.txt"
    assert path.exists()
    assert levels.load(path, levels.DEFAULT_SEED).rooms[0].rows == \
        levels.level(3).rooms[0].rows
    assert 3 in levels.levels()


def test_a_seed_names_a_level_and_another_rolls_another():
    """Issue #121: the rooms are the seed's."""
    a, b = levels.level(3, 1), levels.level(3, 1)
    assert a is b
    assert levels.level(3, 2)[0].rows != a[0].rows
    assert levels.level(3, 2).seed == 2


def _lines(text: str) -> str:
    return text


MINIMAL = """level: 9
name: Test

room: one
map:
""" + "\n".join(["#" * 32] + ["#" + "." * 30 + "#"] * 20 + ["#" * 32]) + """
worker: 40 40 60
cleg: 20 10
searchlight: 3 repeat
start: 40 40
"""


def test_a_minimal_level_loads():
    b = levels.build(levels.parse(MINIMAL)[2])
    assert len(b.rooms) == 1 and b.rooms[0].workers == ((40, 40, 60),)


@pytest.mark.parametrize("bad, why", [
    (MINIMAL.replace("worker: 40 40 60", "worker: 40 40"), "worker wants 3"),
    (MINIMAL.replace("map:", "floor: red\nmap:"), "no longer a key"),
    (MINIMAL.replace("start: 40 40\n", ""), "no `start:`"),
    (MINIMAL.replace("level: 9\n", ""), "no `level:`"),
    (MINIMAL.replace("worker: 40 40 60", "banana: 1"), "unknown key"),
])
def test_a_malformed_file_names_its_fault(bad, why):
    with pytest.raises(ValueError) as err:
        levels.build(levels.parse(bad, "bad.txt")[2], "bad.txt")
    assert why in str(err.value)


def _room(name, hue, doors, wall_east_gap=False, wall_west_gap=False):
    rows = ["#" * 32]
    for r in range(1, 21):
        east = "d" if (wall_east_gap and r in (10, 11, 12)) else "#"
        west = "d" if (wall_west_gap and r in (10, 11, 12)) else "#"
        rows.append(west + "." * 30 + east)
    rows.append("#" * 32)
    body = f"\nroom: {name}\nmap:\n" + "\n".join(rows) + "\nworker: 40 40 60\ncleg: 20 5\nsearchlight: 3 repeat\nstart: 40 40\n"
    for d in doors:
        body += f"door: {d}\n"
    return body


def test_the_loaders_own_refusals():
    head = "level: 9\nname: Test\n"
    # **Two adjacent rooms cannot share a floor hue any more** (issue #145): the
    # hue is the parity of the room's place on the plan, so a chain alternates by
    # construction and there is nothing left to refuse. The check survives for
    # the one shape that can still break it -- a building with no `at:`, whose
    # rooms take the parity of their index, joined 0 to 2 -- and it is provoked
    # here on purpose rather than left untested.
    apart = (head + _room("one", "yellow", ["east 10-12 three"], True)
             + _room("two", "cyan", []) + _room("three", "yellow", ["west 10-12 one"], False, True))
    with pytest.raises(ValueError) as err:
        levels.build(levels.parse(apart, "t.txt")[2], "t.txt")
    assert "share a floor hue" in str(err.value)
    # **A door may now be anywhere in a vertical wall** (issue #135), so rows
    # 5-7 are legal -- and the map has to have them cut, which `_room` does not
    # do, so this is refused for the right reason instead of the old one.
    rows = head + _room("one", "yellow", ["east 5-7 two"], True) + _room("two", "cyan", ["west 5-7 one"])
    with pytest.raises(ValueError) as err:
        levels.build(levels.parse(rows, "t.txt")[2], "t.txt")
    assert "walled up at 31,5" in str(err.value)
    # What a doorway still has to be: three rows, running together, clear of
    # the corners. A person is two cells tall and three is what a tail files
    # through without queueing.
    for door, why in (("east 10-11 two", "3 rows, not 2"),
                      ("east 20-22 two", "runs into the corner")):
        bad = head + _room("one", "yellow", [door], True) + _room("two", "cyan", ["west 10-12 one"])
        with pytest.raises(ValueError) as err:
            levels.build(levels.parse(bad, "t.txt")[2], "t.txt")
        assert why in str(err.value), (door, str(err.value))
    # A door to a room that does not exist: refused, naming it.
    ghost = head + _room("one", "yellow", ["east 10-12 nowhere"], True)
    with pytest.raises(ValueError) as err:
        levels.build(levels.parse(ghost, "t.txt")[2], "t.txt")
    assert "nowhere" in str(err.value)


# --- the budget (issue #115, The rooms AS) -----------------------------------

def test_the_default_budget_is_the_constants_level_three_was_measured_with():
    from spikes import session
    assert B.DEFAULT_BUDGET[:5] == (session.BLOOD_FULL, 5, session.LIVES,
                                    session.MAGNET_FRAMES // 50, True)
    # Level 3's wall memory is the level's own since issue #137: six seconds
    # for the levels that teach, three from Level 4. `fade` is a rate divisor,
    # so 2 is half rate, and the default stays 1 for a building built by hand.
    # The roster rides on the budget since issue #143, because it is the
    # building's rather than a room's; the default is empty, which is what a
    # building of authored rooms wants.
    assert B.DEFAULT_BUDGET.people == ()
    assert levels.level(3).budget == B.DEFAULT_BUDGET._replace(
        building="The Hollins Hotel", fade=2,
        people=(90, 80, 70, 60, 50, 40, 30))
    assert B.DEFAULT_BUDGET.fade == 1
    # The magnet's seconds and wake are the level's since issue #118; the
    # building's name rides on the budget since issue #126.
    assert levels.level(2).budget == B.Budget(64, 5, 3, magnet=8, wake=False,
                                              fade=2,
                                              people=(90, 80, 80, 70, 70, 60, 40),
                                              building="Marrow Street Baths")
    assert levels.level(1).budget == B.Budget(64, 3, 3, magnet=5, wake=False,
                                              fade=2, people=(90, 90, 80, 70),
                                              building="The Severn Depot")


def test_a_level_without_a_budget_gets_the_constants():
    text = "level: 9\nname: Bare\n" + _room("only", "yellow", [])
    number, name, specs, budget, _shapes = levels.parse(text)
    assert budget == B.DEFAULT_BUDGET


def test_the_session_reads_the_budget_from_the_building():
    from spikes import session as S
    run = S.Session(seed=1, building=levels.level(1))
    assert run.blood == run.blood_full == 64
    assert run.lives == 3
    assert run.spray.charges == 3          # three since issue #121
    # Given to the constructor, blood and lives still win.
    run = S.Session(seed=1, building=levels.level(1), lives=99, blood=10)
    assert run.lives == 99 and run.blood == 10


def test_a_level_with_no_spray_starts_with_no_charges_and_the_key_does_nothing():
    from spikes import session as S
    text = "level: 9\nname: Dry\nspray: 0\n" + _room(
        "only", "yellow", ["east 10-12 other"], True) + _room(
        "other", "cyan", ["west 10-12 only"], wall_west_gap=True)
    dry = levels.build(levels.parse(text)[2]).solo(1)    # solo cuts a way out
    dry.budget = levels.parse(text)[3]
    run = S.Session(seed=1, building=dry)
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


def test_a_room_without_a_searchlight_is_refused():
    """Every room has one (issue #118): the beam is how a room is seen."""
    text = "level: 9\nname: X\n" + _room("only", "yellow", []).replace(
        "searchlight: 3 repeat\n", "")
    with pytest.raises(ValueError, match="no `searchlight:`"):
        levels.build(levels.parse(text)[2])


def test_pace_is_the_rooms_and_is_bounded():
    """`mount:` went in issue #137: the housing's corner rotates round the
    building from the run's seed, so it is not a thing a level authors. It is
    a dead key now, refused rather than skipped -- see
    `test_the_dead_keys_are_refused_not_skipped`."""
    text = "level: 9\nname: X\n" + _room("only", "yellow", []).replace(
        "start: 40 40\n", "pace: 8\nstart: 40 40\n")
    room = levels.build(levels.parse(text)[2])[0]
    assert room.searchlight.pace == 8
    with pytest.raises(ValueError, match="pace is frames per cell"):
        levels.parse("level: 9\nname: X\n" + _room("only", "yellow", []).replace(
            "start: 40 40\n", "pace: 0\nstart: 40 40\n"))
    with pytest.raises(ValueError, match="wake is"):
        levels.parse("level: 9\nname: X\nwake: maybe\n" + _room("only", "yellow", []))


def test_the_dead_keys_are_refused_not_skipped():
    """`torch:` and `spotlight:` went with the torch (issue #119); a stale
    level file must not carry them for ever."""
    body = _room("only", "yellow", [])
    with pytest.raises(ValueError, match="no longer a key"):
        levels.parse("level: 9\nname: X\ntorch: 1000\n" + body)
    with pytest.raises(ValueError, match="no longer a key"):
        levels.parse("level: 9\nname: X\n" + body.replace(
            "start: 40 40\n", "spotlight: 4 4 900\nstart: 40 40\n"))


# --- Level 4 and on (issue #121, ruling 7) ------------------------------------

def test_level_four_and_on_is_the_ladder_and_not_level_three_tightened():
    """**The premise of the old test is gone, and that is issue #146.**

    Levels 4 and up used to be Level 3 re-rolled with the clock cut, which was
    the whole of the progression once the fly count topped out. Level 3 is a
    three-room *column* now, and no amount of dial-turning makes a column into a
    ring -- so the ladder is its own authored nine-room building
    (`levels.LADDER_FILE`) that each level takes the first N rooms of.

    What survives is what the old test was really claiming: the levels past the
    last file are derived rather than authored one by one, and they only ever get
    harder. The whole ladder is asserted in `tests/test_the_ladder.py`; this keeps
    the part that belongs beside the loader.
    """
    assert levels.LAST_FILE == 3 and levels.levels() == [1, 2, 3]
    assert not levels.LADDER_FILE.startswith("level")
    assert (levels.LEVELS_DIR / levels.LADDER_FILE).exists()
    four = levels.level(4)
    assert four.level == 4 and four.title == "Rescue"
    assert len(four.rooms) == 4 and len(levels.level(3).rooms) == 3
    # One authored file, so the shape at Level 9 and at Level 400 is the same
    # nine rooms -- and only the name and the dials differ.
    assert ([r.name for r in levels.level(9).rooms]
            == [r.name for r in levels.level(400).rooms])
    # The dials, as the ladder's table gives them.
    assert [levels.level(n).budget.spray for n in (3, 4, 9, 10, 13, 20)] == \
        [5, 5, 5, 4, 3, 3]
    assert [levels.level(n).budget.fade for n in (3, 4, 6, 7, 9)] == [2, 2, 2, 1, 1]
    # `pace: 5` arrives at Level 10 and not 8 (ruled 2026-09-30): at 8 the level
    # moved two rooms, the eighth fly and the quicker beam at once, and perfect
    # play could not finish it.
    assert [levels.level(n)[0].searchlight.pace for n in (3, 4, 8, 9, 10, 20)] == \
        [6, 6, 6, 6, 5, 5]
    assert not levels.level(4)[0].searchlight.vary
    assert levels.level(5)[0].searchlight.vary
    # Doorways leave the middle of the wall from Level 5 and never return to it.
    assert levels.level(4)[0].doorways[0].rows == (10, 11, 12)
    for n in range(5, 24):
        for room in levels.level(n).rooms:
            for door in room.doorways:
                span = door.rows if door.vertical else door.cols
                assert span not in ((10, 11, 12), (14, 15, 16)), n
    # Each building past the last file has a name of its own (issue #126).
    assert levels.level(4).name == "Blackwell Mill"
    assert levels.level(5).name == "Cutter's Yard"
    assert levels.level(14).name == "Blackwell Mill"


def test_the_worst_case_stays_under_the_ceiling_to_level_nine_and_beyond():
    ceiling = B.ENTITY_CEILING
    assert 100 * levels.level(1).worst_case() // ceiling <= 53
    assert 100 * levels.level(2).worst_case() // ceiling <= 92
    assert 100 * levels.level(3).worst_case() // ceiling <= 92
    assert levels.level(9).worst_case() <= ceiling
    assert levels.level(30).worst_case() <= ceiling


def test_pick_accepts_any_level_from_one():
    assert levels.pick(12)[0].level == 12
    with pytest.raises(ValueError, match="no level 0"):
        levels.pick(0)


def test_a_buildings_name_is_the_levels_and_is_bounded():
    text = "level: 9\nname: X\nbuilding: The Old Assize\n" + _room("only", "yellow", [])
    assert levels.parse(text)[3].building == "The Old Assize"
    with pytest.raises(ValueError, match="goes before the first `room:`"):
        levels.parse("level: 9\nname: X\n" + _room("only", "yellow", []) + "building: Late\n")
    with pytest.raises(ValueError, match="1 to 32 characters"):
        levels.parse("level: 9\nname: X\nbuilding: " + "A" * 33 + "\n" + _room("only", "yellow", []))
