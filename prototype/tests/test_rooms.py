"""Every room is run on its own and in its building, and the ramp is
asserted (issue #113, The rooms AQ).

The user's ask: *tests so each room can be run on its own*. Every room of
every level is played with the reference bots on four seeds, alone
(`Building.solo`) and in its building, and what the vault's *The rooms*
says each must pass is asserted here. Slow -- a few minutes -- so it runs
only with `SPOTLIGHT_SLOW=1`, which the CI job sets.

**The gates and where they come from.** Each row names the section of
*The rooms* (the vault, `plans/The rooms.md`) that a failure contradicts:

    gate                                         source in *The rooms*
    ---------------------------------------------------------------------
    solo: oracle all_out, every seed             section 2, the oracle gate
    solo: listener never frame_limit             section 2, the listener gate;
                                                 section 4, "Each room from its
                                                 own start" (the wedge, AP)
    in building from its own start: oracle       section 4, "Each room from its
      all_out, every seed                        own start", the oracle column
    from the exit, Level 1: oracle all_out;      section 4, "The buildings,
      listener all_out and no life lost          from the exit", row 1
    from the exit, Level 2: oracle all_out;      section 4, row 2
      listener at least 6 of 7
    from the exit, Level 3: oracle all_out;      section 4, row 3 (the
      listener 6 of 7, never frame_limit         tester's baseline)
    the ramp within a level: oracle blood in     section 4, "The rooms, by the
      1.1 <= 1.2, 2.1 <= 2.2, 3.1 <= 3.2         oracle's bites", and "Where it
                                                 is not monotone" for the two
                                                 pairs left out (1.2 -> 1.3,
                                                 2.2 -> 2.3)
    the ramp across levels: the oracle's         section 4, "The ramp across
      whole-run blood, Level 1 < 2 < 3           levels, by the fixed bots"

The two pairs left out of the ramp are not monotone by the bots and the
note says why: 1.3 ramps by distance and the fade, and 2.3's threat is the
torch, which no measuring bot carries. A test that demanded monotone
everywhere would be a test of the bots' blindness to the torch.
"""

import os
import statistics

import pytest

from levelplay import SEEDS, play, lives_lost
from spikes import levels, session as S

pytestmark = pytest.mark.skipif(
    not os.environ.get("SPOTLIGHT_SLOW"),
    reason="every room with every bot on four seeds; set SPOTLIGHT_SLOW=1")

LEVELS = (1, 2, 3)
ROOMS = [(level, room) for level in LEVELS
         for room in range(len(levels.level(level)))]


def room_id(pair):
    level, room = pair
    return f"{level}.{room + 1}-{levels.level(level)[room].name}"


def blood_in(run, room_name: str) -> int:
    """Blood taken off the player while standing in `room_name`."""
    return sum(e.count for e in run.log
               if e.kind == S.DRAINED and e.room == room_name)


# --- every room on its own ---------------------------------------------------

@pytest.mark.parametrize("pair", ROOMS, ids=room_id)
@pytest.mark.parametrize("seed", SEEDS)
def test_alone_the_oracle_gets_everyone_out(pair, seed):
    level, room = pair
    run = play(level, "oracle", seed, room=room, solo=True)
    assert run.over == S.ALL_OUT, f"{run.over} with {run.rescued}/{run.total}"


@pytest.mark.parametrize("pair", ROOMS, ids=room_id)
@pytest.mark.parametrize("seed", SEEDS)
def test_alone_the_listener_never_runs_out_of_frames(pair, seed):
    level, room = pair
    run = play(level, "listener", seed, room=room, solo=True)
    assert run.over != S.FRAME_LIMIT, \
        f"stalled at {(run.player.x, run.player.y)} with {run.rescued}/{run.total}"


# --- every room in its building, started there ------------------------------

@pytest.mark.parametrize("pair", ROOMS, ids=room_id)
@pytest.mark.parametrize("seed", SEEDS)
def test_started_in_the_room_the_oracle_gets_everyone_out(pair, seed):
    level, room = pair
    run = play(level, "oracle", seed, room=room)
    assert run.over == S.ALL_OUT, f"{run.over} with {run.rescued}/{run.total}"


# --- each level from the exit -------------------------------------------------

@pytest.fixture(scope="module")
def from_the_exit():
    """One run per bot per seed per level, shared by the gates and the ramp."""
    return {(level, bot, seed): play(level, bot, seed)
            for level in LEVELS for bot in ("oracle", "listener")
            for seed in SEEDS}


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("seed", SEEDS)
def test_from_the_exit_the_oracle_gets_everyone_out(from_the_exit, level, seed):
    run = from_the_exit[(level, "oracle", seed)]
    assert run.over == S.ALL_OUT, f"{run.over} with {run.rescued}/{run.total}"


@pytest.mark.parametrize("seed", SEEDS)
def test_from_the_exit_level_one_the_listener_loses_nobody(from_the_exit, seed):
    run = from_the_exit[(1, "listener", seed)]
    assert run.over == S.ALL_OUT and lives_lost(run) == 0


@pytest.mark.parametrize("seed", SEEDS)
def test_from_the_exit_level_two_the_listener_gets_six_of_seven(
        from_the_exit, seed):
    run = from_the_exit[(2, "listener", seed)]
    assert run.over != S.FRAME_LIMIT and run.rescued >= 6


@pytest.mark.parametrize("seed", SEEDS)
def test_from_the_exit_level_three_the_listener_gets_six_of_seven(
        from_the_exit, seed):
    run = from_the_exit[(3, "listener", seed)]
    assert run.over != S.FRAME_LIMIT and run.rescued >= 6


# --- the ramp -----------------------------------------------------------------

#: The pairs of rooms, in chain order, the note says the oracle's blood is
#: non-decreasing across. The other two pairs are left out on purpose; see
#: the module docstring.
MONOTONE = ((1, 0, 1), (2, 0, 1), (3, 0, 1))


@pytest.mark.parametrize("level,first,second", MONOTONE,
                         ids=["1.1->1.2", "2.1->2.2", "3.1->3.2"])
def test_the_ramp_within_a_level(from_the_exit, level, first, second):
    building = levels.level(level)
    a, b = building[first].name, building[second].name
    runs = [from_the_exit[(level, "oracle", seed)] for seed in SEEDS]
    before = statistics.mean(blood_in(run, a) for run in runs)
    after = statistics.mean(blood_in(run, b) for run in runs)
    assert before <= after, f"{a} took {before} blood, {b} {after}"


def test_the_ramp_across_levels(from_the_exit):
    blood = [statistics.mean(from_the_exit[(level, "oracle", seed)]
                             .tally.blood_lost for seed in SEEDS)
             for level in LEVELS]
    assert blood[0] < blood[1] < blood[2], \
        f"the oracle's blood by level: {blood}"
