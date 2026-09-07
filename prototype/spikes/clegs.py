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
  swarm, it is one Cleg drawn six times.
* **Your own glow reaches a few cells.** Standing still in the dark is a short
  reprieve rather than a hiding place: nothing crosses the room for you, but
  whatever blunders close will find you. Keep moving.
* **What they noticed, they remember.** Switching off does not call them back:
  they keep coming to where the light was. A one-second flash is a decision with
  consequences that arrive several seconds later, which is the whole rhythm.

Once a Cleg is on you the damage is already decided. It cannot be shaken off and
the flyspray does not touch it. The whole defensive game happens *before*
contact -- in where you stand, what you light, and where you laid spray.

No pathfinding, and nothing here should ever acquire any. A Cleg steers for the
nearest lit source by comparing squared distances -- a handful of integer
subtractions per Cleg per step -- and slides along a wall it cannot pass. A fly
that solved mazes would be a different animal and a much more expensive one.
"""

from spotlight.core.constants import COLS

from .layout import PLAY_ROWS
from .sources import LURE_KINDS, LURE_NONE, xorshift16

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
#: Twelve, so a starving Cleg notices the glow from fourteen cells and not from
#: across the room. Both numbers want playing with rather than arguing about --
#: they set how quickly the dark stops being a refuge, which is the single
#: dial that decides whether hiding is a breather or a strategy.
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
                 "kind", "flank", "step_every", "hunger", "heading", "_run",
                 "_timer", "_tick", "_seed")

    def __init__(self, cx: int, cy: int, seed: int = 0xBEEF) -> None:
        self.cx, self.cy = cx, cy
        self.state = HUNTING
        self.taken = 0            # blood drawn during the current attachment
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

    def _try(self, dx: int, dy: int, is_solid, avoid=None) -> bool:
        nx, ny = self.cx + dx, self.cy + dy
        if not (0 <= nx < COLS and 0 <= ny < PLAY_ROWS) or is_solid(nx, ny):
            return False
        if avoid is not None and avoid(nx, ny):
            return False
        self.cx, self.cy = nx, ny
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
        """
        if self._run <= 0 or not self._try(*self.heading, is_solid, avoid):
            r = self._random()
            dx = (r & 1) - ((r >> 1) & 1)
            dy = ((r >> 2) & 1) - ((r >> 3) & 1)
            self.heading = (dx, dy)
            self._run = ROAM_RUN + (r >> 4) % ROAM_SPREAD
            self._try(dx, dy, is_solid, avoid)
        self._run -= 1


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
        """Cells another Cleg is standing in, which none may step into.

        Without it they pile onto whichever square the nearest light is at --
        every one of them steering by the same rule to the same place, arriving
        as a single blob. Keeping a cell each spreads the same arrival over the
        ground around it, which is what a swarm looks like.

        The player's own cell is left out. Several can be attached to you at
        once, and an arriving one must never be blocked from reaching you by
        the ones already feeding.
        """
        taken = {(c.cx, c.cy) for c in self.clegs if c.state != ATTACHED}
        taken.discard(player_cell)
        return taken

    def tick(self, lures, player_cell, is_solid, blood: int,
             is_sprayed=None) -> int:
        """Advance every Cleg. Returns blood remaining.

        `lures` is the cells of every light currently attracting -- see
        `sources.Source.lure`. An empty list means nothing is lit above a glow,
        and the swarm loses interest and blunders.

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
        """
        self.drained = 0
        taken = self._elbow_room(player_cell)
        for cleg in self.clegs:
            if cleg.state == ATTACHED:
                # It is on you, so it goes where you go. Walking away does not
                # leave it behind draining you from across the room, and it is
                # drawn on you rather than at the spot where it landed.
                cleg.cx, cleg.cy = player_cell
                blood = self._drain(cleg, blood)
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
                    poison = is_sprayed if cleg.dodges else None
                    cleg._drift(is_solid,
                                lambda cx, cy: (cx, cy) in taken
                                or (poison is not None and poison(cx, cy)))
                    taken.add((cleg.cx, cleg.cy))
                continue

            # Hunting. A light it can notice becomes the place it is going;
            # one it cannot notice may as well not be lit.
            cleg.hunger += 1
            seen = self.notice(cleg.cx, cleg.cy, lures, cleg.notice,
                               cleg.keenness)
            if seen is not None:
                cleg.commit((seen[0], seen[1]), seen[3])
            target = cleg.goal

            if (cleg.cx, cleg.cy) == player_cell:
                self._attach(cleg)
                continue
            if cleg._tick < (cleg.step_every if target else DRIFT_EVERY):
                continue
            cleg._tick = 0
            here = (cleg.cx, cleg.cy)
            taken.discard(here)
            poison = is_sprayed if cleg.dodges else None
            avoid = (lambda cx, cy: (cx, cy) in taken
                     or (poison is not None and poison(cx, cy)))
            if target is None:
                cleg._drift(is_solid, avoid)
            else:
                cleg._toward(*cleg.aim(target), is_solid, avoid)
                if (cleg.cx, cleg.cy) == target:
                    # Arrived, and whatever it was is not here any more.
                    cleg.goal = None
                if (cleg.cx, cleg.cy) == player_cell:
                    self._attach(cleg)
            taken.add((cleg.cx, cleg.cy))
        return blood

    def _attach(self, cleg: Cleg) -> None:
        cleg.state = ATTACHED
        cleg.taken = 0
        cleg._timer = 0
        self.attachments += 1
        self._bill(cleg, bites=1)

    def _bill(self, cleg: Cleg, bites: int = 0, blood: int = 0) -> None:
        """Charge a bite or a point of blood to whatever lured this fly here.

        Counting only. If this method did nothing at all the run would be
        identical, which is the property issue #22 asks for and the property a
        measurement hook has to have to be worth trusting.
        """
        self.bites_by_source[cleg.goal_source] += bites
        self.blood_by_source[cleg.goal_source] += blood

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
        cleg._timer = SATED_FRAMES
        cleg._tick = 0
        cleg.goal = None
        cleg.hunger = 0            # fed, and no longer straining to find you
        # A meal closes the account (issue #22). What it does next is a new
        # hunt, and a bite it takes after blundering about with nothing in its
        # head belongs to nothing -- which is a finding, not a gap.
        cleg.goal_source = LURE_NONE

    def detach(self, is_solid) -> int:
        """Take every attached Cleg off the player. Returns how many.

        Called when the player bleeds out. **Nothing is removed from the
        swarm** -- that was issue #27, where the death branch deleted every
        attached fly and made dying the cheapest way to empty the room.

        They are fed, and they scatter into the free cells around where you
        fell. Both choices are argued at `SCATTER` above. A fly that finds
        nowhere free stays exactly where it is: it may be inconvenient, it is
        never deleted.
        """
        freed = [c for c in self.clegs if c.state == ATTACHED]
        if not freed:
            return 0
        taken = {(c.cx, c.cy) for c in self.clegs if c.state != ATTACHED}
        for cleg in freed:
            for dx, dy in SCATTER:
                nx, ny = cleg.cx + dx, cleg.cy + dy
                if not (0 <= nx < COLS and 0 <= ny < PLAY_ROWS):
                    continue
                if (nx, ny) in taken or is_solid(nx, ny):
                    continue
                cleg.cx, cleg.cy = nx, ny
                break
            taken.add((cleg.cx, cleg.cy))
            self._sate(cleg)
        return len(freed)

    # --- what the rest of the game sees -------------------------------------

    def attached(self) -> list[Cleg]:
        return [c for c in self.clegs if c.state == ATTACHED]

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
        """Cells to the closest Cleg that is not already on you, or None.

        Chebyshev distance -- the number of steps a Cleg needs, since they move
        on a grid and may go diagonally. It is also two subtractions and a
        comparison, which matters when the buzz asks for it every frame.
        """
        best = None
        for c in self.clegs:
            if c.state == ATTACHED:
                continue
            d = max(abs(c.cx - cx), abs(c.cy - cy))
            if best is None or d < best:
                best = d
        return best
