"""The shapes and the dial ladder, asserted from the loaded buildings.

Issue #146, from *The bigger buildings* §2 and §3. Every building in the game
was a row of three rooms and every doorway was in an east or a west wall; the
five slices before this one made a grid of nine possible and nothing used it.

**Rooms are lettered by their place on the plan**, which is how the vault names
them and how a reader checks a shape against the note:

       A ----- B ----- E          A (0,0)  B (1,0)  E (2,0)
       |       |       |          C (0,1)  D (1,1)  F (2,1)
       C ----- D ----- F          H (0,2)  G (1,2)  I (2,2)
       |       |       |
       H       G       I

`A` always holds the way out.

**Levels 1 to 3 are three teaching shapes and not a chain.** A row, a corner and
a column: each meets one axis with the rest of the game held still, and none is
a superset of another. The issue's table says "each is a superset of the one
before" and that is true only from Level 4 -- which is why Levels 4 and up come
out of `ladder.txt`, a ninth-room building they are cut from, rather than out of
Level 3. A column cannot be turned into a ring by turning dials.
"""

import pytest

from spikes import building as B, levels, session as S
from spotlight.core.constants import CYAN, YELLOW

#: (column, row) -> the letter the vault calls that room.
LETTER = {(0, 0): "A", (1, 0): "B", (2, 0): "E",
          (0, 1): "C", (1, 1): "D", (2, 1): "F",
          (0, 2): "H", (1, 2): "G", (2, 2): "I"}


def shape(building) -> str:
    """The building's rooms as letters, in room order."""
    return " ".join(LETTER[room.at] for room in building.rooms)


def edges(building) -> list[str]:
    """Every doorway as the pair of letters it joins, sorted and deduplicated."""
    seen = set()
    for i, room in enumerate(building.rooms):
        for door in room.doorways:
            seen.add("".join(sorted((LETTER[building[i].at],
                                     LETTER[building[door.to].at]))))
    return sorted(seen)


def leaves(building) -> list[str]:
    return sorted(LETTER[r.at] for r in building.rooms if len(r.doorways) <= 1)


#: The shapes, exactly as the issue's table gives them.
SHAPES = {
    1: ("A B E", ["AB", "BE"]),
    2: ("A B D", ["AB", "BD"]),
    3: ("A C H", ["AC", "CH"]),
    4: ("A B C D", ["AB", "AC", "BD", "CD"]),
    5: ("A B C D", ["AB", "AC", "BD", "CD"]),
    6: ("A B C D E", ["AB", "AC", "BD", "BE", "CD"]),
    7: ("A B C D E", ["AB", "AC", "BD", "BE", "CD"]),
    8: ("A B C D E F G", ["AB", "AC", "BD", "BE", "CD", "DF", "DG", "EF"]),
    9: ("A B C D E F G H I",
        ["AB", "AC", "BD", "BE", "CD", "CH", "DF", "DG", "EF", "FI"]),
}


@pytest.mark.parametrize("level", sorted(SHAPES))
def test_every_shape_is_the_one_the_note_draws(level):
    """Asserted from the loaded building and never from the file text, because
    the file text is not what the game plays: Levels 4 and up are the ladder cut
    to size, and what has to be right is the cut."""
    want_shape, want_edges = SHAPES[level]
    building = levels.level(level)
    assert shape(building) == want_shape, level
    assert edges(building) == want_edges, level


def test_the_ladder_is_one_authored_building_cut_to_size():
    """4, 4, 5, 5, 7, 9 -- and **eight is skipped deliberately**: seven is the
    last size at which every room holds somebody, so eight would buy one empty
    leaf for nothing.

    Each shape from Level 4 on is a superset of the one before it, which is what
    makes this one authored ladder rather than six buildings. Stated as the
    letters, because that is the claim.
    """
    counts = {n: len(levels.level(n).rooms) for n in range(4, 15)}
    assert [counts[n] for n in range(4, 10)] == [4, 4, 5, 5, 7, 9]
    assert all(counts[n] == levels.MOST_ROOMS for n in range(9, 15))
    assert 8 not in set(counts.values()), counts
    grown = [set(shape(levels.level(n)).split()) for n in (4, 6, 8, 9)]
    for smaller, bigger in zip(grown, grown[1:]):
        assert smaller < bigger, (smaller, bigger)


