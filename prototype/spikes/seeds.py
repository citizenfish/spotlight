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

#: The housings' corners (issue #137). **One stream for the building, not one
#: per room**, and the room's index is added to it -- so the corners rotate
#: round the building and two neighbours never share one, and which corner the
#: first room gets is the run's.
#:
#: That is a design and not a shrug, because the obvious thing does not work:
#: `xorshift16` is linear over GF(2), so a fixed difference between two seeds
#: gives a fixed difference between their outputs. Taking two bits off
#: `<TAG> + i` therefore yields only **four** arrangements of a three-room
#: building however many rounds it is put through -- measured over 500 runs at
#: six different bit positions and with one, two and three xorshifts: four
#: patterns every time, with uniform marginals. Breaking that needs a
#: non-linear step, which is a multiply or a table, and a cosmetic corner is
#: not worth either on a Z80. So the rotation is stated instead of pretended.
MOUNT_TAG = 0x4D10

#: Which rooms the building's people are dealt to, and in what order the dead
#: ends are filled (issue #143). Its own stream so that changing the deal does
#: not move the furniture, and so that adding a room moves the deal and nothing
#: else -- the rule the whole module is built on.
PEOPLE_TAG = 0x9E01


def level_seed(run_seed: int, level: int | None) -> int:
    """The seed a level's streams hang off: the run seed and the level."""
    return xorshift16((run_seed or 1) ^ (((level or 0) * 0x9E37) & 0xFFFF))


def stream(level_seed_: int, tag: int) -> int:
    """One stream's seed from the level seed and its tag. Never zero."""
    return xorshift16((level_seed_ ^ tag) or 1)


def roll_seed(run_seed: int, level: int | None) -> int:
    """The roller's seed for a level of a run."""
    return stream(level_seed(run_seed, level), ROLL_TAG)


def people_seed(run_seed: int, level: int | None) -> int:
    """The seed the building's people are dealt to their rooms from (#143)."""
    return stream(level_seed(run_seed, level), PEOPLE_TAG)
