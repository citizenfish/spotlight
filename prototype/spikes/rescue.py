"""Trapped workers: the clock, the tail, and the way out.

The objective, and after issue #13 the whole rescue loop. A worker is somebody
you have to **find in the dark, reach before they bleed out, and walk to the
exit** -- and each of those three is a different kind of pressure.

**They are on a clock, and it is a different clock each.** Each has their own
authored blood and is losing it from the moment the level begins. That is what
turns a search into a race, and it is the answer to the sharpest finding of the
play evaluation: light does not compete with darkness, it competes with *time*.
With nothing bleeding, the best play was to stay dark and be methodical, which
is safe, correct and dull. With a clock running, being slow costs people.

**The clocks are staggered, and that is issue #18.** They were one clock with
one value for everybody, so all seven died in the same frame -- measured, every
run, every seed. Three things were missing and all three were consequences of
that one fact: there was no "who do I go to first", no death anybody could
learn from because the first was also the last, and no body was ever visible
because the level ended on the frame the bodies appeared. The values are
authored per worker in the level data, never rolled, so a room is designed.

**A death is announced.** A worker's last act is to call out, once, from where
they fall. *Nests* says why, and it is not a nest feature: an absence is not a
signal, and a first-timer with six other voices in the building will not notice
that one of them has stopped. A death nobody hears did not happen as far as the
player is concerned. It also hands over a bearing -- you now know which corner.

**Freeing them starts the hard part.** They follow in a tail, in the order
collected, walking the path you walked rather than homing on you -- so the line
strings out behind you and through doorways one at a time. A long tail is not a
score, it is a problem you are carrying.

**They keep bleeding while they follow.** Escorting is against the same clock as
finding, so gathering everybody before heading out is a real gamble rather than
the obvious play.

**A follower is only at risk while lit**, which is the same one rule as
everything else. A worker trailing you through darkness is ignored; one standing
in your cone is prey. The instinct to turn and check on the people behind you is
exactly what gets them eaten.

**Built with issue #19**, and it was the last thing missing: `Swarm.tick` never
saw a worker at all, so the tail was a rucksack -- nothing could happen to it,
and gathering all seven before leaving cost nothing. A Cleg now finds a worker
exactly where the *player* would see one, so a person is prey precisely when
they are drawn. Waiting workers are on the same footing: a spotlight left
burning beside somebody is bait with a person standing in it.

**If a follower dies the line closes up and the body stays where it fell.**
Settled in the vault 2026-09-07. It needs no code of its own and that is the
point: the tail is a path and a set of people walking it, not a set of slots, so
taking somebody out of `tail` moves everybody behind them one place up the trail
and leaves the body at the last position `follow` gave it. Nothing shuffles
because there is nothing to shuffle.

They are people, so the rules from issue #12 apply: drawn only where a light is
on them this frame, and the opening flash does not show them.
"""

from spotlight.core.constants import CELL, COLS

from .layout import PLAY_ROWS

#: A person is 8x16: one cell wide, two tall.
WIDTH, HEIGHT = 8, 16

#: What a trapped worker shouts, and how wide it is in cells.
CALL = "HELP"

#: Frames between one worker's calls, and how long a call is on screen.
#:
#: Twelve seconds apart and four tenths of a second long. Five seconds was tried
#: and was too generous: with the calls spread around the cycle, somebody was
#: shouting seven frames in ten and the room told you where everybody was
#: without your ever lighting it. A call should be a bearing you have to be
#: watching for, not a map.
CALL_PERIOD = 600
CALL_FRAMES = 20

#: The shortest a call cycle gets, for somebody nearly gone.
#:
#: **This is the clock, made audible.** There is no timer on screen and there
#: should not be -- a number counting down is not what a person in a dark
#: building would know. What they would know is that the shouting has got more
#: urgent, so the room tells you who to go to first without ever telling you a
#: figure.
#:
#: **Urgency is time left, not fraction left**, and that is what makes the calls
#: comparable now that the clocks are staggered. The period is interpolated
#: against the *room's* largest blood, so two workers with the same blood left
#: shout at the same rate whatever they started on -- because with one bleed
#: tick for everybody, the same blood is the same number of seconds. A worker
#: on the room's longest clock calls every twelve seconds when fresh and every
#: two when nearly out; one who starts on a third of that is already calling
#: every five seconds from the first frame, which is the whole point. The
#: comparison a player needs is available at the start, which is when the "who
#: first" decision is actually taken.
#:
#: Scaling each worker against their *own* capacity was tried and rejected: it
#: makes everybody sound identical on frame one and turns the shout into a
#: report of how much of themselves is left, which is not information anybody
#: can act on.
CALL_PERIOD_URGENT = 100

