"""Play a level with a bot, for the level tests (The rooms AN, AO and AQ).

One helper so that every level test measures the same way: a fresh session
on the building `--level` and `--room` would pick, one bot, one seed, to an
ending or a frame limit. Sound off, because nothing here listens.
"""

from spikes import bots, levels, session as S

#: The seeds every level's numbers were taken on: the driver's default and
#: the three after it, the same four the sixteen baseline hashes use.
SEEDS = tuple(S.DEFAULT_SEED + i for i in range(4))

#: Three minutes, the longest clock in any level.
THREE_MINUTES = 180 * 50


def play(level: int, bot: str, seed: int, room: int | None = None,
         solo: bool = False, frames: int = THREE_MINUTES,
         light: bool | None = None) -> S.Session:
    """A run to its end, or to `frames`, on `level` from `room`."""
    building, start = levels.pick(level, room, solo)
    run = S.Session(seed=seed, sound=False, building=building,
                    start_room=start)
    player = bots.make(bot, seed=seed, light=light)
    while run.over is None and run.frame < frames:
        run.step(player.intent(run))
    if run.over is None:
        run.finish(S.FRAME_LIMIT)
    return run


def lives_lost(run: S.Session) -> int:
    return S.LIVES - run.lives
