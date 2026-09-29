"""The constants issue #23 deliberately did **not** move, and their reasons.

Holding a number is a decision and it gets a test, because the tempting mistake
is to move the one that was blamed loudest. Every assertion here is paired with
why the value stayed, so that a future reader can judge whether the reason still
holds rather than only that somebody once wrote the number down.

This file is not a list of things that may never change. It is a list of things
that must not change *by accident*, or as a side effect of tuning something
else. If one of these should move, the way to move it is to argue it in the
vault, raise an issue, and edit this file in the same commit as the constant.
"""

from spikes import building, clegs, rescue, scene, session, sources, spray
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import COLS


def test_cleg_hunger_was_cut_in_half_and_it_bought_nothing():
    """`KEEN_MAX` is the one constant this file has released. Issue #25 cut it
    from twelve to six, **the prediction it was cut on was falsified, and the
    cut was reverted.**

    It was held here once, because it had been named as *the* tuning dial on
    the strength of a measured 1.0x that turned out to be a window artefact.
    Issue #25 was a different diagnosis -- an absolute baseline rather than a
    ratio -- and it predicted that halving the cap would take the dark
    thirty-second cost from 33.2 to 18-20, leave the lit cost near 49.6, and
    push a dark first bite past twenty seconds.

    Measured on five seeds with the driver: **33.2, 49.6 and 13.6 seconds.
    Every one of them to the digit, unchanged.** See the test below for the
    arithmetic that made the first two impossible, and `test_spike_clegs.py`
    for the run that pins it.

    **The value goes back to twelve**, because a change is a claim and a
    falsified claim does not get to leave its change behind. Six was defensible
    as a reach and indefensible as a difficulty decision, and a later reader
    finding a six would reasonably assume somebody had tuned it. Twelve is
    where the person who built and judged hunger put it, with their reason
    beside it.

    **Hunger is not the dial**, and the reason is in the attribution hook from
    #22: a dark, motionless player's blood is billed almost entirely to the
    searchlight, which is lit, mobile and noticeable from anywhere, and
    therefore wins the nearest-lure comparison long before the glow's extra
    cells matter.
    """
    assert clegs.KEEN_MAX == 12


def test_the_cap_cannot_move_a_thirty_second_number_at_all():
    """Why the cut measured as an exact no-op, in one line of arithmetic.

    Keenness is `hunger // HUNGER_STEP`, so a fly needs
    `KEEN_MAX * HUNGER_STEP` frames of not feeding to reach the cap -- and at
    six cells that is 1500 frames, which is the entire thirty-second window the
    prediction was stated over. **Inside that window a cap of six and a cap of
    twelve are the same number**, because neither is ever reached. The two
    predicted figures could not have moved whatever the swarm did.

    The assertion is written against six rather than the current twelve on
    purpose: it is the *cut* that had to clear this bar, and it did not.

    This is the check that was not done before the constant was proposed, and
    it costs nothing to keep. If the cap is ever cut again to move a
    thirty-second baseline, this fails and says why.
    """
    window = 30 * 50
    assert 6 * clegs.HUNGER_STEP >= window
    assert clegs.KEEN_MAX * clegs.HUNGER_STEP >= window


def test_the_beam_keeps_its_speed_and_its_size():
    """Both settled by a person at a keyboard -- *"at twice that it was over you
    before you could do anything about it"* -- and nothing measured implicates
    either. A bot's number does not outrank a play report.

    Six frames a cell is about eight cells a second: slow enough to watch, time
    and cross behind. Three was tried and played too fast to do anything about.
    """
    assert sources.Roaming(0, 0).step_every == 6
    assert scene.SEARCHLIGHT_RADIUS == 3


def test_blood_stays_at_sixty_four_in_eight_pips():
    """One bite is one pip, so a player can count what a swarm cost them.

    Note that it *saturates* against three lives over a long stationary run,
    which is why blood totals over long windows are a bad measure. That is a
    problem with the target, not with the number.
    """
    assert session.BLOOD_FULL == 64
    assert session.BLOOD_FULL // clegs.DRAIN_TOTAL == 8


def test_lives_stay_at_three():
    assert session.LIVES == 3


def test_the_spray_keeps_five_charges_and_a_five_second_patch():
    """The nest arithmetic in the vault depends on both, and it already says
    the right thing: five charges against a twenty-second body window."""
    assert spray.Spray().charges == 5
    assert spray.PATCH_FRAMES == 5 * 50


def test_the_body_window_moved_to_the_number_the_vault_agreed():
    """**The discrepancy this file was keeping, collected.**

    `BODY_FRAMES` was 500 -- ten seconds -- against a vault that had agreed
    twenty. It was the spike's leftover and nothing read it, so it was pinned
    here rather than quietly corrected, on the rule that a number should be
    found on purpose rather than by surprise. Issue #33 is the work that reads
    it, so this is where it moves.

    The nest constants beside it are new and are not held: they are derived
    from the spray, not chosen against it. See `rescue.NEST_SPAWN_EVERY`.
    """
    assert rescue.BODY_FRAMES == 20 * 50
    assert rescue.NEST_FRAMES == 30 * 50
    assert rescue.GONE_FRAMES == 50 * 50


