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
    building as building_mod, buzz, clegs as clegs_mod, floor, font, lighting,
    moments as moments_mod, player as player_mod, rescue as rescue_mod,
    scene, screens, sounds, sources, spray as spray_mod, sprites,
    tally as tally_mod, tiles, tune as tune_mod, seeds,
)
from .building import EAST
from .layout import PLAY_BOTTOM, PLAY_TOP, PLAY_ROWS, STRIP_BOTTOM, STRIP_TOP
from .lighting import LightField
from .panel import Panel, bar_pips, blank_strip
from .player import Player

PLAY_ATTR = attr_byte(ink=WHITE, paper=BLACK, bright=False)

#: Blood, as points. Shown as eight pips, so each pip is a Cleg's worth: one
#: attachment takes exactly one bar. A number small enough that the player can
#: count what a swarm cost them.
BLOOD_FULL = 64

#: How long the player has to keep walking into the doorway before the building
#: lets them out (issue #28). Half a second.
#:
#: **The exit delivers on touch; leaving is a separate act.** A brush against
#: the door banks whoever is behind you and costs nothing, and only a sustained
#: walk *into* it ends the run -- so the way out stops being a trapdoor a
#: first-timer falls through in the opening seconds, and going back in for one
#: more becomes possible at all. *Progression and Scoring* calls that decision
#: the game.
#:
#: The number is this file's rather than the vault's: the vault says "sustained"
#: and leaves the frames to whoever can measure them. Half a second is longer
#: than any brush past the door and shorter than the deliberate act of walking
#: out of a building, and it is one held direction rather than a prompt or a
#: second button -- the game has neither to spare.
LEAVE_FRAMES = 25

#: How long the player is a Cleg magnet after the searchlight's beam is on
#: them (issue #82, *The searchlight magnet*): ten seconds, the user's number,
#: and the only number on that page that was given. A hit sets it, never adds
#: to it, so the ten seconds run from the last sighting. Since issue #118 the
#: level authors the seconds (`magnet:` in the level block, ten on Level 3);
#: this is the constant's frames per second of it.
MAGNET_FRAMES = 500
FRAME_RATE = 50

#: The strobe a level opens on (issue #94): the whole room lit for `STROBE_ON`
#: frames, dark for `STROBE_OFF`, `STROBE_FLASHES` times, with the game held.
#: One frame is the briefest flash the machine has -- twenty milliseconds --
#: and the user asked for five, so it is one. Nothing the flash shows is
#: remembered: its light has a memory of nought.
STROBE_ON = 1
STROBE_OFF = 5
STROBE_FLASHES = 3
STROBE_FRAMES = (STROBE_ON + STROBE_OFF) * STROBE_FLASHES
#: Two seconds of the play area completely black on either side of the
#: strobe (issue #95): built from no source at all, so not even the things
#: that never fade are there. The whole opening is held, frame counter at
#: nought.
OPENING_BLACK = 100
OPENING_FRAMES = OPENING_BLACK + STROBE_FRAMES + OPENING_BLACK
#: Where the logo sits on the opening's black (issue #97): its two cell rows
#: centred in the twenty-two of the play area.
OPENING_LOGO_TOP = (PLAY_ROWS - 2) // 2

#: The magnet's tell, in frames on and then off (issue #84, the box since
#: #100): the mark round the player's figure is drawn for this many frames
#: in every twice this many. Eight is a pulse three times a second -- slow enough to read as
#: a thing being tracked, fast enough not to be missed.
MAGNET_PULSE = 8

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
#: Walked out with **nobody living left inside**: some of them died, and there
#: was nothing still in there to go back for.
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
    # **Somebody living was still in there when you walked out** (issue #28).
    # Telling that player the rest of them bled to death is not a wrong screen,
    # it is a lie -- so this ending says what they actually did.
    ABANDONED: ("YOU LEFT THE BUILDING",
                "SOME OF THEM ARE STILL ALIVE"),
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
# `SWAPPED` and `TORCH_OUT` went with the torch (issue #119): the carried
# cone, the floor lamps it was swapped for, and the twenty seconds it lasted
# are no longer in the game.
#: The player stepped through a doorway (issue #21). `count` is the room they
#: arrived in, `room` the room they left. It is logged because a second room is
#: only worth having if people go into it, and "did a first-timer ever find the
#: door" is the first question the playtest asks -- target T10 is stated in it.
CROSSED = "crossed"
#: The searchlight's beam found the player and the room was told (issue #82).
#: On the rising edge only: a player standing in the beam is hit every frame
#: and logs one event. The log moves on purpose; `--no-magnet` is the pin.
MAGNET = "magnet"
GAME_OVER = "game_over"

# --- the body's lifecycle (issue #33) ---------------------------------------
# Five kinds, because a nest is the only thing in the game with a life of its
# own and every stage of it is a thing the playtest wants to be able to count.
# The whole of T11, T12 and T13 is stated in these and in nothing else.