def test_a_ring_of_seven_is_not_available_and_the_shape_says_why():
    """A grid graph is bipartite, so **every cycle on the plan has an even
    length** -- six or eight, never seven. Nine rooms is therefore two
    four-cycles sharing an edge with three spurs hung below, and not a ring of
    seven with two spurs.

    Asserted through the chequerboard, which is the same fact: two hues
    two-colour the plan, and a cycle that alternates hues must be even.
    """
    building = levels.level(9)
    for room in building.rooms:
        for door in room.doorways:
            assert room.ink[B.FLOOR] != building[door.to].ink[B.FLOOR]
    hues = {LETTER[r.at]: r.ink[B.FLOOR] for r in building.rooms}
    assert len(set(hues.values())) == 2
    assert hues["A"] == B.palette(YELLOW)[B.FLOOR]
    assert hues["B"] == B.palette(CYAN)[B.FLOOR]


# --- the dial ladder ---------------------------------------------------------

#: The issue's table, row by row: rooms, the building's whole swarm, spray
#: charges, the beam's pace and the wall-memory divisor.
LADDER = {
    1: (3, 1, 3, 8, 2),
    2: (3, 6, 5, 6, 2),
    3: (3, 6, 5, 6, 2),
    4: (4, 6, 5, 6, 2),
    5: (4, 6, 5, 6, 2),
    6: (5, 6, 5, 6, 2),
    7: (5, 7, 5, 6, 1),
    8: (7, 8, 5, 6, 1),
    9: (9, 9, 5, 6, 1),
    10: (9, 9, 4, 5, 1),
    13: (9, 9, 3, 5, 1),
    14: (9, 9, 3, 5, 1),
}


@pytest.mark.parametrize("level", sorted(LADDER))
def test_the_dials_arrive_one_at_a_time(level):
    """**Every level from 4 to 10 introduces exactly one thing.**

    Level 4 used to move four at once -- `pace`, `spray`, the wall memory and
    the doorways leaving the middle -- and was the steepest single step in the
    game, while Levels 6 to 9 were nearly flat. Spreading them out addresses
    both with one move, and **Level 4 is expected to get easier**.

    This revises three rows of the previous round's ruling 9, taken three days
    earlier: six-second wall memory now runs to Level 6 rather than Level 3,
    `pace: 5` arrives at 10 rather than 4, and `spray: 4` at 10 rather than 4.
    The reason is that ruling 9 was taken when Level 4 gained nothing
    structural and it now gains a ring, and halving the wall memory on the
    level that introduces a topology makes the topology unlearnable.

    **`pace: 5` is at 10 and not 8, ruled 2026-09-30 on a measurement.** The
    issue's table put it at 8, which made that level two rooms, the eighth fly
    *and* the quicker beam -- and **perfect play could not finish it**: the oracle
    cleared six seeds of eight and on the worst freed all seven people and then
    lost three lives to twenty-seven bites. What made that visible was fixing the
    transposed magnet cell, without which a magnetised fly never crossed a
    horizontal doorway at all. At 10 every level from 1 to 9 clears and no row of
    the ladder moves more than two dials, which the issue's table did not manage.
    """
    rooms, flies, spray, pace, fade = LADDER[level]
    building = levels.level(level)
    assert len(building.rooms) == rooms
    assert building.population == flies, "the fly count is a building total"
    assert building.budget.spray == spray
    assert building.budget.fade == fade
    assert building.rooms[0].searchlight.pace == pace


