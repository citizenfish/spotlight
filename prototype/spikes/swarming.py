"""Can the swarm get there? A level check, and not a flood fill.

Issue #26, from *Building Structure* and *Building Designer* in the vault after
a measurement that changed whose job coverage is.

**The finding.** The room had a low wall enclosing its bottom-right corner. A
motionless player lost 146.2 blood in the middle of the room and **1.6 in that
corner** over the same 150 seconds -- ninety-one times safer. It was not a
lighting failure: the beam reached the corner, and Clegs got *closer* to it than
to the middle. They could not close the last two cells, because they steer and
slide rather than pathfind, so they piled against the wall.

So *"nowhere is permanently safe"* is a property **the level author has to
satisfy**, not one the searchlight can guarantee. The beam guarantees light; it
cannot guarantee delivery. In a dark game, floor the player can reach and the
swarm cannot is a permanent refuge worth more than any decision the player can
make -- and it is invisible to whoever drew the room.

**Why this cannot be a flood fill.** A flood fill asks whether a path exists.
That is the wrong question about an animal that cannot find one. The check has
to run the Cleg's own steering rule -- `Cleg._toward`, the same greedy step,
longest axis first, sliding when blocked -- from a spread of starts, and see
where it actually ends up. It is the same shape of mistake as a walkability
check that tests one cell for a person who is two cells tall.

It is deliberately **optimistic about the fly**: a plain Cleg, steering straight
at the target with nothing in its way but the walls. A flanker comes in off to
one side and does worse. So a cell this reports as unreachable is unreachable by
the most capable fly in the swarm, and the report is a floor rather than a
guess.
"""

from spotlight.core.constants import COLS

from .clegs import Cleg
from .layout import PLAY_ROWS

#: How many steps a fly is given to close on a cell before it is called stuck.
#: Twice the diagonal of a room, so anything sliding along a wall the long way
#: round still gets there. Sliding is what a Cleg does instead of a route, and
#: the whole point of the check is to find out how far that carries it.
BUDGET = 2 * (COLS + PLAY_ROWS)

#: A second pass takes starts from every Nth cell the first pass could reach,
#: so the check is run from a spread rather than from one corner of the room.
SPREAD = 5


def origins(room) -> list[tuple[int, int]]:
    """Where flies actually are: the swarm as authored, and the doorways.

    **Not a grid over the floor.** A start placed inside a pocket would say the
    pocket was reachable because something was already standing in it, which is
    the one answer this check must never give. A fly is somewhere the author
    put it, or it walked in through a door.
    """
    places = [tuple(c) for c in room.clegs]
    for door in room.doorways:
        places += [(door.column, cy) for cy in door.rows]
    return sorted(set(places))


def can_reach(room, start: tuple[int, int], target: tuple[int, int],
              budget: int = BUDGET) -> bool:
    """Steer one fly from `start` at `target`. Did it get there?

    `Cleg._toward` and nothing else: this must never be given a route-finder,
    because the thing it is asking about is precisely that Clegs have not got
    one. A fly that has stopped moving has run out of rule -- it is pressed
    into a wall with the target on the other side of it -- and nothing but the
    light moving will shift it, so the walk ends there.
    """
    fly = Cleg(*start)
    for _ in range(budget):
        if (fly.cx, fly.cy) == target:
            return True
        was = (fly.cx, fly.cy)
        fly._toward(target[0], target[1], room.is_solid)
        if (fly.cx, fly.cy) == was:
            return False
    return (fly.cx, fly.cy) == target


def _reached(room, places, budget: int) -> set[tuple[int, int]]:
    """Every floor cell a fly from one of `places` can steer to.

    Nearest start first, so open floor costs a handful of steps and stops.
    Only a genuine pocket pays for the whole spread.
    """
    out = set()
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            if room.is_solid(cx, cy):
                continue
            near = sorted(places,
                          key=lambda s: (s[0] - cx) ** 2 + (s[1] - cy) ** 2)
            if any(can_reach(room, start, (cx, cy), budget) for start in near):
                out.add((cx, cy))
    return out


def unswarmable(room, budget: int = BUDGET) -> list[tuple[int, int]]:
    """Every floor cell in the room the swarm cannot get to. Sorted.

    Two passes. The first steers from where the flies are; the second adds a
    spread of the ground the first pass proved they can stand on, because a
    swarm drifts and a fly that reached somewhere can set off again from there.

    **The spread is drawn from reached ground and never from the whole floor**,
    which is the difference between this and a flood fill run twice: it can
    never assume a fly into a pocket in order to prove the pocket reachable.
    """
    starts = origins(room)
    reached = _reached(room, starts, budget)
    spread = [cell for i, cell in enumerate(sorted(reached)) if i % SPREAD == 0]
    if spread:
        reached |= _reached(room, starts + spread, budget)
    return sorted((cx, cy)
                  for cy in range(PLAY_ROWS) for cx in range(COLS)
                  if not room.is_solid(cx, cy) and (cx, cy) not in reached)
