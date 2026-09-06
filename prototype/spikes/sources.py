"""The four light sources.

Every one of them resolves at 8x8 cell granularity and feeds the same
brightest-wins field in `lighting`. None of them writes an attribute directly --
light decides colour, and it does so in one place.

    1. Glow     one cell in every direction, always on, dim
    2. Room     an authored zone, fixed, always on
    3. Cone     a wedge in the facing direction, toggleable, with power
    4. Roaming  a pool that moves on its own -- sweeping, on a path, or drifting

Each source carries three things the field composites: the **level** it reads
at while it is shining, the **memory** it leaves once it has gone, and a
**hue**, which uncoloured cells take on. Level and memory are separate on
purpose -- the searchlight is as bright as the carried spotlight and forgotten
far sooner.
"""

from math import isqrt

from spotlight.core.constants import COLS, YELLOW

from .layout import PLAY_ROWS
from .lighting import (
    CHARGE_DIM, CHARGE_LIT, CHARGE_SWEEP, DIM, LIT, UNCOLOURED, LightField,
)

# --- facing ----------------------------------------------------------------

UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3

#: facing -> (forward dx, forward dy, sideways dx, sideways dy)
_AXES = {
    UP: (0, -1, 1, 0),
    DOWN: (0, 1, 1, 0),
    LEFT: (-1, 0, 0, 1),
    RIGHT: (1, 0, 0, 1),
}


#: How far off a light can be noticed. A lit source can be seen from anywhere
#: a Cleg is capable of noticing; the dim personal glow cannot.
FAR = 255

#: How close a Cleg has to be to notice your own glow.
#:
#: Small on purpose. It is what stops standing still in the dark being perfectly
#: safe -- something that blunders within a few cells of you will find you --
#: without making the dark useless, because nothing across the room ever will.
#: Keeping still is a short reprieve, not a hiding place.
GLOW_REACH = 2


class Source:
    """Common switching. Subclasses implement `emit`."""

    def __init__(self, level: int = LIT, memory: int = CHARGE_LIT,
                 enabled: bool = True, hue: int = UNCOLOURED,
                 reveals: bool = True) -> None:
        self.level = level
        self.memory = memory
        self.hue = hue
        self.enabled = enabled
        #: Whether this light shows people, or only the room they stand in.
        self.reveals = reveals

    def light(self, field: LightField, cx: int, cy: int) -> None:
        field.add(cx, cy, self.level, self.memory, self.hue, self.reveals)

    # --- what Clegs steer for ----------------------------------------------

    def origin(self) -> tuple[int, int]:  # pragma: no cover - interface
        """The cell a Cleg heads for when this light is what drew it."""
        raise NotImplementedError

    def lure(self) -> tuple[int, int, int] | None:
        """Where this light pulls Clegs to and from how far, or None.

        **All light attracts; how far it carries depends on how bright it is.**
        A lit source can be noticed from anywhere; the dim personal glow only
        from a few cells. So switching your spotlight on is still the decision
        that costs -- it is the difference between being findable across the
        room and being findable at arm's length -- while the dark stops being a
        place you can simply stand in for ever.

        Clegs steer for the light itself, not for the lit ground around it, so
        this is one point per source, checked per Cleg. There is no search over
        cells and no route-finding anywhere in it.
        """
        if not self.enabled or self.level <= 0:
            return None
        return (*self.origin(), FAR)

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def apply(self, field: LightField) -> None:
        if self.enabled:
            self.emit(field)

    def emit(self, field: LightField) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class Glow(Source):
    """The personal glow: one cell in every direction **around the person**.

    Never switched off in play -- it is what stops total darkness being
    unplayable -- but switchable here so its contribution can be seen alone.

    `tall` is how many cells the body occupies above its feet. It matters more
    than it sounds: the glow is anchored on the feet cell, and a person is two
    cells high, so a glow of one cell in every direction from the *feet* stops
    level with the top of the head. The row above was dark, and walking north
    meant walking into walls you could not see. One cell in every direction
    means from the whole figure, not from the square it is standing on.
    """

    def __init__(self, level: int = DIM, memory: int = CHARGE_DIM,
                 tall: int = 2) -> None:
        super().__init__(level, memory)
        self.x = 0
        self.y = 0
        self.tall = tall

    def origin(self) -> tuple[int, int]:
        return self.x, self.y

    def lure(self) -> tuple[int, int, int] | None:
        """You are always slightly visible, and only from very close."""
        return None if not self.enabled else (self.x, self.y, GLOW_REACH)

    def emit(self, field: LightField) -> None:
        for dy in range(-self.tall, 2):
            for dx in (-1, 0, 1):
                self.light(field, self.x + dx, self.y + dy)


