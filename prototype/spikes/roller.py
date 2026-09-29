"""A room from a template: an authored shell with a rolled interior.

Issue #120, the user's ruling 1 of the light round: *"the whole point of
darkness is continued jeopardy as room layouts change and you have to
discover them."* Every room was the same bytes every run. A `room:` block in
a level file may now carry `roll:` instead of `map:`, and what it authors is
the **shell** -- the exit, the doorways, the room light, the beam and its
housing, the people's clocks and count, the flies' count, and a distance
band -- while the walls, the furniture, which cell each person stands on and
where each fly begins are drawn from the run's seed. Atic Atac's roll, *what
lies where*, plus geometry.

**What rolls, in order, from `roll_seed`** (*The light round* §2):

0. Which shell, if the template authors more than one (issue #132). One draw,
   before anything else, so a template that gains a second shell does not
   move the furniture in the first.
1. The shell: its walls -- the plain rectangle, or one of the authored ones --
   then the exit's two `D` cells in the west wall if the room has the exit,
   and each doorway's three `d` cells. The walls do not roll; which of the
   authored shells is used does.
2. Segments: straight solid runs, a pipe lying down (`=`) or a riser
   standing up (`|`), count and length in the authored ranges, each placed
   at a drawn origin and refused if it breaks the clearance rule, sixteen
   tries and then skipped -- fewer than asked is legal, more never is.
3. Pieces: a crate (2x2), a desk (2x1) or a cabinet (1x3), the same way.
4. A person-shaped distance map: breadth-first from the start over cells a
   person can stand in, feet and head both floor. **Route distance, not
   Manhattan**: a segment makes Manhattan a lie by its length, and the
   band is about the walk.
5. People: for each `worker:` line, a standable cell whose route distance
   is in the band and which is two clear of every other person, the start,
   a doorway's landing and the sign, and not under a room light.
6. Flies: floor cells at least `away` from the start and two from every
   person.
7. Gratings: nought to two `%` on floor under nobody. Floor in every
   mechanical respect; they count for nothing.

A roll that cannot place a person or a fly in sixty-four tries is **refused
and the whole room re-rolled from the next seed**, at most four times, and
then it is an error: a template that ever needs a fifth on any tested seed
does not ship. Nothing is patched by moving a segment.

**The clearance rule used to be the fairness, and it was traded** (issue
#132, ruling 2 of *The plateau and the rooms*). It is worth writing down what
it bought, because it was a good rule and what replaces it is longer.

Every rolled solid cell is still two floor cells clear of the border (so in
columns 3-28 and rows 3-18), two clear of every cell of any other segment or
piece, outside the doorway landings (rows 8-14, columns 1-5 and 26-30, which
is also the exit's landing and where its sign hangs) and two clear of the
start figure's two cells -- and, since #132, two clear of the chosen shell's
interior walls as well. An isolated straight run has two free ends and floor
all round, a convex block the same, so a fly blocked by one slides to an end
and goes round; two runs two cells apart leave a channel a one-cell fly walks
through; two clear rows between horizontals and two clear columns between
verticals fit a person.

**What that rule also did was make a corridor impossible.** Nothing it let
through could touch the border, so no seed on any level could produce a bay,
a division, a chamber, a dead end or a room within a room: every room in the
game was one open hall with furniture standing apart in it. The authored room
that had an inner box with a one-cell door could not be reproduced by the
roll on any seed -- and that box, measured, stranded nothing.

So the border exemption is the trade, and the fairness argument moves with
it, in three parts rather than one:

1. **The shell's walls are authored and may touch the border**, and a shell
   is gated once on its bare walls rather than sampled over seeds --
   `swarming.strands_a_shell`, which is a theorem: adding a start can only
   grow the set a fly can reach, and a rolled fly is an extra start, so a
   bare shell that strands nothing strands nothing on any seed. See BJ.
2. **A fly follows a wall to its end** (issue #131). Without that a wall that
   reached the border was a shield rather than an obstacle: the slide was
   dropped whenever the longest axis changed, so a fly beside a long wall
   ping-ponged in a band that never contained the gap.
3. **The clearance rule above still holds for everything that rolls**, the
   shell's interior walls included, which is what keeps a division walkable
   and keeps the furniture off it.

None of it is checked at run time. `swarming.unswarmable` runs over every
template on sixteen seeds in every `pytest`, 128 with `SPOTLIGHT_SLOW=1`, and
the shell gate runs on every shell every time -- at test time, never here,
because the check is a million steering calls and the port cannot afford it.
A roller that leaned on it would be a prototype that lies.

Portable: integers, lists and the xorshift the Z80 has. About five hundred
bytes of code on the port against thirty-two a template.
"""