def test_the_playtest_building_is_inside_the_entity_ceiling():
    """**The number, and the two ways it has been got wrong.**

    Issue #33 asked that level validation be sized for a level's **worst
    plausible failure** rather than its opening state, because a nest is the
    first thing in the game that manufactures entities. It counted that way and
    reported the playtest building as 25.25 Cleg-equivalents against a ceiling
    of eighteen -- over by 40%, and over by 18.25 to 18 before a nest even
    turned.

    **Both figures were in the wrong unit** (issue #34). Eighteen
    Cleg-equivalents is what *The 48K cycle budget* arrived at with
    **pixel-positioned** flies, and cell-aligned Clegs were taken as a decision
    on 2026-09-07 precisely because nests do not fit under it. Counted in
    T-states, which is the currency *Nests* says to use and then did not::

        6 authored + 6 brood = 12 Clegs    9,960
        the player and a tail of six      20,314
        the nest itself                        0   a fixture; it does not move
                                          ------
                                          30,274  against 32,832 -- 92%

    So the building fits, with eight per cent spare, and the tension #33
    reported was an artefact of a retired unit rather than a fact about the
    level.

    **Held here because a ceiling denominated in one entity's cost moves
    whenever that entity's sprite format moves, and it has now done so once.**
    If a format changes again this fails, which is the point. The figures live
    in `building.py` and are quoted from the vault rather than re-derived.
    """
    b = scene.BUILDING
    assert b.worst_case() == 30274, "the worst plausible failure moved"
    assert b.over_budget == 0, "the playtest building no longer fits"
    assert b.worst_case() * 100 // building.ENTITY_CEILING == 92

    # And the part that is not about nests: the tail is the expensive thing in
    # this building, which is *The 48K cycle budget*'s own warning arriving from
    # the other direction. A tail of six costs more than twice the whole swarm,
    # brood included.
    assert building.cost(people=1 + b.largest_tail) \
        > 2 * building.cost(clegs=b.population + rescue.NEST_BROOD)


def test_a_fixture_costs_nothing_and_the_sum_notices_if_that_changes():
    """**The zero, and the thing that was wrong with the way it was justified.**

    A body and a nest do not move, so on the port they belong to the dirty-cell
    accounting rather than to the per-frame entity bill. That reasoning is
    unchanged and is not what issue #36 was about.

    What was wrong was the justification: the constant carried a *receipt* --
    "measured over twenty runs, four bots and five seeds: never more than two"
    -- and a wider sweep found four in one room. **Twenty runs was not too few.
    Any number of runs would have been too few**, because a sample cannot bound
    a worst case, and the lifecycle gave the bound for nothing.

    The guard the issue asks for is here, and it is a sensitivity rather than an
    assertion about the number: **if a fixture ever costs what a person costs,
    the playtest building goes over the ceiling.** So the zero cannot quietly
    become something else -- `worst_case` reads it, maximises over how many of
    the roster are dead, and this fails.
    """
    b = scene.BUILDING
    assert building.FIXTURE_COST == 0
    assert b.worst_case() <= building.ENTITY_CEILING

    was = building.FIXTURE_COST
    try:
        building.FIXTURE_COST = building.PERSON_COST
        assert b.worst_case() > building.ENTITY_CEILING, \
            "a fixture priced as a person would fit, so this guard is asleep"
    finally:
        building.FIXTURE_COST = was
    assert b.worst_case() == 30274, "restoring the constant did not restore it"


def test_the_fixture_bound_comes_from_the_lifecycle_and_not_from_a_sweep():
    """A body is gone fifty seconds after the death that made it, and a
    follower dies where they fall -- so any worker in the building can die in
    any room, and the most fixtures a room can hold is the roster.

    **No measurement is needed and none would help.** The prototype's measured
    peak is four in one room over 105 runs; the bound is seven. That gap is
    what a bound is for.
    """
    b = scene.BUILDING
    assert b.most_fixtures == b.roster == 7
    assert rescue.GONE_FRAMES == rescue.BODY_FRAMES + rescue.NEST_FRAMES


# --- the bound reads a room's neighbours (issue #142) ------------------------

