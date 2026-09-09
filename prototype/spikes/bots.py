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

from . import (
    building, lighting, rescue as rescue_mod, scene, sources,
    spray as spray_mod,
)
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


def neighbours(place, passable=standable):
    """The cells a person can step to from here, doorways included.

    **Bots may path; the game may not.** This is harness. Clegs must never gain
    a route-finder -- a Z80 has nothing to spend on one and the whole design of
    the swarm is that it steers for light and cannot think. What a bot is
    allowed to do is know that a doorway exists, and this is where it does.

    `passable` is what counts as open ground. It defaults to the room's real
    geometry, which is what a bot that has been told the building looks like
    routes over. The Scout passes its own map instead, so that it can only walk
    where it has been able to see (issue #24).
    """
    room, cx, cy = place
    out = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = cx + dx, cy + dy
        if passable(room, nx, ny):
            out.append((room, nx, ny))
            continue
        step = scene.BUILDING.step_across(room, nx, ny)
        if step is not None and passable(*step):
            out.append(step)
    return out


def route(start, goals, passable=standable) -> list:
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
            for nb in neighbours(cell, passable):
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

    #: Whether this bot uses the torch at all. Every bot that does takes it as
    #: a constructor argument, because two of the difficulty targets are the
    #: same bot run twice, lit and dark.
    light = False

    def __init__(self, seed: int = 1) -> None:
        self._seed = seed or 1

    def _torch(self, run) -> bool:
        """Whether to press the torch key this frame.

        **Every intent any bot builds goes through here**, so that a bot with
        an opinion about light has one opinion rather than one per branch. The
        Scout's route decides its light, and it was getting the default in the
        branch it spends most of its time in -- which held the torch on through
        ground it already knew and burned all twenty seconds of it in the first
        half-minute.
        """
        return self.light and not run.cone.enabled

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
        return Intent(torch=self._torch(run))


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

    #: ...and it turns early if it has not moved for this long (issue #24).
    #:
    #: Measured before the fix: 29-42% of its pressing frames blocked, in
    #: stretches of up to fourteen seconds, visiting 146-241 of the room's 475
    #: standable cells in 144 seconds. **No first-timer holds a direction into
    #: a wall for fourteen seconds**, so targets T4 and T5 were a floor beneath
    #: the floor -- measured against a bot handicapped in a way no person is.
    #:
    #: Half a second is the same number `STUCK_FRAMES` uses for the routing
    #: bots, and for the same reason: it is long enough that a real obstacle is
    #: what stopped you, and short enough that nobody would stand there.
    WEDGED_FRAMES = 25

    def __init__(self, seed: int = 1, light: bool = True) -> None:
        super().__init__(seed)
        self.light = light
        self._dx = self._dy = 0
        self._left = 0
        self._was = None
        self._wedged = 0

    def intent(self, run) -> Intent:
        at = (run.here, run.player.x, run.player.y)
        self._wedged = self._wedged + 1 if at == self._was else 0
        self._was = at
        if self._left <= 0 or self._wedged >= self.WEDGED_FRAMES:
            r = self._random()
            self._dx = (r & 0b11) - 1
            self._dy = ((r >> 2) & 0b11) - 1
            self._dx = max(-1, min(1, self._dx))
            self._dy = max(-1, min(1, self._dy))
            self._left = self.TURN_EVERY
            self._wedged = 0
        self._left -= 1
        return Intent(dx=self._dx, dy=self._dy,
                      torch=self._torch(run))


class Walker(Bot):
    """Shared machinery for the bots that go somewhere on purpose."""

    #: What this bot treats as open ground. The room's real geometry for a bot
    #: that has been told what the building looks like; the Scout's own map for
    #: one that has to see it first.
    _passable = staticmethod(standable)

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
            self._goals, self._path = goals, route(here, goals, self._passable)
        if not goals:
            return Intent()

        at = (run.here, run.player.x, run.player.y)
        self._stuck = self._stuck + 1 if at == self._was else 0
        self._was = at
        if self._stuck > STUCK_FRAMES:
            # Wedged. Re-route from where we actually are, and if that is the
            # same answer, take a random step to shake loose.
            self._path = route(here, goals, self._passable)
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
                self._path = route(here, goals, self._passable)
            else:
                want = self._path[0][2]
                dy = (want > run.player.cy) - (want < run.player.cy)
                return Intent(dx=1 if door.side == building.EAST else -1,
                              dy=dy,
                              torch=self._torch(run))
        if not self._path:
            self._path = route(here, goals, self._passable)
        if not self._path or self._path[0][0] != run.here:
            return Intent(torch=self._torch(run))

        tx, ty = stand_pixel(*self._path[0][1:])
        dx = (tx > run.player.x) - (tx < run.player.x)
        dy = (ty > run.player.y) - (ty < run.player.y)
        return Intent(dx=dx, dy=dy, torch=self._torch(run))

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
                          torch=self._torch(run))
        return self._walk(run, self._exit_cells())


