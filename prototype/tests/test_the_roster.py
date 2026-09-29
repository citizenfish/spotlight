"""The roster belongs to the building, and the clock floor grows with it.

Issue #143, from *The bigger buildings* in the vault. Two rules and a number:

**The roster is the building's.** A room used to author its own `worker:`
clocks, which made a building with more rooms than the file has people
unauthorable -- and made the levels past the last file, which reuse the last
file's rooms, unable to gain a room without inventing a person. A level names
`people:` once and `levels.deal` hands the clocks out.

**The deal is a rule, not a convenience**, because the loader refuses a room
reached only through a room with nobody in it: a shout carries exactly one
doorway, so a silent room on a path strands a listening player. Every room that
is not a dead end is given somebody first, then the dead ends in a rolled
order, then the rest -- so the rooms left empty are always dead ends, and which
ones rolls with the seed. A player who can learn which spur is always empty has
learned the level rather than the building.

**The floor scales with the building and not with a room's depth**, which is
measured rather than assumed: the oracle spends 34.1, 32.8 and 33.7 seconds a
person at depths nought, one and two, because it sweeps deepest-first and walks
everybody out together -- the carry falls exactly as the reach rises. What grows
is the whole tour.

The nine-room building below is a **comb**: a spine of three rooms across the
top with a two-room spur hanging under each. It is a tree with three dead ends,
which is what makes it the shape to ask these questions of -- a full three by
three mesh has no dead end at all, so nothing about emptiness could be asked in
one.
"""

import pytest

from spikes import levels, bots, seeds as S, session as sess


#: The comb, room by room, as (column, row) on the plan. Room 0 holds the exit.
PLAN = ((0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2))
NAMES = tuple("room " + letter for letter in "abcdefghi")
#: The spanning tree: the spine, then a spur south from each room of it.
EDGES = ((0, 1), (1, 2), (0, 3), (1, 4), (2, 5), (3, 6), (4, 7), (5, 8))
#: Room 6, 7 and 8 are the dead ends -- the foot of each spur.
LEAVES = (6, 7, 8)

#: Nine rooms, and the floor is 64 blood: 22 at three rooms plus seven a room
#: for the six past it.
NINE_FLOOR = 64


def comb(people: str = "64 64 64 64 64 64 64", rooms: int = 9) -> str:
    """A level file for the first `rooms` rooms of the comb."""
    doors: dict = {i: [] for i in range(rooms)}
    for a, b in EDGES:
        if a >= rooms or b >= rooms:
            continue
        if PLAN[a][1] == PLAN[b][1]:
            doors[a].append(f"door: east 10-12 {NAMES[b]}")
            doors[b].append(f"door: west 10-12 {NAMES[a]}")
        else:
            doors[a].append(f"door: south 14-16 {NAMES[b]}")
            doors[b].append(f"door: north 14-16 {NAMES[a]}")
    out = ["level: 9\nname: Nine\nbuilding: The Comb\nblood: 64\nspray: 3\n"
           f"lives: 3\nmagnet: 5\nwake: off\nfade: 1\npeople: {people}\n"]
    for i in range(rooms):
        col, row = PLAN[i]
        out.append("\n".join([
            f"\nroom: {NAMES[i]}",
            "floor: " + ("yellow" if (col + row) % 2 == 0 else "cyan"),
            "roll:", "segments: 0 1", "length: 4 8", "pieces: 0 2",
            "band: 6 26", "away: 6", "clegs: 1", "searchlight: 3 repeat",
            "start: 120 96", f"at: {col} {row}"] + doors[i]) + "\n")
    return "".join(out)


def hands(text: str, seed: int) -> list:
    """The deal, as a list of clock lists one a room -- without building."""
    _n, _name, specs, budget, _shapes = levels.parse(text)
    floor = levels.clock_floor(len(specs))
    return levels.deal(specs, [max(floor, b) for b in budget.people],
                       S.people_seed(seed, 9), "comb")