from spotlight.core.constants import COLS

from .building import (
    CABINET, CRATE, DESK_L, DESK_R, DOOR, DOORWAY, EAST, FLOOR, GRATING, NORTH,
    PIPE_H, PIPE_V, SOUTH, VERTICAL_SIDES, WALL, WEST,
)
from .layout import PLAY_ROWS
from .sources import xorshift16

#: Where a rolled solid may lie: two floor cells clear of the border.
INTERIOR_COLS = range(3, COLS - 3)          # 3 .. 28
INTERIOR_ROWS = range(3, PLAY_ROWS - 3)     # 3 .. 18

#: The exit's two cells in the west wall, as `Building.solo` cuts them.
EXIT_ROWS = (10, 11)

#: How far a landing reaches: `LANDING_SPREAD` rows either side of the gap's
#: own rows, and `LANDING_DEPTH` columns in from the wall.
#:
#: This used to be `range(8, 15)` of rows by columns 1-5 and 26-30, on both
#: sides of every room whether a doorway was there or not -- which was the
#: middle of the wall, hard-coded, and was only ever right because every
#: doorway in the game sat at rows 10-12. Since issue #135 a doorway may be
#: anywhere in a vertical wall, so **the landing follows the doorway** and is
#: computed per room in `_Roll.landing_band`.
LANDING_SPREAD = 2
LANDING_DEPTH = 5

#: The exit's own landing, which does not move: rows 8-14 of the west wall,
#: the exit at rows 10-11 with the spread either side. It is kept clear whether
#: or not the room has the exit, because that is what the rule was before the
#: doorways were freed and a room's first five columns are where the tail
#: files out.
LANDING_ROWS = range(EXIT_ROWS[0] - LANDING_SPREAD,
                     EXIT_ROWS[-1] + LANDING_SPREAD + 1)
LANDING_COLS = tuple(range(1, 1 + LANDING_DEPTH))

#: How many floor cells a solid keeps clear of the border, another solid and
#: the start: two, which is the Chebyshev distance three below.
CLEAR = 3

#: Tries before a segment or piece is skipped, and before a person or fly
#: refuses the whole roll.
PLACE_TRIES = 16
PEOPLE_TRIES = 64
#: How many whole rooms a template may burn on one seed before it is an error.
REROLLS = 4


#: What a `shape:` block may contain (issue #132): walls, floor and doorways
#: and nothing else. No furniture character, no light, no person, no fly --
#: those are the roll's, and a shell that authored one would be authoring the
#: thing the roll exists to vary.
SHELL_ALPHABET = frozenset((WALL, FLOOR, DOOR, DOORWAY))