class RoomLight(Source):
    """Emergency lighting: an authored zone, fixed, always on.

    The level author's sharpest tool -- what a room shows you for free, and what
    it keeps dark, is most of what makes one room different from another.

    **It shows the room, not who is in it.** A fixed light over a worker would
    otherwise be a permanent window onto that worker, which reads as scenery
    rather than as information and takes the room out of the dark for good.
    Emergency lighting tells you the shape of the place; finding the people in
    it is the player's job (issue #12).
    """

    def __init__(self, left: int, top: int, width: int, height: int,
                 level: int = LIT, memory: int = CHARGE_LIT,
                 reveals: bool = False) -> None:
        super().__init__(level, memory, reveals=reveals)
        self.left, self.top = left, top
        self.width, self.height = width, height

    def origin(self) -> tuple[int, int]:
        """The middle of the zone. Close enough -- a Cleg heading for a lit
        room does not need to pick a particular floor tile of it."""
        return self.left + self.width // 2, self.top + self.height // 2

    def emit(self, field: LightField) -> None:
        for cy in range(self.top, self.top + self.height):
            for cx in range(self.left, self.left + self.width):
                self.light(field, cx, cy)


class Cone(Source):
    """The carried spotlight: a wedge ahead of the player's facing.

    A cone rather than a radius so that facing is a real decision -- you cannot
    light the way forward and watch what is behind you at the same time.

    Widens by one cell every two of reach, which is roughly 45 degrees.
    """

    def __init__(self, reach: int = 7, power: int = 600,
                 level: int = LIT, memory: int = CHARGE_LIT) -> None:
        super().__init__(level, memory, enabled=False)
        self.reach = reach
        self.power = power
        self.x = 0
        self.y = 0
        self.facing = RIGHT

    @property
    def lit(self) -> bool:
        """Lit only when switched on and with power left."""
        return self.enabled and self.power > 0

    def drain(self, amount: int = 1) -> None:
        """Power falls only while lit."""
        if self.lit:
            self.power = max(0, self.power - amount)

    def origin(self) -> tuple[int, int]:
        return self.x, self.y

    def lure(self) -> tuple[int, int, int] | None:
        """The player's own cell, not the wedge ahead of them.

        A Cleg drawn by your spotlight is drawn to *you*: the wedge is where the
        light lands, but the lamp -- and the blood -- are at its point. Steering
        to the wedge would have the swarm converge somewhere in front of you and
        then need a second rule to find you.
        """
        return (self.x, self.y, FAR) if self.lit else None

    def cells(self) -> list[tuple[int, int]]:
        """The wedge, **and the cell you are standing in**.

        You are holding the lamp, so you are in its light. Without this the
        central bargain has no teeth: switching your spotlight on would draw
        the swarm to you and leave you untouchable when it arrived, because a
        Cleg only bites somebody it can see. Found by measuring the cost of
        each lighting policy in issue #10 and getting zero for all of them.
        """
        fx, fy, sx, sy = _AXES[self.facing]
        out = [(self.x, self.y)]
        for d in range(1, self.reach + 1):
            half = d // 2
            for k in range(-half, half + 1):
                out.append((self.x + fx * d + sx * k,
                            self.y + fy * d + sy * k))
        return out

    def emit(self, field: LightField) -> None:
        if self.power <= 0:
            return
        for cx, cy in self.cells():
            self.light(field, cx, cy)


