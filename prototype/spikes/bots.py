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

from . import building, rescue as rescue_mod, scene, sources
from .layout import PLAY_ROWS
from .player import HEIGHT
from .session import Intent

#: How long a bot tolerates not moving before it tears up its route.
#: Walking into a wall you are clipping with your head can stop a figure dead
#: (the phase-0 review found it); a bot that cannot notice would stand there
#: for the rest of the run and report the room as impossible.
STUCK_FRAMES = 25


def standable(room: int, cx: int, cy: int) -> bool:
    """Can a person stand with their feet in this cell of this room?

    A person is 8x16, so they occupy this cell **and the one above it**, and a
    route that ignores the head walks the bot into a lintel. `cy` is the feet
    row, matching `Player.cy`.

    The room is not optional: cell (17, 4) exists in every room in the building
    and means somewhere different in each of them. Cells beyond a room's own
    edges are answered by `Room.is_solid`, so the column just past a doorway is
    the room next door's -- but a *route* must not stand there, because that
    cell belongs to the other room's grid and the bot would think it was still
    here. `neighbours` handles the crossing instead.
    """
    if not (0 <= cx < COLS and 1 <= cy < PLAY_ROWS):
        return False
    solid = scene.BUILDING[room].is_solid
    return not solid(cx, cy) and not solid(cx, cy - 1)


def stand_cells(room: int, cx: int, cy: int) -> list[tuple[int, int, int]]:
    """Where to stand so that the sprite overlaps the cell (room, cx, cy).

    The exit is a door in a wall and the workers are 8x16 like the player, so
    "go to that cell" often means "go to the cell below it". Both are offered
    and the router takes whichever is nearer.
    """
    return [(room, x, y) for x, y in ((cx, cy), (cx, cy + 1))
            if standable(room, x, y)]


def neighbours(place):
    """The cells a person can step to from here, doorways included.

    **Bots may path; the game may not.** This is harness. Clegs must never gain
    a route-finder -- a Z80 has nothing to spend on one and the whole design of
    the swarm is that it steers for light and cannot think. What a bot is
    allowed to do is know that a doorway exists, and this is where it does.
    """
    room, cx, cy = place
    out = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = cx + dx, cy + dy
        if standable(room, nx, ny):
            out.append((room, nx, ny))
            continue
        step = scene.BUILDING.step_across(room, nx, ny)
        if step is not None and standable(*step):
            out.append(step)
    return out


def route(start, goals) -> list:
    """Breadth-first from `start` to the nearest goal. Cells, not pixels.

    Plain BFS over `(room, cx, cy)`, four-connected, crossing doorways. A room
    is 32x22, so a two-room building is fourteen hundred cells and costs
    nothing; it is recomputed only when the goal changes or the bot gets stuck.
    """
    targets = set(goals)
    if not targets or start in targets:
        return []
    seen = {start: None}
    queue = [start]
    while queue:
        nxt = []
        for cell in queue:
            for nb in neighbours(cell):
                if nb in seen:
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


