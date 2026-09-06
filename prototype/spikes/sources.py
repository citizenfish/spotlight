"""The four light sources.

Every one of them resolves at 8x8 cell granularity and feeds the same
brightest-wins field in `lighting`. None of them writes an attribute directly --
light decides colour, and it does so in one place.

    1. Glow     one cell in every direction, always on, dim
    2. Room     an authored zone, fixed, always on
    3. Cone     a wedge in the facing direction, toggleable, with power
    4. Roaming  a pool that moves on its own -- drifting or on a path
"""

from spotlight.core.constants import COLS

from .layout import PLAY_ROWS
from .lighting import DIM, LIT, LightField

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

    def __init__(self, level: int = LIT, enabled: bool = True) -> None:
        self.level = level
        self.enabled = enabled

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

    def __init__(self, level: int = DIM) -> None:
        super().__init__(level)
        self.x = 0
        self.y = 0

    def emit(self, field: LightField) -> None:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                field.add(self.x + dx, self.y + dy, self.level)


class RoomLight(Source):
    """Emergency lighting: an authored zone, fixed, always on.

    The level author's sharpest tool -- what a room shows you for free, and what
    it keeps dark, is most of what makes one room different from another.
    """

    def __init__(self, left: int, top: int, width: int, height: int,
                 level: int = LIT) -> None:
        super().__init__(level)
        self.left, self.top = left, top
        self.width, self.height = width, height

    def emit(self, field: LightField) -> None:
        for cy in range(self.top, self.top + self.height):
            for cx in range(self.left, self.left + self.width):
                field.add(cx, cy, self.level)


class Cone(Source):
    """The carried spotlight: a wedge ahead of the player's facing.

    A cone rather than a radius so that facing is a real decision -- you cannot
    light the way forward and watch what is behind you at the same time.

    Widens by one cell every two of reach, which is roughly 45 degrees.
    """

    def __init__(self, reach: int = 7, power: int = 600,
                 level: int = LIT) -> None:
        super().__init__(level, enabled=False)
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
            field.add(cx, cy, self.level)


def xorshift16(state: int) -> int:
    """A 16-bit xorshift PRNG.

    Deliberately not `random`: this has to run on a Z80, where the equivalent is
    a handful of shifts and XORs. State must never be zero.
    """
    state ^= (state << 7) & 0xFFFF
    state ^= state >> 9
    state ^= (state << 8) & 0xFFFF
    return state & 0xFFFF or 1


class Roaming(Source):
    """A pool of light that moves with no player input.

    Two behaviours, and a level can hold both: a drifter wandering at random,
    and a sweep following an authored path. The drifter is weather; the sweep is
    a puzzle you can learn.
    """

    DRIFT, PATH = 0, 1

    def __init__(self, x: int, y: int, radius: int = 3,
                 path: list[tuple[int, int]] | None = None,
                 seed: int = 0xACE1, level: int = LIT,
                 step_every: int = 8) -> None:
        super().__init__(level)
        self.x, self.y = x, y
        self.radius = radius
        self.path = path or []
        self.mode = self.PATH if self.path else self.DRIFT
        self._seed = seed or 1
        self._leg = 0
        self._tick = 0
        self.step_every = step_every

    def set_mode(self, mode: int) -> None:
        """Switch between drifting and following the path."""
        self.mode = self.PATH if (mode == self.PATH and self.path) else self.DRIFT

    def update(self) -> None:
        """Move. Called every frame; actually steps every `step_every`."""
        self._tick += 1
        if self._tick < self.step_every:
            return
        self._tick = 0
        if self.mode == self.PATH and self.path:
            self._step_towards(*self.path[self._leg])
            if (self.x, self.y) == self.path[self._leg]:
                self._leg = (self._leg + 1) % len(self.path)
        else:
            self._drift()

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
                    field.add(self.x + dx, self.y + dy, self.level)