def test_the_dials_only_ever_move_towards_harder_and_level_eight_is_the_step():
    """The ladder as a difference rather than a table, and **it corrects the
    issue's own prose.**

    The issue says "every level from 4 to 10 introduces exactly one thing" and
    then gives two rows that do not: Level 7 is *the wall memory halves; 7th fly*
    and Level 8 is *a second loop, two junctions; 8th fly* with `pace: 5` in its
    column. The table is the specification and it is what shipped, so what can be
    asserted is the weaker true claim -- **nothing ever moves towards easier, and
    no level-up moves more than two things.**

    **No row moves more than two**, which is better than the issue's own table
    managed: it had Level 8 at three -- two rooms, the eighth fly and `pace: 5` --
    and perfect play could not finish that level. `pace: 5` moved to Level 10 on
    2026-09-30 and the ladder now obeys the principle the round was raised for.

    The busiest rows are the ones that gain rooms *and* a fly, which is the swarm
    ramp running alongside a new shape rather than a dial arriving with another.
    """
    def dials(n):
        b = levels.level(n)
        off = any((d.rows if d.vertical else d.cols) not in
                  ((10, 11, 12), (14, 15, 16))
                  for r in b.rooms for d in r.doorways)
        return (len(b.rooms), b.population, -b.budget.spray, -b.budget.fade,
                -b.rooms[0].searchlight.pace, off)
    for n in range(4, 14):
        now, then = dials(n), dials(n + 1)
        assert all(b >= a for a, b in zip(now, then)), \
            f"level {n + 1} is easier than {n} on some dial: {now} -> {then}"
        moved = sum(a != b for a, b in zip(now, then))
        assert moved <= 3, f"levels {n} to {n + 1} move {moved} things"
    # The swarm grows one at a time to the cap and never jumps.
    swarm = [levels.level(n).population for n in range(4, 15)]
    assert swarm == sorted(swarm) and max(swarm) == levels.MOST_FLIES
    assert all(b - a <= 1 for a, b in zip(swarm, swarm[1:])), swarm
    # And the one row that moves two structural things is Level 8, named.
    def structural(n):
        b = levels.level(n)
        return (len(b.rooms), b.budget.spray, b.budget.fade,
                b.rooms[0].searchlight.pace)
    steps = [n + 1 for n in range(4, 14)
             if sum(a != b for a, b in zip(structural(n), structural(n + 1))) > 1]
    assert steps == [10], steps
    busiest = max(sum(a != b for a, b in zip(dials(n), dials(n + 1)))
                  for n in range(4, 14))
    assert busiest == 2, busiest


def test_the_clock_holds_until_the_building_has_stopped_growing():
    """Everything up to Level 13 is a new shape or a new dial; the clock is what
    is left once neither is. From `CLOCK_FROM` it tightens `CLOCK_STEP` a level
    to the building's own floor (issue #143)."""
    roster = levels.level(9).budget.people
    assert all(levels.level(n).budget.people == roster for n in (10, 13))
    assert levels.level(14).budget.people != roster
    floor = levels.clock_floor(levels.MOST_ROOMS)
    assert min(levels.level(14).budget.people) >= floor
    assert set(levels.level(60).budget.people) == {floor}