def worker_cell(worker) -> tuple[int, int, int]:
    """Where a worker's feet are, which is where you go to touch them."""
    return (worker.room, worker.x // CELL,
            (worker.y + rescue_mod.HEIGHT - 1) // CELL)


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
        here = (run.here, run.player.cx, run.player.cy)
        if goals != self._goals:
            self._goals, self._path = goals, route(here, goals)
        if not goals:
            return Intent()

        at = (run.here, run.player.x, run.player.y)
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
        if self._path and self._path[0][0] != run.here:
            # The next step is in the room next door. **Keep walking at the
            # wall**: the doorway is at the same rows on both sides, so the
            # crossing is more of the same direction plus whatever it takes to
            # line up with the gap, and the room changes underneath you once
            # you have cleared the threshold. There is no "go through the door"
            # action, here or anywhere else.
            door = scene.BUILDING[run.here].doorway_to(self._path[0][0])
            if door is None:
                self._path = route(here, goals)
            else:
                want = self._path[0][2]
                dy = (want > run.player.cy) - (want < run.player.cy)
                return Intent(dx=1 if door.side == building.EAST else -1,
                              dy=dy,
                              torch=self.light and not run.cone.enabled)
        if not self._path:
            self._path = route(here, goals)
        if not self._path or self._path[0][0] != run.here:
            return Intent(torch=self.light and not run.cone.enabled)

        tx, ty = stand_pixel(*self._path[0][1:])
        dx = (tx > run.player.x) - (tx < run.player.x)
        dy = (ty > run.player.y) - (ty < run.player.y)
        return Intent(dx=dx, dy=dy, torch=self.light and not run.cone.enabled)

    def _exit_cells(self) -> list[tuple[int, int, int]]:
        room, cell = scene.BUILDING.exit
        return stand_cells(room, *cell)

    def _leave(self, run) -> Intent:
        """Walk to the door, and then keep walking into it until it lets go.

        Issue #28 made the exit two acts rather than one: touching it hands
        over whoever is behind you, and leaving is `LEAVE_FRAMES` of still
        walking into it. A bot that stopped when it arrived would deliver and
        then stand in the doorway for the rest of the run, so a bot that means
        to leave has to lean on the door like a player does.

        It is still only pressing keys. Nothing here reaches into the run.
        """
        if run.rescue.at_exit(run.here, run.player.occupied_cells()):
            dx, dy = run.exit_facing
            return Intent(dx=dx, dy=dy,
                          torch=self.light and not run.cone.enabled)
        return self._walk(run, self._exit_cells())


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
        self._heard: tuple[int, int, int] | None = None
        self._target = None
        #: A doorway with somebody shouting the other side of it, if the bot
        #: has heard one and has nothing nearer to go to.
        self._doorway: tuple[int, int, int] | None = None

    def intent(self, run) -> Intent:
        for worker in run.shouting:
            self._heard = worker_cell(worker)
            self._target = worker
        # **A call over the doorway is a bearing too**, and it is the only one
        # a room you are not in ever gives you (issue #21). It says the door and
        # not the person, so this is all the bot can act on: go and look. It is
        # what makes this bot the measure of whether the door is findable at
        # all -- take the rule away and it never leaves the near room.
        if not run.shouting and run.door_calls and self._heard is None:
            for door in scene.BUILDING[run.here].doorways:
                if run.rescue.calling(run.frame, door.to):
                    self._doorway = (door.to, door.landing, door.middle)
                    break

        if len(run.rescue.tail) >= self.batch:
            # **Delivering is not leaving any more** (issue #28), so this walks
            # to the door, hands them over on touch, and then goes on pushing
            # until the run ends -- which is what this bot did before the door
            # became two acts, and keeps T1 measuring the same thing. What it
            # is *not* is the multi-trip play the new rule makes possible: that
            # wants the batch gone, and the batch is issue #24's.
            return self._leave(run)

        if self._target is not None and self._target.state != rescue_mod.WAITING:
            self._target, self._heard = None, None
        if self._heard is None:
            # **The doorway comes before the way out**, and the order is the
            # whole of what this bot measures. A call over a doorway is the only
            # bearing a room you are not in ever gives you, so a bot that
            # preferred the exit would walk out of the building the moment it
            # ran out of voices in this room -- and would never test the rule at
            # all. Put the door first and it goes and looks, which is what a
            # first-timer who has understood the game does.
            if self._doorway is not None:
                if self._doorway[0] == run.here:
                    self._doorway = None
                else:
                    return self._walk(run, stand_cells(*self._doorway))
            if run.rescue.tail:
                return self._leave(run)
            # Nobody has called yet, or the last caller is accounted for. Stand
            # still rather than wander: this bot's whole point is that it acts
            # only on what the room told it.
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
        return self._leave(run)


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