def landing_band(doorways) -> set:
    """Every cell a doorway lands on: the ground a tail has to file across.

    The exit's band in the west wall, which does not move, plus a band at each
    doorway -- `LANDING_SPREAD` either side of the gap's span and
    `LANDING_DEPTH` in from the wall it is cut through.

    `doorways` are `(side, span)` pairs, the shape a `Template` carries.

    **A module function since issue #144, and that is the whole point of it.**
    It was a method on the roll, so the only thing that could ask where a
    landing is was the thing placing rolled furniture -- and the authored wall
    was never asked at all. `blocks_a_landing` is the same rule read against a
    shell, and the two agreeing is the reason a spine cannot pass one and fail
    the other.
    """
    out = {(cx, cy) for cy in LANDING_ROWS for cx in LANDING_COLS}
    for side, span in doorways:
        lo = min(span) - LANDING_SPREAD
        hi = max(span) + LANDING_SPREAD
        if side in VERTICAL_SIDES:
            cols = (range(1, 1 + LANDING_DEPTH) if side == WEST
                    else range(COLS - 1 - LANDING_DEPTH, COLS - 1))
            for cy in range(lo, hi + 1):
                for cx in cols:
                    out.add((cx, cy))
        else:
            # The same band read on the other axis (issue #139): the rows just
            # inside the wall the gap is cut through, across the columns the
            # gap spans and the spread either side of them.
            band = (range(1, 1 + LANDING_DEPTH) if side == NORTH
                    else range(PLAY_ROWS - 1 - LANDING_DEPTH, PLAY_ROWS - 1))
            for cy in band:
                for cx in range(lo, hi + 1):
                    out.add((cx, cy))
    return out


def landing_lane(side, span) -> list[tuple[int, int]]:
    """The gap's **own** cells, `LANDING_DEPTH` in from the wall it is cut in.

    Not the same thing as `landing_band`, and issue #144 turns on the
    difference. The band is what a rolled *crate* must keep out of, so it takes
    `LANDING_SPREAD` either side of the gap: furniture standing two cells beside
    a doorway is worth refusing because the roll could as easily have put it
    somewhere else. The lane is what an authored *wall* must keep out of, and a
    wall two cells beside a doorway is a room with a division next to its door
    -- ordinary architecture, and `dogleg` is exactly that. **So the lane is the
    span and no spread.**

    Reading the issue's clause as the whole band refuses `dogleg`, which its own
    acceptance says must still pass; the table it was written from measured the
    gap's own columns. The table is the arbiter.

    Depth is `LANDING_DEPTH` either way, which is one constant read twice: a wall
    four cells inside the lane is an alcove you walk into, not a doorway.
    """
    lo, hi = min(span), max(span)
    if side in VERTICAL_SIDES:
        cols = (range(1, 1 + LANDING_DEPTH) if side == WEST
                else range(COLS - 1 - LANDING_DEPTH, COLS - 1))
        return [(cx, cy) for cy in range(lo, hi + 1) for cx in cols]
    rows_ = (range(1, 1 + LANDING_DEPTH) if side == NORTH
             else range(PLAY_ROWS - 1 - LANDING_DEPTH, PLAY_ROWS - 1))
    return [(cx, cy) for cy in rows_ for cx in range(lo, hi + 1)]


def blocks_a_landing(rows, doorways) -> list[tuple[int, int]]:
    """Every cell of a **shell's own wall** standing in a doorway's lane. Sorted.

    Issue #144, and the fault it exists for shipped in two shells. A doorway is
    `DOORWAY_CELLS` wide so that a tail files through without queueing and a
    first-timer does not bounce off it; an authored shell may run a wall to the
    border, which is what makes a division or a chamber possible at all. **The
    two rules collide and nothing noticed.**

    `spine` puts a wall down column 15 and `spine-low` down column 16, so a
    centre north or south doorway at columns 14-16 has a wall standing in the
    middle of it:

        20  #..............#...............#
        21  ##############ddd###############

    That building loads, validates and passes `swarming.strands_a_shell`,
    because columns 14 and 16 are floor and a fly is one cell. A person is one
    cell wide too and the movement assist nudges by up to a cell, so they
    *squeeze* -- which is the exact failure `DOORWAY_CELLS = 3` exists to
    prevent, and the first thing this audience reads as broken.

    **The roll must never carve this clear.** A silent repair would turn an
    authored division into two stubs and tell nobody. The gate refuses and the
    author fixes; that was ruled rather than assumed.

    `doorways` are `(side, span)` pairs. **The exit is one of them** for the room
    that has it -- `(WEST, EXIT_ROWS)` -- because it is a gap in a wall that a
    tail files through, and a wall across it would seal the building.

    Only `WALL` counts: a `DOORWAY` or `DOOR` cell in a lane is the gap itself.
    """
    solid = set()
    for side, span in doorways:
        for cx, cy in landing_lane(side, span):
            if 0 <= cy < len(rows) and 0 <= cx < len(rows[cy]) \
                    and rows[cy][cx] == WALL:
                solid.add((cx, cy))
    return sorted(solid)