def test_the_fourth_room_is_paid_for_in_blood_and_only_at_level_four():
    """Issue #152. The fourth room makes the dark listener walk seventy-three
    per cent further per person delivered, and the ladder was compensating with
    three and a half per cent more blood; `ROOM_BLOOD` is the measured
    difference. Levels 5 and up are unmeasured and must not quietly inherit it.
    """
    # The expected roster for a level, computed the way `_beyond` does but with
    # no gift at all. **Not simply "the same as Level 5"**: `clock_floor` grows
    # seven blood a room, so a seven-room level lifts the short clocks on its
    # own account -- the first cut of this test read that as a leaked gift and
    # failed on Level 8, which is the floor doing its job.
    _n, _name, specs, budget, _s = levels.parse(
        (levels.LEVELS_DIR / levels.LADDER_FILE).read_text())

    def without_a_gift(n):
        floor = levels.clock_floor(levels.ladder_rooms(n))
        cut = levels.CLOCK_STEP * max(0, n - levels.CLOCK_FROM + 1)
        return tuple(max(floor, blood - cut) for blood in budget.people)

    gift = levels.ROOM_BLOOD[4]
    assert set(levels.ROOM_BLOOD) == {4}, "a second level grew a gift"
    assert levels.level(4).budget.people == \
        tuple(b + gift for b in without_a_gift(4))
    for n in (5, 6, 7, 8, 9, 10, 13, 14, 20):
        assert levels.level(n).budget.people == without_a_gift(n), n


def test_the_gift_leaves_every_gap_between_clocks_alone():
    """It is added, never scaled, because the **spacing** is what T7 rests on:
    twenty seconds between deaths is clocks ten blood apart. A multiplier would
    stretch every gap and a floor would crush the short ones."""
    def gaps(roster):
        got = sorted(roster, reverse=True)
        return [a - b for a, b in zip(got, got[1:])]

    # Levels 4 and 5 are both four-room buildings cut from the same ladder, so
    # their clocks differ by the gift and nothing else.
    assert gaps(levels.level(4).budget.people) == \
        gaps(levels.level(5).budget.people)
    assert min(levels.level(4).budget.people) - \
        min(levels.level(5).budget.people) == levels.ROOM_BLOOD[4]


def test_the_doorways_leave_the_middle_at_level_five_and_not_before():
    for n in (1, 2, 3, 4):
        for room in levels.level(n).rooms:
            for door in room.doorways:
                span = door.rows if door.vertical else door.cols
                assert span == (10, 11, 12) if door.vertical else span == (14, 15, 16)
    for n in (5, 6, 7, 8, 9):
        bands = {door.rows if door.vertical else door.cols
                 for room in levels.level(n).rooms for door in room.doorways}
        assert bands == {levels._shifted(None, n)}, (n, bands)
        assert (10, 11, 12) not in bands and (14, 15, 16) not in bands


# --- the standing rules ------------------------------------------------------

def test_level_one_keeps_open_halls_in_all_three_rooms():
    """A standing ruling from the round before: it is where the beam, the spray
    and the swarm are all met for the first time, and an open hall is the room
    you can read while you learn them."""
    _n, _name, specs, _b, _s = levels.parse(
        (levels.LEVELS_DIR / "level1.txt").read_text())
    assert all(not spec.shells for spec in specs)
    for room in levels.level(1).rooms:
        inner = [(cx, cy) for cy in range(1, 21) for cx in range(1, 31)
                 if room.rows[cy][cx] == B.WALL]
        assert not inner, f"{room.name} has an authored wall in it"


def test_the_roster_stays_at_seven_and_never_rises_with_the_rooms():
    for n in range(2, 15):
        assert len(levels.level(n).budget.people) == 7, n
        assert levels.level(n).roster == 7, n
    assert len(levels.level(1).budget.people) == 4


@pytest.mark.parametrize("level", (6, 7, 8, 9))
def test_a_dead_end_is_never_more_than_one_doorway_from_a_loop(level):
    """Or the empty room stops being a gamble and becomes a punishment ninety
    seconds long."""
    building = levels.level(level)
    for i, room in enumerate(building.rooms):
        if len(room.doorways) > 1:
            continue
        neighbour = building[room.doorways[0].to]
        assert len(neighbour.doorways) > 1, \
            f"level {level}: {room.name} hangs off another dead end"