def build(text: str, seed: int):
    """The comb as a real building, rolled and validated for `seed`."""
    _n, name, specs, budget, _shapes = levels.parse(text)
    b = levels.build(specs, "comb", roll_seed=S.roll_seed(seed, 9),
                     people=budget.people, people_seed=S.people_seed(seed, 9))
    b.level, b.title, b.name, b.budget, b.seed = 9, name, budget.building, budget, seed
    return b


#: Enough seeds that "which dead end" is a distribution and not an anecdote.
MANY = range(256)


# --- the key moved ------------------------------------------------------------

def test_a_rolled_room_no_longer_authors_its_own_people():
    """The refusal names the issue, because every shipped level file used to
    carry these lines and anyone reading an old one needs telling where they
    went."""
    text = comb().replace("clegs: 1", "clegs: 1\nworker: 40", 1)
    with pytest.raises(ValueError, match="does not author its own people"):
        levels.parse(text)


def test_the_roster_is_the_levels_and_goes_before_the_first_room():
    with pytest.raises(ValueError, match="`people:` is the level's"):
        levels.parse(comb().replace("people: 64 64 64 64 64 64 64\n", "")
                     + "people: 40\n")
    with pytest.raises(ValueError, match="cannot start on 0 blood"):
        levels.parse(comb(people="64 0 64"))
    with pytest.raises(ValueError, match="at least one clock"):
        levels.parse(comb(people=""))


def test_a_building_that_rolls_needs_a_roster_and_one_that_does_not_refuses_one():
    _n, _name, specs, _b, _s = levels.parse(comb())
    with pytest.raises(ValueError, match="takes its people from the building"):
        levels.build(specs, "comb", roll_seed=1)
    from test_levels import MINIMAL
    _n, _name, authored, _b, _s = levels.parse(MINIMAL)
    with pytest.raises(ValueError, match="no room in this building rolls"):
        levels.build(authored, "min", people=(40,))


def test_every_shipped_level_loads_on_the_new_key():
    for n in (1, 2, 3, 4, 6):
        b = levels.level(n)
        assert sum(len(room.workers) for room in b.rooms) == len(b.budget.people)


# --- the deal ----------------------------------------------------------------

def test_nine_rooms_and_seven_people_leave_two_dead_ends_empty():
    """The acceptance criterion, over 256 seeds: **exactly two empty rooms and
    both are dead ends.** Seven people and six rooms that are not dead ends, so
    six are spoken for before a single spur is filled.

    One test looping the seeds rather than 256 parametrised cases: the claim is
    "on every seed", and 256 rows in the suite's count would say the project has
    grown 256 tests when it has grown one.
    """
    text = comb()
    for seed in MANY:
        dealt = hands(text, seed)
        empty = [i for i, clocks in enumerate(dealt) if not clocks]
        assert len(empty) == 2, (seed, dealt)
        assert all(i in LEAVES for i in empty), (seed, empty)
        assert sum(len(c) for c in dealt) == 7, (seed, dealt)


def test_which_dead_end_is_empty_rolls_with_the_seed():
    """Asserted rather than assumed. All three of the comb's spurs go empty
    across the seeds, and no arrangement takes more than half of them."""
    seen: dict = {}
    for seed in MANY:
        empty = tuple(i for i, clocks in enumerate(hands(comb(), seed))
                      if not clocks)
        seen[empty] = seen.get(empty, 0) + 1
    assert len(seen) == 3, seen           # three ways to leave one spur filled
    assert set().union(*map(set, seen)) == set(LEAVES)
    assert max(seen.values()) <= len(MANY) // 2, seen


@pytest.mark.parametrize("seed", (0xBEEF, 1, 2, 3))
def test_no_room_is_empty_when_there_are_people_enough(seed):
    """A building with no more rooms than people has no empty room, on any
    seed -- and the extra two of eleven land somewhere, not nowhere."""
    for roster, total in (("64 " * 9, 9), ("64 " * 11, 11)):
        dealt = hands(comb(people=roster.strip()), seed)
        assert all(dealt), dealt
        assert sum(len(c) for c in dealt) == total


