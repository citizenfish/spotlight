"""Level 1, Dark: three rooms, four people, one Cleg (issue #110, The rooms
AN). The maps are the vault's; the numbers are the ones the note holds,
measured again here."""

import statistics

import pytest

from levelplay import SEEDS, play, lives_lost, MOVING
from spikes import building as B, levels, session as S
from spotlight.core.constants import CYAN, YELLOW
from spotlight.core.screen import Screen

LEVEL = 1


@pytest.fixture(scope="module")
def dark():
    return levels.level(LEVEL)


def test_the_level_is_as_the_note_draws_it(dark):
    assert dark.level == 1 and dark.title == "Dark"
    assert [r.name for r in dark.rooms] == ["the glow", "the buzz", "the lamp"]
    assert [r.ink[B.FLOOR] for r in dark.rooms] == [
        B.palette(YELLOW)[B.FLOOR], B.palette(CYAN)[B.FLOOR],
        B.palette(YELLOW)[B.FLOOR]]
    glow, buzz, lamp = dark.rooms
    # The shell (issue #121): the clocks and the counts; where each person
    # stands and where the fly begins are the seed's.
    assert tuple(w[2] for w in glow.workers) == (90,)
    assert tuple(w[2] for w in buzz.workers) == (90, 80)
    assert tuple(w[2] for w in lamp.workers) == (70,)
    assert [len(r.clegs) for r in dark.rooms] == [0, 1, 0]
    # A beam in every room at walking pace (issue #118).
    assert all(r.searchlight.radius == 3 and not r.searchlight.vary
               and r.searchlight.pace == 8 for r in dark.rooms)
    assert dark.budget.magnet == 5 and dark.budget.wake is False
    assert [r.lights for r in dark.rooms] == [
        ((1, 9, 3, 4),), ((0, 10, 3, 3),), ((26, 17, 3, 3),)]
    assert dark.start == (0, (24, 96))
    assert buzz.player_start == (16, 80) and lamp.player_start == (16, 80)
    assert [d.to for d in glow.doorways] == [1]
    assert sorted(d.to for d in buzz.doorways) == [0, 2]
    assert [d.to for d in lamp.doorways] == [1]
    assert dark.exit == (0, (0, 10))


def test_the_level_validates_and_is_priced_as_the_note_says(dark):
    dark.validate()
    assert dark.worst_case() == 17418
    assert dark.roster == 4 and dark.population == 1


def test_every_room_can_be_played_on_its_own(dark):
    for i in range(len(dark)):
        alone = dark.solo(i)
        alone.validate()
        run = S.Session(seed=1, building=alone)
        assert run.here == 0


def test_a_room_with_no_cleg_steps_draws_and_sounds():
    """The start room authors no fly, and nothing in the session or the
    sonar had run with an empty swarm before this level."""
    run = S.Session(seed=SEEDS[0], building=levels.level(LEVEL), sound=True)
    assert not run.places[0].swarm.clegs
    screen = Screen()
    voice = run.voice
    assert voice is not None
    for _ in range(500):
        run.step()
        run.draw(screen)
        voice.audio_frame()
        assert run.here == 0
    assert run.over is None
    assert run.tally.attachments == 0


@pytest.mark.parametrize("seed", SEEDS)
@MOVING
def test_the_oracle_gets_everyone_out(seed):
    run = play(LEVEL, "oracle", seed)
    assert run.over == S.ALL_OUT and run.rescued == 4
    # The note measured 36 s; a minute is the loosest this should ever be.
    assert run.seconds <= 60


@pytest.mark.parametrize("seed", SEEDS)
@MOVING
def test_the_listener_loses_no_life(seed):
    run = play(LEVEL, "listener", seed)
    assert run.over != S.FRAME_LIMIT
    assert lives_lost(run) == 0


@MOVING
def test_the_listener_gets_nearly_everyone_out():
    """3.8 of 4 over the seeds (the light round baseline, issue #124). The
    one it loses is the far room's, to the clock: the listener never leaves
    a room that has gone silent, and once the middle room's people are
    delivered nothing calls it on. A bot's limit, not the level's -- the
    scout, which explores, gets all four out on most seeds."""
    runs = [play(LEVEL, "listener", seed) for seed in SEEDS]
    assert statistics.mean(r.rescued for r in runs) >= 3.5
    assert sum(r.over == S.ALL_OUT for r in runs) >= 2


@pytest.mark.parametrize("seed", SEEDS)
@MOVING
def test_a_statue_at_the_start_lives_three_minutes_and_is_not_bitten_early(seed):
    """With a beam in every room (issue #118) a statue is found -- that is
    T8 -- but Level 1's one fly and five-second magnet never kill it, and
    the beam never opens on the start (issue #116)."""
    run = play(LEVEL, "statue", seed)
    assert run.over == S.FRAME_LIMIT
    first = next((e.frame for e in run.log if e.kind == S.BITTEN), None)
    assert first is None or first >= 500
