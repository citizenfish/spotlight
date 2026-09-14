"""Clegs: drawn to light, attach, drain, and drop off sated.

**Light is the only thing a Cleg responds to.** Not warmth, not blood, not
noise. One rule governs everything they do, which means every question about
what attracts them reduces to a question about what is lit -- and it is what
makes the light in [[Light and Darkness]] a bargain rather than a gift.

Two consequences of that rule are worth stating because they are easy to lose:

* **Only LIT light attracts.** The personal glow is dim, so it draws nothing.
  Walking in the dark is genuinely safe; switching your spotlight on is the
  decision that costs. If the glow attracted, darkness would be no refuge and
  the toggle would be pointless.
* **A light on the floor pulls as hard as one in your hand.** That is baiting:
  leave a spotlight burning, walk away in the dark, and the swarm goes to it.
* **They notice light near them, not light anywhere.** Each fly has its own
  range, so a light recruits the ones around it and leaves the rest blundering.
* **No two of them share a cell.** They all steer for the same light by the same
  rule, so without this they converge on one square and stack -- which is not a
  swarm, it is one Cleg drawn six times. The rule holds through a doorway too,
  since issue #65: see `Swarm.tick`'s `held_beyond`.
* **Your own glow reaches a few cells.** Standing still in the dark is a short
  reprieve rather than a hiding place: nothing crosses the room for you, but
  whatever blunders close will find you. Keep moving.
* **What they noticed, they remember.** Switching off does not call them back:
  they keep coming to where the light was. A one-second flash is a decision with
  consequences that arrive several seconds later, which is the whole rhythm.

Once a Cleg is on you the damage is already decided. It cannot be shaken off and
the flyspray does not touch it. The whole defensive game happens *before*
contact -- in where you stand, what you light, and where you laid spray.

**A lit person is prey, and the player is not the only person.** Issue #19: the
swarm never saw a worker, so a follower in the light was in no danger and the
choice the tail is built on -- turn to check your line and you expose it -- did
not exist in the build. It is not a second rule; it is the one rule read
honestly. *Trapped Workers* has it: "a worker trailing you through darkness is
ignored, and one standing in your cone is prey."

The asymmetry is the mechanic and not an implementation detail. **Darkness
protects the tail; light endangers it.** So a Cleg finds a worker exactly where
a *player* would see one -- see `Swarm.tick`'s `prey` argument, which the
session fills from `LightField.prey_at`, the prey flag beside the reveal flag
the drawing uses. If you can see them, so can the flies -- with one exception
since issue #64, in the safe direction: the held debug view shows everybody
and hands nobody over. (The opening flash did too, until issue #79.)

No pathfinding, and nothing here should ever acquire any. A Cleg steers for the
nearest lit source by comparing squared distances -- a handful of integer
subtractions per Cleg per step -- and slides along a wall it cannot pass. A fly
that solved mazes would be a different animal and a much more expensive one.
"""

from spotlight.core.constants import COLS

from .sources import LURE_KINDS, LURE_MAGNET, LURE_NONE, xorshift16

# --- states ----------------------------------------------------------------

HUNTING, ATTACHED, SATED = 0, 1, 2

# --- temperaments ----------------------------------------------------------
#
# **Not every Cleg is the same Cleg.** They all obey the one rule -- go to the
# light -- but they differ in how, which is the trick Pac-Man's ghosts use and
# it costs almost nothing here either.
#
# The problem it solves was visible the moment the room could be watched: an
# identical rule with an identical target produces identical paths, so the swarm
# converged into a single moving clot. That is bad twice over. It looks like one
# animal rather than several, and one spray patch dropped on the clot killed the
# entire swarm at once.

#: Straight at the light, and straight through anything on the floor.
PLAIN = 0
#: Comes in off to one side, so it does not share a path with the rest.
FLANKER = 1
#: Straight at the light, but will not walk into spray.
DODGER = 2
#: Both. The rare one, and the one that ruins a lazy plan.
WARY = 3

#: Drawn from a Cleg's seed. Weighted so most of a swarm is fodder and being
#: cornered by a clever one is an event rather than the norm. Half of them walk
#: straight into spray; one in four will not walk into it at all.
TEMPERAMENTS = (PLAIN, PLAIN, PLAIN, PLAIN, FLANKER, FLANKER, DODGER, WARY)

#: Where a flanker aims, relative to the light: four cells off, one of eight
#: ways. Four rather than two so the approach is genuinely a different line and
#: not a wobble on the same one.
FLANK_OFFSETS = ((4, 0), (-4, 0), (0, 4), (0, -4),
                 (3, 3), (3, -3), (-3, 3), (-3, -3))

#: How close a flanker gets before it stops swinging wide and comes in.
#:
#: Must not be *less* than the offset, or the flanker switches to a direct line
#: before it has ever reached the position it was flanking to, and the whole
#: thing quietly does nothing. That was the first version.
FLANK_UNTIL = 4

#: Frames between steps. Slightly slower than the player, who covers a cell in
#: eight frames -- so you can outrun a swarm, but you cannot stand and read the
#: room while it closes. That margin is the whole of the moment-to-moment game.
#:
#: Each fly draws its own from this range. Identical speeds put the swarm in
#: lockstep, which is half of why it moved as one body; a spread of a few frames
#: is enough to break the formation up without making any of them notably faster
#: or slower than the player.
STEP_EVERY = 9
STEP_SPREAD = 3

#: Steps a wandering Cleg holds one heading for, and how much that varies.
#: Long enough to cross a good part of the room before it changes its mind.
ROAM_RUN, ROAM_SPREAD = 6, 9

#: Frames between steps for a Cleg with nothing to steer for.
#:
#: Deliberately slow. A Cleg with no light to chase should mill about roughly
#: where it is, not diffuse across the room -- at a brisk drift the whole floor
#: becomes randomly scattered mines, and *moving* costs more blood than standing
#: still, which is exactly backwards. Light is what brings them to you; drifting
#: should not do the job for it.
DRIFT_EVERY = 45

#: Blood a single Cleg takes before it drops off, and how fast it takes it.
#: One point every twelve frames, eight points in all -- about two seconds
#: attached, which is long enough to feel and short enough not to be a cutscene.
DRAIN_TOTAL = 8
DRAIN_EVERY = 12

#: Game steps between wing flips for a Cleg attached to somebody (issue #61).
#: **Six, provisional**: an 8 Hz beat, which is a fly and not a strobe. This
#: is drawing cadence and nothing a rule reads; it touches no log, so it can
#: be tried at other values from a keyboard without moving a run.
#:
#: **The one class of fly that animates on the clock.** The tester measured
#: the step-tied wingbeat and it read as no animation at all: a flip that is
#: coincident with an eight-pixel jump of the whole sprite is credited to the
#: jump, and the fly the player looks at longest -- the one biting them, 28 to
#: 31 per cent of drawn fly-frames -- never flipped at all. So the attached
#: fly flaps on the frame counter, and it is bounded by the number of flies on
#: a person rather than the size of the swarm. Priced on the port: nothing
#: while the victim walks, because their box is redrawn every frame anyway;
#: while they stand still, one erase-and-redraw at `building.CLEG_COST` per
#: attached fly per flip, about 140 T-states a frame each at six.
ATTACHED_FLAP_FRAMES = 6

#: Frames in the wingbeat cycle, A M B M (issue #73). `Cleg.wing` counts
#: 0 to 3 and `sprites.CLEG_FRAMES` is indexed by it, so the two have to
#: agree and `test_spike_sprites` pins that they do. A power of two so that
#: advancing is an increment and a mask on the port -- still one byte per
#: fly, of which two bits are used.
WING_CYCLE = 4