class Listener(Walker):
    """Walks to the last shout it heard, and only leaves when nobody is left.

    A shout is the one piece of information the room gives away for free, and
    the design claims it is a bearing rather than a map. This bot is that claim
    made measurable: it never switches a light on, and the phase-0 review found
    it cleared the room every time -- which is the finding that says the room is
    currently too easy.

    It hears what a player hears. It does not know where anybody is until they
    shout, and it forgets nothing, which is the one place it is kinder to itself
    than a person would be. The other place is `_nobody_left`: knowing that the
    building is empty of living people is not something a shout can tell you,
    and it is allowed here because the alternative is a bot that stands in the
    dark until the frame limit.

    **It had a batch of three and it does not any more** (issue #24). The batch
    assumed the game issue #20 had removed -- deliver and the run is over -- so
    it gathered three, walked out, and every measurement of it was of a bot that
    stopped at three of seven. Now that the exit hands people over on touch and
    the run carries on (issue #28), collecting until there is nothing left to
    hear *is* the behaviour, and going back in for the next one is free.
    """

    name = "listener"

    def __init__(self, seed: int = 1, light: bool = False) -> None:
        super().__init__(seed, light)
        self._heard: tuple[int, int, int] | None = None
        self._target = None
        #: A doorway with somebody shouting the other side of it, if the bot
        #: has heard one and has nothing nearer to go to.
        self._doorway: tuple[int, int, int] | None = None

    @staticmethod
    def _nobody_left(run) -> bool:
        """Is there anybody living still in the building to go back for?"""
        return not run.rescue.alive_waiting()

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

        if self._target is not None and self._target.state != rescue_mod.WAITING:
            self._target, self._heard = None, None
        if self._heard is not None:
            return self._walk(run, stand_cells(*self._heard))

        # **The doorway comes before the way out**, and the order is the whole
        # of what this bot measures. A call over a doorway is the only bearing a
        # room you are not in ever gives you, so a bot that preferred the exit
        # would walk out of the building the moment it ran out of voices in this
        # room -- and would never test the rule at all. Put the door first and it
        # goes and looks, which is what a first-timer who has understood the
        # game does.
        if self._doorway is not None:
            if self._doorway[0] == run.here:
                self._doorway = None
            else:
                return self._walk(run, stand_cells(*self._doorway))

        if self._nobody_left(run):
            # Nobody living is still in there. Walk out -- which hands over
            # anybody behind you on the way through.
            return self._leave(run)
        if run.rescue.tail:
            # Nothing left to hear from here, so take who you have to the door.
            # Touching it banks them and the run carries on, so this is a trip
            # rather than an ending, and the next shout brings it back in.
            return self._walk(run, self._exit_cells())
        # Nobody has called yet, or the last caller is accounted for. Stand
        # still rather than wander: this bot's whole point is that it acts only
        # on what the room told it.
        return Intent(torch=self._torch(run))


