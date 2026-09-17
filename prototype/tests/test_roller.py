"""A room can be a template: an authored shell with a rolled interior,
proved fair over seeds (issue #120, The light round AX).

The proof `roller.py` cannot run: `swarming.unswarmable` on every rolled
room, and the clearance rule read back off the rows. Sixteen seeds per
template in every `pytest`; 128 with `SPOTLIGHT_SLOW=1`; the tester's tool
(`measurements/roll_fairness.py` in the vault) runs a thousand. A template
that fails any seed is a failing test, not a warning.

The templates are every `roll:` room of every level file plus the three
shells below, which are the difficulty table's rows (*The light round* §4)
so that the roller is proved on the shapes the levels take before a level
file carries one.
"""

import os

import pytest

from spikes import building as B, levels, roller, swarming
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import COLS

SEEDS = int(os.environ.get("SPOTLIGHT_ROLL_SEEDS",
                           "128" if os.environ.get("SPOTLIGHT_SLOW") else "16"))
FIRST = 0xBEEF

BOTH = ((B.WEST, (10, 11, 12)), (B.EAST, (10, 11, 12)))
EAST_ONLY = ((B.EAST, (10, 11, 12)),)
WEST_ONLY = ((B.WEST, (10, 11, 12)),)

#: The difficulty table's rows as shells: Level 1's kind room, Level 2's
#: infested middle room, Level 3's main room with the exit.
SHELLS = {
    "dark, an end room": roller.Template(
        segments=(2, 4), length=(4, 8), pieces=(1, 2), band=(8, 18), away=12,
        workers=(70,), clegs=0, doorways=WEST_ONLY, start=(16, 80)),
    "infested, the middle": roller.Template(
        segments=(3, 5), length=(4, 10), pieces=(1, 3), band=(10, 24),
        away=10, workers=(70, 40, 80), clegs=2, doorways=BOTH, start=(16, 80)),
    "rescue, the main room": roller.Template(
        segments=(4, 6), length=(4, 10), pieces=(2, 3), band=(12, 28),
        away=10, workers=(90, 40, 30), clegs=3, doorways=EAST_ONLY,
        start=(24, 96), exit=True),
    "rescue, the far room": roller.Template(
        segments=(4, 6), length=(4, 10), pieces=(2, 3), band=(12, 28),
        away=10, workers=(50, 60, 70, 80), clegs=3, doorways=WEST_ONLY,
        start=(16, 80)),
}


def _level_templates():
    """Every `roll:` room in every level file, as a template."""
    out = {}
    for n in levels.levels():
        _num, _name, specs, _budget = levels.parse(
            (levels.LEVELS_DIR / f"level{n}.txt").read_text())
        for i, spec in enumerate(specs):
            if spec.roll is None:
                continue
            keys = spec.roll
            out[f"level {n}: {spec.name}"] = roller.Template(
                segments=keys.get("segments", (0, 0)),
                length=keys.get("length", (4, 8)),
                pieces=keys.get("pieces", (0, 0)),
                band=keys.get("band", (4, 30)), away=keys.get("away", 6),
                workers=spec.workers, clegs=keys.get("clegs", 0),
                doorways=[(s, r) for s, r, _t, _l in spec.doors],
                start=spec.start, exit=i == 0, lights=spec.lights)
    return out


TEMPLATES = {**SHELLS, **_level_templates()}


def _room(template, rolled) -> B.Room:
    doorways = [B.Doorway(side, rows, to=0) for side, rows in template.doorways]
    return B.Room("rolled", rolled.rows, workers=rolled.workers,
                  clegs=rolled.clegs, player_start=template.start,
                  doorways=doorways, searchlight=B.Searchlight(3, False))


def _solids(rolled) -> set:
    return {(cx, cy) for cy in range(1, PLAY_ROWS - 1) for cx in range(1, COLS - 1)
            if rolled.rows[cy][cx] in B.SOLID}


