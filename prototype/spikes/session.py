"""One run of the game, from the first frame to the ending screen.

This is the loop body of `spike1`, lifted out of it. It was a single 300-line
`while` in the middle of a Pygame program, which made two things impossible:
you could not tell a run apart from the window it was drawn in, and you could
not run one without a keyboard. Issue #17 needs the second of those and issue
#15 needs the first, so the two live here now:

* **`step()` is the game.** One frame of it. The windowed game calls it fifty
  times a second and the headless driver calls it as fast as it can, and they
  are calling the same code with the same constants. There is no second
  simulation anywhere and there must never be one -- every number in the
  phase-0 review came from monkey-patching this loop to fake a headless run,
  and a faked loop is a loop nobody has checked.
* **A `Session` is a whole run and nothing outside it.** Restarting is building
  a new one. No reset method, no state to remember to clear: if it is not
  rebuilt in `__init__` it does not carry over, and that is a much easier rule
  to keep true than a list of things to zero.

* **A run is a *building*, not a room** (issue #21). Every room is simulated
  every frame whether or not it is the one on screen -- the building is a
  simulation running whether you are looking at it or not, which is what makes
  a worker being eaten two cells the other side of a wall a thing that actually
  happens rather than a thing the design merely claims. What a room does *not*
  get is drawn: `draw` paints the room the player is standing in and nothing
  else, so stepping through a doorway flicks the screen.

Nothing here imports pygame, so a run can be driven, measured and even drawn
with no host at all. Sound is the one thing it cannot do; it reports `click`
and lets the host make the noise.
"""

from spotlight.core.constants import BLACK, CELL, COLS, CYAN, GREEN, RED, WHITE
from spotlight.core.screen import Screen, attr_byte

from . import (
    buzz, clegs as clegs_mod, floor, font, lighting, rescue as rescue_mod,
    scene, sources, spray as spray_mod, sprites, tally as tally_mod,
)
from .layout import PLAY_BOTTOM, PLAY_ROWS, PLAY_TOP
from .lighting import LightField
from .panel import Panel, bar_pips, blank_strip
from .player import Player
from .spotlights import FloorLight, Spotlights

PLAY_ATTR = attr_byte(ink=WHITE, paper=BLACK, bright=False)

#: Blood, as points. Shown as eight pips, so each pip is a Cleg's worth: one
#: attachment takes exactly one bar. A number small enough that the player can
#: count what a swarm cost them.
BLOOD_FULL = 64

#: How many times the player can bleed out before the run is over. Deliberately
#: not called "lives" anywhere a player will read it: the testers are people who
#: do not know 8-bit games and that word carries none of its usual freight.
LIVES = 3

#: The default seed. Any integer will do; this one is the arrangement the spike
#: was played and judged on. Note that it does not reproduce the pre-issue-#17
#: room byte for byte -- the searchlight's tour used to be seeded separately and
#: is now derived from the session seed like everything else, so its route
#: differs. Nothing about the room, the workers or the swarm's starting
#: positions changed.
DEFAULT_SEED = 0xBEEF

# --- how a run ends --------------------------------------------------------
# Named, because issue #20 changes *which conditions* fire and issue #21 adds a
# room to say them in. Both should be edits to `_ending()` and to this table,
# not a rewrite of everything that reads an ending.

#: Walked out of the exit with everybody alive and accounted for.
ALL_OUT = "all_out"
#: Walked out of the exit without them. Some are dead; some may still be in
#: there. Either way the player chose to leave, which is what #20 made possible.
NOBODY_LEFT = "nobody_left"
NO_LIVES = "no_lives"
#: The driver ran out of frames, or the player closed the window. Not endings
#: the game reaches on its own, but a run has to be able to say so.
FRAME_LIMIT = "frame_limit"
ABANDONED = "abandoned"

#: How each ending reads to somebody who has never played a game like this.
#: Two lines: what happened, then what it means.
ENDING_TEXT = {
    ALL_OUT: ("YOU GOT EVERYONE OUT",
              "ALL OF THEM ARE ALIVE"),
    NOBODY_LEFT: ("THERE IS NOBODY LEFT TO SAVE",
                  "THE REST OF THEM BLED TO DEATH"),
    NO_LIVES: ("YOU BLED OUT FOR THE LAST TIME",
               "THE FLIES HAVE FINISHED YOU"),
    FRAME_LIMIT: ("TIME RAN OUT", "THE RUN WAS STOPPED"),
    ABANDONED: ("YOU LEFT THE BUILDING", "THE RUN WAS STOPPED"),
}

# --- what happened, as events ----------------------------------------------
# The run log is the source of truth for both reports, so nothing that a report
# wants to say may be reconstructed by guesswork afterwards. It used to be a
# scattering of `print` calls, which is why the phase-0 review could see that
# four workers were "never found" without being able to say what became of the
# three in the tail.