# --- the clock -------------------------------------------------------------

#: Blood a worker starts with when a room does not author a value, and how
#: often they lose a point of it.
#:
#: **`WORKER_BLOOD` is a fallback, not the game's clock.** The playtest building
#: authors one value per worker in `scene.WORKERS` -- 30 to 90 in tens -- and
#: that ladder is the clock. This constant only covers a `Rescue` built from
#: bare positions, which is tests and nothing else. It is deliberately not the
#: ladder's top or bottom, so a room that forgets to author blood does not
#: quietly look like a room that authored it.
WORKER_BLOOD = 48

#: Frames between bleed ticks. **One tick for everybody**, which is what lets a
#: blood figure be read as seconds: blood x BLEED_EVERY frames of life, so 30
#: is sixty seconds and 90 is three minutes.
#:
#: 150 -> 100 with issue #23. Three seconds a point put the ladder on 90, 120,
#: 150... which are awkward numbers to reason about and to space deaths with;
#: two seconds a point lands it on round twenty-second gaps. Nothing else in
#: the game depends on the tick.
BLEED_EVERY = 100

#: A body lies there for a while before it turns into a nest. Nests are not
#: built in this spike; the delay is kept so the window is visible.
BODY_FRAMES = 500

# --- what a worker is doing ------------------------------------------------

WAITING, FOLLOWING, SAVED, DEAD = 0, 1, 2, 3

#: Pixels of the player's trail between one follower and the next. A person is
#: sixteen tall and eight wide; this is a little more than a body length, so the
#: line reads as a line rather than as a stack.
TAIL_SPACING = 12


