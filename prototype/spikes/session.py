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

ALL_OUT = "all_out"
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
LIFE_LOST = "life_lost"
SPRAY_KILL = "spray_kill"
SWAPPED = "swapped"
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
        #: Which room it happened in. One room for now; issue #21 adds the
        #: second and both reports already have somewhere to put the answer.
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


class Session:
    """A run: the room, the people in it, the swarm, and how it ended."""

    def __init__(self, seed: int = DEFAULT_SEED,
                 blood: int = BLOOD_FULL, lives: int = LIVES) -> None:
        self.seed = seed
        scene.validate()
        self.room = scene.ROOM_NAME

        # Every random thing in the run is derived from the one seed, so a seed
        # names a run. The Clegs' temperaments and the searchlight's tour are
        # the only two, and both use the same xorshift the Z80 will.
        cleg_seed = sources.xorshift16(seed or 1)
        beam_seed = sources.xorshift16(cleg_seed)

        self.field = LightField()
        self.player = Player(*scene.PLAYER_START)
        self.glow = sources.Glow()
        self.glow.x, self.glow.y = self.player.cx, self.player.cy
        self.inks = scene.ink_map()
        self.room_lights = [sources.RoomLight(*z) for z in scene.light_zones()]
        self.cone = sources.Cone(reach=7)
        self.cone.x = self.player.cx
        self.cone.y = self.player.cy
        self.cone.facing = self.player.facing
        self.kit = Spotlights(self.cone,
                              [FloorLight(cx, cy, power)
                               for cx, cy, power in scene.SPOTLIGHTS])
        self.cone_full = max(p for _, _, p in scene.SPOTLIGHTS)
        self.spray = spray_mod.Spray(charges=5)
        self.swarm = clegs_mod.Swarm(
            [clegs_mod.Cleg(cx, cy, seed=cleg_seed + i)
             for i, (cx, cy) in enumerate(scene.CLEGS)])
        self.blood = blood
        self.blood_full = blood
        self.lives = lives
        self.sonar = buzz.Sonar()
        #: Set by `step` when the sonar wants a click. The host makes the noise;
        #: deciding how urgent it is stays portable and integer (see buzz).
        self.click = False

        # The room is shown once, at the start, and then taken away. What the
        # player keeps is what they held in their head.
        self.opening = sources.Flash()
        self.opening.fire()
        # A prison searchlight quartering the room, varying its route so it
        # cannot be planned around, and running to the wall rather than turning
        # short of it. Both settled by playing.
        self.roaming = sources.Roaming(0, 0, radius=3, vary=True, seed=beam_seed)
        self.all_sources = (self.glow, self.cone, self.roaming, self.opening,
                            *self.room_lights)

        self.fixtures = [(sprites.SPRITES[name], x, y)
                         for name, x, y in scene.ENTITIES
                         if name not in scene.MOVERS]
        for cx, cy in scene.cells_of(scene.KEY):
            self.fixtures.append((sprites.KEY, cx * CELL, cy * CELL))
        self.sign_cells = scene.exit_sign_cells()

        self.rescue = rescue_mod.Rescue(scene.WORKERS, scene.exit_cell())
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
        self.over: str | None = None
        self.calls_on = True
        self.log: list[Event] = []
        self.frame_events: list[Event] = []
        self.shouting: list = []
        self.call_cells: list[tuple[int, int]] = []
        self._painted_strip = False

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
        room = self.room

        if intent.torch:
            self.kit.toggle()
        if intent.spray and self.spray.fire(self.player.cx, self.player.cy,
                                            self.player.facing):
            self.tally.sprays += 1
            self.panel.set("spray", self.spray.charges)

        # Input is read and acted on in the same frame. Nothing buffers,
        # smooths or accelerates -- responsiveness is a requirement.
        self.player.move(intent.dx, intent.dy, scene.is_solid)
        self.glow.x, self.glow.y = self.player.cx, self.player.cy
        self.cone.x, self.cone.y = self.player.cx, self.player.cy
        self.cone.facing = self.player.facing

        self.roaming.update()
        self.opening.update()
        self.spray.tick()

        # The one rule: Clegs steer for the nearest light that is actually lit.
        # The glow is dim and so pulls nothing, which is what makes walking in
        # the dark safe and the toggle a decision.
        lures = [p for p in (s.lure() for s in self.all_sources)
                 if p is not None]
        lures += self.kit.floor_lures()
        was_attached = len(self.swarm.attached())
        self.blood = self.swarm.tick(lures, (self.player.cx, self.player.cy),
                                     scene.is_solid, self.blood,
                                     is_sprayed=self.spray.covers)
        # Spray reaches everything except a Cleg already on you.
        killed = self.swarm.kill(self.spray.kills(self.swarm.sprayable()))
        if killed:
            self.tally.swatted += killed
            self._record(SPRAY_KILL, count=killed, room=room)

        # Everybody bleeds, found or not. This is the clock, and it is what
        # makes light compete with time rather than with darkness.
        for gone in self.rescue.tick():
            self._record(WORKER_DIED, who=self._index[id(gone)], room=room)

        # Freeing somebody starts the hard part: they follow, and they go on
        # bleeding while they do.
        freed = self.rescue.reach(self.player.occupied_cells())
        if freed is not None:
            self._record(FREED, who=self._index[id(freed)], room=room)
        self.rescue.follow(self.player.x, self.player.y)

        # The exit banks whoever is behind you. Leaving early is safe and slow;
        # gathering everybody first is the gamble.
        for saved in self.rescue.deliver(self.player.occupied_cells()):
            self._record(DELIVERED, who=self._index[id(saved)], room=room)
        if self.rescue.saved != self.tally.found:
            self.tally.found = self.rescue.saved
            self.panel.set("rescued", self.rescue.saved)

        now_attached = len(self.swarm.attached())
        if now_attached > was_attached:
            bites = now_attached - was_attached
            self.tally.attachments += bites
            self._record(BITTEN, count=bites, room=room)
        self.tally.frame(self.cone.lit, self.swarm.drained)

        # Death costs a try and puts you back at the entrance. The building
        # carries on regardless: workers you did not reach are still bleeding,
        # and the swarm is where you left it.
        if self.blood <= 0:
            self.lives -= 1
            self.panel.set("lives", self.lives)
            self._record(LIFE_LOST, count=self.lives, room=room)
            if self.lives > 0:
                self.blood = self.blood_full
                self.player.x, self.player.y = scene.PLAYER_START
                self.swarm.clegs = [c for c in self.swarm.clegs
                                    if c.state != clegs_mod.ATTACHED]

        picked = self.kit.tick(self.player)
        if picked is not None:
            self._record(SWAPPED, count=self.cone.power, room=room)

        self.panel.set("light", bar_pips(self.cone.power, self.cone_full))
        self.panel.set("lit", self.cone.lit)
        self.panel.set("blood", bar_pips(self.blood, self.blood_full, 8))

        # You hear them before you see them -- and since a Cleg is only drawn
        # where a light is on it, in the dark this is all you get.
        self.click = self.sonar.update(
            self.swarm.nearest_distance(self.player.cx, self.player.cy))

        self._light()
        ending = self._ending()
        if ending is not None:
            self.finish(ending)
        return self.frame_events

    def finish(self, reason: str) -> None:
        """End the run, for a reason inside the game or outside it."""
        if self.over is not None:
            return
        self.over = reason
        self._record(GAME_OVER, room=self.room)

    def _ending(self) -> str | None:
        """Has the run ended, and how?

        Three endings, and the difference between the first two is new: the
        spike ended on "nobody left to save", which was true both when everyone
        was dead and when everyone was out, so a clean sweep and a massacre
        ended the same way with nothing to tell them apart.

        Issue #20 changes this method and only this method: it wants the level
        to run on past the last death, ending at the exit or on the last life.
        The endings themselves do not change, only what triggers them.
        """
        if self.lives <= 0:
            return NO_LIVES
        if self.rescue.settled:
            return ALL_OUT if self.rescued == self.total else NOBODY_LEFT
        return None

    def _record(self, kind: str, who: int | None = None, count: int = 0,
                room: str = "") -> Event:
        event = Event(self.frame, kind, who, count, room or self.room)
        self.log.append(event)
        self.frame_events.append(event)
        return event

    def _light(self) -> None:
        """Sources contribute, brightest wins, then everything decays."""
        self.field.begin()
        for src in self.all_sources:
            src.apply(self.field)
        self.kit.apply(self.field)

        # A shout is not a light. It lifts its own cells out of the dark so the
        # word can be read, leaves no memory behind it, and reveals nobody -- so
        # calling out never marks a worker for the swarm.
        self.shouting = self.rescue.calling(self.frame) if self.calls_on else []
        self.call_cells = [c for w in self.shouting for c in w.call_cells()]
        for cx, cy in self.call_cells:
            self.field.add(cx, cy, lighting.LIT, memory=1, hue=GREEN,
                           reveals=False)
        # The exit sign has its own battery, as they do. It is the one thing in
        # a failing building you can always see.
        for cx, cy in self.sign_cells:
            self.field.add(cx, cy, lighting.LIT, memory=1, hue=RED,
                           reveals=False)
        self.field.commit()

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

        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                if scene.is_solid(cx, cy):
                    screen.fill_cell_pixels(cx, cy, on=True)

        # Lit floor is stippled, denser when fully lit. Without this the light
        # has no visible shape -- it only reveals what it falls on.
        floor.draw(screen, self.field, scene.is_solid)

        # Sprites set pixels only. Their colour comes from whichever cells they
        # happen to be standing in.
        for spr, sx, sy in self.fixtures:
            sprites.draw(screen, spr, sx, sy)
        # People are only drawn where a light is on them. A body is not a person
        # any more: it is part of the building, and the fade may remember it.
        for body in self.rescue.bodies():
            sprites.draw(screen, sprites.BODY, body.x, body.y + CELL)
        for worker in self.rescue.alive_waiting():
            sprites.draw(screen, sprites.WORKER, worker.x, worker.y,
                         visible=self.field.reveals_at)
        for worker in self.rescue.tail:
            sprites.draw(screen, sprites.WORKER, worker.x, worker.y,
                         visible=self.field.reveals_at)
        for cleg in self.swarm.clegs:
            sprites.draw(screen, sprites.CLEG, cleg.cx * CELL, cleg.cy * CELL,
                         visible=self.field.reveals_at)
        sprites.draw(screen, sprites.PLAYER, self.player.x, self.player.y)

        for i, (cx, cy) in enumerate(self.sign_cells):
            font.draw_glyph(screen, cx, cy, font.GLYPHS[scene.EXIT_SIGN[i]])

        # "HELP", above the head of anybody shouting. Drawn whatever the light
        # is doing, because it is a voice and not a sighting.
        for worker in self.shouting:
            for i, (cx, cy) in enumerate(worker.call_cells()):
                font.draw_glyph(screen, cx, cy, font.GLYPHS[rescue_mod.CALL[i]])

        # Sprayed ground gets its own droplet pattern and its own hue. Hue is
        # per-cell, so this does not disturb the clash guarantee.
        frame_inks = bytearray(self.inks)
        for cx, cy in self.call_cells:
            frame_inks[cy * COLS + cx] = GREEN
        for cx, cy in self.sign_cells:
            frame_inks[cy * COLS + cx] = RED
        for cx, cy in self.spray.patches:
            for dy, bits in enumerate(spray_mod.STIPPLE):
                for dx in range(CELL):
                    if bits & (0x80 >> dx):
                        screen.plot(cx * CELL + dx, cy * CELL + dy)
            frame_inks[cy * COLS + cx] = CYAN

        # Light decides brightness, contents decide hue. This overwrites every
        # play-area attribute, so it must come after the drawing.
        self.field.paint(screen, frame_inks)
        self.panel.draw(screen)