FREED = "freed"
DELIVERED = "delivered"
WORKER_DIED = "worker_died"
BITTEN = "bitten"
#: A Cleg landed on somebody who is not the player (issue #19). Its own kind
#: rather than a `BITTEN` with a `who`, because every phase-2 baseline is stated
#: in the count of `BITTEN` events and in the frame of the first one, and a
#: worker being bitten must not move either of them.
WORKER_BITTEN = "worker_bitten"
LIFE_LOST = "life_lost"
SPRAY_KILL = "spray_kill"
#: Blood taken this frame. Recorded because difficulty target T8 asks what the
#: second minute in the dark costs against the first, and a running total
#: cannot answer that. Only logged on frames where something was taken, which
#: is a few hundred events in the worst run.
DRAINED = "drained"
SWAPPED = "swapped"
#: The carried torch burned its last frame of power (issue #31). Its own kind
#: rather than a `SWAPPED` with a zero count, because it is the one thing that
#: happens to the player's kit **without the player asking for it** -- and
#: because "how long before a first-timer's torch died, and what did they do
#: next" is a question the playtest wants to be able to ask of a run.
TORCH_OUT = "torch_out"
#: The player stepped through a doorway (issue #21). `count` is the room they
#: arrived in, `room` the room they left. It is logged because a second room is
#: only worth having if people go into it, and "did a first-timer ever find the
#: door" is the first question the playtest asks -- target T10 is stated in it.
CROSSED = "crossed"
GAME_OVER = "game_over"


class Event:
    """Something worth reporting, and the frame it happened on.

    `who` is a worker index where there is one, so a report can name the person
    rather than the count. `count` is for the things that happen in numbers --
    Clegs attaching, Clegs sprayed.
    """

    __slots__ = ("frame", "kind", "who", "count", "room")

    def __init__(self, frame: int, kind: str, who: int | None = None,
                 count: int = 0, room: str = "") -> None:
        self.frame = frame
        self.kind = kind
        self.who = who
        self.count = count
        #: Which room it happened in, by name. Issue #21 made this load-bearing
        #: rather than reserved: the user's question to a playtester is *you
        #: lost the one in the far room at about a minute -- did you know they
        #: were there?*, and a loss that cannot be placed cannot be asked about.
        self.room = room

    @property
    def seconds(self) -> int:
        return self.frame // 50

    def __repr__(self) -> str:
        return (f"Event({self.frame}, {self.kind!r}, who={self.who}, "
                f"count={self.count}, room={self.room!r})")


class Intent:
    """What the player asked for this frame.

    Movement is held (a key down means moving now, per the responsiveness
    requirement); the torch and the spray are edge-triggered, because holding
    the torch key down should not strobe it. Whoever builds the intent decides
    which is which -- the session only obeys.
    """

    __slots__ = ("dx", "dy", "torch", "spray")

    def __init__(self, dx: int = 0, dy: int = 0, torch: bool = False,
                 spray: bool = False) -> None:
        self.dx, self.dy = dx, dy
        self.torch = torch
        self.spray = spray


#: The do-nothing frame. Handy enough to be worth naming.
IDLE = Intent()




class Place:
    """One room while the run is happening: its light, its swarm, its lights.

    The authored `Room` is ROM -- it never changes. This is the part that does,
    and there is one per room in the building because **every room is simulated
    every frame whether or not it is on screen.** Clegs go on hunting, workers
    go on bleeding, and room A's searchlight goes on sweeping over the people
    you left behind in it while you are two cells the other side of a wall. That
    is the whole reason the shout has to carry through a doorway.

    What a room that is not on screen does not get is drawing, which is the
    expensive part, and that is what makes the split affordable on a Z80.
    """

    def __init__(self, index: int, room, clegs, beam_seed: int) -> None:
        self.index = index
        self.room = room
        #: One light field per room, and **that is what stops light crossing a
        #: threshold**. A source belongs to a room, so a field simply has
        #: nowhere to put light that is not its room's -- standing in a doorway
        #: you cannot see through it. It is a real cost and the vault argues it
        #: is the right one: it makes stepping through a commitment rather than
        #: a glance, and compositing two rooms' lighting is exactly what the
        #: room model exists to avoid.
        self.field = LightField()
        self.inks = room.ink_map()
        #: Authored emergency lighting. Room B's is the first any room in the
        #: prototype has ever had, and it sits on the doorway home.
        self.room_lights = [sources.RoomLight(*z) for z in room.light_zones()]
        #: The room's searchlight, or None. Room B authors none -- it is the
        #: dark room, and nothing sweeps it.
        self.roaming = None
        if room.searchlight is not None:
            self.roaming = sources.Roaming(
                0, 0, radius=room.searchlight.radius,
                vary=room.searchlight.vary, seed=beam_seed)
        self.swarm = clegs_mod.Swarm(clegs)
        self.sign_cells = room.exit_sign_cells(scene.EXIT_SIGN)
        self.fixtures = [(sprites.SPRITES[name], x, y)
                         for name, x, y in scene.ENTITIES
                         if name not in scene.MOVERS]
        for cx, cy in room.cells_of(scene.KEY):
            self.fixtures.append((sprites.KEY, cx * CELL, cy * CELL))
        #: The opening flash, **once per room and never on re-entry**. You
        #: cannot play a room you have never seen the shape of; re-entry is
        #: precisely the case where you are supposed to be living off what you
        #: held in your head, and flashing every time would make the fade
        #: pointless and hand the building over for free.
        self.opening = sources.Flash()
        self.seen = False

    @property
    def fixed(self) -> tuple:
        """The lights that belong to this room, wherever the player is."""
        lit = [self.opening, *self.room_lights]
        if self.roaming is not None:
            lit.insert(0, self.roaming)
        return tuple(lit)

    def enter(self) -> bool:
        """The player has just walked in. Returns True the first time only.

        The fade in a room you are not in **keeps running**, because time
        passes everywhere: duck out and back and your memory is still warm,
        come back two minutes later and it has gone. In a building of two rooms
        that costs nothing, because both fields are resident and both decay
        every frame. A larger building keeps a field for the room you are in
        and the one you just left and no others, and catches the second one up
        from a frame stamp on re-entry -- see `LightField.catch_up`, which is
        built and tested and is not yet on this path because with two rooms
        there is never a room to catch up.
        """
        first = not self.seen
        self.seen = True
        if first:
            self.opening.fire()
        return first


