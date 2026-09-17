"""The seed streams: one seed per thing a run rolls, from the run seed.

Issue #116. One chain used to feed everything -- the flies' temperaments,
the searchlight's tour, the brood -- and every room's beam took the same
seed, so they all entered at the same station and swept in step, and the
same run seed gave the same entry on every level. Now the run seed and the
level number make a **level seed**, and each stream takes its own seed
from that by a tag. Changing a template moves the roll and nothing else;
adding a room moves that room's beam and nothing else.

Here rather than in `session.py` because the level loader needs the roll
stream before there is a session (issue #120): a rolled room is the run
seed's, so `levels.load` derives the same `roll_seed` the session would.
Portable: integers, and the xorshift the Z80 has.
"""

from .sources import xorshift16

#: The tags. Rooms' beams take `BEAM_TAG + index`.
ROLL_TAG, CLEG_TAG, BEAM_TAG, BROOD_TAG = 0x5A00, 0xC1E6, 0xBEA0, 0xB700


def level_seed(run_seed: int, level: int | None) -> int:
    """The seed a level's streams hang off: the run seed and the level."""
    return xorshift16((run_seed or 1) ^ (((level or 0) * 0x9E37) & 0xFFFF))


def stream(level_seed_: int, tag: int) -> int:
    """One stream's seed from the level seed and its tag. Never zero."""
    return xorshift16((level_seed_ ^ tag) or 1)


def roll_seed(run_seed: int, level: int | None) -> int:
    """The roller's seed for a level of a run."""
    return stream(level_seed(run_seed, level), ROLL_TAG)