class Template:
    """What a `roll:` block authors. Everything else is drawn."""

    __slots__ = ("segments", "length", "pieces", "band", "away", "workers",
                 "clegs", "doorways", "start", "exit", "lights", "shells")

    def __init__(self, *, segments=(0, 0), length=(4, 8), pieces=(0, 0),
                 band=(4, 30), away=6, workers=(), clegs=0, doorways=(),
                 start=(24, 96), exit=False, lights=(), shells=()) -> None:
        #: The authored shells this room's walls may be, as tuples of rows
        #: (issue #132, ruling 5). Empty means the plain rectangle, which is
        #: what every template was before the shells landed and what an
        #: unconverted one still gets. The roll picks one; the furniture, the
        #: people and the flies then roll inside it as they always did.
        #:
        #: **The walls stopped rolling so that fairness could stop being a
        #: sample.** The old clearance rule made a pocket unrepresentable and
        #: was checked over sixteen seeds a room; an authored shell can be
        #: checked once, on the bare walls, and the answer holds for every
        #: seed -- see `swarming.strands_a_shell` and BJ. A shell you can
        #: learn with contents you cannot is also the better room.
        self.shells = tuple(tuple(rows) for rows in shells)
        self.segments = tuple(segments)
        self.length = tuple(length)
        self.pieces = tuple(pieces)
        self.band = tuple(band)
        self.away = away
        #: One blood figure per person.
        self.workers = tuple(workers)
        self.clegs = clegs
        #: `(side, rows)` pairs; the room beyond is the loader's business.
        self.doorways = tuple((side, tuple(rows)) for side, rows in doorways)
        self.start = tuple(start)
        self.exit = exit
        #: The room's authored lights, `(left, top, width, height)`: nobody
        #: is placed under one. A room light shows the room and not who is
        #: in it, and a person standing in the patch the swarm gathers on
        #: is the lesson undone -- the authored rooms kept them off it, and
        #: a rolled room keeps the rule.
        self.lights = tuple(tuple(z) for z in lights)

    def validate(self, where: str = "a template") -> None:
        for name in ("segments", "length", "pieces", "band"):
            lo, hi = getattr(self, name)
            if lo < 0 or hi < lo:
                raise ValueError(f"{where}: {name} {lo} {hi} is not a range")
        if self.length[0] < 2:
            raise ValueError(f"{where}: a segment is at least two cells")
        if self.away < 0:
            raise ValueError(f"{where}: away cannot be negative")
        if self.clegs < 0:
            raise ValueError(f"{where}: clegs cannot be negative")
        for blood in self.workers:
            if blood <= 0:
                raise ValueError(f"{where}: a worker starts dead")
        for i, rows in enumerate(self.shells):
            if len(rows) != PLAY_ROWS:
                raise ValueError(f"{where}: shell {i} has {len(rows)} rows, "
                                 f"need {PLAY_ROWS}")
            for y, row in enumerate(rows):
                if len(row) != COLS:
                    raise ValueError(f"{where}: shell {i} row {y} is "
                                     f"{len(row)} cells, need {COLS}")
                bad = sorted(set(row) - SHELL_ALPHABET)
                if bad:
                    raise ValueError(
                        f"{where}: shell {i} row {y} has {bad}, and a shell "
                        f"holds walls, floor and doorways only")


class Rolled:
    """What a roll produced: the rows and the placements, and the seed the
    stream was left at, so the next room rolls on from it."""

    __slots__ = ("rows", "workers", "clegs", "seed", "rerolls")

    def __init__(self, rows, workers, clegs, seed, rerolls) -> None:
        self.rows = tuple(rows)
        self.workers = tuple(workers)
        self.clegs = tuple(clegs)
        self.seed = seed
        self.rerolls = rerolls