class Flash(Source):
    """The whole room, lit for a moment, at the start of a level.

    You cannot play a room you have never seen the shape of. The flash gives
    the player the **layout** once, briefly, and then takes it away -- and
    because it tops cells up to the ordinary full memory, the room does not
    snap back to black but fades over the next few seconds. What the player
    keeps is what they managed to hold in their head, which is the whole
    premise of the game rather than a convenience bolted onto it.

    **It shows the building, not who is in it.** Same rule as the room lights:
    a flash that handed you every worker at the start would answer the question
    the level exists to ask. See the design notes on the mains surge, which is
    the moment that *does* show you everything, and is a different thing.
    """

    def __init__(self, frames: int = 12, level: int = LIT,
                 memory: int = CHARGE_LIT) -> None:
        super().__init__(level, memory, enabled=False, reveals=False)
        self.frames = frames
        self.left = 0
        #: Debug: held on indefinitely rather than counting down.
        self.held = False

    def fire(self, surge: bool = False) -> None:
        """Start a flash. Firing again while one is running restarts it.

        A plain flash is the level opening: the **room**, and not who is in it.

        A `surge` is the mains coming back for a moment, and it shows
        everything -- people included. That is the design's own distinction and
        it is the difference between being told the shape of the building and
        being told where everybody is. One is a floor plan you are given; the
        other is the memorisation beat the whole game is built around, and it
        should be rare and startling rather than a key you lean on.
        """
        self.left = self.frames
        self.enabled = True
        self.reveals = surge

    def hold(self, on: bool) -> None:
        """Hold the surge on, or let it go. **A debug view, not a mechanic.**

        A real surge is a quarter of a second, which is the point of it and also
        why it is no use for watching anything: by the time you have registered
        what is on screen it has gone. Held on, the room stays lit and everything
        in it stays drawn, so the Clegs can be watched deciding where to go.

        It changes nothing about their behaviour. A flash lures nobody -- a light
        that is everywhere offers nothing to steer toward -- so the swarm does
        exactly what it would have done in the dark, in full view.
        """
        self.held = on
        self.enabled = on
        self.reveals = on
        if not on:
            self.left = 0

    def update(self) -> None:
        """Burn down. Call once a frame, before applying."""
        if self.held:
            return
        if self.left > 0:
            self.left -= 1
            if self.left == 0:
                self.enabled = False

    def origin(self) -> tuple[int, int]:
        return COLS // 2, PLAY_ROWS // 2

    def lure(self) -> tuple[int, int, int] | None:
        """Nothing. A light that is everywhere has no *toward*.

        Clegs steer up a gradient, and a uniform flash has none -- so it draws
        the swarm nowhere rather than drawing it to an arbitrary middle.
        """
        return None

    def emit(self, field: LightField) -> None:
        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                self.light(field, cx, cy)


def xorshift16(state: int) -> int:
    """A 16-bit xorshift PRNG.

    Deliberately not `random`: this has to run on a Z80, where the equivalent is
    a handful of shifts and XORs. State must never be zero.
    """
    state ^= (state << 7) & 0xFFFF
    state ^= state >> 9
    state ^= (state << 8) & 0xFFFF
    return state & 0xFFFF or 1


#: sin(a) * 256 for a quarter turn in sixteen steps, and the whole of the
#: trigonometry in this game. A Z80 keeps a table like this in ROM and looks it
#: up; there is no other way to get an angle on a machine with no multiply worth
#: the name, and no reason to want one.
_SIN = (0, 25, 50, 74, 98, 121, 142, 162, 181, 198, 213, 226, 237, 245, 251,
        255, 256)

#: Steps in a full turn. Four quarters of sixteen.
TURN = 64


