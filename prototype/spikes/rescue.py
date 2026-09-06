"""Trapped workers: the clock, the tail, and the way out.

The objective, and after issue #13 the whole rescue loop. A worker is somebody
you have to **find in the dark, reach before they bleed out, and walk to the
exit** -- and each of those three is a different kind of pressure.

**They are on a clock.** Each has their own blood and is losing it from the
moment the level begins. That is what turns a search into a race, and it is the
answer to the sharpest finding of the play evaluation: light does not compete
with darkness, it competes with *time*. With nothing bleeding, the best play was
to stay dark and be methodical, which is safe, correct and dull. With a clock
running, being slow costs people.

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

# --- the clock -------------------------------------------------------------

#: Blood a worker starts with, and how often they lose a point of it.
#:
#: Two and a half minutes from full to dead, so a room's worth of people can be
#: found and walked out by somebody who does not dawdle, and cannot by somebody
#: who clears the room methodically first. That is the whole point of the number
#: and it is the one most worth playing with -- see the resource budgets note.
WORKER_BLOOD = 48
BLEED_EVERY = 150

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

    __slots__ = ("x", "y", "state", "blood", "phase", "_tick", "_since_death")

    def __init__(self, x: int, y: int, phase: int = 0,
                 blood: int = WORKER_BLOOD) -> None:
        self.x, self.y = x, y
        self.state = WAITING
        self.blood = blood
        #: Offset into the call cycle, so the room does not shout in chorus.
        self.phase = phase
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
        if self.state != WAITING:
            return False
        return (frame + self.phase) % CALL_PERIOD < CALL_FRAMES

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
        count = max(1, len(positions))
        self.workers = [Worker(x, y, phase=i * CALL_PERIOD // count, blood=blood)
                        for i, (x, y) in enumerate(positions)]
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
        """Bleed everybody. Returns whoever died on this frame."""
        gone = [w for w in self.workers if w.tick()]
        for w in gone:
            if w in self.tail:
                self.tail.remove(w)
            self.died.append(w)
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
