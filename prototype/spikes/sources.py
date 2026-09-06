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


class Source:
    """Common switching. Subclasses implement `emit`."""

    def __init__(self, level: int = LIT, memory: int = CHARGE_LIT,
                 enabled: bool = True, hue: int = UNCOLOURED) -> None:
        self.level = level
        self.memory = memory
        self.hue = hue
        self.enabled = enabled

    def light(self, field: LightField, cx: int, cy: int) -> None:
        field.add(cx, cy, self.level, self.memory, self.hue)

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def apply(self, field: LightField) -> None:
        if self.enabled:
            self.emit(field)

    def emit(self, field: LightField) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class Glow(Source):
    """The personal glow: one cell in every direction. Never switched off in
    play -- it is what stops total darkness being unplayable -- but switchable
    here so its contribution can be seen on its own."""

    def __init__(self, level: int = DIM, memory: int = CHARGE_DIM) -> None:
        super().__init__(level, memory)
        self.x = 0
        self.y = 0

    def emit(self, field: LightField) -> None:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                self.light(field, self.x + dx, self.y + dy)


class RoomLight(Source):
    """Emergency lighting: an authored zone, fixed, always on.

    The level author's sharpest tool -- what a room shows you for free, and what
    it keeps dark, is most of what makes one room different from another.
    """

    def __init__(self, left: int, top: int, width: int, height: int,
                 level: int = LIT, memory: int = CHARGE_LIT) -> None:
        super().__init__(level, memory)
        self.left, self.top = left, top
        self.width, self.height = width, height

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

    def cells(self) -> list[tuple[int, int]]:
        fx, fy, sx, sy = _AXES[self.facing]
        out = []
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


def xorshift16(state: int) -> int:
    """A 16-bit xorshift PRNG.

    Deliberately not `random`: this has to run on a Z80, where the equivalent is
    a handful of shifts and XORs. State must never be zero.
    """
    state ^= (state << 7) & 0xFFFF
    state ^= state >> 9
    state ^= (state << 8) & 0xFFFF
    return state & 0xFFFF or 1


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

    DRIFT, PATH, SWEEP = 0, 1, 2

    def __init__(self, x: int, y: int, radius: int = 3,
                 path: list[tuple[int, int]] | None = None,
                 seed: int = 0xACE1, level: int = LIT,
                 memory: int = CHARGE_SWEEP,
                 hue: int = YELLOW, step_every: int = 3,
                 mode: int | None = None, vary: bool = False,
                 inset: int = 0) -> None:
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
        if mode is None:
            mode = self.PATH if self.path else self.SWEEP
        self.mode = mode
        if self.mode == self.SWEEP:
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

    def _new_sweep(self, first: bool = False) -> None:
        """Lay out the next circuit. Identical unless `vary` is set."""
        if first or not self.vary:
            if first:
                self._sweep = sweep_waypoints(self.radius, inset=self.inset)
            # repeat mode simply re-runs the route it already has
        else:
            self._seed = xorshift16(self._seed)
            self._sweep = sweep_waypoints(
                self.radius,
                offset=self._seed % (self.radius + 1),
                from_left=bool(self._seed & 0b100),
                top_down=bool(self._seed & 0b1000),
                inset=self.inset,
            )
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
        if self.mode == self.SWEEP:
            self._new_sweep(first=True)

    def set_mode(self, mode: int) -> None:
        if mode == self.PATH and not self.path:
            mode = self.DRIFT
        self.mode = mode
        if mode == self.SWEEP:
            self._new_sweep(first=True)

    # --- movement ----------------------------------------------------------

    def update(self) -> None:
        """Move. Called every frame; actually steps every `step_every`."""
        self._tick += 1
        if self._tick < self.step_every:
            return
        self._tick = 0
        if self.mode == self.SWEEP:
            self._follow(self._sweep, on_wrap=self._finish_circuit)
        elif self.mode == self.PATH and self.path:
            self._follow(self.path)
        else:
            self._drift()

    def _finish_circuit(self) -> None:
        self.cycles += 1
        self._new_sweep()

    def _follow(self, route, on_wrap=None) -> None:
        self._step_towards(*route[self._leg])
        if (self.x, self.y) == route[self._leg]:
            self._leg += 1
            if self._leg >= len(route):
                self._leg = 0
                if on_wrap:
                    on_wrap()

    def _step_towards(self, tx: int, ty: int) -> None:
        self.x += (tx > self.x) - (tx < self.x)
        self.y += (ty > self.y) - (ty < self.y)

    def _drift(self) -> None:
        self._seed = xorshift16(self._seed)
        dx = (self._seed & 0b11) - 1          # -1, 0, 1 or 2 -> clamped below
        dy = ((self._seed >> 2) & 0b11) - 1
        self.x = max(0, min(COLS - 1, self.x + max(-1, min(1, dx))))
        self.y = max(0, min(PLAY_ROWS - 1, self.y + max(-1, min(1, dy))))

    def emit(self, field: LightField) -> None:
        r2 = self.radius * self.radius
        for dy in range(-self.radius, self.radius + 1):
            for dx in range(-self.radius, self.radius + 1):
                # Squared distance keeps this integer -- no square roots.
                if dx * dx + dy * dy <= r2:
                    self.light(field, self.x + dx, self.y + dy)
