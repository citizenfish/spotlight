"""Level 2, Infested: three rooms, seven people, six Clegs (issue #111, The
rooms AO). The maps are the vault's; the numbers are the ones the note
holds, measured again here."""

import statistics

import pytest

from levelplay import SEEDS, play, lives_lost, MOVING
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
    assert tuple(w[2] for w in spray.workers) == (90, 80)
    assert tuple(w[2] for w in beam.workers) == (70, 40, 80)
    assert tuple(w[2] for w in wide.workers) == (60, 70)
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
def test_the_listener_gets_six_of_seven_out_on_the_mean_and_never_times_out():
    """6.4 of 7 over eight seeds, 0.6 lives (the light round baseline,
    issue #124); on the four here 6.0 and 0.5. Asserted on the mean: a
    rolled room and a beam the listener cannot see make any one seed a
    coin."""
    runs = [play(LEVEL, "listener", seed) for seed in SEEDS]
    assert all(r.over != S.FRAME_LIMIT for r in runs)
    assert statistics.mean(r.rescued for r in runs) >= 6
    assert statistics.mean(lives_lost(r) for r in runs) <= 1.5


@pytest.mark.parametrize("seed", SEEDS)
@MOVING
def test_a_statue_at_the_start_is_found_and_dies_in_about_two_minutes(seed):
    """Six flies, a beam in every room and an eight-second magnet: a statue
    is found inside forty seconds and dead between a hundred and a hundred
    and fifty (104-141 on these seeds), which is T8 and the design working.
    Before the light round it was never bitten at all."""
    run = play(LEVEL, "statue", seed)
    assert run.over == S.NO_LIVES
    assert 100 <= run.seconds <= 150
    first = next(e.frame for e in run.log if e.kind == S.BITTEN)
    assert 500 <= first <= 40 * 50


@pytest.mark.parametrize("seed", SEEDS)
@MOVING
def test_a_statue_in_the_beam_room_loses_its_last_life_in_a_minute_or_two(seed):
    """From the beam room's own start (`--room 1`): the searchlight finds it
    and the magnet brings the building. 83-115 s on these seeds."""
    run = play(LEVEL, "statue", seed, room=1)
    assert run.over == S.NO_LIVES
    assert 60 <= run.seconds <= 120