class _Dice:
    """The stream, stepped once per draw. Never zero."""

    def __init__(self, seed: int) -> None:
        self.state = seed or 1

    def draw(self, n: int) -> int:
        """0 .. n-1."""
        self.state = xorshift16(self.state)
        return self.state % n

    def between(self, lo: int, hi: int) -> int:
        return lo + self.draw(hi - lo + 1)


def start_cells(start) -> tuple[tuple[int, int], tuple[int, int]]:
    """The start figure's feet cell and head cell, from its pixel position."""
    x, y = start
    feet = (x // 8, (y + 15) // 8)
    return feet, (feet[0], feet[1] - 1)


def _chebyshev(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def shell(template: Template, dice: "_Dice | None" = None) -> list[list[str]]:
    """The walls, the exit and the doorways: the part that never rolls.

    With no authored shell this is the plain rectangle it has always been.
    With one or more (issue #132) the roll picks between them -- one draw,
    taken before any other, so a template that gains a second shell does not
    move the furniture in the first -- and the exit and the doorways are then
    cut into whichever was chosen.

    **The doorways are cut here and not authored in the shell** even though a
    shell is allowed to spell them: `door:` lines in the level file are the
    one source of truth for where a doorway is and which room is beyond it,
    and a shell that disagreed with them would be a second answer to a
    question that already has one.
    """
    if template.shells:
        pick = template.shells[dice.draw(len(template.shells))] if dice \
            else template.shells[0]
        rows = [list(row) for row in pick]
    else:
        rows = [[WALL] * COLS]
        rows += [[WALL] + [FLOOR] * (COLS - 2) + [WALL]
                 for _ in range(PLAY_ROWS - 2)]
        rows.append([WALL] * COLS)
    if template.exit:
        for cy in EXIT_ROWS:
            rows[cy][0] = DOOR
    for side, span in template.doorways:
        # Either axis since issue #139: a vertical doorway is a run of rows in
        # a fixed column, a horizontal one a run of columns in a fixed row.
        if side in VERTICAL_SIDES:
            column = COLS - 1 if side == EAST else 0
            for cy in span:
                rows[cy][column] = DOORWAY
        else:
            row = PLAY_ROWS - 1 if side == SOUTH else 0
            for cx in span:
                rows[row][cx] = DOORWAY
    return rows


def _pieces_of(kind: int, cx: int, cy: int) -> list[tuple[int, int, str]]:
    """The cells a piece of `kind` covers from its top-left, with their glyphs."""
    if kind == 0:                                   # a crate, 2x2
        return [(cx + dx, cy + dy, CRATE) for dy in (0, 1) for dx in (0, 1)]
    if kind == 1:                                   # a desk, 2x1
        return [(cx, cy, DESK_L), (cx + 1, cy, DESK_R)]
    return [(cx, cy + dy, CABINET) for dy in (0, 1, 2)]   # a cabinet, 1x3


class _Roll:
    """One attempt at a room."""

    def __init__(self, template: Template, dice: _Dice) -> None:
        self.template = template
        self.dice = dice
        self.rows = shell(template, dice)
        self.feet, self.head = start_cells(template.start)
        #: Cells a new solid may not take: outside the interior, on a
        #: landing, near the start, or within reach of a placed solid.
        self.blocked = set()
        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                if cx not in INTERIOR_COLS or cy not in INTERIOR_ROWS:
                    self.blocked.add((cx, cy))
        self.blocked |= self.landing_band()
        # **`CLEAR = 3` is kept and the border is the one exemption**
        # (issue #132). A shell's own wall may run to the edge -- that is the
        # whole point of authoring it -- but a *rolled* solid still keeps two
        # floor cells clear of everything solid, and the shell's interior
        # walls are now among the things it keeps clear of. So a division
        # leaves a corridor either side of it wide enough for a person and
        # for a fly to slide down, and the furniture stands off it exactly as
        # it stands off another piece.
        #
        # This is what the retro-gamer's *architecture eats furniture* comes
        # from: a corridor narrower than seven cells admits no piece at all,
        # and that is the price of the shape rather than a bug in it.
        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                if cx in INTERIOR_COLS and cy in INTERIOR_ROWS \
                        and self.rows[cy][cx] == WALL:
                    self._block_around((cx, cy))
        for cell in (self.feet, self.head):
            self._block_around(cell)

    def landing_band(self) -> set:
        """Every cell a rolled solid may not take because a doorway lands on it.

        **It follows the doorway** (issue #135). It used to be the middle rows
        of both walls whether a doorway was there or not, which was right only
        while every doorway in the game sat at rows 10-12; a doorway near a
        corner would have had a solid rolled into the cells a tail has to file
        through, and a doorway in the middle of a room with no doorway there
        would have kept five columns clear for nothing.

        The rule itself is `landing_band` at module level since issue #144, so
        that the gate can read it against an authored wall as well as this can
        read it against a rolled one.
        """
        return landing_band(self.template.doorways)

    def _block_around(self, cell) -> None:
        cx, cy = cell
        for dy in range(-CLEAR + 1, CLEAR):
            for dx in range(-CLEAR + 1, CLEAR):
                self.blocked.add((cx + dx, cy + dy))

    def _place(self, cells) -> bool:
        for cx, cy, _glyph in cells:
            if cx not in INTERIOR_COLS or cy not in INTERIOR_ROWS:
                return False
            if (cx, cy) in self.blocked:
                return False
        for cx, cy, glyph in cells:
            self.rows[cy][cx] = glyph
        for cx, cy, _glyph in cells:
            self._block_around((cx, cy))
        return True

    # --- the solids ----------------------------------------------------------

    def segments(self) -> None:
        t, dice = self.template, self.dice
        for _ in range(dice.between(*t.segments)):
            for _try in range(PLACE_TRIES):
                horizontal = dice.draw(2) == 0
                length = dice.between(*t.length)
                cx = dice.between(INTERIOR_COLS[0], INTERIOR_COLS[-1])
                cy = dice.between(INTERIOR_ROWS[0], INTERIOR_ROWS[-1])
                if horizontal:
                    cells = [(cx + i, cy, PIPE_H) for i in range(length)]
                else:
                    cells = [(cx, cy + i, PIPE_V) for i in range(length)]
                if self._place(cells):
                    break

    def pieces(self) -> None:
        t, dice = self.template, self.dice
        for _ in range(dice.between(*t.pieces)):
            for _try in range(PLACE_TRIES):
                kind = dice.draw(3)
                cx = dice.between(INTERIOR_COLS[0], INTERIOR_COLS[-1])
                cy = dice.between(INTERIOR_ROWS[0], INTERIOR_ROWS[-1])
                if self._place(_pieces_of(kind, cx, cy)):
                    break

    # --- the people and the flies --------------------------------------------

    def solid(self, cx: int, cy: int) -> bool:
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return True
        return self.rows[cy][cx] not in (FLOOR, DOOR, DOORWAY, GRATING)

    def standable(self, cx: int, cy: int) -> bool:
        """Feet here, head above, neither solid: where a person can stand."""
        return cy >= 1 and not self.solid(cx, cy) and not self.solid(cx, cy - 1)

    def distances(self) -> dict:
        """Route distance from the start to every standable cell, by a
        breadth-first walk a person's shape can make."""
        seen = {self.feet: 0}
        queue = [self.feet]
        while queue:
            nxt = []
            for cx, cy in queue:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nb = (cx + dx, cy + dy)
                    if nb not in seen and self.standable(*nb):
                        seen[nb] = seen[(cx, cy)] + 1
                        nxt.append(nb)
            queue = nxt
        return seen

    def landings(self) -> list[tuple[int, int]]:
        """The cells just inside each doorway, where a crossing lands."""
        out = []
        for side, door_rows in self.template.doorways:
            column = COLS - 2 if side == EAST else 1
            out += [(column, cy) for cy in door_rows]
        return out

    def sign(self) -> list[tuple[int, int]]:
        """Where the exit's sign hangs, as `Room.exit_sign_cells` puts it."""
        if not self.template.exit:
            return []
        return [(1 + i, EXIT_ROWS[0]) for i in range(4)]

    def under_a_light(self, cell) -> bool:
        cx, cy = cell
        for left, top, width, height in self.template.lights:
            if left <= cx < left + width and top <= cy < top + height:
                return True
            if left <= cx < left + width and top <= cy - 1 < top + height:
                return True                     # the head cell
        return False

    def people(self, dist: dict) -> list | None:
        t, dice = self.template, self.dice
        lo, hi = t.band
        pool = sorted(cell for cell, d in dist.items()
                      if lo <= d <= hi and not self.under_a_light(cell))
        if not pool:
            return None
        keep_off = [self.feet, self.head] + self.landings() + self.sign()
        placed = []
        for blood in t.workers:
            for _try in range(PEOPLE_TRIES):
                cell = pool[dice.draw(len(pool))]
                near = [c for c in keep_off if _chebyshev(c, cell) < 2]
                near += [c for c in placed if _chebyshev(c, cell) < 2
                         or _chebyshev((c[0], c[1] - 1), cell) < 2]
                if not near:
                    placed.append(cell)
                    break
            else:
                return None
        return [(cx * 8, (cy - 1) * 8, blood)
                for (cx, cy), blood in zip(placed, t.workers)]

    def flies(self, people) -> list | None:
        t, dice = self.template, self.dice
        floor = [(cx, cy) for cy in range(1, PLAY_ROWS - 1)
                 for cx in range(1, COLS - 1) if not self.solid(cx, cy)]
        person_cells = []
        for x, y, _blood in people:
            feet = (x // 8, (y + 15) // 8)
            person_cells += [feet, (feet[0], feet[1] - 1)]
        placed = []
        for _ in range(t.clegs):
            for _try in range(PEOPLE_TRIES):
                cell = floor[dice.draw(len(floor))]
                if _chebyshev(cell, self.feet) < t.away:
                    continue
                if any(_chebyshev(c, cell) < 2 for c in person_cells):
                    continue
                if cell in placed:
                    continue
                placed.append(cell)
                break
            else:
                return None
        return placed

    def gratings(self, people, flies) -> None:
        dice = self.dice
        keep_off = set(flies) | {self.feet, self.head}
        for x, y, _blood in people:
            feet = (x // 8, (y + 15) // 8)
            keep_off |= {feet, (feet[0], feet[1] - 1)}
        floor = [(cx, cy) for cy in INTERIOR_ROWS for cx in INTERIOR_COLS
                 if self.rows[cy][cx] == FLOOR and (cx, cy) not in keep_off]
        for _ in range(dice.draw(3)):
            if floor:
                cx, cy = floor.pop(dice.draw(len(floor)))
                self.rows[cy][cx] = GRATING


def roll(template: Template, seed: int, where: str = "a template") -> Rolled:
    """A room from `template` and `seed`. The same two give the same room.

    Raises `ValueError` when the template cannot place its people or flies
    on this seed in `REROLLS` whole attempts -- a template that does that on
    any tested seed does not ship.
    """
    template.validate(where)
    dice = _Dice(seed)
    for attempt in range(REROLLS + 1):
        if attempt:
            dice.state = xorshift16(dice.state)      # the next seed
        this = _Roll(template, dice)
        this.segments()
        this.pieces()
        dist = this.distances()
        people = this.people(dist)
        if people is None:
            continue
        flies = this.flies(people)
        if flies is None:
            continue
        this.gratings(people, flies)
        return Rolled(["".join(r) for r in this.rows], people, flies,
                      dice.state, attempt)
    raise ValueError(f"{where}: no room could be rolled from seed {seed:#x} "
                     f"in {REROLLS + 1} attempts; the band or the counts are "
                     "wrong for this shell")


def route_distances(rows, start) -> dict:
    """The person-shaped distance map of a finished room, for the tests."""
    t = Template(start=start)
    r = _Roll(t, _Dice(1))
    r.rows = [list(row) for row in rows]
    return r.distances()