class Scout(Listener):
    """Routes only through ground it has seen, and lights the way to see more.

    The bot target T2 exists for: *light must buy something*. That target was
    **unfalsifiable rather than unmet**, because none of the other four bots
    consults the light field at all -- the Listener routes by breadth-first
    search over the true room geometry, so it walks through walls it has never
    seen to reach a shout it has just heard, and a torch can only ever cost it.

    So this one knows nothing about the building it has not observed:

    * **A cell becomes known the first time it is seen lit or dim.** Nothing
      else is known, **including where the walls are**.
    * **It routes through known ground only.** With no route to its target
      through known cells it goes to the nearest **frontier** -- a known cell
      with unknown ground next to it -- and carries on from there.
    * **Its torch use follows from its route.** On while it is heading for a
      frontier, off while it is walking ground it already knows. That is the
      whole point: the light policy is a consequence of where it is going, not
      a flag set from outside.

    Everything else is the Listener's: it goes to the last shout it heard, it
    delivers when its route reaches the door, and it leaves when nobody living
    is left inside. That makes the T2 pair honest -- the same bot with and
    without a torch, differing in what it can see rather than in what it wants.

    **A Scout with `light=False` is the control.** It still explores, because
    the player's own glow marks the cells around them dim, and dim is known. It
    simply learns the building an arm's length at a time.
    """

    name = "scout"

    def __init__(self, seed: int = 1, light: bool = True) -> None:
        super().__init__(seed, light)
        #: Every cell it has ever seen, as (room, cx, cy). Not what is in them.
        self.seen: set[tuple[int, int, int]] = set()
        #: Whether the route it is following is an exploration rather than a
        #: journey to somewhere it knows. This is what holds the torch on.
        self.exploring = False
        #: The direction it stepped off the edge of its map in, and the room it
        #: was in when it did. See `_walk`: a doorway is two frames wide and a
        #: bot that reconsidered in the middle of one would walk back out of it.
        self._push: tuple[int, int] | None = None
        self._push_room = 0

    # --- what it knows -----------------------------------------------------

    def observe(self, run) -> None:
        """Everything the light is on, in the room the bot is standing in.

        Lit or dim, present or remembered -- `level_at` is what the *screen*
        shows, so this is exactly the ground a player could have drawn a map of.
        """
        field = run.place.field
        here = run.here
        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                if field.level_at(cx, cy) > lighting.DARK:
                    self.seen.add((here, cx, cy))

    def _passable(self, room: int, cx: int, cy: int) -> bool:
        """Known ground it could stand in. A cell it has never seen is not a
        wall and is not floor either -- it is simply not somewhere it can plan
        a route through."""
        return ((room, cx, cy) in self.seen
                and (room, cx, cy - 1) in self.seen
                and standable(room, cx, cy))

    def _unknown_from(self, place) -> tuple[int, int] | None:
        """Which way the map runs out from here, if it does.

        **Doorways count**, and they are the case that matters: the cell past a
        doorway is in the next room's coordinates, so a check that only looked
        at this room's grid would decide the building ended at the wall and the
        bot would never have a reason to go through. That is not hypothetical
        -- it is what the first version of this did, and it stood in room A for
        three minutes with four people calling next door.
        """
        room, cx, cy = place
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (room, cx + dx, cy + dy)
            if not standable(*nb):
                step = scene.BUILDING.step_across(room, cx + dx, cy + dy)
                if step is None or not standable(*step):
                    continue
                nb = step
            if nb not in self.seen:
                return dx, dy
        return None

    def frontiers(self, run) -> list[tuple[int, int, int]]:
        """Known ground with unknown ground next to it: where the map runs out."""
        return [place for place in self.seen
                if self._passable(*place) and self._unknown_from(place)]

    # --- where it goes -----------------------------------------------------

    def intent(self, run) -> Intent:
        self.observe(run)
        return super().intent(run)

    def _walk(self, run, goals) -> Intent:
        """Head for the goal if the map reaches it, and for the edge of the map
        if it does not."""
        here = (run.here, run.player.cx, run.player.cy)
        reachable = bool(goals) and bool(route(here, goals, self._passable))
        self.exploring = not reachable
        if reachable:
            return super()._walk(run, goals)
        edges = self.frontiers(run)
        if not edges:
            # Nowhere left to look from here: everything it can see is fully
            # mapped. Stand still rather than blunder about -- this bot's whole
            # claim is that it acts on what it can see.
            return Intent(torch=self._torch(run))
        if self._push is not None and run.here != self._push_room:
            self._push = None                # through, and somewhere new
        step = self._unknown_from(here) if here in edges else None
        if step is None and self._push is not None and not self._passable(*here):
            # **Halfway through a doorway.** The column past a wall belongs to
            # the room next door, so the bot is standing somewhere its own map
            # has no cell for, and every rule below would send it back to the
            # last cell it knew. Crossing takes two or three frames of walking
            # at the wall, so the push is held until the room actually changes.
            step = self._push
        if step is not None:
            # Standing on the edge of the map. Walk off it, which is also how
            # you go through a doorway: there is no "go through the door"
            # action here or anywhere else, only more of the same direction.
            self._push, self._push_room = step, run.here
            return Intent(dx=step[0], dy=step[1], torch=self._torch(run))
        return super()._walk(run, edges)

    def _torch(self, run) -> bool:
        """Press the key if the light is not in the state the route wants.

        On while it is heading for the edge of its map, off on ground it knows.
        That is the whole point of this bot: the light policy is a consequence
        of where it is going, and a policy set from outside measures nothing.
        """
        return self.light and self.exploring != run.cone.enabled

    def _leave(self, run) -> Intent:
        self.exploring = False
        return super()._leave(run)


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


