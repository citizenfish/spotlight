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
PINNED_CLOCKS_A = (90, 40, 30)
PINNED_CLOCKS_B = (50, 60, 70, 80)
PINNED_LIGHTS_B = ((0, 10, 3, 3),)
PINNED_START = (24, 96)
PINNED_DOOR_ROWS = (10, 11, 12)


def test_level_three_is_the_playtest_buildings_shell():
    b = levels.level(3)
    assert [r.name for r in b.rooms] == ["the main room", "the far room"]
    near, far = b.rooms
    assert tuple(w[2] for w in near.workers) == PINNED_CLOCKS_A
    assert tuple(w[2] for w in far.workers) == PINNED_CLOCKS_B
    assert len(near.clegs) == 3 and len(far.clegs) == 3
    assert near.lights == () and far.lights == PINNED_LIGHTS_B
    assert near.has_exit and not far.has_exit
    assert near.ink == B.palette(YELLOW) and far.ink == B.palette(CYAN)
    assert near.searchlight.radius == 3 and near.searchlight.vary is False
    # The far room's beam varies (issue #118): every room has one now.
    assert far.searchlight.radius == 3 and far.searchlight.vary is True
    assert near.searchlight.pace == 6 and near.searchlight.mount == 0
    assert near.player_start == PINNED_START
    assert b.start == (0, PINNED_START)
    assert [(d.side, d.rows, d.to) for d in near.doorways] == [(B.EAST, PINNED_DOOR_ROWS, 1)]
    assert [(d.side, d.rows, d.to) for d in far.doorways] == [(B.WEST, PINNED_DOOR_ROWS, 0)]
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
floor: yellow
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
    (MINIMAL.replace("floor: yellow", "floor: red"), "floor must be"),
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
    body = f"\nroom: {name}\nfloor: {hue}\nmap:\n" + "\n".join(rows) + "\nworker: 40 40 60\ncleg: 20 5\nsearchlight: 3 repeat\nstart: 40 40\n"
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
    from spikes import session
    assert B.DEFAULT_BUDGET == (session.BLOOD_FULL, 5, session.LIVES,
                                session.MAGNET_FRAMES // 50, True)
    assert levels.level(3).budget == B.DEFAULT_BUDGET
    # The magnet's seconds and wake are the level's since issue #118.
    assert levels.level(2).budget == B.Budget(64, 5, 3, magnet=8, wake=False)
    assert levels.level(1).budget == B.Budget(64, 3, 3, magnet=5, wake=False)


def test_a_level_without_a_budget_gets_the_constants():
    text = "level: 9\nname: Bare\n" + _room("only", "yellow", [])
    number, name, specs, budget = levels.parse(text)
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


def test_pace_and_mount_are_the_rooms_and_are_bounded():
    text = "level: 9\nname: X\n" + _room("only", "yellow", []).replace(
        "start: 40 40\n", "pace: 8\nmount: 2\nstart: 40 40\n")
    room = levels.build(levels.parse(text)[2])[0]
    assert room.searchlight.pace == 8 and room.searchlight.mount == 2
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

def test_level_four_and_on_is_level_three_tightened():
    """Every clock three points shorter a level to a floor of 22; one more
    fly a level in the far room from the first level at the floor, to nine
    in the building; every beam varies from Level 5."""
    three = levels.level(3)
    clocks = lambda b: [w[2] for r in b.rooms for w in r.workers]  # noqa: E731
    assert clocks(levels.level(4)) == [c - 3 for c in clocks(three)]
    assert min(clocks(levels.level(6))) == 22
    assert min(clocks(levels.level(20))) == 22
    assert [len(r.clegs) for r in levels.level(6).rooms] == [3, 3]
    assert [len(r.clegs) for r in levels.level(7).rooms] == [3, 4]
    assert [len(r.clegs) for r in levels.level(9).rooms] == [3, 6]
    assert [len(r.clegs) for r in levels.level(12).rooms] == [3, 6]
    assert not levels.level(4)[0].searchlight.vary
    assert all(r.searchlight.vary for r in levels.level(5).rooms)
    assert levels.level(5).level == 5 and levels.level(5).title == "Rescue"
    assert levels.level(5).budget == three.budget


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