def _cheb(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


@pytest.mark.parametrize("name", sorted(TEMPLATES))
def test_every_seed_of_every_template_rolls_a_fair_room(name):
    template = TEMPLATES[name]
    feet, head = roller.start_cells(template.start)
    for seed in range(FIRST, FIRST + SEEDS):
        rolled = roller.roll(template, seed, name)
        room = _room(template, rolled)
        room.validate()
        # No pocket: the swarm can reach every floor cell the player can.
        stranded = swarming.unswarmable(room)
        assert not stranded, f"{name} seed {seed:#x}: stranded {stranded[:5]}"
        # The shell: the border, the doorways clear, the exit where it is.
        assert rolled.rows[0] == "#" * COLS and rolled.rows[-1] == "#" * COLS
        for side, rows in template.doorways:
            column = COLS - 1 if side == B.EAST else 0
            inside = COLS - 2 if side == B.EAST else 1
            for cy in rows:
                assert rolled.rows[cy][column] == B.DOORWAY
                assert rolled.rows[cy][inside] == B.FLOOR
        if template.exit:
            assert rolled.rows[10][0] == rolled.rows[11][0] == B.DOOR
        # The clearance rule, read back off the rows.
        solids = _solids(rolled)
        for cx, cy in solids:
            assert 3 <= cx <= COLS - 4 and 3 <= cy <= PLAY_ROWS - 4, \
                f"{name} seed {seed:#x}: a solid at {(cx, cy)} hugs the border"
            assert not (8 <= cy <= 14 and (cx <= 5 or cx >= COLS - 6)), \
                f"{name} seed {seed:#x}: a solid at {(cx, cy)} on a landing"
            assert _cheb((cx, cy), feet) >= 3 and _cheb((cx, cy), head) >= 3, \
                f"{name} seed {seed:#x}: a solid at {(cx, cy)} crowds the start"
        # The people: in the band by route, on standable floor, apart.
        dist = roller.route_distances(rolled.rows, template.start)
        cells = []
        for x, y, blood in rolled.workers:
            cell = (x // 8, (y + 15) // 8)
            assert cell in dist, f"{name} seed {seed:#x}: a person off the map"
            assert template.band[0] <= dist[cell] <= template.band[1], \
                f"{name} seed {seed:#x}: a person {dist[cell]} cells out"
            assert all(_cheb(cell, c) >= 2 for c in cells)
            cells.append(cell)
        assert len(rolled.workers) == len(template.workers)
        # The flies: on floor, away from the start, off the people.
        assert len(rolled.clegs) == template.clegs
        for cx, cy in rolled.clegs:
            assert not room.is_solid(cx, cy)
            assert _cheb((cx, cy), feet) >= template.away, \
                f"{name} seed {seed:#x}: a fly {(cx, cy)} near the start"
            assert all(_cheb((cx, cy), c) >= 2 for c in cells)
        assert rolled.rerolls <= roller.REROLLS


@pytest.mark.parametrize("name", sorted(TEMPLATES))
def test_a_seed_names_a_room_and_two_seeds_differ(name):
    template = TEMPLATES[name]
    a = roller.roll(template, FIRST, name)
    b = roller.roll(template, FIRST, name)
    assert a.rows == b.rows and a.workers == b.workers and a.clegs == b.clegs
    c = roller.roll(template, FIRST + 1, name)
    assert c.rows != a.rows or c.workers != a.workers


def test_the_stream_runs_on_from_room_to_room():
    """Two rooms of one level roll from one stream in turn, so they differ."""
    t = SHELLS["rescue, the far room"]
    first = roller.roll(t, FIRST)
    second = roller.roll(t, first.seed)
    assert second.rows != first.rows


def test_a_template_that_cannot_place_its_people_is_refused_loudly():
    hopeless = roller.Template(band=(500, 600), workers=(90,), start=(16, 80),
                               doorways=WEST_ONLY)
    with pytest.raises(ValueError, match="no room could be rolled"):
        roller.roll(hopeless, FIRST, "hopeless")


def test_the_template_refuses_nonsense():
    with pytest.raises(ValueError, match="not a range"):
        roller.Template(segments=(4, 2)).validate()
    with pytest.raises(ValueError, match="at least two"):
        roller.Template(length=(1, 3)).validate()
    with pytest.raises(ValueError, match="starts dead"):
        roller.Template(workers=(0,)).validate()


# --- the loader ------------------------------------------------------------

def _roll_level(seed: int) -> str:
    return (
        "level: 9\nname: Rolled\n"
        "room: first\nfloor: yellow\nroll:\nsegments: 2 4\nlength: 4 8\n"
        "pieces: 1 2\nband: 8 18\naway: 10\nworker: 90\nclegs: 1\n"
        "searchlight: 3 repeat\nstart: 24 96\ndoor: east 10-12 second\n"
        "room: second\nfloor: cyan\nroll:\nsegments: 2 4\nlength: 4 8\n"
        "band: 8 18\naway: 10\nworker: 80\nclegs: 1\nlight: 0 10 3 3\n"
        "searchlight: 3 repeat\nstart: 16 80\ndoor: west 10-12 first\n")


def test_the_loader_rolls_a_level_from_a_seed():
    number, name, specs, _b = levels.parse(_roll_level(1))
    a = levels.build(specs, "t.txt", roll_seed=0x1234)
    _n, _m, specs2, _b = levels.parse(_roll_level(1))
    b = levels.build(specs2, "t.txt", roll_seed=0x1234)
    assert [r.rows for r in a.rooms] == [r.rows for r in b.rooms]
    assert a[0].has_exit and not a[1].has_exit
    assert a[0].rows != a[1].rows, "two rooms rolled the same"
    assert len(a[0].workers) == 1 and len(a[0].clegs) == 1
    _n, _m, specs3, _b = levels.parse(_roll_level(1))
    c = levels.build(specs3, "t.txt", roll_seed=0x1235)
    assert c[0].rows != a[0].rows
    a.validate()
    alone = a.solo(1)
    assert alone[0].rows[10][0] == B.DOOR


def test_a_rolled_room_without_a_seed_is_refused():
    _n, _m, specs, _b = levels.parse(_roll_level(1))
    with pytest.raises(ValueError, match="no seed"):
        levels.build(specs, "t.txt")


def test_map_and_roll_in_one_room_are_refused():
    text = _roll_level(1).replace("roll:\nsegments: 2 4", "roll:\nmap:", 1)
    with pytest.raises(ValueError, match="not both"):
        levels.parse(text)
    with pytest.raises(ValueError, match="belongs to a `roll:` room"):
        levels.parse("level: 9\nname: X\nroom: a\nfloor: yellow\nband: 1 2\n")
    with pytest.raises(ValueError, match="counts its flies"):
        levels.parse(_roll_level(1).replace("clegs: 1\nsearchlight", "cleg: 4 4\nsearchlight", 1))
