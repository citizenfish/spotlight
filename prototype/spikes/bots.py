"""The four reference bots, so a run can be driven without hands.

Named in the phase-0 review, which states every phase-2 difficulty target
against them. They exist so the tester can measure the same thing twice, on
different seeds, and get numbers that mean something:

    Statue     never moves. The worst case, and the cheapest control.
    Wanderer   random walk, spotlight held on. A first-timer's opening minute.
    Listener   walks to the last HELP it heard, delivers in batches of three.
               A first-timer who has worked the game out.
    Oracle     knows where everybody is. The ceiling: what the room is worth to
               perfect play.

**A bot's numbers are a ceiling and a floor, not a middle.** They path
perfectly and they never panic, and where a bot and a person disagree the
person is right. That has been true every time so far. Nothing here is a model
of a player; they are instruments for holding one variable still while another
is changed.

Two things worth saying about the code:

* **Bots may path. The game may not.** The BFS below is harness, not mechanics.
  Clegs must never gain a route-finder -- a Z80 has nothing to spend on one and
  the whole design of the swarm is that it steers for light and cannot think.
  This code is deleted the day the harness is.
* **They press keys.** A bot returns an `Intent`, which is the same thing the
  keyboard produces, and the session cannot tell the difference. Nothing here
  reaches into the run to move anybody. The Oracle is allowed to *know* more
  than a player can, because that is what makes it a ceiling, but it still has
  to walk there.

Everything is integer and every random choice comes from the same xorshift the
Z80 would use, so a seed names a run.
"""

from spotlight.core.constants import CELL, COLS

from . import rescue as rescue_mod, scene, sources
from .layout import PLAY_ROWS
from .player import HEIGHT
from .session import Intent

#: How long a bot tolerates not moving before it tears up its route.
#: Walking into a wall you are clipping with your head can stop a figure dead
#: (the phase-0 review found it); a bot that cannot notice would stand there
#: for the rest of the run and report the room as impossible.
STUCK_FRAMES = 25


def standable(cx: int, cy: int) -> bool:
    """Can a person stand with their feet in this cell?

    A person is 8x16, so they occupy this cell **and the one above it**, and a
    route that ignores the head walks the bot into a lintel. `cy` is the feet
    row, matching `Player.cy`.
    """
    if not (0 <= cx < COLS and 1 <= cy < PLAY_ROWS):
        return False
    return not scene.is_solid(cx, cy) and not scene.is_solid(cx, cy - 1)


def stand_cells(cx: int, cy: int) -> list[tuple[int, int]]:
    """Where to stand so that the sprite overlaps the cell (cx, cy).

    The exit is a door in the top wall and the workers are 8x16 like the
    player, so "go to that cell" nearly always means "go to the cell below it".
    Both are offered and the router takes whichever is nearer.
    """
    return [c for c in ((cx, cy), (cx, cy + 1)) if standable(*c)]


def route(start: tuple[int, int], goals) -> list[tuple[int, int]]:
    """Breadth-first from `start` to the nearest goal. Cells, not pixels.

    Plain BFS on the cell grid, four-connected. The room is 32x22, so this is
    seven hundred cells and costs nothing; it is recomputed only when the goal
    changes or the bot gets stuck.
    """
    targets = set(goals)
    if not targets or start in targets:
        return []
    seen = {start: None}
    queue = [start]
    while queue:
        nxt = []
        for cell in queue:
            cx, cy = cell
            for step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (cx + step[0], cy + step[1])
                if nb in seen or not standable(*nb):
                    continue
                seen[nb] = cell
                if nb in targets:
                    path = [nb]
                    while seen[path[-1]] is not None:
                        path.append(seen[path[-1]])
                    path.reverse()
                    return path[1:]
                nxt.append(nb)
        queue = nxt
    return []


def stand_pixel(cx: int, cy: int) -> tuple[int, int]:
    """The pixel position that puts a player's feet in the cell (cx, cy)."""
    return cx * CELL, cy * CELL - (HEIGHT - CELL)


def worker_cell(worker) -> tuple[int, int]:
    """The cell a worker's feet are in, which is where you go to touch them."""
    return worker.x // CELL, (worker.y + rescue_mod.HEIGHT - 1) // CELL