#: A spray charge saved a body inside its window. `who` is the person it was.
DOUSED = "doused"
#: A body nobody reached has become a nest.
NEST_TURNED = "nest_turned"
#: A nest placed one of its six. `count` is how many it has placed in all.
HATCHED = "hatched"
#: A nest burnt out, or a doused body finally went. Nothing is drawn after it.
NEST_BURNT = "nest_burnt"
BODY_GONE = "body_gone"
#: **The valve held a spawn** rather than dropping it. `count` is how many
#: nests were live in the building at the time, which is the number target T13
#: is stated in: a hold with fewer than three nests live means the level is
#: over-populated and the editor should have refused it.
VALVE_HELD = "valve_held"


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
    requirement); the spray is edge-triggered, because holding the key down
    should not empty the can. Whoever builds the intent decides which is
    which -- the session only obeys. Four directions and one button, since
    the torch went (issue #119): every joystick the machine ever had.
    """

    __slots__ = ("dx", "dy", "spray")

    def __init__(self, dx: int = 0, dy: int = 0, spray: bool = False) -> None:
        self.dx, self.dy = dx, dy
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
                vary=room.searchlight.vary, seed=beam_seed,
                is_solid=room.is_solid, step_every=room.searchlight.pace)
            self.roaming.mount = room.searchlight.mount
        #: One byte per cell, non-zero where the room is solid, for the
        #: `--wall-fade` experiment (issue #117).
        self.solid_mask = bytes(
            1 if room.is_solid(cx, cy) else 0
            for cy in range(PLAY_ROWS) for cx in range(COLS))
        self.swarm = clegs_mod.Swarm(clegs)
        self.sign_cells = room.exit_sign_cells(scene.EXIT_SIGN)
        #: Where the room's gratings are (issue #74): floor cells that draw a
        #: grille instead of the stipple. Fixed by the map, so read once here
        #: rather than asked per floor cell per frame.
        self.grating_cells = frozenset(room.cells_of(building_mod.GRATING))
        self.fixtures = [(sprites.SPRITES[name], x, y)
                         for name, x, y in scene.ENTITIES
                         if name not in scene.MOVERS]
        for cx, cy in room.cells_of(scene.KEY):
            self.fixtures.append((sprites.KEY, cx * CELL, cy * CELL))
        # **The way out, drawn as a door** (issue #49). A `D` cell is floor in
        # every mechanical respect, so until now the exit was four magenta
        # stipple dots per cell -- the loudest object in the game and the
        # hardest to see. It is 8x16 because it is the person-shaped hole you
        # walk out through, and `exit_cell` is the top of it, so one sprite
        # covers the two-cell opening a person fits through.
        #
        # Drawn open, because nothing in this building is locked. When a locked
        # door exists it takes `sprites.DOOR_LOCKED` and the hue of the key
        # that opens it; the pair differs in outline rather than in fill,
        # which is the whole point of the redraw.
        if room.has_exit:
            ex, ey = room.exit_cell()
            self.fixtures.append((sprites.DOOR_OPEN, ex * CELL, ey * CELL))

        #: The whole room lit, for the `F` key, the gallery and the tests --
        #: **a debug view and never a mechanic** (issue #79). Until 2026-09-14
        #: this was the opening flash, twelve frames of the room on first
        #: entry; the user ruled that no room is ever shown whole, so nothing
        #: in play switches it on.
        self.floodlight = sources.Floodlight()
        #: The strobe's light (issue #94): the room whole, for one frame at a
        #: time, remembered not at all. Held on and off by `Session.step`
        #: while the strobe runs and never otherwise.
        self.strobe = sources.Floodlight(memory=0)
        self.seen = False

    @property
    def housing(self) -> "tuple[int, int] | None":
        """Where this room's searchlight is bolted, or None if it has none.

        **Not a light, and it must never become one.** `_light` holds the cell
        lit with a direct write into the field, `reveals=False`, exactly as it
        does the exit sign's; `draw` puts the housing sprite on it. A
        `sources.Source` here would be a new permanent lure at the corner the
        beam is mounted on, which changes what the swarm does -- and it would
        show up first in the `blood_by_*` figures, which is where a test looks
        for it.

        Read from the light each time rather than kept, because a varying beam
        takes a new corner with each circuit and **the housing moves with it**.
        A room without a searchlight has none, so its absence is authored
        rather than ambiguous -- which is what went wrong when a player read
        the far room as broken.
        """
        return None if self.roaming is None else self.roaming.housing

    @property
    def fixed(self) -> tuple:
        """The lights that belong to this room, wherever the player is."""
        lit = [self.floodlight, self.strobe, *self.room_lights]
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
        return first


class Session:
    """A run: the building, the people in it, the swarm, and how it ended."""

    def __init__(self, seed: int = DEFAULT_SEED,
                 blood: int | None = None, lives: int | None = None,
                 metrics: bool = False,
                 sound: bool = True, magnet: bool = True,
                 luminous: bool = True, trail: bool = False,
                 strobe: bool = False, building=None,
                 start_room: int | None = None, wall_fade: int = 1) -> None:
        self.seed = seed
        #: Two looks the user tried and ruled on (issue #91, then #92), both
        #: now the default. `luminous`: Clegs are drawn wherever they are,
        #: lit or not, **and their cells wear red** -- a dark cell is black
        #: ink on black paper, so pixels alone showed nothing, which is what
        #: the first cut got wrong. `trail` off: the player's own glow
        #: leaves no memory, so the floor and the walls behind you go
        #: dark the frame after you pass. It reaches the rules -- a body
        #: waits on remembered ground, a scout maps what it has seen -- and
        #: the log moved with it, recorded. `--dark-clegs` and `--trail` put
        #: the old looks back for comparison.
        self.luminous = luminous
        self.trail = trail
        #: `--wall-fade N` (issue #117): 1 is the fade as it is, three
        #: seconds of wall memory behind the beam; 2 tops every remembered
        #: wall cell up by one on even frames, so it fades at half rate and
        #: lasts six. An experiment for the keyboard, not a level key.
        self.wall_fade = wall_fade
        #: **A run takes a building** (issue #108). Left out, it is the one
        #: `scene` shows, which is Level 3; given, it is whatever the driver
        #: loaded -- another level, or one room of one on its own
        #: (`Building.solo`). `start_room` starts the player in that room at
        #: *its* start, so a room deep in a level can be played from its own
        #: door. Everything below reads `self.building` and nothing reads
        #: `scene`, and the same goes for the bots.
        if building is None:
            scene.validate()
            building = scene.BUILDING
        else:
            building.validate()
        self.building = building

        # Every random thing in the run is derived from the one seed, so a seed
        # names a run -- and, since issue #116, **one seed per stream and per
        # room**. Before, one `beam_seed` served every searchlight in the
        # building, so they all entered at the same station and walked the
        # same tour on the same frames, and the same run seed gave the same
        # entry on every level. Now the run seed and the level make a level
        # seed, and each stream -- the roll (issue #120), the flies, each
        # room's beam, the brood -- takes its own from a tag. All of it the
        # xorshift the Z80 will run.
        level_seed = seeds.level_seed(seed, self.building.level)
        self.roll_seed = seeds.stream(level_seed, seeds.ROLL_TAG)
        cleg_seed = seeds.stream(level_seed, seeds.CLEG_TAG)
        beam_seeds = [seeds.stream(level_seed, seeds.BEAM_TAG + i)
                      for i in range(len(self.building))]

        #: Which room the player is standing in. **The whole of the screen
        #: transition**: `draw` paints this room and no other, so stepping
        #: through a doorway flicks the view. Nothing else about a room change
        #: is special-cased anywhere in the game.
        if start_room is None:
            start_room = self.building.start[0]
        elif self.building.rooms[start_room].player_start is None:
            raise ValueError(
                f"{self.building.rooms[start_room].name} has no start")
        self.here = self.start_room = start_room
        self.player = Player(*self.building.rooms[start_room].player_start)
        #: **Where this run is**, for the ending screen and the report (issue
        #: #109): "Level 3 Rescue", and the room after it when the run began
        #: somewhere other than the level's own start room, or is one room
        #: on its own. Empty for a building built by hand, which has no level
        #: to name.
        self.where = ""
        if self.building.level is not None:
            self.where = f"Level {self.building.level} {self.building.title}"
            if start_room != self.building.start[0] or len(self.building) == 1:
                self.where += f", {self.building.rooms[start_room].name}"
        # No trail: a memory of nought, so the cell shows the light's level
        # while the light is on it and is not topped up at all -- the frame
        # after, it is whatever the fade already had there.
        self.glow = sources.Glow() if trail else sources.Glow(memory=0)
        self.glow.x, self.glow.y = self.player.cx, self.player.cy
        #: **The level authors the budget** (issue #115): starting blood,
        #: spray charges and lives are the building's `Budget`, and `blood`
        #: and `lives` given to the constructor override it (a test that
        #: wants ninety-nine lives still gets them).
        #:
        #: **There is no torch** (issue #119, the user's ruling). The carried
        #: cone was pressed once and burned out at twenty seconds in every
        #: lit bot's run, was billed 0-8 blood a run against the magnet's
        #: 58-162, and no human used it; the floor lamps it was swapped for
        #: only ever lit under it. What lights a room is the beam, which
        #: since #117 leaves the walls it passes in memory; what the player
        #: carries is the glow, with a nose. One button: the spray.
        budget = self.building.budget
        self.spray = spray_mod.Spray(charges=budget.spray)
        #: How long a hit keeps the magnet on (issue #118): the level's
        #: seconds, ten on Level 3 as the rule was made.
        self.magnet_frames = budget.magnet * FRAME_RATE

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
            self.places.append(Place(i, room, flies, beam_seeds[i]))
        #: **The never list's rule 4** (issue #116): the beam in the room the
        #: player begins in never opens on the start. `Roaming.safe_entry`
        #: walks the route and moves the entry station on until the first ten
        #: seconds keep off the feet cell; how far it moved is kept for the
        #: record. Only the start room: every other room's beam is already
        #: running when the player arrives, which is what the spill is for.
        self.entry_moved = 0
        beam = self.places[self.start_room].roaming
        if beam is not None:
            self.entry_moved = beam.safe_entry((self.player.cx, self.player.cy))
        #: Every swarm in the building, read as one. See `clegs.Swarms`: the
        #: counters are the building's because a fly that walked through a
        #: doorway is the same fly.
        self.swarm = clegs_mod.Swarms([p.swarm for p in self.places])
        #: The building's searchlights, and the one the debug keys reach for.
        #: There is exactly one -- room A's -- and room B authors none, which is
        #: the point of room B.
        self.searchlights = [p.roaming for p in self.places
                             if p.roaming is not None]
        self.blood = blood if blood is not None else budget.blood
        self.blood_full = self.blood
        self.lives = lives if lives is not None else budget.lives
        self.sonar = buzz.Sonar()
        #: **What the speaker actually did this frame, not what was wanted**
        #: (issue #54). It used to mean *the sonar's counter came due*, and the
        #: host played a click on it; since the fourteen effects arrived there
        #: is one voice for all of them and a click that lands inside a running
        #: effect is dropped. The counters are still the only thing that
        #: decides *when* -- see `sounds.Voice.update` -- and they are never
        #: told the answer, because a counter that restarted on a drop would
        #: make the sonar's rate mean something other than distance.
        self.click = False
        #: The body's tick, and the body it is about (issue #33). Two clicking
        #: voices and one beeper: at most one of `click` and `tick` is ever
        #: true on a frame, and neither is true while an effect is sounding.
        self.ticker = buzz.Ticker()
        self.tick = False
        self.ticking = None
        #: The one speaker (issue #54): the sonar, the body's tick and the
        #: fourteen effects, arbitrated in one place. **It decides nothing
        #: about the run** -- no rule reads it, no counter is reset by it, and
        #: the event log of a run is byte-identical with it and without it,
        #: which is what `sound=False` exists to prove rather than to offer as
        #: a setting anybody should want. With no voice the game is silent: the
        #: alternative would be a second copy of the arbitration order living
        #: in the session, which is the drift this slice exists to end.
        #: **The siren, from the first frame of a run** (issue #67; the
        #: ostinato it replaced was issue #55). The theme belongs to the title
        #: screen and the ending screen is silent, so this is the only tune
        #: the session ever starts -- and it is handed to the voice rather
        #: than kept beside it, because *music is the bottom of the
        #: arbitration order* has to be one object's rule or it is nobody's.
        #: It opens on the wail, as the sketch the user ruled on did; a start
        #: offset so a run opens in the rest is one integer and is not
        #: settled.
        self.voice = (sounds.Voice(tune_mod.Music(tune_mod.SIREN))
                      if sound else None)
        #: Where the next hatchling's temperament comes from. Its own chain,
        #: run on from the starting swarm's, so no fly in the building shares a
        #: seed with another and a brood is as varied as an authored swarm.
        self._brood_seed = seeds.stream(level_seed, seeds.BROOD_TAG)
        # The mains surge's schedule was seeded here, as the last link in the
        # chain after the Cleg, beam and brood seeds -- placed last precisely
        # so that removing it would move nothing upstream. It was removed on
        # 2026-09-14 (issue #79): the building plan is never shown.
        #: How often the valve has held a spawn, and the most nests that have
        #: ever been live at once. Target T13 is stated in both.
        self.valve_holds = 0
        self.most_nests = 0
        #: The most bodies and nests one room has held at once. **Watched
        #: rather than asserted** (issue #36): this number used to be a comment
        #: in `building.py` quoting a sample, the sample was wrong, and the
        #: lesson was that a count belongs in the report where it goes on being
        #: taken. `Building.most_fixtures` is the bound it has to stay under.
        self.peak_fixtures = 0

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
        #: The fourteen moments (issue #52): a flash, a pause and a sound id
        #: for the things that happen. **It decides nothing.** Every moment is
        #: raised beside the event that already knew the thing had happened, no
        #: moment writes to the light field, and the pause on the two endings
        #: and the death is owed to the *shell* and never acted on here -- see
        #: `moments.Moments.pause` for what honouring it in the session would
        #: do to every event log in the project.
        self.moments = moments_mod.Moments()

        #: How many cells change light level per frame, or `None` when nobody
        #: asked (issue #46). **Off in the game and on in the driver**, and off
        #: means off: the counter is not built, the wall maps are not built,
        #: and `step` never enters the counting path. A port carries no metrics
        #: counter, so neither does a run that is being played rather than
        #: measured.
        self.repaint = lighting.Repaint() if metrics else None
        #: A wall map per room, for splitting those changes into wall and
        #: floor. Built here rather than per frame because the rooms are ROM
        #: and a wall never moves -- and built only when something is counting.
        self._wall_maps = ([place.room.solid_map() for place in self.places]
                           if metrics else None)

        self.panel = Panel()
        self.panel.set_total("rescued", len(self.rescue.workers))
        # The badges before the first stepped frame (issue #97): the opening
        # holds the game for four seconds with the strip showing, and "?0"
        # to find on it was a lie for the length of it.
        self.panel.set("left", len(self.rescue.alive_waiting()))
        # The light bar's opening value is computed, not authored. It was the
        # literal 4 -- which was right only for the old building-wide scale,
        # and was the number a player actually saw before their first keypress
        # (issue #38). A hand-written starting value is a second place for the
        # gauge to be wrong in, so there is no longer one.
        for name, value in (("blood", 8),
                            ("spray", self.spray.charges), ("keys", 0)):
            self.panel.set(name, value)
        self.panel.set("lives", self.lives)
        # The level's number where the light bar was (issue #119). A
        # building with no level draws nothing there.
        self.panel.set("level", self.building.level or 0)
        self.panel.set("rescued", 0)

        self.frame = 0
        #: Is the player touching the way out right now, and have they ever not
        #: been? Both are read only by `_ending`, which explains them.
        self.at_exit = False
        #: Frames spent walking into the doorway. `LEAVE_FRAMES` of it is the
        #: way out; anything less is standing in the door with a decision to
        #: make, which is what issue #28 exists to give back.
        self.leaving = 0
        #: Which way is out, as a direction to hold. Read once: it is authored
        #: level data and on the Z80 it is two bytes of ROM.
        self.exit_facing = self.building.exit_facing
        self._gone_in = False
        #: Whether the searchlight magnet is wired in (issue #82). Off, the
        #: run is byte-identical to the tree before the rule, which is the
        #: pin; nothing in play switches it.
        self.magnet_on = magnet
        #: Frames the player is still a Cleg magnet for. Set to
        #: `MAGNET_FRAMES` by a hit, counted down one per stepped frame,
        #: cleared by a death and kept through a doorway.
        self.magnet = 0
        #: Frames of the opening strobe still to run (issue #94). While it
        #: runs the game is held: `step` reads no intent and advances no
        #: frame, so the log cannot see it. **Off unless asked for**: the
        #: strobe is the window's opening, and the shell and the demo ask;
        #: a session driven directly -- the driver, the gallery, every test
        #: -- starts at frame one, as it always did.
        self.strobe = OPENING_FRAMES if strobe else 0
        #: Whether the held frame being drawn is a flash (issue #97): the room
        #: without its flies, rather than black with the logo.
        self._flashing = False
        self.over: str | None = None
        self.calls_on = True
        self.log: list[Event] = []
        self.frame_events: list[Event] = []
        self.shouting: list = []
        #: Cells a call is being drawn over the doorway of, this frame: one run
        #: of them per doorway that has somebody shouting the other side of it.
        self.door_calls: list[list[tuple[int, int]]] = []
        self.call_cells: list[tuple[int, int]] = []
        #: The four cells of each shout in the room on screen, as `_light`
        #: placed them. `draw` paints these rather than asking again -- see
        #: `_light`.
        self.shout_runs: list[list[tuple[int, int]]] = []
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

    # `field`, `inks`, `room_lights`, `floodlight`, `sign_cells` and `fixtures`
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
    def floodlight(self):
        return self.place.floodlight

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
        return (self.glow, *self.place.fixed)

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

    def beam_on_player(self) -> bool:
        """Is the searchlight's beam on the player's feet cell this frame?

        The hit test of *The searchlight magnet* (issue #82), and it is
        geometry rather than a field read: the room's `Roaming` source,
        enabled and burning at `LIT`, and the feet cell inside its disc by the
        same squared-distance inequality `Roaming.emit` lights by -- so a
        player on the disc's edge is hit exactly where the floor under them
        is lit, and there is no frame of lag. Only the beam counts: not a
        room light, the glow, the housing or the debug floodlight, none of
        which give you away to anything that was not already looking. (Nor
        the cone or a floor lamp, while there were any.)
        """
        beam = self.place.roaming
        if beam is not None and beam.enabled and beam.level >= lighting.LIT \
                and beam.covers(self.player.cx, self.player.cy):
            return True
        # **The spill counts** (issue #116): a player standing in doorway
        # cells the far room's beam covers is as lit, and as found, as one
        # standing in that beam.
        for door, other in self._spilling(self.place):
            if self.player.cx == door.column and self.player.cy in door.rows \
                    and other.covers(door.landing, self.player.cy):
                return True
        return False

    def _spilling(self, place):
        """The doorways of `place` whose cells the room beyond's beam can
        reach: `(doorway, that beam)` pairs. The beam beyond is asked about
        the landing column, which is the same cells seen from its side."""
        out = []
        for door in place.room.doorways:
            other = self.places[door.to].roaming
            if other is not None and other.enabled \
                    and other.level >= lighting.LIT:
                out.append((door, other))
        return out

    def _magnet_cell(self, place: Place):
        """What this room's hunting flies are handed while the magnet runs.

        The player's cell in the player's room. In any other room, **the cell
        just past the doorway that leads to the player's room**, in this
        room's own coordinates (issue #88): the fly walks to the door by the
        ordinary greedy step, is handed over by `_migrate` when it crosses,
        and takes the player's cell on the other side. No reach test in either
        room -- the magnet pulls the whole building. A room with no doorway to
        the player's room is handed nothing, which never happens with two.
        """
        if not self.magnet:
            return None
        if place.index == self.here:
            return self.player.cx, self.player.cy
        for door in place.room.doorways:
            if door.to == self.here:
                return door.beyond, door.middle
        return None

    def _magnetise(self) -> None:
        """Count the magnet down, and set it if the beam is on the player.

        Once a frame, after the searchlights have moved and before any swarm
        ticks. **A hit sets the counter to `MAGNET_FRAMES` and never adds to
        it**: a player standing in the beam is hit on every frame and the ten
        seconds run from the last sighting. The event and the moment are
        raised on the rising edge only -- the frame the counter leaves zero.
        With `magnet_on` off nothing here runs, and the run is the tree
        before the rule.
        """
        if not self.magnet_on:
            return
        if self.magnet:
            self.magnet -= 1
        if not self.beam_on_player():
            return
        if not self.magnet:
            self._record(MAGNET)
            self._moment(moments_mod.M_MAGNET)
            # **And the building wakes** (issue #88): every sated fly in every
            # room hunts again, on the rising edge and not on the frames after
            # it -- see `Swarm.wake` for why once. Since issue #118 the level
            # says whether: Levels 1 and 2 let the sated sleep.
            if self.building.budget.wake:
                for place in self.places:
                    place.swarm.wake()
        self.magnet = self.magnet_frames

    def _lit_people(self, place: Place) -> list:
        """Everybody in one room, except the player, who is **plainly lit**.

        The swarm's prey list (issue #19). Three things it is careful about:

        * **It is the same light that decides whether a person is drawn, one
          step stricter** -- `LightField.prey_at` beside `draw`'s
          `reveals_at`: a person a *lit* light is on, not one merely glimpsed
          in your own dim glow. So *if you can see them, so can the flies*,
          and the player is never surprised by a rule they cannot observe.
          Room lights are excluded by `prey_at` itself and deliberately: they
          show the room and not who is in it, to Clegs exactly as to the
          player. **And since issue #64 the two read different flags**, so the
          held debug view can be the one exception, in the safe direction: it
          shows everybody and hands nobody over. This list is what the swarm
          reads, and the held view does not change it. (The opening flash was
          the exception's first user, until issue #79 removed it.)
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

        The room's own fixtures and -- only if the player is in it -- the
        player's glow. **A light belongs to a room**, which is the same rule
        that stops light crossing a threshold, applied to the other half of
        the bargain.
        """
        lures = [p for p in (src.lure() for src in place.fixed) if p is not None]
        if place.index == self.here:
            lures += [p for p in (self.glow.lure(),) if p is not None]
            if self.magnet:
                # The magnet, offered as a lure so that the room next door
                # sees it as door spill exactly as it saw the torch
                # (issue #82). This room's own hunting flies never compare
                # it: `Swarm.tick` hands them the cell directly.
                lures.append((self.player.cx, self.player.cy, sources.FAR,
                              sources.LURE_MAGNET))
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

    def _held_beyond(self, place: Place, arriving: bool = True):
        """The personal-space rule, seen through this room's doorways.

        Returns what `Swarm.tick` takes as `held_beyond`: is the cell (cx, cy),
        near this room's edge or past it, ground a free fly of the room next
        door is standing on -- or, since issue #66, beside? A swarm's own
        `taken` set is its own flies and nothing else's, and a fly stepping
        through a doorway lands in another room's grid -- so until issue #65
        the step onto the threshold was the one step the rule did not see. It
        landed on a fly the far room's light had already pinned at (0, 11),
        and then both were pinned there.

        **One translation, both ways**, because the world is continuous and
        only the view jumps (`Doorway.rows`): a room's grid carries on into
        the next room's at column `COLS`, so a fly next door is at
        `(cx + COLS, cy)` seen from here through an east door and
        `(cx - COLS, cy)` through a west one. That puts the fly *leaving* --
        on column -1 or `COLS`, the landing next door -- and the fly
        *arriving* -- on this room's own edge column, still in its old swarm
        at its old coordinates until the hand-over at the end of the frame
        (`_migrate`) -- into the same numbers the swarm's own `taken` uses,
        and one Chebyshev compare answers on, beside, or neither. Before #66
        these were two hand-written cases; the widened rule needed the ring
        round both, and the translation is shorter than the cases were.

        Only flies within a column of the wall are listed -- on the
        threshold, on the landing, or one cell in from the landing, which is
        beside the threshold a fly from here steps onto. Anything further in
        is two cells from anything here, and the wall stands between
        everything but the doorway rows.

        **The exemption is the swarm's, made across the wall**: a step onto
        the player's cell next door is never refused (several flies may feed
        at once, as at home, `Swarm._elbow_room`), and a step *beside* a fly
        next door is not refused when it lands on or beside prey -- in either
        room, since the haven a step is arriving in may be this room's
        (`Swarm._haven`). Both havens are built only when a neighbour is
        actually found, which is the rare path.

        A fly next door is *free* if it is not attached; the rule in
        `_elbow_room` is the same. It is a list walk of the other room's
        swarm on every call, as it was -- nothing is cached across calls,
        because the tests move a fly and ask again -- and it runs only when
        the swarm asks, which is only near the edge.

        **`arriving=False` is the same question for a fly being placed
        rather than stepped** -- `Swarm.detach`, the scatter off a player who
        bled out (issue #69). The two translations are the whole of what a
        scatter needs from here and the reason it reuses this rather than a
        second copy of them; what it does not need is either exemption, both
        of which are about arriving at prey: a scattering fly is leaving a
        body. So the player's cell next door is not waived -- nobody arrives
        on the player by dying -- and the ring is not asked about at all,
        because a scatter keeps no personal space at home (`clegs.SCATTER`
        puts flies beside each other on purpose) and a rule kept only
        through a wall is one nobody could state. The cell itself, held by a
        free fly next door, is refused; that is the hole and the whole of it.
        """
        room = place.room

        def haven_of(index: int, shift: int) -> frozenset:
            """The cells round prey in room `index`, seen from here."""
            other = self.places[index]
            player = ((self.player.cx + shift, self.player.cy)
                      if index == self.here else None)
            prey = {(x + shift, y) for x, y in
                    clegs_mod.Swarm.prey_cells(self._lit_people(other))}
            return clegs_mod.Swarm._haven(player, prey)

        def held(cx, cy):
            for door in room.doorways:
                shift = COLS if door.side == EAST else -COLS
                wall = ((COLS - 1, COLS, COLS + 1) if door.side == EAST
                        else (-2, -1, 0))
                other = self.places[door.to]
                if (arriving and door.to == self.here
                        and (cx, cy) == (self.player.cx + shift,
                                         self.player.cy)):
                    return False
                cells = [(c.cx + shift, c.cy) for c in other.swarm.clegs
                         if c.state != clegs_mod.ATTACHED
                         and c.cx + shift in wall]
                if (cx, cy) in cells:
                    return True
                if not arriving:
                    continue
                if clegs_mod._beside_any(cx, cy, cells):
                    return ((cx, cy) not in haven_of(door.to, shift)
                            and (cx, cy) not in haven_of(place.index, 0))
            return False

        return held

    # --- one frame ---------------------------------------------------------

    def step(self, intent: Intent = IDLE) -> list[Event]:
        """Advance one frame. Returns what happened on it.

        The order is the order the spike's loop ran in, and some of it matters:
        the spray is acted on before the player moves, because that is the
        frame the key was pressed on; lighting is rebuilt last,
        because the shout and the exit sign are added to it after every source
        has had its say.
        """
        if self.over is not None:
            return []
        if self.strobe:
            # **The opening** (issues #94, #95): two seconds of black, three
            # one-frame flashes of the whole room five dark frames apart,
            # two seconds of black, then play -- the game held throughout.
            # The frame counter does not move, no intent is read, no fly
            # steps and nobody bleeds; the light is rebuilt for the phase and
            # that is the frame. Black is the field built from no source at
            # all; a flash is the strobe's light and a crack of noise.
            self.strobe -= 1
            gone = OPENING_FRAMES - self.strobe - 1
            self.frame_events = []
            self.moments.begin()
            flashing = False
            if OPENING_BLACK <= gone < OPENING_BLACK + STROBE_FRAMES:
                within = gone - OPENING_BLACK
                flashing = within % (STROBE_ON + STROBE_OFF) < STROBE_ON
                if flashing:
                    self._moment(moments_mod.M_STROBE)
            self.place.strobe.hold(flashing)
            self._flashing = flashing
            # Black between the flashes too: the strobe is three frames of
            # the room on black, not three frames of the room on the glow.
            self._light(held=True, black=not flashing)
            if self.voice is not None:
                self.voice.update(False, False, self.moments.sounds(),
                                  self.sonar.interval, self.ticker.interval,
                                  clegs=len(self.place.swarm.clegs))
                self.click = self.tick = False
            if not self.strobe:
                # The last held frame: put the building back exactly as frame
                # nought left it -- the strobe off, and every field's display
                # rebuilt from its untouched charge with nothing shining -- so
                # that the first stepped frame is the first stepped frame, and
                # a bot reading the light on it reads what it always read.
                self.place.strobe.hold(False)
                for place in self.places:
                    place.field.begin()
                    place.field.commit(decay=False)
                # And nothing a held frame worked out is left lying about:
                # a shout list read by a bot on the first stepped frame moved
                # its first decision by a frame.
                self.shouting, self.door_calls = [], []
                self.call_cells, self.shout_runs = [], []
                self._flashing = False
            return self.frame_events
        self.frame += 1
        self.frame_events = []
        # Before anything can raise one, so a moment raised on this frame gets
        # every frame of its flash. It ages the flashes and clears the list of
        # what was raised; it changes nothing a rule can read.
        self.moments.begin()

        # The room is handed to the burst so it lays no poison inside a wall
        # (issue #41) and so a refused cell falls back one step toward the
        # player rather than being lost (issue #44). `is_solid` is the current
        # room's, which is the only authority on where anything can stand.
        if intent.spray and self.spray.fire(self.player.cx, self.player.cy,
                                            self.player.facing, self.here,
                                            self.is_solid):
            self.tally.sprays += 1
            self.panel.set("spray", self.spray.charges)
            # **Raised here because there is no event for it, and this slice
            # must not add one** (issue #52). A new kind in the run log is a
            # changed run log, and every acceptance criterion in the
            # look-and-feel round rests on the log not moving. Firing the spray
            # is a thing the player did on purpose, so it is a sound and
            # nothing else -- no flash, no pause.
            self._moment(moments_mod.M_SPRAY)
            # The charge covers the ground under the player as well as the
            # patch ahead of them. See `_douse_underfoot` -- it is the moment
            # the charge is spent that this is asked, and nowhere else.
            self._douse_underfoot()

        # Input is read and acted on in the same frame. Nothing buffers,
        # smooths or accelerates -- responsiveness is a requirement.
        self.player.move(intent.dx, intent.dy, self.is_solid)
        self._maybe_cross()
        room = self.room
        self.glow.x, self.glow.y = self.player.cx, self.player.cy
        self.glow.facing = self.player.facing

        # Every room, not only the one on screen. The building is a simulation
        # running whether or not you are looking at it, which is what makes the
        # room you walked out of a place where things still happen.
        for place in self.places:
            if place.roaming is not None:
                place.roaming.update()
        self._magnetise()
        self.spray.tick()

        # The one rule: Clegs steer for the nearest light that is actually lit.
        # The glow is dim and so pulls nothing, which is what makes walking in
        # the dark safe and the toggle a decision.
        own = [self._own_lures(place) for place in self.places]
        # **Bites are counted where they happen, not inferred from a headcount.**
        # This used to be `len(swarm.on_player())` before and after, and a net
        # difference loses any frame on which one fly lands and another lets go
        # -- which is how a run came to report seven attachments while the
        # per-lure buckets, billed at the moment of the bite (issue #22), added
        # up to eight. Every phase-2 baseline is stated in this number, so it
        # has to be the one the buckets agree with. `Swarm.attachments` is the
        # swarm's own count, kept where the fly lands and **not** through the
        # attribution hook, which has to stay something the run does not read.
        was_bites = self.swarm.attachments
        for place in self.places:
            here = place.index == self.here
            blood = place.swarm.tick(
                own[place.index],
                (self.player.cx, self.player.cy) if here else None,
                place.room.is_solid, self.blood if here else 0,
                is_sprayed=self.spray.in_room(place.index),
                prey=self._lit_people(place),
                doors=self._doors(place, own),
                # The clock an attached fly flaps on (issue #61). Drawing
                # cadence only: the swarm reads it for nothing else.
                frame=self.frame,
                # The rule that no two flies share a cell, carried through
                # the doorway (issue #65).
                held_beyond=self._held_beyond(place),
                # The player's cell while they are a magnet, to the room
                # they are in; to every other room, the threshold of the
                # doorway that leads there (issues #82, #88).
                magnet=self._magnet_cell(place))
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
        # Where they died, for the moment's flash: the list has to be taken
        # before `kill` removes them, because a dead fly has no cell to ask
        # afterwards. Only this room's, since the screen shows one room and a
        # cell reference in another is a different place with the same number.
        died_at = []
        for place in self.places:
            dead = self.spray.kills(place.swarm.sprayable(), place.index)
            if place.index == self.here:
                died_at.extend((fly.cx, fly.cy) for fly in dead)
            killed += place.swarm.kill(dead)
        if killed:
            self.tally.swatted += killed
            self._record(SPRAY_KILL, count=killed, room=room)
            self._moment(moments_mod.M_SPRAY_KILL, sorted(set(died_at)))

        # Everybody bleeds, found or not. This is the clock, and it is what
        # makes light compete with time rather than with darkness.
        for gone in self.rescue.tick():
            # **In the room they fell in**, which is the point of saying it at
            # all: a follower lost on the walk home died somewhere, and the
            # question the user asks a playtester is where.
            self._record(WORKER_DIED, who=self._index[id(gone)],
                         room=self.places[gone.room].room.name)
            # **No flash, and it must not gain one.** They are usually not on
            # lit ground, so there would be nothing to flash, and the death
            # already has its own channel in the shout. See `moments`.
            self._moment(moments_mod.M_WORKER_DIED, room=gone.room)

        # A body is temporary whatever you do about it: twenty seconds in which
        # a charge saves it, thirty as a nest if it is not, and then nothing.
        # Dousing is looked at before the turn, so a patch laid on the last
        # frame of the window still counts.
        self._douse()
        self._nests()

        # Freeing somebody starts the hard part: they follow, and they go on
        # bleeding while they do.
        freed = self.rescue.reach(self.here, self.player.occupied_cells())
        if freed is not None:
            self._record(FREED, who=self._index[id(freed)], room=room)
            # The two cells they were standing in **at the instant they were
            # freed**. It follows them nowhere: a moment marks where a thing
            # happened, which is also why it costs nothing per frame.
            self._moment(moments_mod.M_FREED, sorted(freed.cells()))
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
            # The door, not the person: what the player is looking at when
            # somebody is banked is the way out, and the door is the thing that
            # did it. Two cells, because a person-shaped hole is 8x16.
            self._moment(moments_mod.M_DELIVERED, self._exit_cells())
        self.at_exit = at_door
        self._gone_in = self._gone_in or not at_door
        # **Leaving is pushing through it.** Not the frame you touch the door
        # -- that is the delivery -- but the half-second of still walking into
        # it afterwards. The outward component is what counts, so leaning on
        # the door diagonally is leaving; walking *along* the wall past it is
        # not, and neither is standing in it.
        fx, fy = self.exit_facing
        pushing = ((intent.dx == fx or not fx) and (intent.dy == fy or not fy))
        self.leaving = self.leaving + 1 if at_door and pushing else 0
        if self.rescue.saved != self.tally.found:
            self.tally.found = self.rescue.saved
            self.panel.set("rescued", self.rescue.saved)
        # **Where every one of the seven is** (issue #90): following you,
        # dead, still to find. `set` repaints only on a change, so this costs
        # three compares a frame and a cell or two when somebody moves
        # between columns. With the tally they add up to the total.
        self.panel.set("with", len(self.rescue.tail))
        self.panel.set("dead", self.rescue.lost)
        self.panel.set("left", len(self.rescue.alive_waiting()))

        bites = self.swarm.attachments - was_bites
        if bites:
            self.tally.attachments += bites
            self._record(BITTEN, count=bites, room=room)
            # **No flash.** Bites are frequent and a bar that alerts on every
            # one is furniture rather than an alert; a bite is a sound.
            self._moment(moments_mod.M_BITE)
        if self.swarm.drained:
            self._record(DRAINED, count=self.swarm.drained, room=room)
        self.tally.frame(self.swarm.drained)

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
            # Raised **before** the respawn, because the cells to flash are the
            # ones they died in and `_respawn` is about to put the player back
            # at the entrance. This is one of the three moments that pause, and
            # the pause is the shell's -- nothing here waits for it.
            self._moment(moments_mod.M_PLAYER_DIED,
                         sorted(self.player.occupied_cells()))
            if self.lives > 0:
                self._respawn()

        self.panel.set("blood", bar_pips(self.blood, self.blood_full, 8))
        self.panel.tick()

        # You hear them before you see them -- and since a Cleg is only drawn
        # where a light is on it, in the dark this is all you get.
        # **The nearest Cleg in the room you are in.** A distance across a room
        # boundary means nothing, so the room behind you falls silent the
        # moment you leave it -- which is exactly the hole the shouts through a
        # doorway exist to fill.
        wants_click = self.sonar.update(
            self.place.swarm.nearest_distance(self.player.cx, self.player.cy))

        # **A body is found by ear or it is not found at all**, so the tick is
        # the primary channel and not a garnish: measured, a body sits on
        # lit-or-remembered ground for at best 1.6 seconds of its twenty, and
        # for none at all on the first three deaths of every seed.
        #
        # **It carries from the room next door**, unlike the sonar, which
        # reports only the room you are in. A ticking body is one fixed thing
        # and there is never more than one of it, so this is affordable where a
        # second room's sonar is not -- and it is the only reason going back
        # for a body behind you is a decision rather than a guess.
        rooms = {self.here}
        rooms.update(door.to for door in self.place.room.doorways)
        self.ticking = self.rescue.ticking(rooms)
        wants_tick = self.ticker.update(
            buzz.NEVER if self.ticking is None else self.ticking.tick_period)
        # **The speaker is asked once, here, and by nobody else** (issue #54).
        # *The sonar wins the speaker* used to be a line of session code; it is
        # now one clause of `sounds.Voice`, alongside the body's tick and the
        # fourteen effects, because a Spectrum has one beeper and an
        # arbitration order split across two files is an order that drifts.
        #
        # **Last thing in the frame, after every moment has been raised**, so
        # that a click and an effect arriving on the same frame really are on
        # the same frame -- which is the boundary the ruling left open and this
        # slice settles deliberately: the click wins and the effect never
        # starts. The two counters have already been advanced above and are
        # never told what became of what they asked for.
        if self.voice is not None:
            # The two intervals decide nothing and are only for the
            # starvation figures: a sonar with no Cleg in reach is meant to be
            # silent, and a click lost at contact is not the same event as one
            # lost at the edge of hearing.
            # **The Clegs on screen, and only those** (issue #55). The music
            # takes what the frame has left after they are drawn, and the port
            # draws the room the player is standing in and no other -- so a
            # swarm in the room next door costs the frame nothing and must not
            # thin the music. It is the one number the music reads and it
            # decides nothing above the music.
            self.voice.update(wants_click, wants_tick, self.moments.sounds(),
                              self.sonar.interval, self.ticker.interval,
                              clegs=len(self.place.swarm.clegs))
            self.click = self.voice.kind == sounds.CLICK
            self.tick = self.voice.kind == sounds.TICK
        else:
            self.click = self.tick = False

        self._light()
        if self.repaint is not None:
            # After the light is rebuilt and before the run can end, so the
            # last frame of a run is priced like every other one. The room the
            # player is standing in and no other: the screen shows one room, so
            # that is the only field whose cells anything has to redraw.
            self.repaint.frame(self.place.field.display,
                               self._wall_maps[self.here])
        ending = self._ending()
        if ending is not None:
            self.finish(ending)
        return self.frame_events

    # --- bodies, and what becomes of them -----------------------------------

    def _douse(self) -> None:
        """A spray patch on a body inside its window saves it from turning.

        **Sprayed ground douses a body**, which is the same rule the spray has
        always had rather than a new verb: you do not aim it at a corpse, you
        put a patch where one is lying -- `spray.py` has said "on a fresh body
        before it turns" since it was written. One charge, of five, and it is
        the cheapest thing the spray ever does.

        A patch laid before the death counts, and that is right: the ground is
        poisoned either way, and requiring the charge to be spent *after* the
        fall would reward waiting rather than anticipating.
        """
        for body in self.rescue.bodies():
            if body.doused:
                continue
            if any(self.spray.covers(cx, cy, body.room)
                   for cx, cy in body.cells()):
                self._douse_body(body)

    def _douse_underfoot(self) -> None:
        """A charge spent standing on a fresh body douses it, any facing.

        **The patch is not widened and this lays no ground**: the spray is area
        denial, not a weapon, and letting a burst poison the cell the player
        stands in would let them kill the fly that is on them. What is fixed
        here is narrower -- the charge reaches the body under their own feet
        and nothing else.

        The fault (issue #39): `patch_cells` starts its loop one cell *ahead*
        of the player, so a burst never covers where they stand. Because a
        person is two cells tall, facing **up** put the patch on their own
        upper cell and the douse happened to work -- in exactly one facing out
        of four, with no facing indicator on screen (the glow's nose is that
        indicator since issue #117). So
        the one place a body can be found without spending light, by walking
        onto it in the dark, was the one place it could not be saved from. That
        matters more since a death shout gives a direction rather than a
        position: walking that direction in the dark is precisely what puts a
        body under your feet.

        **Untouched by the rebound** (issue #44), and it still has to exist. A
        blocked cell now falls back one step toward the player, but the fallback
        that would reach the cell the player is standing in is the one the rule
        refuses -- the feet cell is still never sprayed, so a body underfoot is
        still not reachable through the patch. What the rebound did change is
        the arithmetic in the paragraph above: facing **up** is no longer the
        only facing whose burst can land on the player's own *upper* cell, since
        `(1, +/-1)` falling back to `(0, +/-1)` lands there facing left or right
        as well. Measured over the playtest building that is 169 of 3,920
        standing-cell-by-facing combinations, on top of the 980 facing up.
        Attached Clegs are excluded from the spray (`Swarm.sprayable`), so it
        still cannot clear a fly that is already on you.

        Asked only when a charge is spent, and of the player's own two cells:
        two compares on the Z80 per fresh body in the room, and nothing per
        frame. The bodies list is the room's, because a cell reference in
        another room is a different place with the same number.
        """
        under = self.player.body_cells()
        for body in self.rescue.bodies(self.here):
            if body.doused:
                continue
            cells = body.cells()
            if any(cell in cells for cell in under):
                self._douse_body(body)

    def _douse_body(self, body) -> None:
        """Spend the douse and say so, from either route into it.

        One place, so a body saved by standing on it and a body saved by a
        patch produce the same event -- the report counts `DOUSED` and must not
        be able to tell which rule saved them.
        """
        if body.douse():
            self._record(DOUSED, who=self._index[id(body)],
                         room=self.places[body.room].room.name)

    def _load(self, room: int) -> int:
        """What drawing this room costs, in T-states.

        **The valve's whole input.** It asks one question -- *could the port
        draw this room as it stands?* -- and it asks it of the room the nest is
        in, plus the player, who is always drawn and could walk in at any
        moment.

        **It counts the building's flies against this room's people**, which is
        what #33 chose and #34 was raised to re-decide. It is kept, and the
        reason is that the alternative measured better and guaranteed nothing:

        * Counting **the room's own flies** reads well -- a busy room delaying a
          brood -- and lets every spawn land. But flies cross doorways and go to
          light, so a spawn waved through into a quiet room is a spawn that can
          walk into the loud one ten seconds later. Measured, it lets the
          building reach **44 flies** and peaks at 87% of the ceiling: under it,
          but by luck rather than by construction.
        * Counting **the building's** caps the population at 36 and peaks at
          74%, and costs a Wanderer eighteen spawns in 168. *Nests* calls this
          valve "the budget's only guarantee", and a guarantee that holds
          because the swarm happened not to converge is not one.

        **So what was wrong with #33 was the ceiling, not the count.** Against
        eighteen Cleg-equivalents this same arithmetic held spawns with the room
        at 27 to 61 per cent of the real budget and landed nine of a Statue's
        thirty-six. Against the T-states the port actually has, it fires for one
        bot in four and lets 89% of every brood through.

        Bodies and nests cost nothing here, because neither moves and both are
        drawn from remembered ground -- see `building.FIXTURE_COST`, which
        carries the bound and the measurement that checked it.
        """
        # The player is counted whichever room this is: they are always drawn,
        # and a room they are not in is one they can walk into. Their tail is
        # counted where it physically is, because that is where it is drawn.
        people = 1 + sum(1 for w in self.rescue.workers
                         if w.room == room and w.alive)
        return building_mod.cost(
            clegs=len(self.swarm.clegs),
            people=people,
            nests=len(self.rescue.nests(room)),
            bodies=len(self.rescue.bodies(room)))

    def _hatch(self, nest) -> bool:
        """Place one of a nest's brood. Returns False if there was no room.

        **Ordinary Clegs in every respect but one: they have never fed**, so
        they are born at the top of the hunger curve and can notice the faintest
        light in the room from the moment they hatch. They come straight for
        you, wherever you are. That is not a second rule -- it is the existing
        hunger rule read honestly for a fly that has never eaten, and it resets
        to nothing the first time each of them feeds, in `Swarm._sate`, which
        needed no change at all.

        That is what makes a nest a spike rather than a climate: a nest-born fly
        is only exceptional until its first meal.

        It hatches on the nest's own cell where it can, which is what makes a
        patch of spray laid over a nest kill the brood as it arrives -- one
        charge, one spawn, exactly as the arithmetic in `rescue` says. The
        `SCATTER` table is the fallback for a crowded nest, because no two
        Clegs may share a cell.
        """
        place = self.places[nest.room]
        taken = {(c.cx, c.cy) for c in place.swarm.clegs}
        at = nest.cell()
        for dx, dy in ((0, 0),) + clegs_mod.SCATTER:
            cell = (at[0] + dx, at[1] + dy)
            if cell in taken or place.room.is_solid(*cell):
                continue
            self._brood_seed = sources.xorshift16(self._brood_seed)
            fly = clegs_mod.Cleg(cell[0], cell[1], seed=self._brood_seed)
            fly.hunger = clegs_mod.KEEN_MAX * clegs_mod.HUNGER_STEP
            place.swarm.clegs.append(fly)
            nest.hatched += 1
            self._record(HATCHED, who=self._index[id(nest)],
                         count=nest.hatched, room=place.room.name)
            # **The flash is already running and this does not start one.**
            # A hatch is announced two seconds *before* it happens, so it is a
            # state on the nest rather than something this event can drive --
            # see `moments.hatch_is_near`. The moment is still raised, because
            # it still has a sound.
            self._moment(moments_mod.M_HATCHED, [at], room=nest.room)
            return True
        return False

    def _nests(self) -> None:
        """One frame of every body in the building: turn, hatch, burn out.

        The lifecycle itself is arithmetic on the frame counter and lives in
        `rescue.Worker`; what is here is the three things a body cannot do on
        its own -- announce itself, make a Cleg, and be told it cannot.

        **The valve.** A nest whose spawn would take the room over the ceiling
        **holds it rather than dropping it**, and spends its thirty seconds
        regardless: a busy room delays a brood, it never cancels one, and the
        nest still burns out on time. It is the budget's only guarantee now that
        the game manufactures entities, and it was demoted to a backstop behind
        the twenty-second death spacing until that spacing became distributional
        -- a guarantee cannot survive a randomising accelerator, and Clegs
        eating workers is one.

        **One a frame at most.** A nest that has been held for a while does not
        empty itself in a burst when the room clears; it places the backlog a
        fly at a time, which is what a delay is supposed to look like.
        """
        live = len(self.rescue.nests())
        self.most_nests = max(self.most_nests, live)
        for place in self.places:
            self.peak_fixtures = max(
                self.peak_fixtures,
                len(self.rescue.bodies(place.index))
                + len(self.rescue.nests(place.index)))
        for body in self.rescue.workers:
            if body.state != rescue_mod.DEAD:
                continue
            if body.age == rescue_mod.BODY_FRAMES and not body.doused:
                self._record(NEST_TURNED, who=self._index[id(body)],
                             room=self.places[body.room].room.name)
                self._moment(moments_mod.M_NEST_TURNED, [body.cell()],
                             room=body.room)
            if body.age == rescue_mod.GONE_FRAMES:
                self._record(NEST_BURNT if not body.doused else BODY_GONE,
                             who=self._index[id(body)],
                             room=self.places[body.room].room.name)
            if body.owed <= 0:
                continue
            if self._load(body.room) + building_mod.CLEG_COST \
                    > building_mod.ENTITY_CEILING:
                self.valve_holds += 1
                self._record(VALVE_HELD, who=self._index[id(body)],
                             count=live,
                             room=self.places[body.room].room.name)
                continue
            self._hatch(body)

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
        * **First entry is noted**, and nothing is fired on it. The opening
          flash used to be: twelve frames of the whole room, once per room.
          Since issue #79 no room is ever shown whole, and what you see of a
          room is what your own light and the room's own lights show you.

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
        # **No flash**: the screen has just flicked to a different room, which
        # is already the largest visual event in the game.
        self._moment(moments_mod.M_DOOR)
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
        # Whatever you were doing, you are not doing it now. Without this, a
        # player who died on the frame they finished pushing through the door
        # would be carried out of a building they had just been dragged back
        # into the middle of.
        self.leaving = 0
        # And the room has lost you (issue #82): a death puts you back at the
        # door with the flies that were on you scattered, and a magnet that
        # survived it would hand you straight back to them.
        self.magnet = 0
        room = self.places[self.start_room]
        self.here = self.start_room
        self.player.x, self.player.y = self.building.rooms[self.here].player_start
        self._migrate()
        # The scatter asks the room next door before it lands a fly near the
        # edge, exactly as a step does (issue #69). A death in a doorway used
        # to scatter a fly onto the landing beyond it, checked against this
        # room's cells only, and the door light pinned it there on top of
        # whichever fly next door already held the cell. Asked as a placing
        # and not an arrival -- see `_held_beyond`.
        room.swarm.detach(room.room.is_solid,
                          held_beyond=self._held_beyond(room, arriving=False))

    def finish(self, reason: str) -> None:
        """End the run, for a reason inside the game or outside it."""
        if self.over is not None:
            return
        self.over = reason
        self._record(GAME_OVER, room=self.room)
        # An ending may stop the clock, and these two are the only pauses in
        # the game besides a death. Everything but walking out with all of them
        # alive is the same beat; getting everyone out has its own.
        self._moment(moments_mod.M_ALL_OUT if reason == ALL_OUT
                     else moments_mod.M_GAME_OVER)

    def _ending(self) -> str | None:
        """Has the run ended, and how?

        **Three things end a run: you get everyone out, you walk out of the
        building, or you lose the last life.** Not reaching the exit -- issue
        #20 read *"reaching the exit ends the level"* literally and it deleted
        the decision *Progression and Scoring* calls the game. Issue #28 is
        the correction, and issue #80 the one exception to it:

        * **Delivering the last living person ends the run there and then**
          (issue #80). The user got all seven out and stood in the doorway
          with nothing happening, and reported a bug. The walk-out rule below
          exists to keep the decision *do you go back in?*, and with everybody
          out alive there is nobody to go back in for; a rule that then waits
          for half a second of pushing is not protecting a decision, it is
          hiding the ending. `ALL_OUT` on the delivery that makes the tally
          full, with its moment and its pause as before.

        * **Touching the door banks whoever is behind you and the run carries
          on.** You are standing in the doorway with an empty tail and a
          building still full of people, and the question is whether you go back
          in. That question is the game; a rule that ends the level the moment
          you deliver deletes it.
        * **Leaving is pushing through** -- `LEAVE_FRAMES` of still walking into
          the door after you have arrived at it. A brush delivers and costs
          nothing, which is what stops the way out being a trapdoor: a Wanderer
          used to end its run in under two seconds on three seeds in twelve by
          random-walking into a door a hundred pixels from the start.

        **Which ending it is depends on what you left behind, not on what
        triggered it.** Three of them, and the middle one was unreachable from
        inside the game until now:

        * Everybody out alive -- `ALL_OUT`.
        * Somebody **living** still in there -- **no ending at all** since
          issue #87: the door does not let you out. `ABANDONED` was the ending
          here from #28 to #87 and its text stays for the screen only.
        * Nobody living left, but not everybody got out -- `NOBODY_LEFT`, which
          now says only what is true.

        `_gone_in` is what stops the door being an ending on frame one. The
        prototype's start is a patch of open floor in the middle of the room, so
        today the flag is set on the first frame and changes nothing -- but
        *Building Structure* settled that **the player starts at the exit,
        because that is where they came in**, and on the day that lands, a door
        that could end the run before you had been anywhere would end every run
        instantly. That start position is **deliberately not moved here**: it
        changes where every phase-2 baseline was measured from, and this issue
        is one mechanic. One bit, set the first time you are anywhere else, and
        the door means "back out the way I came" rather than "here I am".
        """
        if self.lives <= 0:
            return NO_LIVES
        if self.total and self.rescued == self.total:
            return ALL_OUT
        if self.inside:
            # **The door does not let you out while anybody living is still
            # inside** (issue #87, the user, from play). Pushing through it
            # does nothing; `ABANDONED` is unreachable and its text is kept
            # only for the screen. What this withdraws is the decision *do
            # you go back in, or leave with what you have* -- the user wants
            # the one where you go back in, and the question is whether you
            # get there in time.
            return None
        if self.leaving < LEAVE_FRAMES or not self._gone_in:
            return None
        return ALL_OUT if self.rescued == self.total else NOBODY_LEFT

    @property
    def score(self) -> int:
        """What this run scored (issue #123): ten a living person delivered,
        a point a second of the level's shortest authored clock left when
        the last living person was delivered (nought if anybody died or
        nobody was), and five a body doused before it turned. Small
        integers, a person always worth most, unspent spray worth nothing.
        Summed across a game by the shell; never on the strip."""
        points = 10 * self.rescued
        delivered = [e.frame for e in self.log if e.kind == DELIVERED]
        if delivered and self.rescued == self.total and not self.lost:
            shortest = min(w[2] for room in self.building.rooms
                           for w in room.workers) * rescue_mod.BLEED_EVERY
            points += max(0, (shortest - max(delivered)) // FRAME_RATE)
        points += 5 * sum(1 for e in self.log if e.kind == DOUSED)
        return points

    def _record(self, kind: str, who: int | None = None, count: int = 0,
                room: str = "") -> Event:
        event = Event(self.frame, kind, who, count, room or self.room)
        self.log.append(event)
        self.frame_events.append(event)
        return event

    # --- the moments (issue #52) -------------------------------------------

    def _moment(self, name: str, cells=(), room: int | None = None):
        """Raise one of the fourteen. It logs nothing and decides nothing.

        **A moment is not an event.** It is raised beside one, from the code
        that already knew the thing had happened, and it adds no kind to the run
        log -- `M_SPRAY` is raised from the call site precisely because there is
        no `SPRAY_FIRED` and this slice must not invent one. Nothing in a run
        reads a moment back, so a moment cannot change a run.

        **Only cells the player is already being shown are flashed.** Flashing
        something in the dark is a light that costs nothing, and this game does
        not have one of those. The test is the cell's displayed level, read from
        the room the moment happened in -- which is last frame's field, because
        `_light` runs at the end of a step. That is the same frame of lag the
        swarm's prey test has and it is the honest reading of *what the player
        was being shown when this happened*.

        The moment is raised whether or not any cell survives that test: a
        moment over dark ground still has a sound, it simply has nothing to
        flash.
        """
        room = self.here if room is None else room
        field = self.places[room].field
        moment = self.moments.raise_moment(
            name, cells, room,
            lit=lambda cx, cy: field.level_at(cx, cy) != lighting.DARK)
        # The two strip flashes go through the mechanism the strip already has.
        # `Panel.alert` is the attribute flash bit on a readout, which is the
        # same thing this is, so a second mechanism would only be a second
        # thing to keep in step.
        for readout in moment.strip:
            self.panel.alert(readout, moment.frames)
        return moment

    def _exit_cells(self) -> list:
        """The two cells of the way out, or none if this room has no door.

        `exit_cell` names the top of the opening and a person is 8x16, so the
        pair is the person-shaped hole `sprites.DOOR_OPEN` is drawn in.
        """
        room = self.place.room
        if not room.has_exit:
            return []
        ex, ey = room.exit_cell()
        return [(ex, ey), (ex, ey + 1)]

    def flash_cells(self) -> set:
        """Every cell wearing the FLASH bit this frame, in the room on screen.

        Three sources, and only the first is a moment:

        * the live flashes a moment raised, which were light-tested once when
          they were raised and are not tested again -- a cell that goes dark
          mid-flash is black ink on black paper, and flashing swaps ink and
          paper, so it stops showing anything on its own;
        * **a body**, for its whole window, from the death until it is doused or
          it turns. The visual half of the tick, and it had never been built;
        * **a nest about to place one**, from two seconds before the spawn until
          the spawn is placed. A tell rather than a report, which is why it
          cannot be driven by the `HATCHED` event.

        The two states are re-tested against the light every frame, because they
        are states: a body lying on ground the player cannot see is not being
        shown anything, and the rule is that a moment may only flash what the
        player is already being shown.
        """
        cells = self.moments.cells(self.here)
        state = set()
        for body in self.rescue.bodies(self.here):
            if moments_mod.body_is_flashing(body):
                state.add(body.cell())
        for nest in self.rescue.nests(self.here):
            if moments_mod.hatch_is_near(nest.age - rescue_mod.BODY_FRAMES,
                                         nest.hatched, nest.owed):
                state.add(nest.cell())
        field = self.place.field
        cells.update(cell for cell in state
                     if field.level_at(cell[0], cell[1]) != lighting.DARK)
        return cells

    def _light(self, held: bool = False, black: bool = False) -> None:
        """Sources contribute, brightest wins, then everything decays.

        Run for **every** room, because the fade keeps running while you are out
        of one and because a room's swarm needs to know who is standing lit in
        it whether or not you are there to see them.

        A source belongs to a room and writes into that room's field, so
        **light does not cross a threshold** and never has to be stopped from
        doing so. Standing in A's doorway you cannot see into B -- with one
        exception since issue #116: **the beam shows in a doorway from both
        sides.** A searchlight whose disc covers a doorway's cells writes
        those same cells into the room beyond, at its own level and memory,
        so a beam sweeping past a door is seen through it and a player
        standing in the gap is found from either side. Every field begins
        before any source writes, because a spill lands in another room's
        field and a `begin` after it would wipe it.
        """
        self.shouting = []
        self.door_calls = []
        self.call_cells = []
        self.shout_runs = []
        for place in self.places:
            place.field.begin()
        if black:
            # The opening's black (issue #95): no source at all, not even
            # the ones that never fade. The fields are committed from their
            # untouched charge, so nothing is remembered of it either.
            for place in self.places:
                place.field.commit(decay=not held)
            return
        for place in self.places:
            here = place.index == self.here
            field = place.field
            for src in place.fixed:
                src.apply(field)
            self._spill(place)
            if here:
                self.glow.apply(field)

            # A shout is not a light. It lifts its own cells out of the dark so
            # the word can be read, leaves no memory behind it, and reveals
            # nobody -- so calling out never marks a worker for the swarm.
            calling = (self.rescue.calling(self.frame, place.index)
                       if self.calls_on else [])
            # **Where the word goes is decided once, here, and the drawing
            # reads the answer** (issue #59). It used to be worked out twice --
            # once for the cells the shout lifts out of the dark and once again
            # in `draw` -- and the two now depend on where everybody is
            # standing, so computing it twice is two chances to disagree about
            # which four cells are green.
            #
            # The people are passed in because the word may not land on one:
            # a sign forces its cell's ink, so a shout on the player's feet
            # paints the figure that means *this is you* in the colour that
            # means *a voice*. Only gathered when somebody is actually calling.
            people = self._people_cells(place) if calling else frozenset()
            runs = [w.call_cells(people, place.room.is_solid) for w in calling]
            cells = [c for run in runs for c in run]
            if here:
                self.shouting = calling
                self.shout_runs = runs
                # Gated on `calls_on` like every other shout. A switch
                # labelled "workers call for help" that leaves one kind of
                # shouting running is a liar -- the same argument the death
                # beat is held to.
                self.door_calls = (self._calls_through_doors()
                                   if self.calls_on else [])
                cells = cells + [c for run in self.door_calls for c in run]
                self.call_cells = cells
            for cx, cy in cells:
                # No hue here: the green comes from the frame's ink map,
                # below, where every other colour on screen comes from. It was
                # passed to the light as well until issue #47, which was the
                # one place two things chose one cell's colour -- and the light
                # was the one that never won.
                field.add(cx, cy, lighting.LIT, memory=1, reveals=False)
            # The exit sign has its own battery, as they do. It is the one
            # thing in a failing building you can always see -- in the room it
            # is in, which is the near room and no other.
            for cx, cy in place.sign_cells:
                field.add(cx, cy, lighting.LIT, memory=1, reveals=False)
            # **The searchlight's housing, held lit the same way** (issue #49):
            # one permanently lit cell at the mount corner, the brightest
            # single cell in the room, and it never moves. A room without a
            # searchlight has none, so the absence is authored rather than
            # ambiguous -- which is what went wrong when a player read the far
            # room as broken.
            #
            # **It is a direct write and not a `sources.Source`, deliberately.**
            # A source there is a new permanent lure at the corner the beam is
            # mounted on: every fly within notice of that corner would have
            # somewhere to go for ever, which moves every difficulty figure in
            # the vault. `reveals=False` for the same reason the sign has it --
            # it shows the fixture, never a person standing under it, so
            # nobody is made prey by standing in the corner.
            housing = place.housing
            if housing is not None:
                field.add(*housing, level=lighting.LIT, memory=1,
                          reveals=False)
        for place in self.places:
            place.field.commit(decay=not held)
            if self.wall_fade == 2 and not held and self.frame % 2 == 0:
                place.field.linger(place.solid_mask)

    def _spill(self, place: Place) -> None:
        """This room's beam, through its doorways, into the rooms beyond
        (issue #116). Each doorway cell the disc covers is written into the
        neighbour's field at the landing column, the beam's own level,
        memory and reveal bits -- the same `light` the beam lights its own
        room by."""
        beam = place.roaming
        if beam is None or not beam.enabled:
            return
        for door in place.room.doorways:
            beyond = self.places[door.to].field
            for cy in door.rows:
                if beam.covers(door.column, cy):
                    beam.light(beyond, door.landing, cy)

    def _people_cells(self, place) -> set:
        """Every cell a figure is drawn in, in one room (issue #59).

        What it is for: **a shout may not be written in a cell somebody is
        standing in.** A sign forces its cell's ink, so the word would recolour
        the figure under it -- and the figure it recoloured in the session that
        found this was the player, whose foot mark is the one thing on screen
        that says *this is you*.

        **Position rather than visibility**, deliberately: the word steps aside
        for somebody standing in the dark as readily as for somebody lit. Tying
        it to the light would make the word jump when the beam passed, which
        is a worse fault than the one being fixed.

        All four figures count, because all four are drawn as people: the
        player, the waiting, the following and the dead. A body's cells are
        where it is *drawn*, which since this issue is two cells of one row --
        see `sprites.body_cells`.
        """
        room = place.index
        cells: set = set()
        if room == self.here:
            cells |= self.player.occupied_cells()
        for worker in self.rescue.alive_waiting(room):
            cells |= worker.cells()
        for worker in self.rescue.tail:
            if worker.room == room:
                cells |= worker.cells()
        for body in self.rescue.bodies(room):
            cells.update(sprites.body_cells(*body.cell(),
                                            place.room.is_solid))
        return cells

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

        It is more load-bearing than when it was written. A follower eaten in
        the dark is invisible, so the sonar is the only channel left -- and
        since issue #32 the sonar does report a fly feeding on somebody who is
        not you. But it reports it **in the room you are in**, so the moment
        that follower is the other side of a wall the click stops and this is
        all that is left.

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
        people = None
        for door in self.place.room.doorways:
            if not self.rescue.calling(self.frame, door.to):
                continue
            row = door.middle
            # **Beside the doorway, on this room's side of it, never across
            # it** (issue #59). It used to start at the doorway's own column,
            # so in the far room the word printed straight over the way home:
            # the first letter looked clipped and a word sat on the one fixture
            # that tells the player where the way back is. A label that hides
            # its own referent has failed at the only job it has.
            #
            # Clamped like every other run, though at these columns the clamp
            # never bites -- it is here so that a doorway one cell from the
            # edge, which the building could author tomorrow, cannot put the
            # word off screen.
            left = (door.column - word if door.side == EAST
                    else door.column + 1)
            # And it steps further into the room if somebody is standing where
            # it would be written -- the player stood in his own doorway is the
            # case, and the word painting his cell green is the fault this
            # issue is about. **Inward only**: stepping the other way would put
            # the word back on the door.
            steps = rescue_mod.CALL_STEPS_INWARD
            if door.side == EAST:
                steps = tuple(-step for step in steps)
            if people is None:
                people = self._people_cells(self.place)
            run = rescue_mod.clear_run(left, row, people, steps)
            runs.append(run if run is not None
                        else rescue_mod.clear_run(left, row))
        return runs

    # --- drawing -----------------------------------------------------------

    def draw(self, screen: Screen) -> None:
        """The whole frame: the room, the people, and the status strip."""
        if self.strobe:
            # **The opening is black to the bottom of the screen** (issue
            # #105, Look and feel 3 row 13): on every held frame the strip's
            # sixty-four attributes are black on black, its pixels left as
            # they are under them, and the strip is painted fresh with the
            # first played frame. "Completely black" was a lit strip under a
            # logo until the user said so.
            screen.clear_rows(PLAY_TOP, PLAY_BOTTOM, PLAY_ATTR)
            black = attr_byte(ink=BLACK, paper=BLACK, bright=False)
            for cy in range(STRIP_TOP, STRIP_BOTTOM):
                for cx in range(COLS):
                    screen.set_attr(cx, cy, black)
            self._painted_strip = False
            if not self._flashing:
                # **The black, with the logo on it** (issue #97): the play
                # area is nothing but SPOTLIGHT, centred. Not the sign, not
                # the housing, not a fixture -- black means black.
                screens.draw_logo(screen, top=OPENING_LOGO_TOP)
                return
        elif not self._painted_strip:
            # Painted once and thereafter only where it changes. On a restart
            # this runs again, because the session is new and the strip on
            # screen belongs to the run before it -- and after the opening,
            # whose held frames hid it.
            blank_strip(screen)
            self.panel.draw_labels(screen)
            self.panel.draw(screen, force=True)
            self._painted_strip = True

        # The play area is cleared every frame; the strip is not touched.
        if not self.strobe:
            screen.clear_rows(PLAY_TOP, PLAY_BOTTOM, PLAY_ATTR)

        # **One room, and only one.** This is the whole of the screen
        # transition: everything below asks the room the player is standing in,
        # so walking through a doorway flicks the view with nothing to animate
        # and nothing to scroll. The room behind you is *gone* rather than dark,
        # which is the moment the second room exists for.
        place = self.place
        field, is_solid = place.field, place.room.is_solid

        # **Where a sign or a shout is written** (issue #48). Those cells draw
        # the *dim* wall tile whatever their light level, so the word is
        # painted onto the wall instead of punched through it: the outline runs
        # unbroken through it and only the masonry is lost, where the paint is.
        # Collected before anything is drawn because the wall goes down first
        # and the word goes on top of it.
        painted = set(place.sign_cells) | set(self.call_cells)

        # A wall is made of something when you can see it and is a line on a
        # plan when you are only remembering it, and a `d` cell draws the
        # returns that make a gap read as a doorway. This used to be
        # `fill_cell_pixels(on=True)` -- 64 pixels of white per cell, lit or
        # remembered, which is what a figure standing against a wall used to
        # disappear into.
        tiles.draw(screen, place.room, field, painted)

        # Lit floor is stippled, denser when fully lit. Without this the light
        # has no visible shape -- it only reveals what it falls on. The same
        # `painted` set as the walls: a sign or a shout on the floor sits on
        # black rather than on the stipple (issue #71), because the noise tile
        # does not fall between the letters the way the lattice happened to.
        # A grating cell draws its grille instead of the stipple (issue #74).
        floor.draw(screen, field, is_solid, painted, place.grating_cells)

        # Sprites set and clear pixels only -- each clears its one-pixel halo
        # and sets its ink (issue #70). Their colour comes from whichever
        # cells they happen to be standing in.
        for spr, sx, sy in place.fixtures:
            sprites.draw(screen, spr, sx, sy)
        # The searchlight's housing: a ring with a lens, on the cell `_light`
        # holds permanently lit. A fixture rather than a light -- see
        # `Place.housing`.
        housing = place.housing
        if housing is not None:
            sprites.draw(screen, sprites.HOUSING,
                         housing[0] * CELL, housing[1] * CELL)
        # People are only drawn where a light is on them, and only if they are
        # in this room. A body is not a person any more: it is part of the
        # building, and the fade may remember it -- and it stays where it fell,
        # in the room it fell in.
        #
        # **A body is laid down across two cells** (issue #59), because an
        # eight-pixel box cannot say that a person is lying rather than
        # standing, and a cold reader twice called a corpse the person they
        # were hunting. **Its stored position has not moved**: `body.cell()` is
        # the cell it has always been read at -- by the tally, by the doused
        # check, by the nest's turn and by the flash -- and only the *drawing*
        # snaps to that cell. Which neighbour it extends into is
        # `sprites.body_cells`, and it is an authored rule rather than a guess.
        for body in self.rescue.bodies(self.here):
            cells = sprites.body_cells(*body.cell(), is_solid)
            left, row = cells[0]
            sprites.draw(screen, sprites.BODY, left * CELL, row * CELL,
                         columns=len(cells))
        # A nest is drawn where the body's feet were, in the object's own 8x8
        # box, which is the same cell the body is anchored to. **A nest and a
        # body are told apart by size** -- one cell against two, and since
        # issue #59 by shape as well, because the body is the wide one. That
        # the shrink happens in place is the whole of the tell: the player has
        # to be able to see a body turn into a nest.
        for nest in self.rescue.nests(self.here):
            cx, cy = nest.cell()
            sprites.draw(screen, sprites.NEST, cx * CELL, cy * CELL)
        # ...and a burnt-out nest is in neither list, so **it leaves nothing on
        # screen**. Anything drawn is a claim that it matters, because the
        # player paid light to see it.
        # **Waiting workers have their arms up and followers have them down.**
        # Raised arms mean "I still need reaching", so a person who is already
        # walking behind you must not be drawn making the signal -- and a
        # follower dropped back to waiting goes back to arms up on the frame
        # they are dropped, because the sprite is chosen from the state rather
        # than remembered.
        #
        # **And every walking figure walks on four strides, picked by the
        # figure's own stride counter** (issue #72) -- exactly as a Cleg's
        # wing is, and never by `self.frame`, which would be a 25Hz strobe.
        # The counter advances every four pixels of travel and at no other
        # time, so a follower strides as the trail carries them. Choosing the
        # frame here is a table lookup on a counter that was already decided;
        # it adds no dirty cell, because a figure that moved is redrawn on
        # that frame regardless.
        #
        # **A waiting worker does not walk; it waves on the shout.** Drawn on
        # `WORKER` while silent and on `WORKER_W` for exactly the frames its
        # HELP is painted -- `self.shouting` is the list `_light` built this
        # frame and the word below is painted from the same answer, so the
        # wave and the word can never disagree about a frame. No counter and
        # no random number: a waiting worker that is not shouting is still.
        # The `calls_on` switch silences the wave with the word, because a
        # switch labelled "workers call for help" that left one kind of
        # calling running would be a liar.
        for worker in self.rescue.alive_waiting(self.here):
            sprites.draw(screen,
                         sprites.WORKER_FRAMES[worker in self.shouting],
                         worker.x, worker.y, visible=field.reveals_at)
        # **A follower is drawn wherever they are** (issue #90). They are
        # yours and you know where they are; seven of them reach ten cells
        # behind you, the glow lit the first and nothing lit the rest, and
        # the user watched a full tail vanish. The prey rule is
        # untouched: a follower is bitable only while lit, and the swarm reads
        # the light and not the drawing.
        for worker in self.rescue.tail:
            if worker.room == self.here:
                sprites.draw(screen, sprites.FOLLOWER_FRAMES[worker.stride],
                             worker.x, worker.y)
        # The frame is the fly's own wing phase, advanced when it steps a
        # cell, and -- since issue #61 -- on the clock while it is attached
        # to somebody, and in place when an idle fly's drift comes up (0, 0).
        # Two bits over the cycle A M B M since issue #73, on the same
        # events. The advance is done in `Swarm.tick` on the game step;
        # drawing only reads the phase, so a paused game is a still picture. See
        # `clegs.Cleg.wing` for the cost argument and its two exceptions;
        # since issue #60 the people follow the movement rule.
        # **Not during a flash of the opening** (issue #97): the flash shows
        # the room and the people and not the flies, so a glimpse hands over
        # where the people are and nothing about what is hunting them.
        # **Own colour, own square** (issue #106, *Colour clash, resolved*):
        # the player and the flies are the two things that carry a colour of
        # their own, and they are drawn last, each into cells cleared to
        # black first -- his the cells his ink lands in, a fly's its own
        # whole cell -- so a white cell holds only him and a red cell only
        # the fly. The squares go on after the words below, and the fly's
        # after his, because the fly wins a cell both want. The box is drawn
        # here, before them, and loses pixels to a fly's square as
        # everything else does.
        figure = sprites.PLAYER_FRAMES[self.player.stride]

        # **Painted, not punched** (issue #48). `paint_glyph` sets pixels and
        # clears none, so the wall tile under the word survives. On floor the
        # cell was left unstippled above (issue #71), so there the word is on
        # black and there is nothing under it to survive.
        for i, (cx, cy) in enumerate(place.sign_cells):
            font.paint_glyph(screen, cx, cy, font.GLYPHS[scene.EXIT_SIGN[i]])

        # "HELP", above the head of anybody shouting. Drawn whatever the light
        # is doing, because it is a voice and not a sighting.
        #
        # The cells are the ones `_light` chose, not a second answer to the
        # same question: since issue #59 the placement depends on where every
        # figure is standing, and the cells the shout lights and the cells it
        # paints have to be the same four.
        for run in self.shout_runs:
            for i, (cx, cy) in enumerate(run):
                font.paint_glyph(screen, cx, cy,
                                 font.GLYPHS[rescue_mod.CALL[i]])
        # ...and over the doorway, for anybody shouting in the room the other
        # side of it. The same word, in the same green, saying **the door and
        # not the person**.
        for run in self.door_calls:
            for i, (cx, cy) in enumerate(run):
                font.paint_glyph(screen, cx, cy,
                                 font.GLYPHS[rescue_mod.CALL[i]])

        # Sprayed ground gets its own droplet pattern and its own hue. Hue is
        # per-cell, so this does not disturb the clash guarantee. Drawn
        # before the squares (issue #106): it is ground, and a square on it
        # clears it for the frame.
        frame_inks = bytearray(place.inks)
        for cx, cy in self.spray.cells_in(self.here):
            for dy, bits in enumerate(spray_mod.STIPPLE):
                for dx in range(CELL):
                    if bits & (0x80 >> dx):
                        screen.plot(cx * CELL + dx, cy * CELL + dy)

        # The squares (issue #106): the player's, then every fly's.
        player_cells = set()
        if not self.strobe:
            player_cells = {c for c in sprites.ink_cells(figure, self.player.x,
                                                          self.player.y)
                            if 0 <= c[0] < COLS and 0 <= c[1] < PLAY_ROWS}
            sprites.draw_square(screen, figure, self.player.x, self.player.y,
                                player_cells)
        if self.magnet and (self.frame // MAGNET_PULSE) % 2 == 0 \
                and not self.strobe:
            # **You, while the room knows where you are** (issue #100): a
            # closed box round the figure with its margin cleared -- locked
            # on -- eight frames in every sixteen for as long as the magnet
            # runs. Shape, not colour: the FLASH bit was two yellow blocks
            # with the figure cut out, a filled halo made a compact figure a
            # blob, and the brackets of #84 were the pool's own noise on a
            # lit pool. Drawing state on the frame counter, like the
            # wingbeat; no attribute moves and the log cannot see it.
            # Drawn after his own square, which would otherwise clear the
            # line where it falls inside his ink's cells, and before the
            # flies', which it loses pixels to as everything does (#106).
            sprites.draw_box(screen, figure, self.player.x, self.player.y)
        fly_cells = []
        for cleg in place.swarm.clegs if not self.strobe else ():
            if not (0 <= cleg.cx < COLS and 0 <= cleg.cy < PLAY_ROWS):
                continue
            # `--dark-clegs` (issue #91) keeps its meaning: an unlit fly
            # clears nothing and writes nothing.
            if not self.luminous and not field.reveals_at(cleg.cx, cleg.cy):
                continue
            cell = (cleg.cx, cleg.cy)
            sprites.draw_square(screen, sprites.CLEG_FRAMES[cleg.wing],
                                cleg.cx * CELL, cleg.cy * CELL, {cell})
            fly_cells.append(cell)
        for cx, cy in self.call_cells:
            frame_inks[cy * COLS + cx] = GREEN
        for cx, cy in place.sign_cells:
            frame_inks[cy * COLS + cx] = RED
        # The housing is white and its cell is held at full brightness, so it
        # is the brightest single cell in the room. White because it means
        # *fixture* here for the same reason it means *solid* on a wall: it is
        # the building, not the room.
        if housing is not None:
            frame_inks[housing[1] * COLS + housing[0]] = WHITE
        for cx, cy in self.spray.cells_in(self.here):
            frame_inks[cy * COLS + cx] = CYAN

        # Light decides brightness, contents decide hue. This overwrites every
        # play-area attribute, so it must come after the drawing.
        field.paint(screen, frame_inks)

        # **A flash is one bit on top of that, and it is not a light**
        # (issue #52). Bit 7, which the ULA blinks in hardware at no cost per
        # frame: the ink, the paper and the bright bit are whatever the light
        # and the cell's contents already chose, and a moment adds nothing to
        # the field they chose them from. It has to come after `paint`, which
        # overwrites every play-area attribute.
        # **What is seen in the dark wears its own ink** (issue #92), after
        # the paint because the paint makes a dark cell black on black and
        # pixels alone show nothing there. A luminous Cleg's cell is bright
        # red wherever it is -- the one colour the play area did not use, and
        # the user's; a follower's cells wear the room's hue, unbright, where
        # the light left them dark, so the tail is seen as the tail. Both are
        # attribute writes on cells the sprites have just been drawn into;
        # the clash a red fly makes of a lit cell it stands in is accepted
        # for now.
        for worker in self.rescue.tail:
            if worker.room != self.here:
                continue
            for cx, cy in worker.cells():
                if 0 <= cx < COLS and 0 <= cy < PLAY_ROWS \
                        and field.level_at(cx, cy) == lighting.DARK:
                    screen.set_attr(cx, cy, attr_byte(
                        ink=frame_inks[cy * COLS + cx], paper=BLACK,
                        bright=False))
        # **You are white** (issue #99, Look and feel 3 row 2). In a tail
        # of seven in the room's hue the user's reviewers picked the wrong
        # figure; one attribute a frame on his cells says which one is you,
        # in both rooms, and the tail keeps the room's hue. Written after
        # the Cleg's red so a fly on you does not turn you red, and before
        # the moments' flash so the bit rides on it. Overturns *colour never
        # tells an entity apart* -- #92 broke that first with the red fly --
        # and the vault says so.
        white = attr_byte(ink=WHITE, paper=BLACK, bright=True)
        for cx, cy in player_cells:
            screen.set_attr(cx, cy, white)
        # **And the fly's red, everywhere, last** (issue #106): the #98 gate
        # on the dark gave a fly in the light the light's colour, which was
        # the brief's first sentence given away; its square holds only its
        # own pixels now, so there is nothing for the red to recolour.
        red = attr_byte(ink=RED, paper=BLACK, bright=True)
        for cx, cy in fly_cells:
            screen.set_attr(cx, cy, red)
        for cx, cy in self.flash_cells():
            screen.set_attr(cx, cy,
                            screen.get_attr(cx, cy) | moments_mod.FLASH_BIT)
        if not self.strobe:
            # Held frames leave the strip black (issue #105); the readouts
            # that changed stay dirty and are painted with the first played
            # frame, which repaints everything anyway.
            self.panel.draw(screen)