def _grid(coords, flies_each, roster):
    """A building on the plan's grid: `coords` as (col, row), joined wherever
    two rooms are a doorway apart, with `flies_each` flies in every room and
    `roster` people dealt round the rooms, so the roster is the roster whatever
    the shape -- seven people over three rooms is three, two and two.

    Built from `Room` directly rather than through a level file, because what is
    being pinned is arithmetic over a topology and the level file's own rules --
    two hues, a worker in every room a shout crosses -- would decide the shapes
    instead.
    """
    rows = ["#" * COLS]
    rows += ["#" + "." * (COLS - 2) + "#" for _ in range(PLAY_ROWS - 2)]
    rows.append("#" * COLS)
    n = len(coords)
    share = [roster // n + (1 if i < roster % n else 0) for i in range(n)]
    rooms = []
    for i, (col, row) in enumerate(coords):
        doorways = []
        for j, (c2, r2) in enumerate(coords):
            if i == j:
                continue
            for side, at in ((building.EAST, (col + 1, row)),
                             (building.WEST, (col - 1, row)),
                             (building.SOUTH, (col, row + 1)),
                             (building.NORTH, (col, row - 1))):
                if (c2, r2) == at:
                    span = (10, 11, 12) if side in building.VERTICAL_SIDES \
                        else (14, 15, 16)
                    doorways.append(building.Doorway(side, span, j))
        rooms.append(building.Room(
            f"r{i}", rows, clegs=tuple((5, 5) for _ in range(flies_each)),
            workers=tuple((40, 40, 60) for _ in range(share[i])),
            player_start=(24, 96), doorways=tuple(doorways), at=(col, row)))
    return building.Building(rooms)


STRIP3 = [(0, 0), (1, 0), (2, 0)]
BLOCK9 = [(c, r) for r in range(3) for c in range(3)]


def test_a_strip_of_three_at_nine_flies_is_the_worst_case_it_always_was():
    """The bound used to crowd the **whole building** into one room, which was
    close to true on a row of three: the room next door empties into a lit one
    in about ten seconds. So the strip's figure must not move, and it does not --
    three flies a room, both neighbours, a brood of six and the tail.

    3 + 3 + 3 = 9 near flies, + 6 brood = 15, and seven people behind you.
    """
    b = _grid(STRIP3, flies_each=3, roster=7)
    assert b.population == 9 and b.roster == 7
    near = 3 + 3 + 3 + rescue.NEST_BROOD
    assert near == 15
    assert b.worst_case() == near * building.CLEG_COST + 7 * building.PERSON_COST
    assert b.worst_case() == 32764, "the strip's worst case moved"
    assert b.over_budget == 0


def test_a_three_by_three_at_nine_flies_is_cheaper_than_the_strip():
    """The point of the change. A fly four doorways away cannot arrive inside
    the life of a nest, and the old bound said it could -- which priced a
    four-room building 241 T-states over the ceiling and a nine-room one at
    124%, none of it from anything the game does.

    One fly a room, the centre room's four neighbours, a brood of six: 11 flies
    and the tail. The centre room is the dearest, which is what the maximum over
    the rooms is for.
    """
    b = _grid(BLOCK9, flies_each=1, roster=7)
    assert b.population == 9 and b.roster == 7
    near = 1 + 4 + rescue.NEST_BROOD
    assert near == 11
    assert b.worst_case() == near * building.CLEG_COST + 7 * building.PERSON_COST
    assert b.worst_case() == 29444
    assert b.over_budget == 0
    strip = _grid(STRIP3, flies_each=3, roster=7)
    assert b.worst_case() < strip.worst_case(), \
        "a grid should be cheaper than a strip at the same fly count"


def test_the_dearest_room_is_the_one_with_the_most_doorways():
    """A centre room with four doorways and a leaf with one, in the same
    building: the bound is the maximum over the rooms, so the centre decides
    it."""
    b = _grid(BLOCK9, flies_each=1, roster=7)
    doors = [len(room.doorways) for room in b.rooms]
    assert doors == [2, 3, 2, 3, 4, 3, 2, 3, 2], doors
    centre = b.rooms[4]
    assert len(centre.doorways) == 4
    # A leaf on its own prices lower, which is why the maximum is taken.
    leaf = _grid([(0, 0), (1, 0)], flies_each=1, roster=7)
    assert leaf.worst_case() < b.worst_case()


def test_the_bound_is_never_less_than_a_room_and_a_brood_and_the_tail():
    """The floor, whatever the topology: a room's own flies cannot be reduced by
    its being far from anything. A building of rooms with no doorways at all is
    the degenerate case and still prices its own flies."""
    for coords in ([(0, 0)], STRIP3, BLOCK9):
        for flies in (1, 3):
            b = _grid(coords, flies_each=flies, roster=7)
            least = ((flies + rescue.NEST_BROOD) * building.CLEG_COST
                     + 7 * building.PERSON_COST)
            assert b.worst_case() >= least, (coords, flies)


def test_it_is_one_hop_and_not_a_transitive_closure():
    """Two hops is the whole building again on any shape the plan holds, and a
    bound that cannot tell a strip from a grid is the one this replaced. A row
    of three is the case where one hop **is** the whole building, and a row of
    four is the case where it is not."""
    four = _grid([(0, 0), (1, 0), (2, 0), (0, 1)], flies_each=1, roster=7)
    # No room in that shape touches all four, so the bound is below the whole
    # building's four flies plus a brood.
    whole = (4 + rescue.NEST_BROOD) * building.CLEG_COST \
        + 7 * building.PERSON_COST
    assert four.worst_case() < whole