class Session:
    """A run: the building, the people in it, the swarm, and how it ended."""

    def __init__(self, seed: int = DEFAULT_SEED,
                 blood: int = BLOOD_FULL, lives: int = LIVES) -> None:
        self.seed = seed
        scene.validate()
        self.building = scene.BUILDING

        # Every random thing in the run is derived from the one seed, so a seed
        # names a run. The Clegs' temperaments and the searchlight's tour are
        # the only two, and both use the same xorshift the Z80 will.
        cleg_seed = sources.xorshift16(seed or 1)
        beam_seed = sources.xorshift16(cleg_seed)

        #: Which room the player is standing in. **The whole of the screen
        #: transition**: `draw` paints this room and no other, so stepping
        #: through a doorway flicks the view. Nothing else about a room change
        #: is special-cased anywhere in the game.
        self.here, self.start_room = self.building.start[0], self.building.start[0]
        self.player = Player(*self.building.start[1])
        self.glow = sources.Glow()
        self.glow.x, self.glow.y = self.player.cx, self.player.cy
        self.cone = sources.Cone(reach=7)
        self.cone.x = self.player.cx
        self.cone.y = self.player.cy
        self.cone.facing = self.player.facing
        self.kit = Spotlights(
            self.cone,
            [FloorLight(cx, cy, power, room=i)
             for i, room in enumerate(self.building.rooms)
             for cx, cy, power in room.spotlights])
        # What a full light bar means on the panel: the strongest thing in the
        # building, since that is the most the player can ever be carrying. A
        # building may author no pickups at all -- the first three-room fixture
        # written did -- so it falls back to what the carried cone starts on.
        self.cone_full = max([light.power for light in self.kit.floor]
                             or [self.cone.power])
        self.spray = spray_mod.Spray(charges=5)

        # One `Place` per room. Cleg seeds run on across the building rather
        # than restarting per room, so no two flies in the building share a
        # temperament by accident -- and so that moving a fly from one room's
        # authored list to another's does not silently duplicate one.
        self.places = []
        made = 0
        for i, room in enumerate(self.building.rooms):
            flies = [clegs_mod.Cleg(cx, cy, seed=cleg_seed + made + n)
                     for n, (cx, cy) in enumerate(room.clegs)]
            made += len(flies)
            self.places.append(Place(i, room, flies, beam_seed))
        #: Every swarm in the building, read as one. See `clegs.Swarms`: the
        #: counters are the building's because a fly that walked through a
        #: doorway is the same fly.
        self.swarm = clegs_mod.Swarms([p.swarm for p in self.places])
        #: The building's searchlights, and the one the debug keys reach for.
        #: There is exactly one -- room A's -- and room B authors none, which is
        #: the point of room B.
        self.searchlights = [p.roaming for p in self.places
                             if p.roaming is not None]
        self.blood = blood
        self.blood_full = blood
        self.lives = lives
        self.sonar = buzz.Sonar()
        #: Set by `step` when the sonar wants a click. The host makes the noise;
        #: deciding how urgent it is stays portable and integer (see buzz).
        self.click = False

        # The room is shown once, on first entry, and then taken away. What the
        # player keeps is what they held in their head. Each room gets its own,
        # and re-entry does not fire it.
        self.place.enter()

        # Everybody in the building, with the room they are trapped in on the
        # same authored line as their position and their clock, so the three
        # cannot be renumbered apart. The exit is the building's, not a room's.
        people = [(i, x, y, clock)
                  for i, room in enumerate(self.building.rooms)
                  for x, y, clock in room.workers]
        self.rescue = rescue_mod.Rescue(people, self.building.exit)
        #: Workers by identity, so an event can name who without the report
        #: having to search a list to find out.
        self._index = {id(w): i for i, w in enumerate(self.rescue.workers)}
        self.tally = tally_mod.Tally()

        self.panel = Panel()
        self.panel.set_total("rescued", len(self.rescue.workers))
        for name, value in (("blood", 8), ("light", 4), ("lit", 1),
                            ("spray", self.spray.charges), ("keys", 0)):
            self.panel.set(name, value)
        self.panel.set("lives", self.lives)
        self.panel.set("rescued", 0)

        self.frame = 0
        #: Is the player touching the way out right now, and have they ever not
        #: been? Both are read only by `_ending`, which explains them.
        self.at_exit = False
        self._gone_in = False
        self.over: str | None = None
        self.calls_on = True
        self.log: list[Event] = []
        self.frame_events: list[Event] = []
        self.shouting: list = []
        #: Cells a call is being drawn over the doorway of, this frame: one run
        #: of them per doorway that has somebody shouting the other side of it.
        self.door_calls: list[list[tuple[int, int]]] = []
        self.call_cells: list[tuple[int, int]] = []
        #: How many times the player has stepped through a doorway.
        self.crossings = 0
        self._painted_strip = False

    # --- where the player is -----------------------------------------------

    @property
    def place(self) -> Place:
        """The room the player is standing in, and everything live in it."""
        return self.places[self.here]

    @property
    def room(self) -> str:
        """What to call it in a report."""
        return self.place.room.name

    @property
    def is_solid(self):
        """What the player may walk into, here. The room decides, not the game.

        It is a bound method of the current `Room`, and it answers for the
        column just past a doorway by asking the room next door -- which is why
        walking through one needs no code of its own in the player, the Clegs or
        the bots.
        """
        return self.place.room.is_solid

    # `field`, `inks`, `room_lights`, `opening`, `sign_cells` and `fixtures`
    # all belong to a *room* now. They are still reachable from the session,
    # meaning "the one the player can see", because that is what every caller
    # wanted when there was only one room and it is still what they want.

    @property
    def field(self) -> LightField:
        return self.place.field

    @property
    def inks(self):
        return self.place.inks

    @property
    def room_lights(self) -> list:
        return self.place.room_lights

    @property
    def opening(self):
        return self.place.opening

    @property
    def sign_cells(self) -> list:
        return self.place.sign_cells

    @property
    def fixtures(self) -> list:
        return self.place.fixtures

    @property
    def roaming(self):
        """The building's searchlight.

        Singular because the building has one. When a building has several this
        becomes a list and the debug keys grow a selector; naming it now would
        be guessing at an interface nobody has needed.
        """
        return self.searchlights[0] if self.searchlights else None

    @property
    def all_sources(self) -> tuple:
        """Every light shining into the room the player is in."""
        return (self.glow, self.cone, *self.place.fixed)

    # --- what is going on --------------------------------------------------

    @property
    def total(self) -> int:
        return len(self.rescue.workers)

    @property
    def rescued(self) -> int:
        return self.rescue.saved

    @property
    def lost(self) -> int:
        return self.rescue.lost

    @property
    def inside(self) -> int:
        """People still in the building: waiting, or following you out.

        The third column, and the reason it exists. The phase-0 review found a
        run reported as "0 out, 0 lost, 4 never found" with seven people in the
        room: three were in the tail when the last life went and appeared in no
        column at all. Whatever an ending says, it has to add up.
        """
        return self.rescue.waiting + len(self.rescue.tail)

    @property
    def seconds(self) -> int:
        return self.frame // 50

    def tally_adds_up(self) -> bool:
        """out + died + still inside == everybody. Cheap enough to assert."""
        return self.rescued + self.lost + self.inside == self.total

    def _lit_people(self, place: Place) -> list:
        """Everybody in one room, except the player, who is **plainly lit**.

        The swarm's prey list (issue #19). Three things it is careful about:

        * **It is the same test that decides whether a person is drawn.**
          `LightField.prey_at` is what `draw` uses through `reveals_at`, one
          step stricter: a person a *lit* revealing light is on, not one merely
          glimpsed in your own dim glow. So *if you can see them, so can the
          flies*, and the player is never surprised by a rule they cannot
          observe. Room lights are excluded by `prey_at` itself and
          deliberately: they show the room and not who is in it, to Clegs
          exactly as to the player.
        * **It reads last frame's field**, because `_light()` runs at the end of
          `step` -- the swarm reacts to the light the player was standing in
          when they last saw it, which is a frame of lag nobody can perceive and
          the honest reading of "what was lit". It also means nobody is prey on
          frame one, before any light has been cast.
        * **Waiting workers count too**, not only followers. Somebody standing
          in the searchlight's path, or beside a spotlight left burning on the
          floor, is prey where they stand. That is the same baiting the design
          already has, with a person in the middle of it.
        """
        lit = []
        for worker in self.rescue.workers:
            if not worker.alive or worker.room != place.index:
                continue
            for cx, cy in worker.cells():
                if place.field.prey_at(cx, cy):
                    lit.append(worker)
                    break
        return lit

    def _own_lures(self, place: Place) -> list:
        """Every light in one room that a Cleg standing in it can steer for.

        The room's own fixtures, whatever is burning on its floor, and -- only
        if the player is in it -- the player's glow and torch. **A light belongs
        to a room**, which is the same rule that stops light crossing a
        threshold, applied to the other half of the bargain.
        """
        lures = [p for p in (src.lure() for src in place.fixed) if p is not None]
        lures += self.kit.floor_lures(place.index)
        if place.index == self.here:
            lures += [p for p in (self.glow.lure(), self.cone.lure())
                      if p is not None]
        return lures

    def _doors(self, place: Place, own: list) -> list:
        """The light in the rooms next door, offered as lures on the threshold.

        **Clegs cross doorways in pursuit of light.** A light in the room next
        door is offered here as a lure standing on the threshold -- the cell
        just past the doorway, which belongs to the room beyond -- so a fly that
        takes it walks into the doorway and out the other side by the ordinary
        greedy step. There is no pathfinding in it and there never will be: the
        fly is steering at a cell it can see, and that cell happens to be a
        doorway.

        Kept apart from the room's own lures because **a fly looks round its
        own room first** and only takes up a doorway when nothing on this side
        of the wall is lit within its notice. See `Swarm.tick` for what
        happened when the two lists were one, and `sources.through_doorway` for
        the reach and for the two versions of this that were tried and
        rejected.
        """
        lures = []
        for door in place.room.doorways:
            spill = sources.through_doorway(
                (door.beyond, door.middle), (door.landing, door.middle),
                own[door.to])
            if spill is not None:
                lures.append(spill)
        return lures

    # --- one frame ---------------------------------------------------------

    def step(self, intent: Intent = IDLE) -> list[Event]:
        """Advance one frame. Returns what happened on it.

        The order is the order the spike's loop ran in, and some of it matters:
        the torch and the spray are acted on before the player moves, because
        that is the frame the key was pressed on; lighting is rebuilt last,
        because the shout and the exit sign are added to it after every source
        has had its say.
        """
        if self.over is not None:
            return []
        self.frame += 1
        self.frame_events = []

        if intent.torch:
            self.kit.toggle()
        if intent.spray and self.spray.fire(self.player.cx, self.player.cy,
                                            self.player.facing, self.here):
            self.tally.sprays += 1
            self.panel.set("spray", self.spray.charges)

        # Input is read and acted on in the same frame. Nothing buffers,
        # smooths or accelerates -- responsiveness is a requirement.
        self.player.move(intent.dx, intent.dy, self.is_solid)
        self._maybe_cross()
        room = self.room
        self.glow.x, self.glow.y = self.player.cx, self.player.cy
        self.cone.x, self.cone.y = self.player.cx, self.player.cy
        self.cone.facing = self.player.facing

        # Every room, not only the one on screen. The building is a simulation
        # running whether or not you are looking at it, which is what makes the
        # room you walked out of a place where things still happen.
        for place in self.places:
            if place.roaming is not None:
                place.roaming.update()
            place.opening.update()
        self.spray.tick()

        # The one rule: Clegs steer for the nearest light that is actually lit.
        # The glow is dim and so pulls nothing, which is what makes walking in
        # the dark safe and the toggle a decision.
        own = [self._own_lures(place) for place in self.places]
        was_attached = len(self.swarm.on_player())
        for place in self.places:
            here = place.index == self.here
            blood = place.swarm.tick(
                own[place.index],
                (self.player.cx, self.player.cy) if here else None,
                place.room.is_solid, self.blood if here else 0,
                is_sprayed=self.spray.in_room(place.index),
                prey=self._lit_people(place),
                doors=self._doors(place, own))
            if here:
                self.blood = blood
        # Flies that walked through a doorway are handed over before anything
        # else looks at them, so the spray, the bite log and the drawing all
        # see every fly in the room it is actually in.
        self._migrate()
        for victim in self.swarm.bitten:
            self._record(WORKER_BITTEN, who=self._index[id(victim)],
                         count=1, room=self.places[victim.room].room.name)
        # Spray reaches everything except a Cleg already on you, and only in
        # the room the patch was laid in.
        killed = 0
        for place in self.places:
            killed += place.swarm.kill(
                self.spray.kills(place.swarm.sprayable(), place.index))
        if killed:
            self.tally.swatted += killed
            self._record(SPRAY_KILL, count=killed, room=room)

        # Everybody bleeds, found or not. This is the clock, and it is what
        # makes light compete with time rather than with darkness.
        for gone in self.rescue.tick():
            # **In the room they fell in**, which is the point of saying it at
            # all: a follower lost on the walk home died somewhere, and the
            # question the user asks a playtester is where.
            self._record(WORKER_DIED, who=self._index[id(gone)],
                         room=self.places[gone.room].room.name)

        # Freeing somebody starts the hard part: they follow, and they go on
        # bleeding while they do.
        freed = self.rescue.reach(self.here, self.player.occupied_cells())
        if freed is not None:
            self._record(FREED, who=self._index[id(freed)], room=room)
        self.rescue.follow(self.here, self.player.x, self.player.y)
        # Again, because `follow` is what moves a follower through the doorway
        # and a fly on one has to go with them. Twice a frame over six flies is
        # nothing, and the alternative is a window one frame wide in which a fly
        # is riding somebody in the room next door -- during which losing the
        # host would leave it hunting at coordinates that mean somewhere else.
        self._migrate()

        # The exit banks whoever is behind you, and then it ends the run --
        # see `_ending`. Leaving early is safe and cheap in people; going back
        # for one more is the gamble, and after issue #19 it is a gamble with
        # the tail you already have on the table.
        at_door = self.rescue.at_exit(self.here, self.player.occupied_cells())
        for saved in self.rescue.deliver(self.here,
                                         self.player.occupied_cells()):
            self._record(DELIVERED, who=self._index[id(saved)], room=room)
        self.at_exit = at_door
        self._gone_in = self._gone_in or not at_door
        if self.rescue.saved != self.tally.found:
            self.tally.found = self.rescue.saved
            self.panel.set("rescued", self.rescue.saved)

        now_attached = len(self.swarm.on_player())
        if now_attached > was_attached:
            bites = now_attached - was_attached
            self.tally.attachments += bites
            self._record(BITTEN, count=bites, room=room)
        if self.swarm.drained:
            self._record(DRAINED, count=self.swarm.drained, room=room)
        self.tally.frame(self.cone.lit, self.swarm.drained)

        # Death costs a try and puts you back at the entrance. The building
        # carries on regardless: workers you did not reach are still bleeding,
        # and the swarm is where you left it -- **all of it**.
        #
        # This branch used to read `self.swarm.clegs = [c for c in ... if
        # c.state != ATTACHED]`, which deleted every fly that was on you at the
        # moment you died, for the rest of the run. A lit Statue on seed 3 went
        # from six Clegs to three across two deaths and finished with a try in
        # hand, and the gap between the first death and the second was nearly
        # four times the gap before the first, because the room had emptied.
        # **Dying was the cheapest way to make the game easier**, which inverts
        # the bargain the whole design rests on (issue #27). Every measurement
        # taken from a run with a death in it was taken against a depleted
        # swarm.
        #
        # `Swarm.detach` puts them back in the room instead; where they land
        # and why they are fed is argued in `clegs.SCATTER`.
        if self.blood <= 0:
            self.lives -= 1
            self.panel.set("lives", self.lives)
            self._record(LIFE_LOST, count=self.lives, room=room)
            if self.lives > 0:
                self._respawn()

        # **Say the light ran out** (issue #31). A first-timer switches the
        # torch on to see, leaves it on, and goes dark twenty seconds later --
        # and until now nothing said so. The bar has been sliding towards empty
        # the whole time, but a bar you are not looking at is not an event, and
        # the moment it matters is exactly the moment the player is looking at
        # something else in the dark.
        #
        # Swapping onto a fresh spotlight on the same frame is not the torch
        # running out: the bar refills in front of you and the player did that
        # on purpose. The alert is for the thing that happened *to* them.
        was_lit = self.cone.lit
        picked = self.kit.tick(self.player, self.here)
        if picked is not None:
            self._record(SWAPPED, count=self.cone.power, room=room)
        elif was_lit and self.cone.power <= 0:
            self._record(TORCH_OUT, room=room)
            self.panel.alert("light")

        self.panel.set("light", bar_pips(self.cone.power, self.cone_full))
        self.panel.set("lit", self.cone.lit)
        self.panel.set("blood", bar_pips(self.blood, self.blood_full, 8))
        self.panel.tick()

        # You hear them before you see them -- and since a Cleg is only drawn
        # where a light is on it, in the dark this is all you get.
        # **The nearest Cleg in the room you are in.** A distance across a room
        # boundary means nothing, so the room behind you falls silent the
        # moment you leave it -- which is exactly the hole the shouts through a
        # doorway exist to fill.
        self.click = self.sonar.update(
            self.place.swarm.nearest_distance(self.player.cx, self.player.cy))

        self._light()
        ending = self._ending()
        if ending is not None:
            self.finish(ending)
        return self.frame_events

    # --- the doorway --------------------------------------------------------

    def _maybe_cross(self) -> bool:
        """Has the player just walked out of one room and into the next?

        **The world is continuous; only the view jumps.** The transition fires
        when the figure has cleared the threshold entirely -- at x=255 you
        straddle room A's last column and room B's first, and at x=256 you are
        wholly in room B's first column, which is x=0 there. So nothing about
        the walk changes: no snap, no pause, no re-placing.

        Two things come with the player and are the only special cases in the
        whole crossing:

        * **The flies on you.** A Cleg attached to the player rides the player,
          so it has to change swarms when the player does. It is fed, it is
          still draining, and leaving it in the room behind would silently heal
          you every time you used a door.
        * **The opening flash, once.** Fired on first entry to each room and
          never on re-entry -- re-entry is precisely the case where you are
          supposed to be living off what you held in your head, and flashing
          every time would make the fade pointless and hand the building over
          for free.

        The tail is *not* on that list, and that is the whole point of it: the
        trail carries the room each step was taken in, so followers reach the
        doorway in their own time and come out of it one at a time. Nothing
        pulls them through.
        """
        crossed = self.building.cross(self.here, self.player.x, self.player.y)
        if crossed is None:
            return False
        to, x = crossed
        left = self.room
        self.player.x = x
        self.here = to
        self.crossings += 1
        self._record(CROSSED, count=to, room=left)
        self.place.enter()
        # Straight away, not at the end of the frame: a fly on the player has
        # to change swarms with them, or the swarm it left behind ticks a
        # frame with a host who is not in the room.
        self._migrate()
        return True

    def _migrate(self) -> None:
        """Move any Cleg that has ended up somewhere its swarm is not.

        Two ways it happens, and neither is the fly's doing:

        * It **walked through a doorway**. `Room.is_solid` let it step onto the
          column just past the wall, which is the next room's first column, so
          it is standing in a cell this room does not have. It is handed over
          at the same point in the other room's coordinates and its goal is
          cleared, because what it was heading for was the threshold and the
          threshold is behind it now. What it was heading for *originally* --
          the light that lured it -- is offered again by that room's own lures,
          so it carries on rather than losing interest at the door.
        * It is **attached to somebody who crossed**. A fly rides its host, so
          it goes where the host goes. This is the case that would otherwise
          heal the player every time they used a door.
        """
        for place in self.places:
            leaving = []
            for cleg in place.swarm.clegs:
                if cleg.state == clegs_mod.ATTACHED:
                    want = (self.here if cleg.victim is None
                            else cleg.victim.room)
                    if want != place.index:
                        cell = ((self.player.cx, self.player.cy)
                                if cleg.victim is None else cleg.victim.cell())
                        leaving.append((cleg, want, cell, False))
                    continue
                step = self.building.step_across(place.index, cleg.cx, cleg.cy)
                if step is not None:
                    leaving.append((cleg, step[0], (step[1], step[2]), True))
            for cleg, to, cell, forget in leaving:
                place.swarm.clegs.remove(cleg)
                cleg.cx, cleg.cy = cell
                if forget:
                    cleg.goal = None
                self.places[to].swarm.clegs.append(cleg)

    def _respawn(self) -> None:
        """Death costs a try and puts you back where you came in.

        The building carries on regardless: workers you did not reach are still
        bleeding, and the swarm is where you left it -- **all of it**. This
        branch used to delete every fly that was on you at the moment you died,
        which made dying the cheapest way to make the game easier and inverted
        the bargain the whole design rests on (issue #27).

        With two rooms it does one more thing: **it brings the flies that were
        on you back with you.** They are fed and they scatter into the free
        cells around where you land, in the room you land in, which is the room
        the exit is in and not necessarily the one you died in.
        """
        self.blood = self.blood_full
        room = self.places[self.start_room]
        self.here = self.start_room
        self.player.x, self.player.y = self.building.rooms[self.here].player_start
        self._migrate()
        room.swarm.detach(room.room.is_solid)

    def finish(self, reason: str) -> None:
        """End the run, for a reason inside the game or outside it."""
        if self.over is not None:
            return
        self.over = reason
        self._record(GAME_OVER, room=self.room)

    def _ending(self) -> str | None:
        """Has the run ended, and how?

        **Two conditions, and nothing else ends a run** (issue #20): you reach
        the exit, or you lose the last life. The three endings are the same
        three; what changed is what fires them.

        What it removes is `rescue.settled` -- *everybody saved or dead* -- which
        stopped the run on the exact frame the last worker died. That cost three
        things at once, and all three are the reason this issue exists:

        * **A loss could not be felt**, because there was no *after* to feel it
          in. The screen went to a tally on the frame the person died.
        * **A body was never seen.** Bodies were created on the frame the level
          ended, so `rescue.BODY_FRAMES` -- ten seconds in which a flyspray could
          have saved a corpse from becoming a nest -- had never once elapsed on
          screen in the whole life of the prototype.
        * **A player who could not save anybody had no way to leave**, and being
          made to stand in a room you have failed until your blood runs out is
          not an ending, it is a punishment for having lost.

        So the exit is a finish line, not a delivery hatch: *Progression and
        Scoring* says "reach the exit with at least the quota of rescued
        workers", and this is that rule. Arriving with a tail hands them over
        first -- `deliver` runs earlier in `step` -- so the count is right before
        the run is judged. **A player with people still alive and unreachable
        can walk out**, and should be able to; they take the loss with them.

        `_gone_in` is what stops the door being an ending on frame one. The
        prototype's start is a patch of open floor in the middle of the room,
        so today the flag is set on the first frame and changes nothing at all
        -- but *Building Structure* settled on 2026-09-07 that **the player
        starts at the exit, because that is where they came in**, and on the day
        that lands, a door that ends the run on contact ends every run
        instantly. One bit, set the first time you are anywhere else, and the
        door means "back out the way I came" rather than "here I am".

        **Two things this leaves open, both measured and both the vault's to
        settle rather than this method's.** They are written down here because
        the next person to read this code will hit them and should know they
        were seen.

        1. **A door you can leave by is a door you can leave by *accidentally*.**
           A Wanderer -- the bot that models a first-timer's opening minute --
           ends its run in under two seconds on three of twelve seeds, by
           random-walking into the exit with nobody rescued. The exit is about
           a hundred pixels from the start, its sign is permanently lit, and
           nothing asks the player whether they meant it.
        2. **`NOBODY_LEFT` reads "THERE IS NOBODY LEFT TO SAVE / THE REST OF
           THEM BLED TO DEATH", and that is now sometimes untrue** -- a player
           who walks out with four people still alive in there gets told they
           are dead. `ABANDONED` already carries the right words ("YOU LEFT THE
           BUILDING") and is currently unreachable from inside the game.

        Neither is fixed here, because issue #20 says in as many words that the
        three endings do not change and only their triggers do. Both want an
        answer before a stranger plays it.
        """
        if self.lives <= 0:
            return NO_LIVES
        if self.at_exit and self._gone_in:
            return ALL_OUT if self.rescued == self.total else NOBODY_LEFT
        return None

    def _record(self, kind: str, who: int | None = None, count: int = 0,
                room: str = "") -> Event:
        event = Event(self.frame, kind, who, count, room or self.room)
        self.log.append(event)
        self.frame_events.append(event)
        return event

    def _light(self) -> None:
        """Sources contribute, brightest wins, then everything decays.

        Run for **every** room, because the fade keeps running while you are out
        of one and because a room's swarm needs to know who is standing lit in
        it whether or not you are there to see them.

        A source belongs to a room and writes into that room's field, so
        **light does not cross a threshold** and never has to be stopped from
        doing so. Standing in A's doorway you cannot see into B.
        """
        self.shouting = []
        self.door_calls = []
        self.call_cells = []
        for place in self.places:
            here = place.index == self.here
            field = place.field
            field.begin()
            for src in place.fixed:
                src.apply(field)
            if here:
                self.glow.apply(field)
                self.cone.apply(field)
            self.kit.apply(field, place.index)

            # A shout is not a light. It lifts its own cells out of the dark so
            # the word can be read, leaves no memory behind it, and reveals
            # nobody -- so calling out never marks a worker for the swarm.
            calling = (self.rescue.calling(self.frame, place.index)
                       if self.calls_on else [])
            cells = [c for w in calling for c in w.call_cells()]
            if here:
                self.shouting = calling
                # Gated on `calls_on` like every other shout. A switch
                # labelled "workers call for help" that leaves one kind of
                # shouting running is a liar -- the same argument the death
                # beat is held to.
                self.door_calls = (self._calls_through_doors()
                                   if self.calls_on else [])
                cells = cells + [c for run in self.door_calls for c in run]
                self.call_cells = cells
            for cx, cy in cells:
                field.add(cx, cy, lighting.LIT, memory=1, hue=GREEN,
                          reveals=False)
            # The exit sign has its own battery, as they do. It is the one
            # thing in a failing building you can always see -- in the room it
            # is in, which is the near room and no other.
            for cx, cy in place.sign_cells:
                field.add(cx, cy, lighting.LIT, memory=1, hue=RED,
                          reveals=False)
            field.commit()

    def _calls_through_doors(self) -> list:
        """Where a shout from the room next door is written, if there is one.

        **A worker calling in the adjacent room has their call drawn over the
        doorway that connects to it.** The one genuinely new rule in issue #21,
        and it exists because a second room creates a hole the design cannot
        live with: the sonar reports the nearest Cleg **in the room you are in**
        -- it has to, since a distance across a room boundary means nothing --
        so the room behind you falls silent the moment you leave it, and a
        follower being eaten two cells the other side of a wall is invisible
        *and* inaudible. To an audience with no 8-bit fluency that is a number
        going down for no reason.

        It is more load-bearing than when it was written, because a follower
        eaten in the dark turns out to be silent as well as invisible: the sonar
        skips attached flies, so once one has landed there is nothing left to
        hear at all.

        A shout is already the right channel -- a bearing you have to be
        watching for, not a map. It lifts its own cells out of the dark, leaves
        no trace, reveals nobody and draws no Clegs, and all of that holds
        unchanged when the cells it lifts are a doorway's.

        Three limits keep it honest and all three are existing design:

        * **Only the adjacent room carries.** This walks this room's own
          doorways and asks about the room on the other side of each, so a
          third room is two doors away and says nothing. There is no path,
          no search and no propagation.
        * **The call shows the door, not the person.** Four cells on the
          doorway's middle row, anchored so the word covers the gap and reads
          into the room. Where in the far room they are shouting from is not in
          it and must never be.
        * **Calls are rate-limited by blood**, so a room of fresh workers is
          nearly silent and one with somebody nearly gone is not.

        This is also how the door is found. A first-timer sees `HELP` appear
        over a gap in the east wall and understands there are people through
        there -- which is why the door needs no colour of its own.
        """
        runs = []
        word = len(rescue_mod.CALL)
        for door in self.place.room.doorways:
            if not self.rescue.calling(self.frame, door.to):
                continue
            row = door.middle
            left = COLS - word if door.column else 0
            runs.append([(left + i, row) for i in range(word)])
        return runs

    # --- drawing -----------------------------------------------------------

    def draw(self, screen: Screen) -> None:
        """The whole frame: the room, the people, and the status strip."""
        if not self._painted_strip:
            # Painted once and thereafter only where it changes. On a restart
            # this runs again, because the session is new and the strip on
            # screen belongs to the run before it.
            blank_strip(screen)
            self.panel.draw_labels(screen)
            self.panel.draw(screen, force=True)
            self._painted_strip = True

        # The play area is cleared every frame; the strip is not touched.
        screen.clear_rows(PLAY_TOP, PLAY_BOTTOM, PLAY_ATTR)

        # **One room, and only one.** This is the whole of the screen
        # transition: everything below asks the room the player is standing in,
        # so walking through a doorway flicks the view with nothing to animate
        # and nothing to scroll. The room behind you is *gone* rather than dark,
        # which is the moment the second room exists for.
        place = self.place
        field, is_solid = place.field, place.room.is_solid

        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                if is_solid(cx, cy):
                    screen.fill_cell_pixels(cx, cy, on=True)

        # Lit floor is stippled, denser when fully lit. Without this the light
        # has no visible shape -- it only reveals what it falls on.
        floor.draw(screen, field, is_solid)

        # Sprites set pixels only. Their colour comes from whichever cells they
        # happen to be standing in.
        for spr, sx, sy in place.fixtures:
            sprites.draw(screen, spr, sx, sy)
        # People are only drawn where a light is on them, and only if they are
        # in this room. A body is not a person any more: it is part of the
        # building, and the fade may remember it -- and it stays where it fell,
        # in the room it fell in.
        for body in self.rescue.bodies(self.here):
            sprites.draw(screen, sprites.BODY, body.x, body.y + CELL)
        for worker in self.rescue.alive_waiting(self.here):
            sprites.draw(screen, sprites.WORKER, worker.x, worker.y,
                         visible=field.reveals_at)
        for worker in self.rescue.tail:
            if worker.room == self.here:
                sprites.draw(screen, sprites.WORKER, worker.x, worker.y,
                             visible=field.reveals_at)
        for cleg in place.swarm.clegs:
            sprites.draw(screen, sprites.CLEG, cleg.cx * CELL, cleg.cy * CELL,
                         visible=field.reveals_at)
        sprites.draw(screen, sprites.PLAYER, self.player.x, self.player.y)

        for i, (cx, cy) in enumerate(place.sign_cells):
            font.draw_glyph(screen, cx, cy, font.GLYPHS[scene.EXIT_SIGN[i]])

        # "HELP", above the head of anybody shouting. Drawn whatever the light
        # is doing, because it is a voice and not a sighting.
        for worker in self.shouting:
            for i, (cx, cy) in enumerate(worker.call_cells()):
                font.draw_glyph(screen, cx, cy, font.GLYPHS[rescue_mod.CALL[i]])
        # ...and over the doorway, for anybody shouting in the room the other
        # side of it. The same word, in the same green, saying **the door and
        # not the person**.
        for run in self.door_calls:
            for i, (cx, cy) in enumerate(run):
                font.draw_glyph(screen, cx, cy, font.GLYPHS[rescue_mod.CALL[i]])

        # Sprayed ground gets its own droplet pattern and its own hue. Hue is
        # per-cell, so this does not disturb the clash guarantee.
        frame_inks = bytearray(place.inks)
        for cx, cy in self.call_cells:
            frame_inks[cy * COLS + cx] = GREEN
        for cx, cy in place.sign_cells:
            frame_inks[cy * COLS + cx] = RED
        for cx, cy in self.spray.cells_in(self.here):
            for dy, bits in enumerate(spray_mod.STIPPLE):
                for dx in range(CELL):
                    if bits & (0x80 >> dx):
                        screen.plot(cx * CELL + dx, cy * CELL + dy)
            frame_inks[cy * COLS + cx] = CYAN

        # Light decides brightness, contents decide hue. This overwrites every
        # play-area attribute, so it must come after the drawing.
        field.paint(screen, frame_inks)
        self.panel.draw(screen)