class Bot:
    """A player's hands. Given a run, return what to press this frame."""

    name = "bot"

    def __init__(self, seed: int = 1) -> None:
        self._seed = seed or 1

    def _random(self) -> int:
        self._seed = sources.xorshift16(self._seed)
        return self._seed

    def intent(self, run) -> Intent:
        return Intent()


class Statue(Bot):
    """Never moves, never lights. The control, and the worst case.

    Used in pairs: the same statue with the torch held on and with it held off
    is the whole of difficulty target T3, which is whether light costs anything.
    """

    name = "statue"

    def __init__(self, seed: int = 1, light: bool = False) -> None:
        super().__init__(seed)
        self.light = light

    def intent(self, run) -> Intent:
        # Pressed once, on the first frame it is needed. Holding a key does not
        # toggle a torch twice.
        return Intent(torch=self.light and not run.cone.enabled)


class Wanderer(Bot):
    """Random walk with the spotlight held on: a first-timer's opening minute.

    Not a model of a beginner -- a beginner has intentions -- but it is the only
    honest floor available: it is what the room does to somebody who has not
    worked anything out yet.
    """

    name = "wanderer"

    #: Frames before it picks a new direction. Long enough to cross a room, so
    #: it explores rather than jittering on the spot.
    TURN_EVERY = 40

    def __init__(self, seed: int = 1, light: bool = True) -> None:
        super().__init__(seed)
        self.light = light
        self._dx = self._dy = 0
        self._left = 0

    def intent(self, run) -> Intent:
        if self._left <= 0:
            r = self._random()
            self._dx = (r & 0b11) - 1
            self._dy = ((r >> 2) & 0b11) - 1
            self._dx = max(-1, min(1, self._dx))
            self._dy = max(-1, min(1, self._dy))
            self._left = self.TURN_EVERY
        self._left -= 1
        return Intent(dx=self._dx, dy=self._dy,
                      torch=self.light and not run.cone.enabled)


class Walker(Bot):
    """Shared machinery for the two bots that go somewhere on purpose."""

    def __init__(self, seed: int = 1, light: bool = False) -> None:
        super().__init__(seed)
        self.light = light
        self._path: list[tuple[int, int]] = []
        self._goals: tuple = ()
        self._stuck = 0
        self._was = (0, 0)

    def _walk(self, run, goals) -> Intent:
        """Head for the nearest of `goals`, as cells. Returns keys, not moves."""
        goals = tuple(sorted(goals))
        here = (run.player.cx, run.player.cy)
        if goals != self._goals:
            self._goals, self._path = goals, route(here, goals)
        if not goals:
            return Intent()

        at = (run.player.x, run.player.y)
        self._stuck = self._stuck + 1 if at == self._was else 0
        self._was = at
        if self._stuck > STUCK_FRAMES:
            # Wedged. Re-route from where we actually are, and if that is the
            # same answer, take a random step to shake loose.
            self._path = route(here, goals)
            self._stuck = 0
            if not self._path:
                r = self._random()
                return Intent(dx=(r & 1) * 2 - 1, dy=((r >> 1) & 1) * 2 - 1)

        while self._path and self._path[0] == here:
            self._path.pop(0)
        if not self._path:
            self._path = route(here, goals)
        if not self._path:
            return Intent(torch=self.light and not run.cone.enabled)

        tx, ty = stand_pixel(*self._path[0])
        dx = (tx > run.player.x) - (tx < run.player.x)
        dy = (ty > run.player.y) - (ty < run.player.y)
        return Intent(dx=dx, dy=dy, torch=self.light and not run.cone.enabled)

    def _exit_cells(self) -> list[tuple[int, int]]:
        return stand_cells(*scene.exit_cell())