class Worker:
    """One trapped worker: where they are, how long they have, and what next."""

    __slots__ = ("x", "y", "state", "blood", "start_blood", "reference",
                 "phase", "recorded", "_tick", "_since_death")

    def __init__(self, x: int, y: int, phase: int = 0,
                 blood: int = WORKER_BLOOD, reference: int = 0) -> None:
        self.x, self.y = x, y
        self.state = WAITING
        self.blood = blood
        #: What they started on. Kept so a report can say who was given which
        #: rung of the ladder without having to consult the level data.
        self.start_blood = blood
        #: The blood the call rate is measured against -- the longest clock in
        #: the room, so urgency reads as time left rather than as a fraction.
        #: Defaults to their own, which is right for a room of one.
        self.reference = reference or blood
        #: Offset into the call cycle, so the room does not shout in chorus.
        self.phase = phase
        #: Has this death been counted yet? A worker can now die of a bite as
        #: well as of bleeding (issue #19), and the two happen in different
        #: places in the frame, so "who died" is a sweep for the unrecorded
        #: rather than the return value of one function. One bit on the Z80.
        self.recorded = False
        self._tick = 0
        self._since_death = 0

    # --- state ------------------------------------------------------------

    @property
    def found(self) -> bool:
        """Reached at least once -- following, delivered, or dead after both."""
        return self.state in (FOLLOWING, SAVED)

    @property
    def alive(self) -> bool:
        return self.state in (WAITING, FOLLOWING)

    def cells(self) -> set[tuple[int, int]]:
        """Every cell the figure stands in."""
        return {
            (cx, cy)
            for cx in range(self.x // CELL, (self.x + WIDTH - 1) // CELL + 1)
            for cy in range(self.y // CELL, (self.y + HEIGHT - 1) // CELL + 1)
        }

    def cell(self) -> tuple[int, int]:
        """The one cell they are standing on: feet, as `Player.cy` uses.

        A fly attached to them is drawn here, so it rides them rather than
        staying where it landed -- the same rule the player gets, and for the
        same reason (issue #19).
        """
        return self.x // CELL, (self.y + HEIGHT - 1) // CELL

    # --- the clock --------------------------------------------------------

    def bleed(self, amount: int = 1) -> bool:
        """Lose blood. Returns True if this was the moment they died.

        Being carried does not stop it. A follower is still injured, so the walk
        to the exit is against the same clock as the search was.
        """
        if not self.alive:
            return False
        self.blood = max(0, self.blood - amount)
        if self.blood:
            return False
        self.state = DEAD
        self._since_death = 0
        return True

    def bitten(self, amount: int = 1) -> bool:
        """Lose blood to a Cleg. Same wound, different moment in the frame.

        A fly drains in `Swarm.tick`, which runs *before* `Rescue.tick`, so a
        worker killed by one is already dead when the clock comes round and
        gets an extra ageing tick on their own death frame. Starting the body a
        frame behind cancels it, and the two kinds of death then have the same
        frame zero.

        It is one frame -- nobody could see it. It is worth a method anyway,
        because the body's age is what the nest window will be measured in and
        an off-by-one that nobody can perceive today is an off-by-one somebody
        builds on tomorrow. A test caught it; that is what the test is for.
        """
        died = self.bleed(amount)
        if died:
            self._since_death = -1
        return died

    def tick(self) -> bool:
        """One frame of bleeding. Returns True if they died on it."""
        if not self.alive:
            self._since_death += 1
            return False
        self._tick += 1
        if self._tick < BLEED_EVERY:
            return False
        self._tick = 0
        return self.bleed()

    @property
    def turning(self) -> bool:
        """Has this body lain long enough to become a nest?

        Nests are not built here. The window is, because it is the thing the
        flyspray is for and it wants to be visible even before there is
        anything at the end of it.
        """
        return self.state == DEAD and self._since_death >= BODY_FRAMES

    # --- calling out -------------------------------------------------------

    def calling(self, frame: int) -> bool:
        """Is this worker shouting right now?

        **A shout is not a light.** It shows you roughly where somebody is
        without lighting them, so it costs the player nothing and draws nothing
        -- Clegs respond to light and only to light, and a voice is not on that
        list. It is the counterpart of the Clegs' own sonar: the room is full of
        information you cannot see, and both sides of it reach you by ear.

        Only somebody still waiting calls. A follower is behind you and a body
        has nothing left to say.
        """
        if self.state == DEAD:
            # **The death beat.** One shout, on the frame they die and for as
            # long as any other call, from the cell they fell in. It is the
            # announcement of a loss and it is deliberately the same idiom as
            # every other shout -- a voice, in green, lifting its own cells out
            # of the dark, revealing nobody and drawing nothing.
            #
            # It is not gated on having been found or on being in the tail: a
            # follower who bleeds out on the walk to the exit has died too, and
            # that is the loss the player most needs to be told about. The
            # session's `calls_on` debug switch silences it along with every
            # other shout, because a switch labelled "workers call for help"
            # that leaves one kind of shouting running is a liar.
            #
            # If a playtester misses it, the first thing to try is a longer
            # hold rather than a different word; a sound for it is item 8 of
            # the readiness list and is not built here.
            return self._since_death < CALL_FRAMES
        if self.state != WAITING:
            return False
        return (frame + self.phase) % self.call_period < CALL_FRAMES

    @property
    def call_period(self) -> int:
        """How often they shout: more often the less blood they have left.

        Measured against the room's longest clock, not against their own, so
        that equal blood sounds equally urgent whoever is carrying it. See
        `CALL_PERIOD_URGENT` for why that is the right way round.
        """
        span = CALL_PERIOD - CALL_PERIOD_URGENT
        period = CALL_PERIOD_URGENT + span * self.blood // max(1, self.reference)
        # A room may author blood above its own reference only by mistake, but
        # a call period longer than CALL_PERIOD would be a worker who has gone
        # quiet, which is the one thing a shout must never do.
        return min(CALL_PERIOD, period)

    def call_cells(self) -> list[tuple[int, int]]:
        """Where the word sits: above their head, or below if there is no room."""
        head = self.y // CELL
        row = head - 1
        if row < 0:
            row = (self.y + HEIGHT - 1) // CELL + 1
        row = max(0, min(PLAY_ROWS - 1, row))
        left = max(0, min(COLS - len(CALL), self.x // CELL - 1))
        return [(left + i, row) for i in range(len(CALL))]


class Rescue:
    """Everybody in the room, and the state of the rescue."""

    def __init__(self, positions, exit_cell: tuple[int, int] | None = None,
                 blood: int = WORKER_BLOOD) -> None:
        """`positions` is (x, y) or (x, y, blood) per worker.

        The three-element form is how a level authors the clock ladder, and it
        is three-element rather than a table alongside `WORKERS` so that a
        position and its clock cannot be renumbered apart from one another.
        The two-element form takes `blood` for everybody and exists for tests
        and for a room that has not been given a ladder yet.
        """
        rows = [tuple(p) for p in positions]
        count = max(1, len(rows))
        bloods = [row[2] if len(row) > 2 else blood for row in rows]
        # The room's longest clock. Every worker's call rate is read against
        # it, so the shouting is a comparison between people rather than seven
        # separate percentages.
        reference = max(bloods) if bloods else blood
        self.workers = [Worker(row[0], row[1],
                               phase=i * CALL_PERIOD // count,
                               blood=own, reference=reference)
                        for i, (row, own) in enumerate(zip(rows, bloods))]
        self.exit = exit_cell
        #: In the order collected. A tail, not a set.
        self.tail: list[Worker] = []
        self.died: list[Worker] = []
        self._trail: list[tuple[int, int]] = []

    # --- counting ----------------------------------------------------------

    @property
    def waiting(self) -> int:
        return sum(1 for w in self.workers if w.state == WAITING)

    @property
    def saved(self) -> int:
        return sum(1 for w in self.workers if w.state == SAVED)

    @property
    def lost(self) -> int:
        return sum(1 for w in self.workers if w.state == DEAD)

    @property
    def settled(self) -> bool:
        """Nobody left to save or lose."""
        return all(w.state in (SAVED, DEAD) for w in self.workers)

    def alive_waiting(self) -> list[Worker]:
        return [w for w in self.workers if w.state == WAITING]

    def bodies(self) -> list[Worker]:
        return [w for w in self.workers if w.state == DEAD]

    def calling(self, frame: int) -> list[Worker]:
        return [w for w in self.workers if w.calling(frame)]

    # --- the frame ---------------------------------------------------------

    def tick(self) -> list[Worker]:
        """Bleed everybody. Returns whoever has died since the last look.

        The return value used to be "whoever bled out on this frame", which was
        the same thing while bleeding was the only way to die. Issue #19 gave
        Clegs a second way, and it happens earlier in the frame than this does,
        so the question became *who is dead and not yet counted* -- see `reap`.
        """
        for worker in self.workers:
            worker.tick()
        return self.reap()

    def reap(self) -> list[Worker]:
        """Count anybody who has died and not been counted, whatever killed them.

        A sweep rather than a return value, because a death can now arrive from
        two directions -- the clock here, and a Cleg in `Swarm.tick`. One bit
        per worker says whether it has been counted, which is cheaper and far
        harder to get wrong than making every killer remember to report.

        **Taking them out of the tail is what closes the line.** Followers are
        placed by their index into the player's trail, so removing one moves
        everybody behind them one place forward, and the body is left at
        whatever position `follow` last gave it. The vault settled that on
        2026-09-07 and it costs nothing to honour.
        """
        gone = []
        for worker in self.workers:
            if worker.state == DEAD and not worker.recorded:
                worker.recorded = True
                if worker in self.tail:
                    self.tail.remove(worker)
                self.died.append(worker)
                gone.append(worker)
        return gone

    def reach(self, cells) -> Worker | None:
        """Has the player got to somebody still waiting? Returns them the once.

        `cells` is every cell the *player* occupies, not the one cell they stand
        on. Two figures whose bodies overlap are touching, and requiring their
        feet to land in the same cell meant walking through somebody chest-first
        and not reaching them.
        """
        standing = set(cells)
        for worker in self.workers:
            if worker.state == WAITING and standing & worker.cells():
                worker.state = FOLLOWING
                self.tail.append(worker)
                return worker
        return None

    def follow(self, x: int, y: int) -> None:
        """Walk the tail along the path the player walked.

        Followers step where the player stepped rather than heading for where
        the player *is*. That is what makes a line behave like a line -- it
        strings out around corners and through a doorway one at a time, instead
        of clumping into the player's back and cutting every corner.
        """
        if not self._trail or self._trail[0] != (x, y):
            self._trail.insert(0, (x, y))
        needed = TAIL_SPACING * (len(self.tail) + 1)
        del self._trail[needed:]
        for i, worker in enumerate(self.tail):
            at = TAIL_SPACING * (i + 1)
            if at < len(self._trail):
                worker.x, worker.y = self._trail[at]

    def deliver(self, cells) -> list[Worker]:
        """At the exit, everybody following is out. Returns who was saved.

        `cells` is the player's whole body, not the cell under their feet. The
        exit is a door in a wall, and a person is two cells tall -- so standing
        *on* a door in the top row of a room would put their head inside the
        masonry, and the feet-cell test made the way out unreachable. Touching
        the door is leaving by it.
        """
        if self.exit is None or not self.tail or self.exit not in set(cells):
            return []
        out = list(self.tail)
        for worker in out:
            worker.state = SAVED
        self.tail.clear()
        return out
