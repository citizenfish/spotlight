"""One seed per stream and per room, the entry station that never opens on
the start, and the beam seen in a doorway from both sides (issue #116, The
light round AT)."""

import pytest

from levelplay import SEEDS, play
from spikes import levels, lighting, session as S, sources
from spikes.session import Session


# --- the streams -------------------------------------------------------------

def test_two_rooms_beams_enter_at_different_stations_on_one_seed():
    """Before #116 every searchlight in a building took one seed, so they
    all entered at the same station and swept in step."""
    building = levels.level(2, SEEDS[0])       # every room has a beam
    run = Session(seed=SEEDS[0], building=building)
    entries = [p.roaming.entry for p in run.places]
    assert len(set(entries)) > 1, f"every beam entered at {entries[0]}"


def test_the_same_seed_and_level_give_the_same_entries():
    a = Session(seed=7)
    b = Session(seed=7)
    assert [p.roaming.entry for p in a.places if p.roaming] == \
           [p.roaming.entry for p in b.places if p.roaming]
    assert [c._seed for p in a.places for c in p.swarm.clegs] == \
           [c._seed for p in b.places for c in p.swarm.clegs]


def test_different_levels_give_different_entries_on_one_seed():
    """The level is part of the level seed, so Level 2's beam room and
    Level 3's main room do not sweep the same tour for one run seed."""
    two = Session(seed=SEEDS[0], building=levels.level(2))
    three = Session(seed=SEEDS[0], building=levels.level(3))
    beam_two = [p.roaming for p in two.places if p.roaming][0]
    beam_three = [p.roaming for p in three.places if p.roaming][0]
    assert (beam_two.entry, beam_two._seed) != (beam_three.entry, beam_three._seed)


def test_the_streams_are_distinct_and_never_zero():
    run = Session(seed=1)
    seeds = {run.roll_seed, run._brood_seed,
             *[p.roaming._seed for p in run.places if p.roaming],
             *[c._seed for p in run.places for c in p.swarm.clegs]}
    assert 0 not in seeds
    beams = sum(1 for p in run.places if p.roaming)
    assert len(seeds) == 1 + 1 + beams + 6, "two streams share a seed"


# --- the safe entry ------------------------------------------------------------

def _rooms_with_beams():
    out = []
    for n in levels.levels():
        for i, room in enumerate(levels.level(n).rooms):
            if room.searchlight is not None:
                out.append((n, i))
    return out


@pytest.mark.parametrize("level,room", _rooms_with_beams())
def test_the_beam_never_opens_on_the_start(level, room):
    """The never list's rule 4: on twenty-four seeds, a statue at a beamed
    room's own start is not caught inside ten seconds. Before #116 it was,
    on 12 to 15 of 24."""
    for seed in range(S.DEFAULT_SEED, S.DEFAULT_SEED + 24):
        run = play(level, "statue", seed, room=room, frames=sources.SAFE_ENTRY_FRAMES)
        magnets = [e for e in run.log if e.kind == S.MAGNET]
        assert not magnets, \
            f"seed {seed}: the beam found the start at frame {magnets[0].frame}"


def test_safe_entry_walks_the_route_and_reports_how_far_it_moved():
    beam = sources.Roaming(0, 0, radius=3, seed=48880)
    before = beam.entry
    moved = beam.safe_entry((3, 13))
    assert 0 <= moved < len(sources.KNIGHT_TOUR)
    assert beam.entry == (before + moved) % len(sources.KNIGHT_TOUR)
    # And the promise holds for the beam it left behind.
    for _ in range(sources.SAFE_ENTRY_FRAMES):
        assert not beam.covers(3, 13)
        beam._hold = 0
        beam.update()


def test_the_start_room_is_the_only_room_the_rule_runs_on():
    run = Session(seed=48880, building=levels.level(2), start_room=2)
    assert run.entry_moved == 0, "the wide dark has no beam to move"


# --- the doorway spill ----------------------------------------------------------

def _park(beam, cx, cy):
    """Hold a beam on a cell: no route, no stepping."""
    beam.mode = beam.DRIFT
    beam.x, beam.y = cx, cy
    beam.update = lambda: None


def test_the_far_rooms_beam_shows_in_the_near_rooms_doorway_and_nowhere_else():
    run = Session(seed=1, building=levels.level(2))
    spray, beam_room = run.places[0], run.places[1]
    # The spray room's own beam off (every room has one since issue #118),
    # so the only LIT cells near its east wall are the spill's.
    spray.roaming.enabled = False
    door = beam_room.room.doorway_to(0)          # the beam room's west door
    _park(beam_room.roaming, door.column + 1, 11)
    run.step()
    near = spray.field
    back = spray.room.doorway_to(1)              # the spray room's east door
    lit = {(cx, cy) for cy in range(22) for cx in range(32)
           if near.level_at(cx, cy) >= lighting.LIT}
    spilt = {(back.column, cy) for cy in back.rows}
    assert spilt <= lit, "the doorway cells are not lit from the far side"
    # Nothing else across the wall: the only LIT cells in the near room's
    # last three columns are the doorway's (the room lights and the glow are
    # far from it, and the spray room has no beam of its own).
    across = {c for c in lit if c[0] >= back.column - 2}
    assert across == spilt, across - spilt


def test_a_player_standing_in_the_spilt_doorway_is_a_magnet():
    run = Session(seed=1, building=levels.level(2))
    beam_room = run.places[1]
    door = beam_room.room.doorway_to(0)
    _park(beam_room.roaming, door.column + 1, 11)
    back = run.places[0].room.doorway_to(1)
    run.player.x, run.player.y = back.column * 8, (11 - 1) * 8
    assert (run.player.cx, run.player.cy) == (back.column, 11)
    assert run.beam_on_player()
    run.player.x -= 8
    assert not run.beam_on_player()
