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
from .sources import xorshift16

# --- states ----------------------------------------------------------------

HUNTING, ATTACHED, SATED = 0, 1, 2

#: Frames between steps. Slightly slower than the player, who covers a cell in
#: eight frames -- so you can outrun a swarm, but you cannot stand and read the
#: room while it closes. That margin is the whole of the moment-to-moment game.
STEP_EVERY = 9

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
SATED_FRAMES = 150
SATED_DRIFT_EVERY = 9

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

    __slots__ = ("cx", "cy", "state", "taken", "notice", "goal",
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

    # --- movement ----------------------------------------------------------

    def _random(self) -> int:
        self._seed = xorshift16(self._seed)
        return self._seed

    def _try(self, dx: int, dy: int, is_solid) -> bool:
        nx, ny = self.cx + dx, self.cy + dy
        if not (0 <= nx < COLS and 0 <= ny < PLAY_ROWS) or is_solid(nx, ny):
            return False
        self.cx, self.cy = nx, ny
        return True

    def _toward(self, tx: int, ty: int, is_solid) -> None:
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
            if step != (0, 0) and self._try(*step, is_solid):
                return

    def _drift(self, is_solid) -> None:
        """A step with no preference, for a Cleg with nothing to steer for.

        Each axis is the difference of two bits, so it is -1, 0, 0 or 1 -- one
        cell at most and no direction favoured. Taking two bits as a number
        instead drifts steadily down and to the right, which reads as purpose
        and is exactly what a Cleg with nothing to aim at must not have.
        """
        r = self._random()
        dx = (r & 1) - ((r >> 1) & 1)
        dy = ((r >> 2) & 1) - ((r >> 3) & 1)
        self._try(dx, dy, is_solid)


class Swarm:
    """Every Cleg in the room, and the one rule they all follow."""

    def __init__(self, clegs: list[Cleg] | None = None) -> None:
        self.clegs = list(clegs or [])
        self.drained = 0          # blood taken this frame, for the caller
        self.attachments = 0      # completed attachments, for the record

    # --- the one rule ------------------------------------------------------

    @staticmethod
    def nearest_lure(cx: int, cy: int, lures,
                     within: int | None = None) -> tuple[int, int] | None:
        """The closest light this Cleg can notice, or None.

        Each lure is `(cx, cy, reach)`: where it is, and how far it carries.
        A light must be inside **both** its own reach and this Cleg's -- a
        bright light across the room is no use to a fly that cannot notice it,
        and your dim glow is no use to one three rooms away.

        Squared distance, so there is no square root -- the Z80 has neither
        that nor a divide, and comparing squares orders the same as comparing
        distances.
        """
        best, best_d2 = None, None
        for lx, ly, reach in lures:
            limit = reach if within is None else min(within, reach)
            dx, dy = lx - cx, ly - cy
            d2 = dx * dx + dy * dy
            if d2 > limit * limit:
                continue
            if best_d2 is None or d2 < best_d2:
                best, best_d2 = (lx, ly), d2
        return best

    # --- the frame ---------------------------------------------------------

    def tick(self, lures, player_cell, is_solid, blood: int) -> int:
        """Advance every Cleg. Returns blood remaining.

        `lures` is the cells of every light currently attracting -- see
        `sources.Source.lure`. An empty list means nothing is lit above a glow,
        and the swarm loses interest and blunders.

        **A Cleg that ends up in your cell attaches, lit or not.** It does not
        have to see you to land on you. Requiring light for that was tried and
        was wrong twice over: walking into a fly did nothing at all, which reads
        as a broken game, and standing still in the dark was perfect safety,
        which makes the best play no play.

        What the dark still buys you is that nothing *comes looking* from far
        away -- see `sources.Source.lure`. You are hard to find, not immune.
        """
        self.drained = 0
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
                    cleg._drift(is_solid)
                continue

            # Hunting. A light it can notice becomes the place it is going;
            # one it cannot notice may as well not be lit.
            seen = self.nearest_lure(cleg.cx, cleg.cy, lures, cleg.notice)
            if seen is not None:
                cleg.goal = seen
            target = cleg.goal

            if (cleg.cx, cleg.cy) == player_cell:
                self._attach(cleg)
                continue
            if cleg._tick < (STEP_EVERY if target else DRIFT_EVERY):
                continue
            cleg._tick = 0
            if target is None:
                cleg._drift(is_solid)
            else:
                cleg._toward(*target, is_solid)
                if (cleg.cx, cleg.cy) == target:
                    # Arrived, and whatever it was is not here any more.
                    cleg.goal = None
                if (cleg.cx, cleg.cy) == player_cell:
                    self._attach(cleg)
        return blood

    def _attach(self, cleg: Cleg) -> None:
        cleg.state = ATTACHED
        cleg.taken = 0
        cleg._timer = 0
        self.attachments += 1

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
            if cleg.taken >= DRAIN_TOTAL:
                cleg.state = SATED
                cleg._timer = SATED_FRAMES
                cleg._tick = 0
                cleg.goal = None
        return blood

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