class Listener(Walker):
    """Walks to the last shout it heard, and leaves in batches of three.

    A shout is the one piece of information the room gives away for free, and
    the design claims it is a bearing rather than a map. This bot is that claim
    made measurable: it never switches a light on, and the phase-0 review found
    it cleared the room every time -- which is the finding that says the room is
    currently too easy.

    It hears what a player hears. It does not know where anybody is until they
    shout, and it forgets nothing, which is the one place it is kinder to itself
    than a person would be.
    """

    name = "listener"

    #: How many it gathers before walking them out. The design's central choice
    #: -- one at a time is safe and slow, everybody at once is the gamble -- and
    #: three is the middle of it.
    BATCH = 3

    def __init__(self, seed: int = 1, light: bool = False,
                 batch: int = BATCH) -> None:
        super().__init__(seed, light)
        self.batch = batch
        self._heard: tuple[int, int] | None = None
        self._target = None

    def intent(self, run) -> Intent:
        for worker in run.shouting:
            self._heard = worker_cell(worker)
            self._target = worker

        if len(run.rescue.tail) >= self.batch:
            return self._walk(run, self._exit_cells())

        if self._target is not None and self._target.state != rescue_mod.WAITING:
            self._target, self._heard = None, None
        if self._heard is None:
            # Nobody has called yet, or the last caller is accounted for. Stand
            # still rather than wander: this bot's whole point is that it acts
            # only on what the room told it.
            if run.rescue.tail:
                return self._walk(run, self._exit_cells())
            return Intent(torch=self.light and not run.cone.enabled)
        return self._walk(run, stand_cells(*self._heard))


class Oracle(Walker):
    """Knows where everybody is. The ceiling, and nothing like a player.

    Greedy: it walks to whoever is nearest by route, collects everybody, and
    then leaves once. That is the best play in the room as it currently stands
    and it is exactly what the design does not want to be optimal -- see the
    phase-0 review, where the Oracle clears the room in twenty-one seconds
    against a worker's two and a half minutes.

    Greedy-nearest is not provably optimal; a real ceiling would need an
    ordering search. It is the ceiling we can afford, and it is stated here so
    nobody later mistakes it for a proof.
    """

    name = "oracle"

    def intent(self, run) -> Intent:
        waiting = run.rescue.alive_waiting()
        if waiting:
            goals = [c for w in waiting for c in stand_cells(*worker_cell(w))]
            return self._walk(run, goals)
        return self._walk(run, self._exit_cells())


#: What each letter means in a script. Directions are held; the two buttons are
#: pressed once, which is what the keyboard does.
SCRIPT_CODES = {
    "R": (1, 0), "L": (-1, 0), "D": (0, 1), "U": (0, -1), ".": (0, 0),
}


def parse_script(text: str) -> list[Intent]:
    """Turn "100R 40D T 200." into one `Intent` per frame.

    A scripted run is how you pin a bug to a frame. A bot is reproducible but
    it reacts, so it will not do the same thing once the constants move -- and
    when the tuning loop in phase 2 moves a constant, the run that showed the
    problem has to be replayable exactly.

    Counts are frames, default one. `T` is the torch, `S` the spray; both are
    pressed on a single frame because that is what a key does.
    """
    frames: list[Intent] = []
    for token in text.replace(",", " ").split():
        count, code = "", token
        while code and code[0].isdigit():
            count, code = count + code[0], code[1:]
        repeat = int(count) if count else 1
        code = code.upper()
        if code in SCRIPT_CODES:
            dx, dy = SCRIPT_CODES[code]
            frames += [Intent(dx=dx, dy=dy) for _ in range(repeat)]
        elif code == "T":
            frames += [Intent(torch=True)] + [Intent()] * (repeat - 1)
        elif code == "S":
            frames += [Intent(spray=True)] + [Intent()] * (repeat - 1)
        else:
            raise ValueError(f"not a script code: {token!r}")
    return frames


class Script(Bot):
    """Replays a fixed list of key presses and then stands still.

    The most honest instrument of the lot: it has no opinions, so anything it
    shows is the game's doing.
    """

    name = "script"

    def __init__(self, frames: list[Intent], seed: int = 1) -> None:
        super().__init__(seed)
        self.frames = list(frames)
        self.at = 0

    def intent(self, run) -> Intent:
        if self.at >= len(self.frames):
            return Intent()
        self.at += 1
        return self.frames[self.at - 1]


#: Every bot the driver can be asked for, by the names the review uses.
BOTS = {
    "statue": Statue,
    "wanderer": Wanderer,
    "listener": Listener,
    "oracle": Oracle,
}


def make(name: str, seed: int = 1, light: bool | None = None) -> Bot:
    """Build a bot by name. `light` overrides whether it uses the torch.

    Two of the difficulty targets are the same bot run twice with the torch on
    and off, so that has to be a parameter rather than a different bot.
    """
    if name not in BOTS:
        raise KeyError(f"no such bot: {name}; have {sorted(BOTS)}")
    kind = BOTS[name]
    if light is None:
        return kind(seed=seed)
    return kind(seed=seed, light=light)