#: How long a sated Cleg blunders about before it is hungry again, and how
#: fast it moves while doing it.
#:
#: **A fed fly leaves.** It drifts quickly rather than slowly, so it is somewhere
#: else by the time it is hungry again. Without that it simply sits on the cell
#: it fed from, notices the glow it is standing in, and bites again for ever --
#: one Cleg draining a whole blood budget on its own, which is not a swarm, it
#: is a leak.
#: Ten seconds, which is long and deliberately so. **A swarm reaching you has
#: to be a crisis rather than a climate.** At three seconds a fed Cleg was back
#: on you almost at once and six of them held a permanent grip -- roughly a bite
#: every three seconds, for ever, which is not a swarm arriving, it is weather.
#: Long enough away, and drifting briskly while it is, means an arrival is an
#: event you survive and then have time to do something about.
SATED_FRAMES = 500
SATED_DRIFT_EVERY = 9

# --- what happens to a Cleg riding a player who bleeds out ------------------
#
# **Death must not remove Clegs from the game.** It used to: the session's death
# branch dropped every attached fly out of the swarm list, permanently, so a run
# with two deaths was played against half a swarm and the gap between the first
# death and the second was nearly four times as long as the gap before the first.
# Dying was rewarded, which inverts the whole bargain (issue #27).
#
# Two things had to be decided with the fix, and both change how dangerous the
# minute after a death is:
#
# **Where they go.** They scatter into the free cells around the spot you fell
# on. They do not ride you to the entrance -- that is instant re-death and no
# player could read it -- and they do not stay stacked on the one cell either,
# because the swarm's own rule is that no two share a cell and six flies in one
# square is not a swarm, it is one Cleg drawn six times. Scattering leaves the
# place you died a knot of flies you can see coming and learn to walk around.
#
# **Whether they are fed.** They are. A fly that was drinking when the blood ran
# out has had the whole budget off you, and the design already says what a fed
# fly does: it goes sated and drifts briskly away, because otherwise it "sits on
# the cell it fed from, notices the glow it is standing in, and bites again for
# ever". Detaching them hungry reproduces exactly that leak on top of a player
# who has just been put back with a fresh eight pips, which is the instant
# re-death the issue rules out. Being fed is not a reprieve the player earned by
# dying: it is ten seconds bought with a full blood budget, against a swarm that
# is still the size it was.
#
# Rejected, and recorded because it is the obvious alternative: **letting a
# part-fed Cleg keep its progress** across the death, so a fly on 6 of 8 needs
# only two more bites from the new life. It is defensible -- it makes the minute
# after a death harsher, which is the direction this bug wants correcting in --
# but it stacks a second drain on a player who cannot yet have moved, and the
# issue asks explicitly that the respawn be survivable. The blood is charged
# once, for one meal.

#: Where a detached Cleg is put, relative to the cell it was feeding on. Tried
#: in this order: the four orthogonal neighbours, then the diagonals, then the
#: ring at two cells. Ordered by squared distance, so a fly ends up as close to
#: where it was as the room allows.
#:
#: A fixed table, deliberately. It is two adds and a solidity test per entry
#: until one fits -- no search, no route-finding, nothing a Cleg is not allowed
#: to have. `(0, 0)` is not in it: every detached fly leaves the square you fell
#: on, which is the square you are put back on if you died at the entrance.
SCATTER = ((0, -1), (0, 1), (-1, 0), (1, 0),
           (-1, -1), (1, -1), (-1, 1), (1, 1),
           (0, -2), (0, 2), (-2, 0), (2, 0),
           (-1, -2), (1, -2), (-1, 2), (1, 2),
           (-2, -1), (2, -1), (-2, 1), (2, 1),
           (-2, -2), (2, -2), (-2, 2), (2, 2))

# --- hunger ----------------------------------------------------------------
#
# **A Cleg that has not fed notices fainter light.**
#
# This is the answer to a problem that took measuring to see. With the light
# off, the only light on the player is their own glow, which carries two cells,
# so effectively nothing ever targeted them: over two minutes of hiding in a
# corner, 37% of the swarm was chasing the searchlight, 15% was idle, and **1%
# was heading for the player.** You could sit in a corner and watch them ignore
# you, because a searchlight is a light they can always notice and never catch,
# and it occupied them for ever.
#
# Hunger fixes it without adding a second stimulus, which matters -- light is
# the only thing Clegs respond to and that rule is load-bearing. Hunger does not
# change *what* they respond to. It changes **how faint a light has to be before
# they cannot notice it**, which is a property of the fly, not of the world.
#
# What it buys is the thing the room was missing: **pressure that builds.** The
# dark is a genuine refuge for a while and then stops being one, so hiding is a
# breather you take rather than a place you live. It also gives the swarm a
# rhythm -- they converge, feed, lose interest, and drift back -- which reads as
# an animal rather than as a rule.

#: Frames of not feeding per extra cell of sensitivity. Five seconds a cell.
HUNGER_STEP = 250

#: The most it can add. Past this a fly is as keen as it is going to get, and
#: without a cap a long quiet spell would make the whole room omniscient.
#:
#: **Twelve, and a cut to six was tried and reverted (issue #25).** The cut was
#: made on an argument that hunger is what closes the last stretch on a
#: motionless player: at twelve a starving fly notices the glow from fourteen
#: cells, and standing still in the dark cost 33.2 blood every thirty seconds
#: against 49.6 with the torch lit. Cutting the cap was predicted to take the
#: dark figure to 18-20 and leave the lit one alone.
#:
#: **It changed nothing, at any setting.** Measured over five seeds: the dark
#: thirty-second cost is 33.2 at every cap from 2 to 12, 25.6 at 1, and 20.8
#: with hunger abolished entirely. Two reasons, both arithmetic:
#:
#: * Six cells of keenness takes 6 * 250 = 1500 frames, which *is* the thirty
#:   second window. Inside it, caps of six and twelve are the same number.
#: * The beam wins the nearest-lure comparison first. Over three minutes the cap
#:   changes which lure a fly picks on 0-35 cleg-frames, and never on a frame
#:   where the fly steps.
#:
#: So **hunger's first two cells do all its work and the cap is inert**: the beam
#: delivers a fly to within about four cells and the base glow does the rest.
#: Past four there is nothing left for keenness to find. The claim that this is
#: "the single most important number in the game" was withdrawn with the sweep.
#:
#: Do not reach for this dial. The cost of light lives in what recruits the
#: swarm, not in what sharpens it -- see `FAR`.
KEEN_MAX = 12

#: How far a Cleg can notice a light, and how much that varies between them.
#:
#: **A Cleg is not omniscient.** Without a limit every fly in the room reacts to
#: the same light on the same frame, so the swarm moves as one clump and a light
#: anywhere recruits everything -- which in practice meant the searchlight, being
#: always lit and always moving, held 94% of the swarm's attention for ever. They
#: trailed after a beam they could never catch and never came near the player.
#:
#: Giving each fly its own range fixes both. A light recruits the ones near it
#: and no others, so they arrive in a trickle rather than a wave, from different
#: directions, at different times.
NOTICE_MIN, NOTICE_MAX = 7, 19