def sin256(step: int) -> int:
    """sin of `step`/64 of a turn, scaled by 256. Integer, by table."""
    step %= TURN
    quarter, i = divmod(step, TURN // 4)
    if quarter == 0:
        return _SIN[i]
    if quarter == 1:
        return _SIN[16 - i]
    if quarter == 2:
        return -_SIN[i]
    return -_SIN[16 - i]


def cos256(step: int) -> int:
    """cos, which is sin a quarter turn ahead."""
    return sin256(step + TURN // 4)


def arc_waypoints(radius: int, pivot: tuple[int, int], reach: int,
                  start: int, end: int, step: int = 2
                  ) -> list[tuple[int, int]]:
    """Points along an arc swung about `pivot` at distance `reach`.

    A real searchlight is bolted to something and turns. The spot it throws does
    not run in straight lines across a room -- it swings, and it moves faster
    the further out it reaches. Sweeping in arcs rather than rows is the single
    change that stops the beam reading as a machine going back and forth.

    Angles are in sixty-fourths of a turn, so `start` and `end` are integers and
    the whole thing is table lookups and a shift.

    Points outside the room are **dropped, not squashed onto the edge**. Clamping
    them was the first version and it was badly wrong: an arc whose far half lies
    outside the room becomes a row of identical boundary cells, so the beam walks
    the wall instead of sweeping. Measured at 62% of a whole circuit spent exactly
    on the outer ring, which is what a player described as the light tracking the
    walls. Dropping them leaves only the part of the arc that is really in the
    room, and the beam crosses to the next piece as it would anyway.
    """
    out = []
    direction = 1 if end >= start else -1
    for a in range(start, end + direction, direction * max(1, step)):
        cx = pivot[0] + (reach * cos256(a) >> 8)
        cy = pivot[1] + (reach * sin256(a) >> 8)
        if 0 <= cx < COLS and 0 <= cy < PLAY_ROWS:
            out.append((cx, cy))
    return out


#: Corner to opposite corner. Sweeping further than this is sweeping outside
#: the room, and the circuit is long enough already.
_DIAGONAL = isqrt((COLS - 1) ** 2 + (PLAY_ROWS - 1) ** 2)

#: Frames the beam holds at a station it stops at, and how much that varies.
#:
#: **It does not stop at every station.** It did, and 48 pauses in a circuit is
#: not a light being aimed, it is a stutter -- a stop about once a second, and a
#: fifth of the circuit spent motionless. One station in `DWELL_EVERY` now, held
#: for longer, which reads as an operator pausing to look at something rather
#: than as the mechanism catching.
DWELL, DWELL_SPREAD, DWELL_EVERY = 20, 30, 6

#: The searchlight's stations: a grid, inset from the walls, spaced closely
#: enough that a beam sitting on one lights out past its neighbours.
#:
#: Eight by six rather than eight by five, and that is arithmetic. The worst-lit
#: point of a grid is the middle of a station rectangle, at half the diagonal
#: from the four around it -- so the spacings must satisfy `sx^2 + sy^2 <= 4r^2`.
#: Five rows across a 22-cell room leaves gaps of four and a quarter and misses
#: the corners; six leaves gaps of three and four, which is 8 against a radius
#: of 3 squared, and covers.
STATION_COLS, STATION_ROWS = 8, 6
STATION_INSET = 2

#: A closed knight's tour of that grid: forty-eight stations, every step a
#: knight move, and the last joins back to the first.
#:
#: This answers a complaint that would not go away -- the beam kept reading as
#: travelling one way, and it was true and it was structural. **Any serpentine
#: is a set of parallel passes**, so most of its motion is along one axis by
#: construction; turning the passes on end only trades one axis for the other,
#: which is what the previous attempt did.
#:
#: A knight's tour has no parallel passes at all. Every move is two one way and
#: one the other, no two consecutive moves are alike, and none of them runs along
#: a wall. It reads as something being *aimed* rather than driven.
#:
#: **Closed is what makes it usable.** Because the last station joins back to the
#: first, the tour can be entered anywhere and still visits all forty-eight -- so
#: the start is free to be random with no argument about coverage. Reversing it
#: and mirroring it in either axis give the rest of the variety, and all of them
#: are still the same tour, still complete.
#:
#: Found once by Warnsdorff's rule with randomised restarts and kept as a table,
#: which is what a Z80 would do: forty-eight bytes of ROM and no search at all at
#: runtime.
KNIGHT_TOUR = (
    (1, 1), (3, 0), (5, 1), (7, 0), (6, 2), (7, 4), (5, 5), (6, 3),
    (7, 5), (5, 4), (7, 3), (6, 5), (4, 4), (2, 5), (0, 4), (1, 2),
    (0, 0), (2, 1), (4, 0), (6, 1), (4, 2), (5, 0), (7, 1), (5, 2),
    (6, 0), (7, 2), (6, 4), (4, 5), (3, 3), (1, 4), (0, 2), (1, 0),
    (3, 1), (2, 3), (3, 5), (4, 3), (2, 4), (0, 5), (1, 3), (3, 2),
    (2, 0), (0, 1), (2, 2), (4, 1), (5, 3), (3, 4), (1, 5), (0, 3),
)

_SPAN_X = COLS - 1 - 2 * STATION_INSET
_SPAN_Y = PLAY_ROWS - 1 - 2 * STATION_INSET


def station(col: int, row: int) -> tuple[int, int]:
    """Where a grid station sits, in cells. Integer rounding, no divides at
    runtime -- on the Z80 these are two more small tables."""
    return (STATION_INSET
            + (col * _SPAN_X + (STATION_COLS - 1) // 2) // (STATION_COLS - 1),
            STATION_INSET
            + (row * _SPAN_Y + (STATION_ROWS - 1) // 2) // (STATION_ROWS - 1))


def tour_route(radius: int, seed: int = 0xACE1, start: int = 0,
               reverse: bool = False, flip_x: bool = False,
               flip_y: bool = False
               ) -> tuple[list[tuple[int, int]], list[int]]:
    """The beam's route for one circuit: a knight's tour of the stations.

    Returns the waypoints and how long to hold at each.

    The tour visits every station once, so the room is covered by the discs the
    beam throws at them and by the tracks between. `start` enters it anywhere --
    which is only safe because the tour is closed -- and the flips and the
    reversal turn one table into hundreds of distinct circuits without any of
    them being a different route in the sense that matters.

    Nothing here runs along a wall, and nothing here is parallel to anything
    else, which is the whole point.
    """
    order = list(KNIGHT_TOUR)
    if reverse:
        order.reverse()
    start %= len(order)
    order = order[start:] + order[:start]

    points: list[tuple[int, int]] = []
    dwells: list[int] = []
    state = seed or 1
    for i, (col, row) in enumerate(order):
        if flip_x:
            col = STATION_COLS - 1 - col
        if flip_y:
            row = STATION_ROWS - 1 - row
        state = xorshift16(state)
        points.append(station(col, row))
        pause = state % DWELL_EVERY == 0
        dwells.append(DWELL + state % DWELL_SPREAD if pause else 0)
    points.append(points[0])       # close the loop
    dwells.append(0)
    return points, dwells


def sweep_waypoints(radius: int, offset: int = 0, from_left: bool = True,
                    top_down: bool = True, inset: int = 0
                    ) -> list[tuple[int, int]]:
    """A serpentine route that covers every cell of the room.

    The beam runs the width of the room, steps down by its own diameter, and
    comes back the other way -- so one full circuit lights everything, with the
    rows spaced so consecutive passes just overlap.

    `offset`, `from_left` and `top_down` shift the pattern without breaking that
    guarantee, which is what makes a varying sweep possible.

    `inset` keeps the beam's centre that many cells in from the walls. With it
    at the radius, the whole disc stays on the room instead of turning half
    off-screen at each end of a pass. The columns beyond the turn are then
    reached only from the passes above and below, so an inset route spaces its
    rows one closer than the beam's diameter to keep them covered. What it still
    misses is the outer ring of cells, which in a room is wall (issue #12).

    The route is **closed** -- it ends where it began. A serpentine that simply
    stops at the far corner would make the first circuit shorter than every one
    after it, since the beam has to travel back before it can start again. The
    return leg is part of the cycle, so it belongs in the route.
    """
    top, bottom = inset, PLAY_ROWS - 1 - inset
    rows: list[int] = []
    y = top + min(offset, radius)
    while True:
        row = min(y, bottom)
        rows.append(row)
        # Done when the beam reaches the room's edge -- not the centre's
        # limit, which with an inset is a radius short of it.
        if row + radius >= PLAY_ROWS - 1 or row == bottom:
            break
        y += 2 * radius - (1 if inset else 0)
    if not top_down:
        rows.reverse()

    left, right = inset, COLS - 1 - inset
    points: list[tuple[int, int]] = []
    going_right = from_left
    for row in rows:
        a, b = (left, right) if going_right else (right, left)
        points.append((a, row))
        points.append((b, row))
        going_right = not going_right
    points.append(points[0])          # close the loop
    return points


class Roaming(Source):
    """A pool of light that moves with no player input.

    The main behaviour is a **sweep**: a prison searchlight quartering the room,
    running the width of it, stepping down, and coming back -- so one circuit
    covers everywhere.

    What happens at the end of a circuit is the difficulty dial:

    It reads as bright as the carried spotlight while it is on you, and leaves
    only a short memory behind it -- the ground the beam has passed goes out in
    well under a second, so the beam reads as a moving pool rather than as a bar
    being painted across the room (issue #12).

    * **repeat** -- the same route every time. Learnable. Time your crossing.
    * **vary** -- a different route each circuit: another corner, another
      direction, the rows offset. Still total coverage, but you cannot plan
      around it.

    `PATH` follows waypoints the level author drew, and `DRIFT` wanders at
    random, both kept for the editor to offer.
    """

    DRIFT, PATH, SWEEP, ARC = 0, 1, 2, 3

    def __init__(self, x: int, y: int, radius: int = 3,
                 path: list[tuple[int, int]] | None = None,
                 seed: int = 0xACE1, level: int = LIT,
                 memory: int = CHARGE_SWEEP,
                 hue: int = YELLOW, step_every: int = 6,
                 mode: int | None = None, vary: bool = False,
                 inset: int = 0) -> None:
        # Frames per cell. Six is a beam that crosses the room in about four
        # seconds -- slow enough to watch, time, and cross behind. Three was
        # tried and played too fast to do anything about.
        super().__init__(level, memory, hue=hue)
        self.x, self.y = x, y
        self.radius = radius
        self.inset = inset
        self.path = path or []
        self._seed = seed or 1
        self._leg = 0
        self._tick = 0
        self.step_every = step_every
        self.vary = vary
        self.cycles = 0
        self.mount = 0
        #: How long to hold at each waypoint, or None for a route with no
        #: pauses. An operator stops at the end of a swing; a machine does not.
        self._dwells = None
        self._hold = 0
        #: Where the current leg began, so the beam can walk a straight line
        #: to its target rather than a dog-leg.
        self._from = (x, y)

        if mode is None:
            mode = self.PATH if self.path else self.ARC
        self.mode = mode
        if self.mode in (self.SWEEP, self.ARC):
            self._new_sweep(first=True)

    # --- sweeps ------------------------------------------------------------

    def _snap_to_route_start(self) -> None:
        """Begin a sweep at its own first waypoint.

        A sweeping light owns its position -- the x and y passed to the
        constructor are ignored in SWEEP mode, because the route decides where
        the beam is.

        Otherwise the first circuit is a different length from every later one --
        the beam has to travel from wherever it was placed to where the route
        begins -- and "the same route every time" is not true of the first pass.
        """
        if self._sweep:
            self.x, self.y = self._sweep[0]
            self._from = (self.x, self.y)

    def _lay_out(self, seed: int | None = None):
        """One circuit's route, in whichever shape this light sweeps."""
        if self.mode == self.ARC:
            if seed is None:
                route, self._dwells = tour_route(self.radius)
                return route
            # A closed tour can be entered anywhere, so the start is free to be
            # random; the flips and the reversal are the rest of the variety.
            self.mount = seed & 0b11
            route, self._dwells = tour_route(
                self.radius, seed=seed, start=(seed >> 2) % len(KNIGHT_TOUR),
                reverse=bool(seed & 1), flip_x=bool(seed & 2),
                flip_y=bool(seed & 4))
            return route
        self._dwells = None
        if seed is None:
            return sweep_waypoints(self.radius, inset=self.inset)
        return sweep_waypoints(
            self.radius,
            offset=seed % (self.radius + 1),
            from_left=bool(seed & 0b100),
            top_down=bool(seed & 0b1000),
            inset=self.inset,
        )

    def _new_sweep(self, first: bool = False) -> None:
        """Lay out the next circuit. Identical unless `vary` is set."""
        if first or not self.vary:
            if first:
                self._sweep = self._lay_out()
            # repeat mode simply re-runs the route it already has
        else:
            self._seed = xorshift16(self._seed)
            self._sweep = self._lay_out(self._seed)
        self._leg = 0
        if first:
            self._snap_to_route_start()

    def reshape(self, radius: int | None = None,
                inset: int | None = None) -> None:
        """Change the beam's size or how close it runs to the walls.

        A sweep is laid out for a particular radius, so the route is rebuilt and
        restarted from its first waypoint. Tuning knobs, for judging by eye.
        """
        if radius is not None:
            self.radius = radius
        if inset is not None:
            self.inset = inset
        if self.mode in (self.SWEEP, self.ARC):
            self._new_sweep(first=True)

    def set_mode(self, mode: int) -> None:
        if mode == self.PATH and not self.path:
            mode = self.DRIFT
        self.mode = mode
        if mode in (self.SWEEP, self.ARC):
            self._new_sweep(first=True)

    # --- movement ----------------------------------------------------------

    def update(self) -> None:
        """Move. Called every frame; actually steps every `step_every`.

        **A diagonal step waits half again as long**, because it covers half
        again as much ground. Giving every step the same interval makes the beam
        speed up by 41% whenever it moves diagonally and slow down whenever it
        does not, which on a knight's move -- where the two alternate constantly
        -- is a visible stutter rather than a smooth sweep.
        """
        if self._hold > 0:
            self._hold -= 1
            return
        self._tick += 1
        due = self.step_every
        if self._next_is_slanted():
            due += due // 2
        if self._tick < due:
            return
        self._tick = 0
        if self.mode in (self.SWEEP, self.ARC):
            self._follow(self._sweep, on_wrap=self._finish_circuit)
        elif self.mode == self.PATH and self.path:
            self._follow(self.path)
        else:
            self._drift()

    def _finish_circuit(self) -> None:
        self.cycles += 1
        self._new_sweep()

    def _next_is_slanted(self) -> bool:
        """Would the step about to be taken be a diagonal one?

        Asked *before* waiting rather than after stepping, which matters: the
        interval has to belong to the step it pays for. Keying it to the step
        just taken gets the timing exactly one step out of phase, and on a route
        where diagonal and orthogonal steps alternate that is no better than not
        compensating at all.
        """
        route = (self._sweep if self.mode in (self.SWEEP, self.ARC)
                 else self.path if self.mode == self.PATH else None)
        if not route:
            return False
        dx, dy = self._delta_towards(*route[self._leg])
        return bool(dx and dy)

    def _follow(self, route, on_wrap=None) -> None:
        self._step_towards(*route[self._leg])
        if (self.x, self.y) == route[self._leg]:
            if self._dwells is not None and self._leg < len(self._dwells):
                self._hold = self._dwells[self._leg]
            self._leg += 1
            self._from = (self.x, self.y)
            if self._leg >= len(route):
                self._leg = 0
                if on_wrap:
                    on_wrap()

    def _delta_towards(self, tx: int, ty: int) -> tuple[int, int]:
        """One cell along the straight line from where this leg began.

        Not "diagonally until one axis lines up, then straight", which is what
        this was and which bunches every leg's odd steps into a run at the end.
        On a knight's move of eight cells across and three down that run is five
        cells of pure sideways travel -- a third of the journey, and visible as
        exactly the horizontal drift a player complained of.

        Walking the real line spreads those steps evenly instead. It is the
        error-accumulation trick every line routine uses, kept stateless by
        measuring progress from where the leg started rather than carrying an
        error term.
        """
        fx, fy = self._from
        dx, dy = tx - fx, ty - fy
        sx = (tx > self.x) - (tx < self.x)
        sy = (ty > self.y) - (ty < self.y)
        if abs(dx) >= abs(dy):
            if not sx:
                return 0, sy
            nx = self.x + sx
            # Where the minor axis should be, now the major has moved.
            want = fy + (nx - fx) * dy // (dx or 1)
            return sx, (want > self.y) - (want < self.y)
        if not sy:
            return sx, 0
        ny = self.y + sy
        want = fx + (ny - fy) * dx // (dy or 1)
        return (want > self.x) - (want < self.x), sy

    def _step_towards(self, tx: int, ty: int) -> None:
        dx, dy = self._delta_towards(tx, ty)
        self.x += dx
        self.y += dy

    def _drift(self) -> None:
        self._seed = xorshift16(self._seed)
        dx = (self._seed & 0b11) - 1          # -1, 0, 1 or 2 -> clamped below
        dy = ((self._seed >> 2) & 0b11) - 1
        self.x = max(0, min(COLS - 1, self.x + max(-1, min(1, dx))))
        self.y = max(0, min(PLAY_ROWS - 1, self.y + max(-1, min(1, dy))))

    def origin(self) -> tuple[int, int]:
        return self.x, self.y

    def emit(self, field: LightField) -> None:
        r2 = self.radius * self.radius
        for dy in range(-self.radius, self.radius + 1):
            for dx in range(-self.radius, self.radius + 1):
                # Squared distance keeps this integer -- no square roots.
                if dx * dx + dy * dy <= r2:
                    self.light(field, self.x + dx, self.y + dy)
