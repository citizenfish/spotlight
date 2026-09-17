"""Level 2, Infested: three rooms, seven people, six Clegs (issue #111, The
rooms AO). The maps are the vault's; the numbers are the ones the note
holds, measured again here."""

import pytest

from levelplay import SEEDS, play
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
    assert spray.workers == ((176, 128, 90), (216, 24, 80))
    assert beam.workers == ((64, 24, 70), (136, 128, 40), (224, 16, 80))
    assert wide.workers == ((224, 24, 60), (224, 136, 70))
    assert spray.clegs == ((20, 3), (26, 12))
    assert beam.clegs == ((26, 8), (12, 19))
    assert wide.clegs == ((16, 3), (16, 19))
    assert spray.spotlights == ((3, 16, 150),)
    assert beam.spotlights == ()
    assert wide.spotlights == ((29, 11, 1500),)
    assert spray.lights == ((14, 9, 3, 3),)
    assert beam.lights == () and wide.lights == ()
    assert spray.searchlight is None and wide.searchlight is None
    assert beam.searchlight.radius == 3 and not beam.searchlight.vary
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
def test_the_oracle_gets_everyone_out_inside_forty_five_seconds(seed):
    run = play(LEVEL, "oracle", seed)
    assert run.over == S.ALL_OUT and run.rescued == 7
    assert run.seconds <= 45


@pytest.mark.parametrize("seed", SEEDS)
def test_the_listener_gets_at_least_six_out_and_never_times_out(seed):
    run = play(LEVEL, "listener", seed)
    assert run.over != S.FRAME_LIMIT
    assert run.rescued >= 6


@pytest.mark.parametrize("seed", SEEDS)
def test_a_statue_at_the_start_is_never_bitten(seed):
    run = play(LEVEL, "statue", seed)
    assert run.over == S.FRAME_LIMIT
    assert run.tally.attachments == 0


@pytest.mark.parametrize("seed", SEEDS)
def test_a_statue_in_the_beam_room_loses_its_last_life_in_a_minute_or_two(seed):
    """From the beam room's own start (`--room 1`): the searchlight finds it
    and the magnet brings the building. The note measured 73-100 s; Level
    3's main room gives 89 s for the same statue."""
    run = play(LEVEL, "statue", seed, room=1)
    assert run.over == S.NO_LIVES
    assert 60 <= run.seconds <= 110