class Undertaker(Oracle):
    """An Oracle that **abandons what it is doing at the moment of death** and
    goes to douse the body. Difficulty target T12, and nothing else.

    T12 asks whether the body window is winnable and whether it is free, and it
    is a comparison between two bots rather than a number: this one should reach
    a body in at least three deaths in five, and a `Listener` -- which carries
    on working, because it does not know a body exists -- in at most one in
    five. A window only one bot can use is a window; one both can use is a
    formality, and one neither can use is a twenty-second lie.

    So this is the ceiling on the window, exactly as the Oracle is the ceiling
    on the room: it knows there is a body and where, it has a route, and it
    still has to walk there before the twenty seconds are up. **It presses keys
    like every other bot** -- the spray goes down ahead of it, so it fires on
    the approach, on the first frame from which a patch would land on the body.

    It goes for **the body nearest turning**, which is the one the game is
    ticking about. With deaths this close together that is a real choice and
    not a formality.
    """

    name = "undertaker"

    def intent(self, run) -> Intent:
        body = run.rescue.ticking()
        if body is not None and not run.spray.empty:
            if self._would_cover(run, body):
                return Intent(spray=True, torch=self._torch(run))
            return self._walk(run, stand_cells(body.room, *body.cell()))
        return super().intent(run)

    @staticmethod
    def _would_cover(run, body) -> bool:
        """Would a burst fired this frame land on that body?

        Asked of the spray's own rule rather than guessed at, and it is why the
        bot never has to think about which way it is facing: it is walking
        towards the body, so the patch it lays ahead of itself arrives on the
        body as soon as it is close enough.

        Both halves of the rule, since issue #39: the patch ahead, and the body
        the player is standing on. The second half is here because routing aims
        at the cell the body is lying in, so the bot can arrive standing on it
        -- and asking only about the patch would then have it refuse to fire on
        a body a charge would now save. **A bot is an instrument, and it has to
        measure the rules the game actually has**, or every difficulty number
        taken with it understates what a charge can do.
        """
        if run.here != body.room:
            return False
        cells = body.cells()
        # The room goes in, because a burst drops the cells that land on wall
        # (issue #41) and a bot has to measure the burst the game lays, not an
        # idealised one. A body never lies on solid ground, so in practice this
        # changes no answer -- it stops the two drifting apart if that ever
        # stops being true.
        patch = set(spray_mod.patch_cells(run.player.cx, run.player.cy,
                                          run.player.facing, run.is_solid))
        return bool(patch & cells) or any(c in cells
                                          for c in run.player.body_cells())


