"""Level 2, Infested: three rooms, seven people, six Clegs (issue #111, The
rooms AO). The maps are the vault's; the numbers are the ones the note
holds, measured again here."""

import statistics

import pytest

from levelplay import SEEDS, WIDE_SEEDS, play, lives_lost, MOVING
from spikes import building as B, levels, session as S
from spotlight.core.constants import CYAN, YELLOW

LEVEL = 2


@pytest.fixture(scope="module")
def infested():
    return levels.level(LEVEL)


def test_the_level_is_as_the_note_draws_it(infested):
    assert infested.level == 2 and infested.title == "Infested"
    assert [r.name for r in infested.rooms] == [
        "the spray", "the beam", "the wide dark"]
    assert [r.ink[B.FLOOR] for r in infested.rooms] == [
        B.palette(YELLOW)[B.FLOOR], B.palette(CYAN)[B.FLOOR],
        B.palette(YELLOW)[B.FLOOR]]
    spray, beam, wide = infested.rooms
    # The shell (issue #121): the clocks and the counts; the cells are the
    # seed's.
    #
    # **Dealt from the building's roster since issue #143** (`people: 90 80 80
    # 70 70 60 40`), shortest nearest the way out: the spray room is at the
    # door and holds the two shortest clocks, the wide dark is two doorways in
    # and holds the two longest.
    assert tuple(w[2] for w in spray.workers) == (40, 60)
    assert tuple(w[2] for w in beam.workers) == (70, 70, 80)
    assert tuple(w[2] for w in wide.workers) == (80, 90)
    assert [len(r.clegs) for r in infested.rooms] == [2, 2, 2]
    # The floor lamps (150 by the exit, 1500 on the wide dark's far wall)
    # went with the torch (issue #119).
    assert spray.lights == ((14, 9, 3, 3),)
    assert beam.lights == () and wide.lights == ()
    # A beam in every room (issue #118), at the beam's own pace.
    assert all(r.searchlight.radius == 3 and not r.searchlight.vary
               and r.searchlight.pace == 6 for r in infested.rooms)
    assert infested.budget.magnet == 8 and infested.budget.wake is False
    assert infested.start == (0, (24, 96))
    assert beam.player_start == (16, 80) and wide.player_start == (16, 80)
    assert [d.to for d in spray.doorways] == [1]
    assert sorted(d.to for d in beam.doorways) == [0, 2]
    assert [d.to for d in wide.doorways] == [1]
    # **A corner since issue #146**: east, then south. `the beam` is the first
    # room in the game whose two doorways are at right angles rather than
    # opposite, which is the whole lesson of the level -- until now "the way out"
    # and "the way back" were the two ends of the same wall.
    assert [r.at for r in infested.rooms] == [(0, 0), (1, 0), (1, 1)]
    assert [d.side for d in spray.doorways] == [B.EAST]
    assert sorted(d.side for d in beam.doorways) == sorted((B.WEST, B.SOUTH))
    assert [d.side for d in wide.doorways] == [B.NORTH]


def test_the_level_validates_and_is_priced_as_the_note_says(infested):
    infested.validate()
    assert infested.worst_case() == 30274
    assert infested.roster == 7 and infested.population == 6


def test_every_room_can_be_played_on_its_own(infested):
    for i in range(len(infested)):
        alone = infested.solo(i)
        alone.validate()
        assert S.Session(seed=1, building=alone).here == 0


@pytest.mark.parametrize("seed", SEEDS)
@MOVING
def test_the_oracle_gets_everyone_out_inside_forty_five_seconds(seed):
    run = play(LEVEL, "oracle", seed)
    assert run.over == S.ALL_OUT and run.rescued == 7
    assert run.seconds <= 45


@MOVING
def test_the_dark_listener_gets_most_of_them_out_and_never_times_out():
    """5.9 of 7 over eight seeds and 5.88 over sixteen, 1.2 lives (the
    searchlight baseline, issue #130); it was 6.4 and 0.6 on the 29-cell
    disc. The round disc catches more, which is what it is for. **The
    human proxy is the spraying listener** and it is unmoved: 6.5 of 7
    with a quarter of a life -- the test below. Asserted on the mean: a
    rolled room and a beam the listener cannot see make any one seed a
    coin.

    **Taken over eight seeds since issue #135**, and it is the sharpest
    example of #130 yet: the same gate reads **4.5 on four seeds and 5.5 on
    eight** ([6, 4, 6, 2] against [6, 4, 6, 2, 6, 6, 7, 7]). The first four
    happen to include the two worst rolls in the set. Four was never enough
    for a mean and this is the run that proves it.

    **And 3.88 of 7 since issue #143**, from 6.25, with lives lost going 1.38
    to 2.75 -- the largest single drop any gate in this suite has taken. The
    roster is the building's now: which room holds how many people rolls (the
    wide dark holds three instead of two on four seeds of eight) and the two
    shortest clocks land together in the room you start in.

    **Level 2 and Level 3 now read the same for this bot** -- 3.88 and 3.88 --
    which is the plateau the last round removed, back in two rungs. It is
    recorded rather than tuned, in *2026-09-29 The roster deal*, and #147 is
    the slice that re-takes the ramp with all of it in view. The human proxy,
    the spraying listener below, took a fifth of that: 5.88 to 5.38.
    """
    runs = [play(LEVEL, "listener", seed) for seed in WIDE_SEEDS]
    assert statistics.mean(r.rescued for r in runs) >= 3.5
    assert statistics.mean(lives_lost(r) for r in runs) <= 3


