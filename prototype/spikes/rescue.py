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

**And with issue #21 the doorway is real.** The trail carries the room each step
was taken in, so crossing is not a case anything here handles: the player walks
out of one room and into the next, the trail records it, and followers reach that
step in their own time and cross where the player crossed. What the player sees
is what the vault asks for -- the room behind you is *gone* rather than dark, and
people come out of the doorway one at a time into your glow. What it costs is
that turning back for a straggler is a walk against your own line, in the dark,
with the clock running.

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

**And a body does not lie there for ever** (issue #33). A worker who bleeds out
leaves one, it ticks for twenty seconds while a spray charge can still save it,
and if nobody comes it turns into a nest that spawns six Clegs and burns out.
Twenty seconds of window, thirty of nest, gone -- **whatever you do about it**,
because a doused body expires on the same clock as the nest it prevented.

That last part is a fix as much as a mechanic. Measured after issue #20, bodies
accumulated and never left: up to seven on screen at once in a losing room's
last minute, and *Screen Layout*'s rule is that anything drawn is a claim that
it matters, because the player paid light to see it.

**A body is found by ear or it is not found at all.** In its whole window a body
sits on lit-or-remembered ground for 0 to 80 frames -- at best 1.6 seconds of
twenty, and none at all on the first three deaths of every seed. So the tick is
the primary channel and not a garnish, it quickens as the window runs out, and
it carries from the room next door, which the sonar does not.

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

# --- the body, the window, and the nest at the end of it -------------------
#
# **A worker who bleeds out leaves a body, and every body is temporary whatever
# you do about it.** Twenty seconds of window, thirty of nest, gone -- and a
# body you save is gone at the same moment the nest it prevented would have
# burnt out, because the alternative is a screen of them. Measured after issue
# #20: bodies accumulated and never left, seven of them on screen at once in a
# losing room's last minute, and *Screen Layout*'s rule is that anything drawn
# is a claim that it matters, because the player paid light to see it.

#: How long a body lies there before it turns: twenty seconds.
#:
#: **1,000 with issue #33, and it was 500 until then on purpose.** The vault
#: agreed twenty seconds when the mechanic was argued; the spike left ten
#: behind, and `test_held_constants.py` pinned the old value so the discrepancy
#: would be found deliberately rather than by surprise. This is that moment.
BODY_FRAMES = 1000

#: Clegs a nest produces, and how long it waits between them.
#:
#: **The spray economy already says the right thing and no number here was
#: chosen to make it:** a patch lasts `spray.PATCH_FRAMES` -- five seconds --
#: and a nest spawns every five, so **one charge buys exactly one spawn**. You
#: start with five charges and a nest's life is six spawns, so you cannot
#: suppress a nest for its whole life even by spending everything, and if you
#: tried you would have nothing left for the doorway you then have to get your
#: tail through. That is what *Clegs* means by suppression: you can hold ground
#: near a nest, you cannot destroy one.
#:
#: It is also why the window is worth so much more than the nest -- one charge
#: before it turns, against more than five after and still losing.
NEST_BROOD = 6
NEST_SPAWN_EVERY = 250

#: How long a nest lasts: thirty seconds, which is its six spawns.
#:
#: **A nest burns out and leaves nothing on screen.** It is the only thing
#: standing between a bad run and an unrecoverable one -- a Wanderer saves
#: nobody and douses nothing, so it faces up to six nests in sequence.
NEST_FRAMES = NEST_BROOD * NEST_SPAWN_EVERY

#: When a body stops existing, doused or not.
#:
#: **One rule, and that is the point of it.** A doused body lingers for as long
#: as the nest it prevented would have taken, so every body's whole life is the
#: same fifty seconds however it ends -- twenty of window and thirty of either a
#: nest or a corpse nobody has to keep looking at. Ending a doused body's life
#: thirty seconds after the *dousing* was the other reading and was rejected: it
#: makes saving somebody's body leave it on screen longer than losing it does.
GONE_FRAMES = BODY_FRAMES + NEST_FRAMES

#: Frames between a fresh body's ticks, and between a body's on the turn.
#:
#: **A body is found by ear or it is not found at all.** Measured: in its whole
#: window a body sits on lit-or-remembered ground for 0 to 80 frames -- at best
#: 1.6 seconds of twenty, and zero frames on the first three deaths of every
#: seed. The twenty-second window was argued from *reaching* a body and quietly
#: assumed the player would ever *see* one. They mostly will not, so the tick is
#: the primary channel rather than a garnish.
#:
#: **The same two numbers as the sonar, deliberately.** In Spotlight a
#: quickening tick always means you have less time than you did -- the swarm's
#: clicks quicken as they close, a worker's calls quicken as their blood runs
#: out, a body's tick quickens as it turns. One language, three speakers, three
#: things you cannot see. What tells them apart is timbre and not rate: the body
#: is a lower, doubled click against the sonar's single one, because rate is
#: already carrying the meaning and cannot carry identity as well.
TICK_SLOWEST = 50
TICK_FASTEST = 8

# --- what a worker is doing ------------------------------------------------

WAITING, FOLLOWING, SAVED, DEAD = 0, 1, 2, 3

#: Pixels of the player's trail between one follower and the next. A person is
#: sixteen tall and eight wide; this is a little more than a body length, so the
#: line reads as a line rather than as a stack.
#:
#: **Held at twelve by issue #21, deliberately.** A tail of four spans six cells
#: at this spacing and clears a doorway in under a second, which is a queue
#: rather than a line -- the vault wants about half a room and two to three
#: seconds. That is a **tuning number, not a design change**: it is tracked in
#: *Resource budgets* with the rest of phase 2, and the second room is what
#: finally makes it measurable. Hard-coding a wider spacing here would be a
#: number chosen by the person who built the doorway rather than by the person
#: measuring it, and phase 2 would then have to fight it.
TAIL_SPACING = 12


class Worker:
    """One trapped worker: where they are, how long they have, and what next."""

    __slots__ = ("x", "y", "room", "start", "state", "blood", "start_blood",
                 "reference", "phase", "recorded", "doused", "hatched",
                 "_tick", "_since_death")

    def __init__(self, x: int, y: int, phase: int = 0,
                 blood: int = WORKER_BLOOD, reference: int = 0,
                 room: int = 0) -> None:
        self.x, self.y = x, y
        #: **Which room they are in.** A waiting worker never changes it; a
        #: follower's is set by `follow`, because the trail they walk is a path
        #: through the building rather than a path across a room. A body keeps
        #: whichever it had: the vault settled on 2026-09-07 that a follower who
        #: dies mid-tail leaves the line to close up and **the body stays where
        #: it fell, in the room it fell in** -- which is the interesting part,
        #: because going back for it is a second journey against the same clock.
        self.room = room
        #: Where they were trapped, kept so a report can say where the player
        #: found them rather than where they ended up. It is what somebody
        #: remembers ninety seconds later.
        self.start = (room, x, y)
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
        #: **Has a spray charge been spent on this body inside its window?**
        #: One bit, and it is the whole of what dousing changes: a doused body
        #: never turns, so it never spawns, and it still goes at `GONE_FRAMES`
        #: like every other body. One byte on the Z80 alongside `recorded`.
        self.doused = False
        #: How many of this nest's brood have been placed. The rest of the
        #: nest's state is arithmetic on `_since_death`, so a nest that is
        #: held up by the valve keeps its clock and spends its thirty seconds
        #: regardless -- see `owed`.
        self.hatched = 0
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

    def at(self, room: int) -> bool:
        """Are they in this room? Everything about a person is room-local."""
        return self.room == room

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

    # --- the body's own lifecycle -----------------------------------------
    #
    # Four states and no state variable: a body is where it is in its fifty
    # seconds, plus one bit saying whether somebody spent a charge on it. That
    # is deliberate -- the whole of this section is arithmetic on the frame
    # counter every body already had, which is what makes it affordable to run
    # for seven people in two rooms on a Z80.

    @property
    def age(self) -> int:
        """Frames since they died, which is the whole of a body's state.

        Negative for exactly one frame after a Cleg kills somebody -- see
        `bitten`, which starts the body a frame behind so that the two kinds of
        death share a frame zero.
        """
        return self._since_death

    @property
    def gone(self) -> bool:
        """Has this body stopped existing?

        **Every body expires, doused or not, and this is the one rule that says
        so.** A burnt-out nest leaves nothing on screen and neither does a body
        somebody saved; what the player is left with is what they did about it
        while it was there.
        """
        return self.state == DEAD and self._since_death >= GONE_FRAMES

    @property
    def turning(self) -> bool:
        """Has this body lain long enough to become a nest?

        The name is older than nests: it was the window, kept visible before
        there was anything at the end of it. There is now, and the only thing
        that changes the answer is a spray charge spent inside the window.
        """
        return (self.state == DEAD and not self.doused
                and self._since_death >= BODY_FRAMES)

    @property
    def nesting(self) -> bool:
        """Is this a nest right now -- turned, and not yet burnt out?"""
        return self.turning and not self.gone

    @property
    def in_window(self) -> bool:
        """Is this a body a spray charge could still save?

        The twenty seconds between the death and the turn, and only those. A
        doused body cannot be doused again and a nest cannot be undone.
        """
        return (self.state == DEAD and not self.doused
                and self._since_death < BODY_FRAMES)

    def douse(self) -> bool:
        """Spend a charge on this body. Returns True the once.

        **One charge, of five, and it stays a body.** It is the cheapest thing
        the spray ever does -- one charge before it turns against more than five
        after and still losing -- and it is why the window is the mechanic and
        the nest is the consequence.
        """
        if not self.in_window:
            return False
        self.doused = True
        return True

    @property
    def owed(self) -> int:
        """Spawns this nest has earned and not yet placed.

        Earned from the clock rather than counted down, so **a nest that is
        held up spends its thirty seconds regardless**: the hold-the-spawn valve
        can delay a brood and it can never cancel one, and it cannot buy the
        nest more time by making it wait. The first hatches on the frame it
        turns and the sixth five seconds before it burns out.
        """
        if not self.nesting:
            return 0
        age = self._since_death - BODY_FRAMES
        earned = min(NEST_BROOD, age // NEST_SPAWN_EVERY + 1)
        return earned - self.hatched

    # --- the body's tick ---------------------------------------------------

    @property
    def ticking(self) -> bool:
        """Is this body making a noise?

        **From the moment of death until it is doused or it turns**, which is
        exactly the window a charge is worth spending in. A doused body is
        silent because there is nothing left to decide about it; a nest is
        silent because it is no longer a decision either -- by then the room is
        telling you about it in Clegs.
        """
        return self.in_window

    @property
    def tick_period(self) -> int:
        """Frames between this body's ticks: slower fresh, quicker on the turn.

        Linear in the age of the body, in integers, the same shape as the
        sonar's own interval. It is the third speaker of the same sentence:
        a quickening tick means you have less time than you did.
        """
        span = TICK_SLOWEST - TICK_FASTEST
        age = min(BODY_FRAMES, max(0, self._since_death))
        return TICK_SLOWEST - span * age // BODY_FRAMES

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

    def __init__(self, positions, exit_at=None,
                 blood: int = WORKER_BLOOD) -> None:
        """`positions` is (x, y), (x, y, blood) or (room, x, y, blood).

        Everything is authored on one line so that a position, its clock and
        the room it is in cannot be renumbered apart from one another. The
        shorter forms take `blood` and room zero, and exist for tests and for a
        room that has not been given a ladder yet.

        `exit_at` is `(room, (cx, cy))`, or `(cx, cy)` for a building of one
        room. **There is one way out of a building**, not one per room, and it
        is where every distance is measured from.
        """
        rows = [tuple(p) for p in positions]
        count = max(1, len(rows))
        placed = [row if len(row) == 4 else (0,) + row for row in rows]
        bloods = [row[3] if len(row) > 3 else blood for row in placed]
        # The **building's** longest clock. Every worker's call rate is read
        # against it, so the shouting is a comparison between people rather than
        # seven separate percentages -- and with two rooms it has to be the
        # building's, or the same blood would sound differently urgent
        # depending on which side of a wall somebody was standing.
        reference = max(bloods) if bloods else blood
        self.workers = [Worker(row[1], row[2],
                               phase=i * CALL_PERIOD // count,
                               blood=own, reference=reference, room=row[0])
                        for i, (row, own) in enumerate(zip(placed, bloods))]
        if exit_at is not None and not isinstance(exit_at[1], (tuple, list)):
            exit_at = (0, tuple(exit_at))
        #: (room, (cx, cy)), or None for a building with no way out.
        self.exit = None if exit_at is None else (exit_at[0], tuple(exit_at[1]))
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

    def alive_waiting(self, room: int | None = None) -> list[Worker]:
        return [w for w in self.workers if w.state == WAITING
                and (room is None or w.room == room)]

    def bodies(self, room: int | None = None) -> list[Worker]:
        """The bodies lying there: still in their window, or doused.

        **Not the nests and not the ones that have gone.** A body that turned
        is a nest and is drawn as one; a body that ran out of lifecycle is not
        drawn at all. Everything that asks this question is asking what to
        paint, and a burnt-out nest is a claim that something matters made
        about nothing.

        `lost` and `died` still count all of them, because they are a tally of
        what happened to seven people and that does not expire.
        """
        return [w for w in self.workers
                if w.state == DEAD and not w.turning and not w.gone
                and (room is None or w.room == room)]

    def nests(self, room: int | None = None) -> list[Worker]:
        """The bodies that turned and have not yet burnt out."""
        return [w for w in self.workers if w.nesting
                and (room is None or w.room == room)]

    def ticking(self, rooms=None) -> Worker | None:
        """The body to be heard, of those in `rooms`, or None.

        **At most one body ticks at a time**, and with twenty-second clocks and
        a twenty-second window that is nearly always literally true rather than
        a choice this has to make. When a bite makes it false, the one with the
        least time left wins: the tick means *you have less time than you did*,
        so the body nearest turning is the one it is about.

        `rooms` is which rooms can be heard from where the player is standing.
        **The tick carries from the adjacent room**, unlike the sonar, which
        reports only the room you are in -- and that is the only reason going
        back for a body behind you is a decision rather than a guess.
        """
        heard = [w for w in self.workers if w.ticking
                 and (rooms is None or w.room in rooms)]
        if not heard:
            return None
        return max(heard, key=lambda w: w._since_death)

    def calling(self, frame: int, room: int | None = None) -> list[Worker]:
        """Whoever is shouting, optionally only in one room.

        The room filter is what the doorway rule is built on (issue #21): the
        player sees the calls in the room they are standing in over the people
        making them, and the calls in the room next door over the **doorway**
        that connects to it. Same query, asked twice.
        """
        return [w for w in self.workers if w.calling(frame)
                and (room is None or w.room == room)]

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

    def reach(self, room: int, cells) -> Worker | None:
        """Has the player got to somebody still waiting? Returns them the once.

        `cells` is every cell the *player* occupies, not the one cell they stand
        on. Two figures whose bodies overlap are touching, and requiring their
        feet to land in the same cell meant walking through somebody chest-first
        and not reaching them.

        `room` is which room those cells are in, and it is not optional. Cell
        (17, 4) exists in every room in the building and means somewhere
        different in each of them; without the room a player could free somebody
        through a wall from the room next door.
        """
        standing = set(cells)
        for worker in self.workers:
            if worker.state == WAITING and worker.room == room \
                    and standing & worker.cells():
                worker.state = FOLLOWING
                self.tail.append(worker)
                return worker
        return None

    def follow(self, room: int, x: int, y: int) -> None:
        """Walk the tail along the path the player walked.

        Followers step where the player stepped rather than heading for where
        the player *is*. That is what makes a line behave like a line -- it
        strings out around corners and through a doorway one at a time, instead
        of clumping into the player's back and cutting every corner.

        **The trail is a path through the building, not across a room** (issue
        #21). Each step carries the room it was taken in, so a follower arrives
        at the doorway, crosses at the point the player crossed, and appears in
        the new room one at a time as they get there. Nothing about the crossing
        is special-cased: the room is simply another coordinate.
        """
        step = (room, x, y)
        if not self._trail or self._trail[0] != step:
            self._trail.insert(0, step)
        needed = TAIL_SPACING * (len(self.tail) + 1)
        del self._trail[needed:]
        for i, worker in enumerate(self.tail):
            at = TAIL_SPACING * (i + 1)
            if at < len(self._trail):
                worker.room, worker.x, worker.y = self._trail[at]

    def at_exit(self, room: int, cells) -> bool:
        """Is the player touching the way out?

        Split out of `deliver` for issue #20: the exit now ends the run whether
        or not anybody is following, so "am I at the door" and "is there
        anybody to hand over" are two questions and were one. The room is asked
        for the same reason `reach` asks: a cell reference means nothing without
        one.
        """
        return (self.exit is not None and self.exit[0] == room
                and self.exit[1] in set(cells))

    def deliver(self, room: int, cells) -> list[Worker]:
        """At the exit, everybody following is out. Returns who was saved.

        `cells` is the player's whole body, not the cell under their feet. The
        exit is a door in a wall, and a person is two cells tall -- so standing
        *on* a door in the top row of a room would put their head inside the
        masonry, and the feet-cell test made the way out unreachable. Touching
        the door is leaving by it.
        """
        if self.exit is None or not self.tail or not self.at_exit(room, cells):
            return []
        out = list(self.tail)
        for worker in out:
            worker.state = SAVED
        self.tail.clear()
        return out
