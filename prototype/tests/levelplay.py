"""Play a level with a bot, for the level tests (The rooms AN, AO and AQ).

One helper so that every level test measures the same way: a fresh session
on the building `--level` and `--room` would pick, one bot, one seed, to an
ending or a frame limit. Sound off, because nothing here listens.
"""

import pytest

from spikes import bots, levels, session as S

#: The light round moved the game on purpose (issues #116-#125) and every
#: gate measured before it went stale; they carried an xfail mark until
#: slice BB (issue #124) re-took the baseline and re-pinned them to the
#: figures in the vault's *2026-09-17 The light round baseline*. The mark
#: is kept as a no-op so the gates that wore it still name the round.
MOVING = pytest.mark.light_round

#: The seeds every level's numbers were taken on: the driver's default and
#: the three after it, the same four the sixteen baseline hashes use.
SEEDS = tuple(S.DEFAULT_SEED + i for i in range(4))

#: The seeds a **mean** is taken over: eight, because a rolled room can
#: hand one seed a catastrophe -- the Level 3 listener takes 0 of 7 on two
#: seeds in sixteen -- and a mean of four is then a coin rather than a
#: measurement (issue #130).
WIDE_SEEDS = tuple(S.DEFAULT_SEED + i for i in range(8))

#: Three minutes, the longest clock in any level.
THREE_MINUTES = 180 * 50


def play(level: int, bot: str, seed: int, room: int | None = None,
         solo: bool = False, frames: int = THREE_MINUTES,
         spray: bool = False) -> S.Session:
    """A run to its end, or to `frames`, on `level` from `room`, the rooms
    rolled for `seed` (issue #121). `spray` arms the bot (issue #122)."""
    building, start = levels.pick(level, room, solo, seed=seed)
    run = S.Session(seed=seed, sound=False, building=building,
                    start_room=start)
    player = bots.make(bot, seed=seed, spray=spray)
    while run.over is None and run.frame < frames:
        run.step(player.intent(run))
    if run.over is None:
        run.finish(S.FRAME_LIMIT)
    return run


def lives_lost(run: S.Session) -> int:
    return S.LIVES - run.lives