def test_no_building_has_a_dead_end_before_level_six():
    """The ring arrives at Level 4 and the first room with one way out at Level
    6, two levels later: the player learns that going on gets you home, and then
    exactly one room punishes that belief.

    Levels 1 to 3 are chains, so their end rooms have one doorway -- a chain has
    no loop for a dead end to be measured against, and the rule is about the
    buildings that have one.
    """
    for n in (4, 5):
        assert leaves(levels.level(n)) == [], n
    assert leaves(levels.level(6)) == ["E"]


@pytest.mark.parametrize("level", (6, 7, 8, 9))
def test_a_spur_keeps_repeat_and_never_varies(level):
    """The one room you cannot go round is the one room whose light you can
    learn to time."""
    building = levels.level(level)
    for room in building.rooms:
        if len(room.doorways) <= 1:
            assert not room.searchlight.vary, f"level {level}: {room.name}"
    if level >= levels.VARY_FROM:
        assert any(r.searchlight.vary for r in building.rooms), level


@pytest.mark.parametrize("seed", (0xBEEF, 1, 2, 3, 99))
def test_nine_rooms_hold_seven_people_with_two_empty_dead_ends(seed):
    """The mechanic Level 9 exists for: a dead end is worth walking into because
    one in three of them has somebody in it and the building does not say which.

    Which two are empty rolls every run, and both are always dead ends -- the
    dealing rule is #143's and this is the building it was written for.
    """
    building = levels.level(9, seed)
    empty = [LETTER[r.at] for r in building.rooms if not r.workers]
    assert len(empty) == 2, empty
    assert set(empty) <= {"G", "H", "I"}, empty
    assert building.roster == 7


def test_which_spur_holds_the_person_rolls():
    seen = set()
    for seed in range(64):
        building = levels.level(9, seed)
        seen.add(frozenset(LETTER[r.at] for r in building.rooms if not r.workers))
    assert len(seen) == 3, seen
    assert set().union(*seen) == {"G", "H", "I"}


def test_level_sixes_dead_end_always_holds_somebody():
    """At five rooms and seven people no room can be empty, so **the first dead
    end the game ever shows you teaches that a dead end is worth entering.**
    Level 9 is where that is taken away, three level-ups later, and the second
    only means anything because of the first."""
    for seed in range(32):
        building = levels.level(6, seed)
        spur = next(r for r in building.rooms if len(r.doorways) <= 1)
        assert spur.workers, seed


@pytest.mark.parametrize("level", (6, 7, 8, 9))
def test_a_dead_end_never_holds_the_shortest_clock(level):
    """A short clock behind one doorway is a person you find dead."""
    for seed in (0xBEEF, 1, 2, 3):
        building = levels.level(level, seed)
        shortest = min(w[2] for r in building.rooms for w in r.workers)
        for room in building.rooms:
            if len(room.doorways) <= 1 and room.workers:
                assert min(w[2] for w in room.workers) > shortest, \
                    f"level {level} seed {seed}: {room.name}"


# --- the budget and the swarm ------------------------------------------------

@pytest.mark.parametrize("level", list(range(1, 15)) + [20, 26])
def test_every_level_loads_validates_and_fits_the_frame(level):
    building = levels.level(level)
    building.validate()
    assert building.over_budget == 0, (level, building.worst_case())
    assert len(building.rooms) <= levels.MOST_ROOMS


def test_the_swarm_is_a_building_total_dealt_across_the_live_rooms():
    """Never a per-room number (ruling 12). Evenly, with the remainder to the
    deepest rooms, which are the ones a player reaches last."""
    for n in (4, 6, 8, 9):
        building = levels.level(n)
        per = [len(r.clegs) for r in building.rooms]
        assert sum(per) == levels.ladder_flies(n), (n, per)
        assert max(per) - min(per) <= 1, (n, per)
        assert per == sorted(per), (n, per)


def test_the_ladder_file_is_not_a_level():
    """`levels()` globs `level*.txt`; the ladder is not one, so nothing loads it
    by number and `--level 4` goes through the cut."""
    assert levels.levels() == [1, 2, 3]
    assert (levels.LEVELS_DIR / levels.LADDER_FILE).exists()
    assert not levels.LADDER_FILE.startswith("level")