class Cleg:
    """One fly. Position is a cell; Clegs do not need pixel placement."""

    __slots__ = ("cx", "cy", "state", "taken", "notice", "goal", "goal_source",
                 "kind", "flank", "step_every", "hunger", "heading", "victim",
                 "wing", "_run", "_timer", "_tick", "_seed")

    def __init__(self, cx: int, cy: int, seed: int = 0xBEEF) -> None:
        self.cx, self.cy = cx, cy
        self.state = HUNTING
        self.taken = 0            # blood drawn during the current attachment
        #: **Who it is on**, and `None` means the player (issue #19). One byte
        #: on the Z80 -- an index into the building's people, with zero for the
        #: player -- and it is the only thing that has to be remembered to let a
        #: fly feed on somebody who is not you. It is `None` rather than an
        #: index here because the player is passed to `tick` as a bare cell and
        #: a worker as an object; that asymmetry is deliberate, so that the
        #: player's path through this file is byte-for-byte what it was.
        self.victim = None
        self._timer = 0
        self._tick = 0
        self._seed = seed or 1
        #: How far this one notices light. Its own number, not the swarm's.
        self.notice = NOTICE_MIN + (self._random() %
                                    (NOTICE_MAX - NOTICE_MIN + 1))
        #: Where it last saw light and is still heading. **Kept after the light
        #: goes out**, which is what makes a one-second flash cost something:
        #: it commits whoever noticed to walking to where you were standing.
        self.goal: tuple[int, int] | None = None
        #: **Which light it came for**, kept from the moment it acquired the
        #: goal until it next feeds. One byte, and the thing bites are billed
        #: to -- see `commit` and issue #22. Nothing reads it to decide
        #: anything; it is a record, not an input.
        self.goal_source = LURE_NONE
        #: What sort of Cleg this is, and how it comes at you.
        self.kind = TEMPERAMENTS[self._random() % len(TEMPERAMENTS)]
        self.flank = FLANK_OFFSETS[self._random() % len(FLANK_OFFSETS)]
        self.step_every = STEP_EVERY + self._random() % STEP_SPREAD
        #: Frames since it last fed. Makes it keener, never faster.
        self.hunger = 0
        #: Which way it is wandering, and how much longer for.
        self.heading = (0, 0)
        self._run = 0
        #: **Which wing frame this fly is drawn in**: two bits since issue
        #: #73, a phase 0-3 over the cycle A M B M that `sprites.CLEG_FRAMES`
        #: is indexed by, advanced in `_beat`. From issue #49 to #73 it was
        #: one bit, flipped, and **the third frame changed nothing below
        #: about when it moves**: a flip became an advance, on the same
        #: events, so a fly is redrawn exactly when it was. It moves in
        #: `_try` when the fly steps a cell (issue #49), and since issue #61
        #: also in `flap`, on the clock, while the fly is attached to
        #: somebody. It was the only animation state anything in the play
        #: area carried until issue #60 gave the people a bit under the same
        #: rule.
        #:
        #: **The cadence is movement by default, and this is a port decision
        #: wearing an art decision's clothes.** Alternating every fly on
        #: `session.frame` is 25Hz, which is not a wingbeat but a strobe, and
        #: it dirties every fly's cell every other frame whether or not the fly
        #: moved: a worst case of thirty-six flies at `building.CLEG_COST` to
        #: erase and redraw, on every other frame, is about 15,000 T-states a
        #: frame spent animating flies that are standing still, against 32,832
        #: for all entities. **That sum used to read "eighteen flies at 1,654"
        #: and came to the same 15,000** (issue #58): the fly's price halved on
        #: 2026-09-07 and the worst case doubled with it, so the argument is
        #: untouched -- but the old wording quoted the pixel-positioned cost,
        #: which is withdrawn, and a figure in Cleg-equivalents is only a
        #: figure if it says which sprite format it was taken under. Tied to
        #: movement it is free, because a fly that stepped is being erased and
        #: redrawn anyway.
        #:
        #: **Two named exceptions, both bounded, ruled on 2026-09-11 (issue
        #: #61)** after the tester measured the step-tied beat and found it
        #: read as a still sprite: the flip rode on the jump and the eye
        #: credited the jump, and the fly biting the player never flipped.
        #:
        #: 1. **An attached fly flaps on the clock**, every
        #:    `ATTACHED_FLAP_FRAMES` game steps, in `flap`. Its phase is read
        #:    off the seed it already holds and never drawn -- see `phase`.
        #: 2. **An idle fly twitches in place.** A wandering fly whose drift
        #:    heading came up (0, 0) steps into its own cell through `_try`,
        #:    and `_try` flips the wing. The tester found this on 13 to 19 per
        #:    cent of flips and nothing documented it; it is now the rule, at
        #:    the rate the drift already rolls it (one heading in four), and it
        #:    is not tuned -- a draw to set its rate, or dropping (0, 0) from
        #:    the headings, would move every log in the project.
        #:
        #: So the sentence this docstring used to end on, *a still swarm costs
        #: nothing to animate*, was wrong and is withdrawn: an idle fly's
        #: twitch is an erase and a redraw of a fly that has not moved, at
        #: `building.CLEG_COST` per twitch. What is still true is that the
        #: cost is per twitching or attached fly, not per fly on screen.
        self.wing = 0

    def commit(self, cell: tuple[int, int], kind: int) -> None:
        """Take up a lure: where it is, **and what it was**.

        The whole of the attribution hook on the Cleg's side (issue #22), and
        it is one line of behaviour and one line of bookkeeping deliberately
        kept together, because the bookkeeping is only correct if it happens at
        the same instant as the decision.

        **The source is recorded at acquisition and then left alone for as long
        as the journey lasts.** A hunting Cleg re-takes its goal on every frame
        it can notice a light, and the light it can notice from one cell away is
        nearly always the player's own glow -- so billing the *latest*
        acquisition credits the glow with almost every bite in the game and
        measures nothing but the last hop. That version was built first and it
        put 100% of a dark Statue's blood on the glow, which is the coincidence
        the issue warns about rather than a finding.

        So the source moves only when the fly takes up a lure **having had
        none**: at the start of a journey. It survives the fly changing its mind
        mid-journey, which is the case that matters -- a Cleg that crossed the
        room for the searchlight and then switched to the glow at the last
        moment, or blundered onto a dark player after arriving, is the beam's
        kill. Feeding clears it, in `_sate`.

        Also tried and rejected: keeping the *first* lure since the last meal,
        never overwriting until the fly feeds. It bills a fly to something it
        walked to, arrived at and left forty cells and twenty seconds ago, which
        is not the journey that killed you.
        """
        if self.goal is None:
            self.goal_source = kind
        self.goal = cell

    @property
    def keenness(self) -> int:
        """Extra cells of sensitivity bought by going hungry."""
        return min(KEEN_MAX, self.hunger // HUNGER_STEP)

    @property
    def dodges(self) -> bool:
        """Will it refuse to walk into spray?

        Note what this does *not* do: it does not make the Cleg immune. Spray
        it is standing on still kills it. What a dodger denies you is the lazy
        version -- one patch dropped in front of a bunched swarm taking the lot.
        It will stand and wait rather than walk in, which leaves the spray doing
        exactly the job the design gives it: **area denial, not a weapon.**
        """
        return self.kind in (DODGER, WARY)

    @property
    def flanks(self) -> bool:
        """Does it come in off to one side rather than straight down the middle?"""
        return self.kind in (FLANKER, WARY)

    def aim(self, goal: tuple[int, int]) -> tuple[int, int]:
        """Where this Cleg actually steers for, given where the light is.

        A flanker aims two cells to one side of it until it is nearly there,
        then comes in. Same destination, different approach -- which is all it
        takes to stop six of them walking single file.
        """
        if not self.flanks:
            return goal
        if max(abs(goal[0] - self.cx), abs(goal[1] - self.cy)) <= FLANK_UNTIL:
            return goal
        return goal[0] + self.flank[0], goal[1] + self.flank[1]

    # --- movement ----------------------------------------------------------

    def _random(self) -> int:
        self._seed = xorshift16(self._seed)
        return self._seed

    @property
    def phase(self) -> int:
        """Where in the attached-flap cycle this fly beats (issue #61).

        **Read from the seed the fly already holds, never drawn from it.** One
        extra call to `_random` here would advance this fly's xorshift stream,
        change every heading it rolls afterwards, and move the event log of
        every run in the project -- the check on issue #61 is a byte-identical
        log, and this property is where that check would fail. The seed is
        stable for the whole of an attachment, because an attached fly draws
        no random numbers, so the phase is a constant of the bite.

        Three flies on one player get three seeds and so, mostly, three
        phases: they do not flap in lockstep. On the port this is the low
        byte of the seed reduced mod `ATTACHED_FLAP_FRAMES`, or a byte stored
        at attachment; either is read, not rolled.
        """
        return self._seed % ATTACHED_FLAP_FRAMES

    def flap(self, frame: int) -> None:
        """One game step of an attached fly's wingbeat (issue #61).

        Called from `Swarm.tick` where the attached fly's cell is written --
        on the game step, and never from the audio interrupt or the shell's
        loop, so a paused game is a still picture. `frame` is the session's
        frame counter; the bit flips when the counter, offset by this fly's
        `phase`, comes round to a multiple of `ATTACHED_FLAP_FRAMES`. Since
        issue #73 that is an advance through the four-frame cycle rather
        than a flip, on the same frames.

        This is the whole of exception 1 to the cadence rule on `wing`, and
        it is a comparison and an increment so that its cost on the port is
        a handful of T-states on the frames it does nothing, which is five
        in six.
        """
        if (frame + self.phase) % ATTACHED_FLAP_FRAMES == 0:
            self._beat()

    def _beat(self) -> None:
        """Advance the wingbeat one frame (issue #73).

        **The one place the wing state moves**, so that the events it moves
        on -- a step, the attached clock, the idle twitch -- are exactly the
        three the flip had, and a fourth cannot arrive without being named
        here. It is drawing state and nothing else: no random number is
        drawn, no rule reads it, and the event log does not know it exists.
        The check on issue #73 is the event log byte-identical on thirty-five
        runs, drawing on and off, and this method is where that would fail
        if it ever did more than count. One thing it does change: a full
        beat, wings out to wings out, is now four of these events where it
        was two, so at the same `ATTACHED_FLAP_FRAMES` an attached fly's
        out-to-out period doubles. The frame still changes every period;
        the period is the user's constant and is not touched here.

        The alternative not taken was to keep the bit and add a direction,
        A-M-B then B-M-A: the same picture with a second byte of state and
        a branch. A four-entry table with M in it twice draws it with an
        increment and a mask.
        """
        self.wing = (self.wing + 1) & (WING_CYCLE - 1)

    def _try(self, dx: int, dy: int, is_solid, avoid=None) -> bool:
        """One step, if the room will have it.

        **`is_solid` is the only authority on where a fly may stand**, edges
        included. It used to be checked *after* a bounds test against the room's
        own width and height, which meant a Cleg could never leave the room it
        started in however the level was drawn -- and that had to go with issue
        #21, because the column just past a doorway is the room next door's
        first column and `Room.is_solid` says so. Nothing here knows a doorway
        exists; a fly crosses one by walking into a cell that turns out not to
        be a wall.

        The room still stops it everywhere else: `Room.is_solid` answers True
        for anything outside its grid that is not a doorway, so the walls are
        as solid as they ever were.
        """
        nx, ny = self.cx + dx, self.cy + dy
        if is_solid(nx, ny):
            return False
        if avoid is not None and avoid(nx, ny):
            return False
        self.cx, self.cy = nx, ny
        # It stepped, so it is being erased and redrawn anyway: the wingbeat
        # rides on the move and costs nothing. See `wing`. **A (0, 0) step
        # lands here too**, and the beat it causes is the idle twitch of
        # issue #61 -- deliberate, see `_drift`, and not free.
        self._beat()
        return True

    def _toward(self, tx: int, ty: int, is_solid, avoid=None) -> None:
        """One greedy step, longest axis first, sliding if blocked.

        Trying the longer axis first is what makes the approach look purposeful
        rather than staircased, and falling back to the other axis is what stops
        a Cleg pressing itself into a wall for ever. Neither is pathfinding:
        there is no search, no memory of where it has been, and no way out of a
        dead end except the light moving.
        """
        dx = (tx > self.cx) - (tx < self.cx)
        dy = (ty > self.cy) - (ty < self.cy)
        if abs(tx - self.cx) >= abs(ty - self.cy):
            first, second = (dx, 0), (0, dy)
        else:
            first, second = (0, dy), (dx, 0)
        for step in (first, second):
            if step != (0, 0) and self._try(*step, is_solid, avoid):
                return

    def _drift(self, is_solid, avoid=None) -> None:
        """Wander, for a Cleg with nothing to steer for.

        It holds a heading for a run of steps rather than re-rolling every
        time. That single change is the difference between **diffusing and
        going somewhere**: an unbiased step-by-step walk barely leaves where it
        started, so parts of the room stayed permanently empty and a player who
        sat in one was left alone by everything that was not already beside
        them. Holding a heading covers ground at the same slow pace.

        It is also what a fly looks like. They do not jitter on the spot; they
        cross a room, stop, and cross it again.

        **And when the heading comes up (0, 0), the fly twitches** (issue
        #61). One heading in four is the null one -- `dx` and `dy` each come
        from a pair of bits and are zero when the pair agrees -- and a run on
        it is a run of steps into the fly's own cell, each of which `_try`
        accepts and flips the wing on. The tester found this on 13 to 19 per
        cent of all flips, undocumented, and the ruling made it the idle fly's
        twitch at exactly the rate it already had. **Do not tune it.** A draw
        to set the rate consumes a random number; dropping (0, 0) from the
        headings changes which headings are rolled; either moves every log.
        Priced on `wing`: an erase and a redraw of a fly that has not moved.
        """
        if self._run <= 0 or not self._try(*self.heading, is_solid, avoid):
            r = self._random()
            dx = (r & 1) - ((r >> 1) & 1)
            dy = ((r >> 2) & 1) - ((r >> 3) & 1)
            self.heading = (dx, dy)
            self._run = ROAM_RUN + (r >> 4) % ROAM_SPREAD
            self._try(dx, dy, is_solid, avoid)
        self._run -= 1


def _beside_any(cx: int, cy: int, cells) -> bool:
    """Is (cx, cy) next to any of `cells` -- Chebyshev distance exactly 1?

    The personal-space rule of issue #66, as a compare. Distance 0 is the
    older rule and is tested by the caller first, so this is only ever asked
    about a cell nobody is standing in. On the Z80 it is two subtractions and
    two compares per free fly in the room, on a step that happens every nine
    to twelve frames per fly. Measured over a 9,000-frame run of the statue
    and of the wanderer on the first look-round seed, the session's doorway
    walks included: 0.6 to 1.0 of these walks per frame for the whole
    building, each over 8 to 9 free flies, so 5 to 8 compares a frame --
    nothing. Two in five find a neighbour, because flies steering at one
    light from one side queue two apart, which is the rule doing what it
    says. The room next door is asked on 0.1 to 0.15 steps a frame.
    """
    for tx, ty in cells:
        if abs(cx - tx) <= 1 and abs(cy - ty) <= 1:
            return True
    return False


def _near_the_edge(cx: int) -> bool:
    """Is this column within one cell of the room's edge, or past it?

    The only place a step can land in, or beside, another room's grid.
    `Room.is_solid` answers for the column *past* a doorway by asking the
    room next door (issue #21), so a fly can stand at column -1 or `COLS`;
    and a fly next door can be standing on *this* room's first or last
    column, on the threshold it has just stepped onto and not yet been
    handed over from -- the session hands flies across at the end of the
    frame, after every swarm has ticked, so for the rest of that frame it is
    in the other room's list at the other room's coordinates. Both are the
    same cell seen from two rooms, and the no-two-share-a-cell rule has to
    see it once (issue #65).

    **One column further in since issue #66**, when the rule became no two
    *beside* each other: a step onto column 1 can land beside a fly next door
    standing on column 0. Was `_at_the_edge`, columns 0 and `COLS - 1` and
    past them; the first cut of #66 left it there, and the far room's door
    clot promptly re-formed out of main-room flies stepping through the
    doorway onto the cell *beside* a far-room fly, four of them touching at
    the lamp -- the #65 leak again, one ring out. Two compares on a step
    that happens every nine frames, and the list walk behind it runs only
    when they say so. Nothing here knows a doorway exists; it knows where
    its own grid ends.
    """
    return cx <= 1 or cx >= COLS - 2


class Swarm:
    """Every Cleg in the room, and the one rule they all follow."""

    def __init__(self, clegs: list[Cleg] | None = None) -> None:
        self.clegs = list(clegs or [])
        self.drained = 0          # blood taken this frame, for the caller
        self.attachments = 0      # completed attachments, for the record
        #: **What each lure cost the player**, indexed by the `LURE_*` kind in
        #: `sources`. Issue #22: the claim that the searchlight delivers three
        #: quarters of the swarm was inferred from timing, and no beam constant
        #: moves until it is measured at the point of attachment instead.
        #:
        #: Write-only as far as the game is concerned. Nothing in `tick` reads
        #: either of these, and nothing ever should -- a Cleg that knew which
        #: lure had paid best would be a different animal.
        self.bites_by_source = [0] * LURE_KINDS
        self.blood_by_source = [0] * LURE_KINDS

        # --- what the swarm took off somebody who is not the player --------
        #
        # Kept apart from the four counters above **on purpose**. The vault
        # quotes "184-192 of a dark Statue's 192 points of blood are the
        # searchlight's" and the whole value of that figure is that it is a
        # measurement of what the *player* paid; folding a worker's blood into
        # the same buckets would silently invalidate every number taken with
        # the #22 hook. Worker blood is a different currency anyway -- a point
        # is `rescue.BLEED_EVERY` frames of somebody's life, not a pip of eight.
        #: Victims that gained a fly this frame, for the session to log.
        self.bitten: list = []
        #: Blood taken off non-player victims: this frame, and in all.
        self.victim_drained = 0
        self.victim_blood = 0
        self.victim_attachments = 0

    # --- the one rule ------------------------------------------------------

    @staticmethod
    def notice(cx: int, cy: int, lures, within: int | None = None,
               keenness: int = 0) -> tuple[int, int, int, int] | None:
        """The closest light this Cleg can notice, whole, or None.

        Each lure is `(cx, cy, reach, kind)`: where it is, how far it carries,
        and **what it is** -- the last of which is carried so a bite can be
        billed to the light that caused it (issue #22). It takes no part in the
        choice: the winner is decided on squared distance exactly as before,
        and the kind comes along with it.
        A light must be inside **both** its own reach and this Cleg's -- a
        bright light across the room is no use to a fly that cannot notice it,
        and your dim glow is no use to one three rooms away.

        `keenness` is what hunger adds to a light's reach. It matters only for
        faint ones: a bright light already carries further than any Cleg can
        notice, so hunger cannot make it carry further still. The one light it
        does change is the player's own glow, which is exactly the point.

        Squared distance, so there is no square root -- the Z80 has neither
        that nor a divide, and comparing squares orders the same as comparing
        distances.
        """
        best, best_d2 = None, None
        for lure in lures:
            lx, ly, reach = lure[0], lure[1], lure[2]
            reach += keenness
            limit = reach if within is None else min(within, reach)
            dx, dy = lx - cx, ly - cy
            d2 = dx * dx + dy * dy
            if d2 > limit * limit:
                continue
            if best_d2 is None or d2 < best_d2:
                best, best_d2 = lure, d2
        return best

    @classmethod
    def nearest_lure(cls, cx: int, cy: int, lures, within: int | None = None,
                     keenness: int = 0) -> tuple[int, int] | None:
        """Where the closest light this Cleg can notice *is*, or None.

        `notice` with the answer narrowed to the cell. Kept because the cell is
        all most callers want, and because the one rule reads better without
        the bookkeeping in the middle of it.
        """
        seen = cls.notice(cx, cy, lures, within, keenness)
        return None if seen is None else (seen[0], seen[1])

    # --- the frame ---------------------------------------------------------

    def _elbow_room(self, player_cell):
        """Cells another Cleg is standing in, which none may step into **or
        beside**.

        Without it they pile onto whichever square the nearest light is at --
        every one of them steering by the same rule to the same place, arriving
        as a single blob. Keeping a cell each spreads the same arrival over the
        ground around it, which is what a swarm looks like.

        Since issue #66 the set is read two ways: a step *into* one of these
        cells is refused everywhere, and a step *next to* one is refused too
        unless the step is arriving at somebody -- see `_haven`. One cell each
        was measured and found wanting: the far room's permanent lamp held its
        own flies at nearest-neighbour 1.2 to 1.8 cells, 76 to 87 per cent of
        them within two cells of their centroid, which is a clot, and the user
        said so. Two cells each is the ruling, with the lamp left where it is.

        The player's own cell is left out. Several can be attached to you at
        once, and an arriving one must never be blocked from reaching you by
        the ones already feeding. The set is otherwise exactly what it was --
        this swarm's free flies, updated in step order -- and that is
        deliberate: the widening is in how it is read, not in what is in it.
        """
        taken = {(c.cx, c.cy) for c in self.clegs if c.state != ATTACHED}
        taken.discard(player_cell)
        return taken

    @staticmethod
    def _haven(player_cell, victims) -> frozenset:
        """Cells where the personal-space rule is waived: every cell holding
        prey, and the ring around each (issue #66).

        The two-cell rule is about **how flies arrive**, not about how many
        can reach a person once there. Without this a fly waiting one cell
        from the player fences off the ring the next arrival has to pass
        through, and the tester's model of the rule without it dropped bites
        on the routing bots by 15 to 20 per cent -- a difficulty change
        arriving through a spacing rule, which nobody asked for and which
        would have been unreadable against the blood and population levers.

        **Keyed to prey and not to the fly's goal, on purpose.** Prey is the
        session's prey list -- the player, lit or not, and any worker a lit
        revealing light is on -- and nothing else. A fly hunting a room light
        has a goal and no prey, so the ring round the far room's lamp is *not*
        in this set and the clot there spreads, which is the whole point. Keyed
        to the goal the clot would re-form one ring out and the rule would buy
        nothing. `test_spike_space` pins both directions.

        Built once a frame, like `prey_cells`: at most eight people times
        three cells times nine, and each step that is about to be refused
        then does one lookup. The set is a Pygame-side convenience; on the Z80
        it is a Chebyshev compare against the prey list instead, reached only
        after the neighbour compare has found somebody -- which, measured, is
        two steps in five that get that far, well under one a frame.
        """
        cells = set()
        anchors = list(victims)
        if player_cell is not None:
            anchors.append(player_cell)
        for px, py in anchors:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cells.add((px + dx, py + dy))
        return frozenset(cells)

    @staticmethod
    def prey_cells(prey) -> dict:
        """cell -> the lit person standing in it.

        `prey` is whoever is **plainly lit this frame and not the player**: see
        `Session._lit_people`, which builds it from `LightField.prey_at`, the
        prey flag beside the reveal flag that decides whether a person is
        drawn -- the same light, except under the held debug view. A person in
        darkness is not in this map and is therefore ignored, which is the
        whole of the tail's tension (issue #19).

        Built once a frame rather than asked per fly, because a fly must not
        acquire a search: this is at most seven people times the three cells an
        8x16 figure straddles, and the swarm then does one dictionary lookup
        each. On the Z80 it is a short list of (cell, person) pairs walked
        linearly, which for a handful of entries is cheaper than a hash.

        Later people win a shared cell. Two figures standing in the same square
        is rare and either answer is defensible; what matters is that it is
        decided here rather than by iteration order somewhere else.
        """
        cells = {}
        for person in prey:
            for cell in person.cells():
                cells[cell] = person
        return cells

    def tick(self, lures, player_cell, is_solid, blood: int,
             is_sprayed=None, prey=(), doors=(), frame: int | None = None,
             held_beyond=None, magnet=None) -> int:
        """Advance every Cleg. Returns the **player's** blood remaining.

        `magnet` is the player's cell while the player is a Cleg magnet
        (issue #82, *The searchlight magnet*), or None. **While it is given,
        every hunting fly in this swarm commits to it every frame in place of
        the lure comparison**: no reach test, no notice range, no looking at
        the doorways. It is not a light and it is not compared with one; the
        beam gave the player away and for ten seconds the room knows where
        they are. Sated and attached flies are untouched, and so is hunger --
        a magnet changes where a fly is going and nothing about what it is.
        The source is overwritten on every commit, so a fly that was on a
        beam journey when the magnet started is billed to the magnet, which
        is the beam's kill by another name.

        `frame` is the session's frame counter, and it is here for one thing:
        an attached fly's wingbeat runs on it (issue #61, `Cleg.flap`). It is
        drawing cadence, so nothing else in this method may read it -- the
        moment a rule does, the same run drawn and undrawn would differ.
        `None` means the caller has no clock, which is true of most tests and
        of nothing in the game, and under it an attached fly holds its frame
        as it did before the flap existed; the session always passes one, and
        a test pins that it does.

        `lures` is the cells of every light currently attracting -- see
        `sources.Source.lure`. An empty list means nothing is lit above a glow,
        and the swarm loses interest and blunders.

        `doors` is light in the room next door, offered as a lure standing on
        the threshold (issue #21). **A fly looks round its own room first and
        only then at the doorways**, and that ordering is the whole rule rather
        than a refinement of it:

        * Light in the next room is the faintest thing a fly can be offered,
          because it is not really light at all -- it is a glow at the edge of a
          hole in a wall. Anything lit on this side of the wall beats it.
        * Without the ordering the building converges on whichever room has the
          steadiest light, and it does so **away from the player**. Measured:
          the far room authors a permanent room light one cell from its side of
          the doorway, so a fly anywhere near the near room's east wall found
          the doorway nearer than the player's torch across the room, crossed,
          and was then held by the room light for ever. Over five minutes the
          near room went from three flies to one with a lit player standing in
          it, and a still, lit player's blood loss fell by roughly four times.
          A permanent lure is meant to hold its **own** room's swarm at the
          door the player has to use; it is not meant to empty the room next
          door.

        On the Z80 it is the same routine called twice with a different list,
        and the second call is skipped whenever the first finds anything --
        which is most frames, in a room with a searchlight in it.

        `prey` is every *lit* person who is not the player (issue #19). They
        are bitten on the same terms the player is -- `DRAIN_TOTAL` points at
        one every `DRAIN_EVERY` frames, then the fly is sated and leaves -- and
        a worker who runs out of blood under a fly dies of it, which is how a
        follower can be lost on the walk to the exit.

        **The player is prey whether lit or not; everybody else is prey only
        while lit.** That is not an inconsistency, it is the asymmetry the
        design is built on: your own glow is a light you cannot switch off, so
        contact is contact for you, and darkness is what protects the people
        behind you. Turning to look at them is what gets them eaten.

        **A Cleg that ends up in your cell attaches, lit or not.** It does not
        have to see you to land on you.

        Gating that on the Cleg having *chosen* you was tried and turned out to
        be dead code: your glow is a lure at zero distance, so anything in your
        cell has noticed you by definition. Worth recording, because the idea is
        an obvious one to have twice.

        What the dark still buys you is that nothing *comes looking* from far
        away -- see `sources.Source.lure`. You are hard to find, not immune.

        `is_sprayed` says which ground is poisoned. Only the Clegs that dodge
        consult it; the rest walk in and die, which is what the spray is for.
        A dodger will stand still rather than step into it, so spray still holds
        ground against them -- it just no longer kills them for free.

        `held_beyond` is the no-two-share-a-cell rule **through a doorway**
        (issue #65). `taken` is this swarm's cells and nothing else's, so a fly
        stepping east out of one room onto the threshold -- the next room's
        first column, which `is_solid` lets it have -- was checked against the
        room it was leaving and never against the one it was entering. It
        landed on a cell a fly there already held, and the room light one cell
        in then pinned both of them there for the rest of the run: the tester
        found two free flies sharing a cell on 8 per cent of a statue's room
        samples, all at the far room's (0, 11) and (0, 12). The session
        answers, for a cell near this room's edge or past it, whether a free
        fly of the room next door is standing on it -- or, since issue #66,
        beside it. **It is asked only near the edge** -- see `_near_the_edge`
        -- because the port would otherwise pay for the other room's list on
        every step of every fly for a case that arises at two columns. `None`
        means there is no room next door, which is every test that ticks a
        swarm on its own.

        **A free fly will not step beside another free fly** (issue #66):
        where a step used to be refused if its destination was in `taken`, it
        is now refused if the destination is within one cell of anything in
        it, and the same rule serves the hunting step and the drift. The
        exemption is `_haven`: a step onto or beside a cell holding prey is
        not checked, so the flies already round a lit person never fence off
        the one arriving. Through a doorway the session's `held_beyond`
        answers the same two questions with the same exemption, in the other
        room's coordinates -- it has to, or the far room's door clot simply
        re-forms out of flies arriving from the main room, which is what the
        first cut of #66 measured.
        """
        self.drained = 0
        self.victim_drained = 0
        self.bitten = []
        victims = self.prey_cells(prey)
        taken = self._elbow_room(player_cell)
        haven = self._haven(player_cell, victims)

        def avoid_for(cleg):
            # Where this fly may not step: another fly's cell here, a fly's
            # cell in the room next door if the step is onto the edge,
            # poisoned ground if it is one of the ones that dodge, and --
            # since issue #66 -- any cell beside another fly's, unless the
            # step is arriving at somebody.
            poison = is_sprayed if cleg.dodges else None
            here = (cleg.cx, cleg.cy)

            def refused(cx, cy):
                if (cx, cy) in taken:
                    return True
                if poison is not None and poison(cx, cy):
                    return True
                if (held_beyond is not None and _near_the_edge(cx)
                        and held_beyond(cx, cy)):
                    return True
                # A step into the fly's own cell is not a step (the idle
                # twitch of issue #61) and is not checked for neighbours:
                # refused, the drift would re-roll a heading it would never
                # have rolled and the log would move for no reason anybody
                # meant. A fly can be beside another without having stepped
                # there -- a brood hatches into the ring round its nest.
                if (cx, cy) == here:
                    return False
                # Neighbours first, then the exemption, so the prey list is
                # consulted only for a step that is about to be refused.
                # Same answer either way round.
                return _beside_any(cx, cy, taken) and (cx, cy) not in haven
            return refused
        for cleg in self.clegs:
            if cleg.state == ATTACHED:
                # It is on whoever it landed on, so it goes where they go.
                # Walking away does not leave it behind draining you from
                # across the room, and it is drawn on the host rather than at
                # the spot where it landed. A follower who runs is carrying it
                # too.
                if cleg.victim is None:
                    # `player_cell` of None means the player is not in this
                    # room, so a fly on them should not be in this swarm
                    # either. It can be, for the part of a frame between the
                    # player walking through a doorway and the session handing
                    # the fly over -- so it waits rather than draining somebody
                    # who is not here (issue #21).
                    if player_cell is None:
                        continue
                # **It flaps on the clock, here, where its cell is written**
                # (issue #61): before the bite, so the frame it is drawn in on
                # this step is settled while it is still attached, whatever
                # the bite goes on to do to its state.
                if frame is not None:
                    cleg.flap(frame)
                if cleg.victim is None:
                    cleg.cx, cleg.cy = player_cell
                    blood = self._drain(cleg, blood)
                else:
                    self._ride(cleg)
                continue
            cleg._tick += 1
            if cleg.state == SATED:
                cleg._timer -= 1
                if cleg._timer <= 0:
                    cleg.state = HUNTING
                if cleg._tick >= SATED_DRIFT_EVERY:
                    cleg._tick = 0
                    here = (cleg.cx, cleg.cy)
                    taken.discard(here)
                    cleg._drift(is_solid, avoid_for(cleg))
                    taken.add((cleg.cx, cleg.cy))
                continue

            # Hunting. A light it can notice becomes the place it is going;
            # one it cannot notice may as well not be lit.
            cleg.hunger += 1
            if magnet is not None:
                # The magnet (issue #82): the player's cell, whatever the
                # light, and the bite billed to it whatever the journey was.
                cleg.goal = magnet
                cleg.goal_source = LURE_MAGNET
            else:
                seen = self.notice(cleg.cx, cleg.cy, lures, cleg.notice,
                                   cleg.keenness)
                if seen is None and doors:
                    seen = self.notice(cleg.cx, cleg.cy, doors, cleg.notice,
                                       cleg.keenness)
                if seen is not None:
                    cleg.commit((seen[0], seen[1]), seen[3])
            target = cleg.goal

            if (cleg.cx, cleg.cy) == player_cell:
                self._attach(cleg)
                continue
            here_victim = victims.get((cleg.cx, cleg.cy))
            if here_victim is not None:
                self._attach(cleg, here_victim)
                continue
            if cleg._tick < (cleg.step_every if target else DRIFT_EVERY):
                continue
            cleg._tick = 0
            here = (cleg.cx, cleg.cy)
            taken.discard(here)
            avoid = avoid_for(cleg)
            if target is None:
                cleg._drift(is_solid, avoid)
            else:
                cleg._toward(*cleg.aim(target), is_solid, avoid)
                if (cleg.cx, cleg.cy) == target:
                    # Arrived, and whatever it was is not here any more.
                    cleg.goal = None
                if (cleg.cx, cleg.cy) == player_cell:
                    self._attach(cleg)
                else:
                    stepped_onto = victims.get((cleg.cx, cleg.cy))
                    if stepped_onto is not None:
                        self._attach(cleg, stepped_onto)
            taken.add((cleg.cx, cleg.cy))
        return blood

    def _attach(self, cleg: Cleg, victim=None) -> None:
        """Land on somebody. `victim` of `None` is the player.

        The player's counters are the ones every phase-2 baseline is stated in,
        so a bite on a worker is counted separately and is billed to no lure at
        all -- see `__init__`.
        """
        cleg.state = ATTACHED
        cleg.victim = victim
        cleg.taken = 0
        cleg._timer = 0
        if victim is None:
            self.attachments += 1
            self._bill(cleg, bites=1)
        else:
            self.victim_attachments += 1
            self.bitten.append(victim)

    def _bill(self, cleg: Cleg, bites: int = 0, blood: int = 0) -> None:
        """Charge a bite or a point of blood to whatever lured this fly here.

        Counting only. If this method did nothing at all the run would be
        identical, which is the property issue #22 asks for and the property a
        measurement hook has to have to be worth trusting.
        """
        self.bites_by_source[cleg.goal_source] += bites
        self.blood_by_source[cleg.goal_source] += blood

    def _ride(self, cleg: Cleg) -> None:
        """One frame of a fly attached to somebody who is not the player.

        The same clock and the same appetite as `_drain` -- *"bites cost the
        victim blood on the same terms the player is bitten on"* -- against a
        different pocket. A point of a worker's blood is `rescue.BLEED_EVERY`
        frames of their life, so a full meal of `DRAIN_TOTAL` is a real bite out
        of the clock rather than a scratch, and it is what lets a follower die
        on the walk to the exit.

        **A host that stops being a host loses the fly**, and the fly is *not*
        sated by it: it goes back to hunting with its hunger where it was. Two
        cases, and neither is a reward for the player. A worker who dies under a
        fly has been drunk down to nothing and there is nothing left to take, so
        sating the fly would hand the player ten seconds of drift for a death.
        A worker who reaches the exit walks out of the building, which should
        not feed anything either.

        Rejected, and recorded because it is the obvious alternative: sating the
        fly on the victim's death, by analogy with `detach` and issue #27. It is
        wrong here for the reason that made it right there -- a fly on a dying
        *player* has taken a whole blood budget, and a fly on a worker has taken
        at most eight points of a clock that was already running out.
        """
        victim = cleg.victim
        if not victim.alive:
            self._lose_host(cleg)
            return
        cleg.cx, cleg.cy = victim.cell()
        cleg._timer += 1
        if cleg._timer < DRAIN_EVERY:
            return
        cleg._timer = 0
        victim.bitten(1)
        cleg.taken += 1
        self.victim_drained += 1
        self.victim_blood += 1
        if not victim.alive:
            self._lose_host(cleg)
        elif cleg.taken >= DRAIN_TOTAL:
            self._sate(cleg)

    @staticmethod
    def _lose_host(cleg: Cleg) -> None:
        """The thing it was feeding on is gone. Back to hunting, still hungry."""
        cleg.state = HUNTING
        cleg.victim = None
        cleg.taken = 0
        cleg._timer = 0
        cleg._tick = 0
        cleg.goal = None

    def _drain(self, cleg: Cleg, blood: int) -> int:
        """An attached Cleg takes its fixed amount, then leaves of its own
        accord. Nothing the player does interrupts this.

        Running does not help either -- it is riding on you. The only thing
        that ever helped was not being there.
        """
        cleg._timer += 1
        if cleg._timer >= DRAIN_EVERY:
            cleg._timer = 0
            bite = 1 if blood > 0 else 0
            blood -= bite
            cleg.taken += 1
            self.drained += bite
            self._bill(cleg, blood=bite)
            if cleg.taken >= DRAIN_TOTAL:
                self._sate(cleg)
        return blood

    @staticmethod
    def _sate(cleg: Cleg) -> None:
        """It has eaten. Off you, uninterested, and away for a while.

        Shared by the fly that drank its fill and by the fly that was still
        drinking when the blood ran out -- see `detach` and issue #27. Hunger
        goes back to zero, which is what stops a fed fly noticing the glow it
        is standing in and biting again for ever.
        """
        cleg.state = SATED
        cleg.victim = None
        cleg._timer = SATED_FRAMES
        cleg._tick = 0
        cleg.goal = None
        cleg.hunger = 0            # fed, and no longer straining to find you
        # A meal closes the account (issue #22). What it does next is a new
        # hunt, and a bite it takes after blundering about with nothing in its
        # head belongs to nothing -- which is a finding, not a gap.
        cleg.goal_source = LURE_NONE

    def detach(self, is_solid, held_beyond=None) -> int:
        """Take every attached Cleg off the player. Returns how many.

        Called when the player bleeds out. **Nothing is removed from the
        swarm** -- that was issue #27, where the death branch deleted every
        attached fly and made dying the cheapest way to empty the room.

        They are fed, and they scatter into the free cells around where you
        fell. Both choices are argued at `SCATTER` above. A fly that finds
        nowhere free stays exactly where it is: it may be inconvenient, it is
        never deleted.

        `held_beyond` is the no-two-share-a-cell rule through a doorway, for
        a scatter (issue #69). `taken` is this swarm's cells and nothing
        else's, and a scatter from a doorway cell reaches the landing next
        door -- `is_solid` lets a fly have the column past a doorway (issue
        #21) -- so a fly scattered off a player who died in a doorway could
        land on a cell a fly of the room beyond already held, and the door
        light then pinned both there. The same hole issue #65 closed for a
        *step* through a doorway, in the one path that places flies rather
        than stepping them; found by the coder who fixed the other and left
        because it was not a step. The session answers, for a cell near this
        room's edge or past it, whether a free fly next door is standing on
        it -- the same two translations `tick` asks through, and asked only
        near the edge for the same reason. **The exemption for prey does not
        apply**: a scattering fly is leaving a body, not arriving at prey,
        so the session is asked with `arriving=False` and answers on the
        cell alone -- no waiver for the player's cell next door, and no
        ring, because a scatter keeps no personal space at home either
        (`SCATTER` puts flies beside each other by design) and it would be a
        rule nobody could state if it kept one only through a wall.
        `None` means there is no room next door, which is every test that
        detaches a swarm on its own.
        """
        # **Only the flies on the player.** One on a follower is not riding the
        # person who just bled out, and scattering it would teleport it across
        # the room to the spot where you fell (issue #19).
        freed = [c for c in self.clegs
                 if c.state == ATTACHED and c.victim is None]
        if not freed:
            return 0
        taken = {(c.cx, c.cy) for c in self.clegs
                 if c.state != ATTACHED or c.victim is not None}
        for cleg in freed:
            for dx, dy in SCATTER:
                nx, ny = cleg.cx + dx, cleg.cy + dy
                if (nx, ny) in taken or is_solid(nx, ny):
                    continue
                if (held_beyond is not None and _near_the_edge(nx)
                        and held_beyond(nx, ny)):
                    continue
                cleg.cx, cleg.cy = nx, ny
                break
            taken.add((cleg.cx, cleg.cy))
            self._sate(cleg)
        return len(freed)

    # --- what the rest of the game sees -------------------------------------

    def attached(self) -> list[Cleg]:
        """Every fly currently feeding, on anybody."""
        return [c for c in self.clegs if c.state == ATTACHED]

    def on_player(self) -> list[Cleg]:
        """Only the flies feeding on the player.

        The session counts bites by watching this number rise, and every
        phase-2 baseline is stated in that count, so it must not move when a
        worker is bitten (issue #19). Worker bites are counted in
        `victim_attachments` and reported as their own event.
        """
        return [c for c in self.clegs
                if c.state == ATTACHED and c.victim is None]

    def sprayable(self) -> list[Cleg]:
        """Clegs the spray can reach: everything not currently attached."""
        return [c for c in self.clegs if c.state != ATTACHED]

    def kill(self, dead) -> int:
        """Remove Clegs. Returns how many died."""
        doomed = set(map(id, dead))
        before = len(self.clegs)
        self.clegs = [c for c in self.clegs if id(c) not in doomed]
        return before - len(self.clegs)

    def nearest_distance(self, cx: int, cy: int) -> int | None:
        """Cells to the closest Cleg that is not on *you*, or None.

        Chebyshev distance -- the number of steps a Cleg needs, since they move
        on a grid and may go diagonally. It is also two subtractions and a
        comparison, which matters when the buzz asks for it every frame.

        **A fly feeding on somebody else still counts** (issue #32). One on the
        player is not news -- your blood is already saying it, and a click that
        repeats it is noise. One on somebody trailing behind you in the dark is
        otherwise invisible *and* silent: nothing beyond your own two-cell glow
        is drawn at all, and the only other channel is the death shout, which
        arrives when it is already too late. The sonar is the one channel the
        dark has, so it reports the fly on them, at their cell -- `_ride` keeps
        a fly on its host every frame, so the distance is right the moment it
        stops being excluded.
        """
        best = None
        for c in self.clegs:
            if c.state == ATTACHED and c.victim is None:
                continue
            d = max(abs(c.cx - cx), abs(c.cy - cy))
            if best is None or d < best:
                best = d
        return best


class Swarms:
    """Every swarm in the building, read as one.

    **A room has its own swarm** (issue #21), because a swarm ticks against one
    room's lures, one room's walls and one room's lit people, and a distance
    across a room boundary means nothing. That is the per-room entity list
    *Building Structure* says has to be learned, and learning it on two rooms is
    the cheapest it will ever be.

    But **a fly that walked through a doorway is the same fly**, so everything
    the rest of the game counts is the building's: how much blood the swarm took
    off you, which lure it was billed to, how many are left alive. This adds
    them up on read, which costs nothing and means no counter has to be moved
    when a Cleg crosses.

    Two things are deliberately *not* here. `nearest_distance` is not, because
    the sonar reports the nearest Cleg **in the room you are in** and the caller
    has to say which room that is. And `tick` is not, because a swarm ticks
    against its own room and there is no such thing as ticking the building.
    """

    __slots__ = ("swarms",)

    def __init__(self, swarms) -> None:
        self.swarms = list(swarms)

    def __iter__(self):
        return iter(self.swarms)

    def __getitem__(self, index: int) -> "Swarm":
        return self.swarms[index]

    def __len__(self) -> int:
        return len(self.swarms)

    @property
    def clegs(self) -> list[Cleg]:
        return [c for s in self.swarms for c in s.clegs]

    @property
    def drained(self) -> int:
        return sum(s.drained for s in self.swarms)

    @property
    def attachments(self) -> int:
        return sum(s.attachments for s in self.swarms)

    @property
    def bitten(self) -> list:
        return [v for s in self.swarms for v in s.bitten]

    @property
    def victim_attachments(self) -> int:
        return sum(s.victim_attachments for s in self.swarms)

    @property
    def victim_drained(self) -> int:
        return sum(s.victim_drained for s in self.swarms)

    @property
    def victim_blood(self) -> int:
        return sum(s.victim_blood for s in self.swarms)

    @property
    def bites_by_source(self) -> list[int]:
        return [sum(s.bites_by_source[k] for s in self.swarms)
                for k in range(LURE_KINDS)]

    @property
    def blood_by_source(self) -> list[int]:
        return [sum(s.blood_by_source[k] for s in self.swarms)
                for k in range(LURE_KINDS)]

    def attached(self) -> list[Cleg]:
        return [c for s in self.swarms for c in s.attached()]

    def on_player(self) -> list[Cleg]:
        return [c for s in self.swarms for c in s.on_player()]

    def sprayable(self) -> list[Cleg]:
        return [c for s in self.swarms for c in s.sprayable()]

    def kill(self, dead) -> int:
        return sum(s.kill(dead) for s in self.swarms)

    def detach(self, is_solid, held_beyond=None) -> int:
        """Take every attached fly off the player, wherever its swarm is.

        The player is in one room, so at most one swarm has anything to do here
        -- but which one is not this object's business, and asking them all is
        one comparison each. `held_beyond` is per room, so a caller with more
        than one room asks the swarm directly, as the session does.
        """
        return sum(s.detach(is_solid, held_beyond) for s in self.swarms)