class Crosser(Walker):
    """Walks a stated route, over and over, lit or dark. Difficulty target T3e.

    **The instrument the light bargain has been waiting for.** Three rounds of
    tuning produced one survivor and two reverts, and the pattern was not luck:
    the survivor was about sequencing, which the other bots can see, and both
    failures were about what light costs, which they cannot. Measured, over a
    whole run nothing distinguishes a lit player from a dark one -- blood
    saturates (a lit Statue is at 191.8 of 192 by 150s on every seed) and
    survival time gives a seven-second difference inside a forty-four-second
    spread.

    The reason is that **the swarm has a conserved feeding throughput**: six
    flies on a drink-and-sate cycle eat as fast as they can cycle, so what the
    player switches on changes *which light a fly walked to, not how many meals
    it gets*. Light does not change how much blood you lose, it changes when --
    and the design never claimed otherwise. The spine says light *draws the
    swarm onto you*, which is a claim about arrival, and arrival measures at
    3.3x on every seed.

    **The bargain is a race, and every bot measured so far is standing still.**
    So this one runs one: a crossing is about five seconds, it is bounded so it
    cannot saturate, and it is the shape of the decision a player actually
    takes -- *do I light this crossing or feel my way?* The two figures it
    reports are the ones T3e is stated in:

    * **extra bites per crossing**, lit against dark; and
    * **the share of crossings in which a fly attaches before the far end**.

    Both are per crossing rather than per run, which is what stops them being a
    quotient of two long totals.
    """

    name = "crosser"

    #: The route, stated here because a result nobody can reproduce is not a
    #: measurement. Row 14 of the near room is its longest clear run -- thirty
    #: cells with no wall in them -- and the ends are set two cells inside it so
    #: that arriving is not the same thing as being stopped by a wall. Twenty-
    #: seven cells is 216 pixels, which at one pixel a frame is 4.3 seconds:
    #: about the five the target asks for, and well short of anything that
    #: could saturate.
    ROUTE = ((scene.NEAR, 2, 14), (scene.NEAR, 29, 14))

    def __init__(self, seed: int = 1, light: bool = False, route=None) -> None:
        super().__init__(seed, light)
        self.route = tuple(route or self.ROUTE)
        self.at = 0
        #: One record per completed crossing. See `summary`.
        self.crossings: list[dict] = []
        self._started = 0
        self._at_start = 0
        self._bites = 0
        self._attached = False
        self._lit = 0

    def _target(self) -> tuple[int, int, int]:
        return self.route[self.at]

    def intent(self, run):
        here = (run.here, run.player.cx, run.player.cy)
        bites = run.swarm.attachments
        if self._started:
            self._lit += run.cone.lit
        if self._bites != bites:
            # A fly landed on this leg. Whether it landed *before the far end*
            # is the whole of the second figure, and it is true by construction
            # here: the crossing is not finished until the target is reached.
            self._attached = True
            self._bites = bites
        if here == self._target():
            if self._started:
                frames = run.frame - self._started
                self.crossings.append({
                    "from": list(self.route[self.at - 1]),
                    "to": list(self._target()),
                    "frames": frames,
                    "lit_frames": self._lit,
                    # **Lit if the torch burned for most of it.** A carried
                    # spotlight is twenty seconds and a crossing is four, so a
                    # long run has both kinds in it whatever the bot was asked
                    # for -- and a crossing half spent in the dark is neither
                    # thing and must not be counted as either.
                    "lit": self._lit * 2 >= frames,
                    "bites": bites - self._at_start,
                    "bitten_before_arrival": self._attached,
                })
            self.at = (self.at + 1) % len(self.route)
            self._start(run.frame, bites)
        elif not self._started:
            # The first leg does not count: it starts wherever the player
            # happens to begin rather than at an end of the route.
            self._start(run.frame, bites)
        return self._walk(run, stand_cells(*self._target()))

    def _start(self, frame: int, bites: int) -> None:
        self._started, self._at_start = max(1, frame), bites
        self._attached, self._lit = False, 0

    @staticmethod
    def _figures(crossings: list[dict]) -> dict:
        """T3e's two figures over a set of crossings.

        Bites are in **tenths of a bite per crossing**, because the target is
        stated as "one extra bite every two crossings" and integers are the
        house rule. The share is a percentage of the crossings counted.
        """
        n = max(1, len(crossings))
        bites = sum(c["bites"] for c in crossings)
        bitten = sum(1 for c in crossings if c["bitten_before_arrival"])
        return {
            "crossings": len(crossings),
            "crossing_frames": sum(c["frames"] for c in crossings) // n,
            "bites": bites,
            "bites_per_crossing_tenths": 10 * bites // n,
            "bitten_before_arrival": bitten,
            "bitten_before_arrival_percent": 100 * bitten // n,
        }

    def summary(self) -> dict:
        """The route, and T3e's figures split by whether the torch was burning.

        **Split within the run as well as between runs.** A torch is twenty
        seconds and a crossing is four, so a bot asked to hold the light on
        spends the first five crossings lit and the rest of a two-minute run
        dark -- and a run report that averaged those together would be reporting
        neither. The lit and dark buckets here are the same room, the same seed
        and the same swarm, which is a tighter comparison than two runs; the
        across-seeds pair the target asks for is still what settles it.
        """
        lit = [c for c in self.crossings if c["lit"]]
        dark = [c for c in self.crossings if not c["lit"]]
        return {
            "route": [list(cell) for cell in self.route],
            "all": self._figures(self.crossings),
            "lit": self._figures(lit),
            "dark": self._figures(dark),
        }


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
    "scout": Scout,
    "crosser": Crosser,
    "oracle": Oracle,
    "undertaker": Undertaker,
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