# --- the gate the shapes exist to satisfy ------------------------------------

@pytest.mark.parametrize("level", list(range(1, 10)))
def test_the_oracle_clears_every_level_of_the_ladder(level):
    """**A level a perfect player cannot finish is a broken level, not a hard
    one**, and this is the acceptance the round's shapes are held to.

    Four seeds here and eight when it was measured: `all_out` on 8 of 8 at every
    level from 1 to 9.

    **The swarm bites whoever is following you**, and that is what this gate kept
    finding. A bite costs about eight blood -- sixteen seconds of bleeding -- and
    the tail is exposed for the whole tour, so a person on a low clock is freed,
    joins the line and dies with most of their clock unspent. It cost the oracle a
    person on the ladder's Level 5, on Level 8, on Level 3 and on
    `test_spike_corners`' L, each found separately. Every roster in the game now
    starts at 40 and every one of those clears -- **except Level 3.**

    **Level 3 is the one exception and it is deliberate** (ruled 2026-09-30). Its
    ladder is the one the vault agreed -- `90 80 70 60 50 40 30`, seven clocks ten
    blood apart, which is target T7's twenty seconds between deaths and one body
    window each. Lifting its floor to 40 while keeping ten-blood steps forces
    `100 90 80 70 60 50 40`, and that moves the playtest building's clock span
    from 60-180 seconds to 80-200 and every figure in the vault stated against it.
    That is a bigger change than the fault: the oracle clears **7 of 8 seeds**,
    losing one of seven on the eighth. Recorded here and handed to #147.

    **And the Level 3 carve-out was wrong, 2026-10-04.** It was written when the
    figure was read on four and eight seeds, where no other level ever misses. At
    **thirty-two** the oracle clears 29 to 32 of 32 and the misses are on Levels
    3, 6, 7, 8 and 9 -- so losing a follower is a property of the game and not of
    one level's roster.

    Diagnosed rather than assumed: all eight misses in 288 runs are
    `nobody_left`, every one loses **exactly one** person, every one of those
    people was **following** when they died, and **nobody was ever left
    waiting**. Perfect play reached all seven on all 288 runs. So what this gate
    asserts is the fairness property -- *everybody can be got to* -- and it
    tolerates the jeopardy the game is built on, which is that the tail is
    exposed for the whole tour. See *2026-10-04 Is it fair* in the vault.
    """
    from levelplay import play, SEEDS
    from spikes import rescue as rescue_mod
    for seed in SEEDS:
        run = play(level, "oracle", seed, frames=300 * 50)
        where = f"level {level} seed {seed}"
        # **The fairness clause.** Anybody still waiting at the end was never
        # fetched, which is what an unwinnable building looks like; a person who
        # died in the tail is the swarm, which is the game.
        waiting = [i for i, w in enumerate(run.rescue.workers)
                   if w.state == rescue_mod.WAITING]
        assert not waiting, f"{where}: never reached {waiting}"
        assert run.over != S.FRAME_LIMIT, f"{where}: ran out of frames"
        # And it loses at most one, only ever from the tail.
        assert run.rescued >= run.total - 1, \
            f"{where}: {run.rescued}/{run.total}, {run.over}"


def test_the_tour_gets_longer_as_the_building_grows():
    """What the ladder is for, in the one measure no bot's blindness can flatter:
    how long perfect play takes. 27.5 s at Level 1 to 63.5 s at Level 9 over
    eight seeds, and the three-room teaching levels are within a few seconds of
    one another because they are three shapes of the same size."""
    from levelplay import play, SEEDS
    import statistics
    secs = {n: statistics.mean(play(n, "oracle", s, frames=300 * 50).seconds
                               for s in SEEDS)
            for n in (4, 6, 8, 9)}
    assert secs[4] < secs[6] < secs[8] < secs[9], secs