@MOVING
def test_the_spraying_listener_still_gets_six_of_seven_out():
    """The bot nearest a person: one button, pressed at a fly two cells ahead.

    6.5 of 7 over eight seeds with a quarter of a life and **no death** until
    issue #131. A fly that follows a wall to its end reaches people it used to
    mill about beside, and the human proxy now reads **6.4 of 7 over eight
    seeds with half a life, and dies on one seed in eight** -- the rescues are
    inside the noise and the death is new.

    That is recorded rather than tuned, and it is the first thing in five
    levels to make Level 2 harder for the proxy: the plateau this round exists
    to fix runs from Level 2 to Level 6. Whether one death in eight is the
    right amount for a teaching level is BN's question, with the whole ramp in
    front of it, and not a dial to reach for here.

    Taken over eight seeds and not four (issue #130): on four it reads 6.0 and
    0.75 of a life, which is the coin that ruling flagged.

    **And 5.9 of 7 with the authored walls** (issue #137): 6, 6, 6, 7, 4, 6, 7,
    5 with 0.9 of a life and **no death** -- the death that #131 introduced went
    away again when the rooms changed shape, which is a fair warning about how
    much any one of these figures is worth. The proxy is doing slightly worse
    and dying less. Whether a teaching level should ask this much is BN's
    question, with the whole ramp in front of it.

    **5.38 of 7 since issue #143**, from 5.88, with 1.12 of a life: 4, 5, 7, 5,
    7, 5, 4, 6, and it dies on one seed in eight again. **A fifth of what the
    dark listener lost** to the same change, which is the useful half of this
    pair -- the bot with a button in its hand absorbs a deal it cannot hear
    coming, and the bot navigating purely by ear does not. See
    *2026-09-29 The roster deal*.

    **And 4.75 of 7 since issue #146**, with 1.62 of a life and a death on three
    seeds in eight: 4, 4, 7, 4, 4, 7, 4, 4. Two things in that slice moved it and
    both were meant to. Level 2 is a **corner** now, so the room in the middle has
    its two doorways at right angles and a fly arriving from either side comes from
    a direction the other does not. And the magnet was **broken** in any room
    reached north or south -- `Session._magnet_cell` handed a fly the transposed
    cell, so it walked at the wrong wall and never crossed -- which means every
    figure for a horizontal doorway before this slice was measured with the magnet
    switched off. It is on now, and the proxy feels it.

    Three deaths in eight on a teaching level is a lot, and it is **recorded rather
    than tuned**: the pattern 4, 4, 7, 4, 4, 7, 4, 4 says the level is either
    cleanly won or stuck at four, which is a shape worth a look. #147 owns it.
    """
    runs = [play(LEVEL, "listener", seed, spray=True) for seed in WIDE_SEEDS]
    assert statistics.mean(r.rescued for r in runs) >= 4.5
    assert statistics.mean(lives_lost(r) for r in runs) <= 2
    assert sum(1 for r in runs if r.over == S.NO_LIVES) <= 3, \
        "the proxy died on more than three seeds in eight"


@pytest.mark.parametrize("seed", SEEDS)
@MOVING
def test_a_statue_at_the_start_is_found_and_dies_in_about_two_minutes(seed):
    """Six flies, a beam in every room and an eight-second magnet: a statue
    is found inside forty seconds and dead between a hundred and a hundred
    and fifty (104-141 on these seeds), which is T8 and the design working.
    Before the light round it was never bitten at all."""
    run = play(LEVEL, "statue", seed)
    assert run.over == S.NO_LIVES
    # 106-155 s over eight seeds on the round disc (issue #130).
    assert 100 <= run.seconds <= 160
    first = next(e.frame for e in run.log if e.kind == S.BITTEN)
    assert 500 <= first <= 40 * 50


@pytest.mark.parametrize("seed", SEEDS)
@MOVING
def test_a_statue_in_the_beam_room_loses_its_last_life_in_a_minute_or_two(seed):
    """From the beam room's own start (`--room 1`): the searchlight finds it
    and the magnet brings the building.

    **98-115 s since issue #146**, from 83-115. Level 2 is a corner now and the
    beam room is its middle: its two doorways are at right angles instead of
    opposite, so a fly crossing from the spray room arrives through the west wall
    and one from the wide dark through the south, and neither lines up with the
    other.

    The band barely moved in the end, and that is the magnet: with the transposed
    goal cell fixed, a fly in the room *below* is handed the south threshold and
    actually comes through it, where before it walked at the west wall and stayed
    put. A corner reached from two directions is slower to converge on a statue;
    a magnet that works in both of them is faster. The two nearly cancel.

    The first bite still lands in 5 to 18 seconds -- the beam finds it as fast as
    it ever did -- and it still loses every life, which is what the test is for.
    """
    run = play(LEVEL, "statue", seed, room=1)
    assert run.over == S.NO_LIVES
    assert 90 <= run.seconds <= 130
    first = next((e.frame for e in run.log if e.kind == S.BITTEN), None)
    assert first is not None and first <= 30 * 50, \
        "the beam no longer finds a statue quickly"