@pytest.mark.parametrize("seed", (0xBEEF, 1, 2, 3, 4, 5, 6, 7))
def test_clocks_never_shorten_with_depth(seed):
    """Shortest-nearest-the-exit: nobody is asked to cross a building on the
    shortest fuse in it. Stated over the whole comb, whose spurs are four
    doorways deep, with a roster of nine different clocks."""
    roster = "22 30 40 50 60 70 80 90 99"
    dealt = hands(comb(people=roster), seed)
    depth = {0: 0}
    for _ in range(len(PLAN)):
        for a, b in EDGES:
            if a in depth and b not in depth:
                depth[b] = depth[a] + 1
            if b in depth and a not in depth:
                depth[a] = depth[b] + 1
    for i, clocks in enumerate(dealt):
        for j, theirs in enumerate(dealt):
            if depth[i] < depth[j] and clocks and theirs:
                assert max(clocks) <= min(theirs), (i, j, dealt)


def test_more_rooms_on_a_path_than_people_is_refused():
    """Six of the comb's nine rooms are on a path between two others, so five
    people cannot fill it -- and the refusal says why rather than quietly
    stranding a listener in a silent room."""
    with pytest.raises(ValueError, match="cannot fill 6 rooms"):
        hands(comb(people="64 64 64 64 64"), 0xBEEF)


# --- the floor ----------------------------------------------------------------

def test_the_floor_scales_with_the_building():
    """44 seconds at three rooms and 128 at nine, at two seconds a blood point.

    The issue that asked for this glossed nine rooms as 86 seconds. 86 is the
    **six**-room figure; the formula and its 44-second anchor agree, and the
    gloss was the slip. Pinned here so the arithmetic is on the record.
    """
    from spikes.rescue import BLEED_EVERY
    seconds = BLEED_EVERY // 50
    assert levels.clock_floor(3) * seconds == 44
    assert levels.clock_floor(6) * seconds == 86
    assert levels.clock_floor(9) * seconds == 128
    # Smaller than three rooms does not lower it: three is the anchor.
    assert levels.clock_floor(1) == levels.clock_floor(3) == levels.CLOCK_FLOOR
    assert levels.clock_floor(9) == NINE_FLOOR


def test_no_worker_starts_below_the_floor():
    """A roster authored under the floor is raised to it, room by room."""
    dealt = hands(comb(people="10 10 10 10 10 10 10"), 0xBEEF)
    assert [c for room in dealt for c in room] == [NINE_FLOOR] * 7


def test_the_levels_past_the_last_file_tighten_to_the_buildings_floor():
    """`_beyond` cuts every clock three blood a level and stops at the floor
    of the building it is cutting -- not at the bare constant."""
    floor = levels.clock_floor(len(levels.level(3).rooms))
    deep = levels.level(60)
    assert min(deep.budget.people) == floor
    assert min(w[2] for room in deep.rooms for w in room.workers) == floor


# --- the gate -----------------------------------------------------------------

@pytest.mark.parametrize("seed", (0xBEEF, 0xBEF0, 0xBEF1, 0xBEF2))
def test_the_oracle_gets_everybody_out_of_nine_rooms_at_the_floor(seed):
    """The number `CLOCK_PER_ROOM` exists to satisfy: **perfect play clears
    the largest building with every clock on the floor.** Four seeds.

    It clears with room to spare -- 55 to 63 seconds against 128 of clock -- so
    seven blood a room is generous rather than tight, and whether it should be
    is the round's last slice (#147) with the whole ramp in front of it.
    """
    building = build(comb(), seed)
    assert min(w[2] for room in building.rooms for w in room.workers) == NINE_FLOOR
    run = sess.Session(seed=seed, sound=False, building=building, start_room=0)
    player = bots.make("oracle", seed=seed)
    while run.over is None and run.frame < 300 * 50:
        run.step(player.intent(run))
    assert run.over == sess.ALL_OUT, f"{run.over} with {run.rescued}/{run.total}"


def test_nine_rooms_fit_the_frame_and_the_entity_ceiling():
    """A building this big is only authorable because `worst_case()` prices one
    hop rather than the whole building (issue #142)."""
    building = build(comb(), 0xBEEF)
    from spikes.building import ENTITY_CEILING
    assert building.worst_case() <= ENTITY_CEILING
