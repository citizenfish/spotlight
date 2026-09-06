"""Trapped workers, and reaching them. The objective, at its smallest.

Spike 2 asks whether the light bargain is tense to play, and until now the room
had nothing in it to want. **You cannot judge whether switching the light on is
worth it when there is nothing you need to see.** So there is now something to
find: seven people, scattered, and reaching one is enough.

Deliberately not built here, because spike 2 is not building them: blood clocks,
the following tail, bodies turning to nests, or a quota. A worker is a thing you
have to locate in the dark, which is the only part of the rescue the bargain
needs.

The important property is that workers are **people**, so the rules from
issue #12 already apply to them: they are drawn only where a light is on them
this frame, and the opening flash does not show them. The player is given the
shape of the room for free and has to buy the people with light -- and light is
what brings the swarm. That is the bargain, stated as a level.
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


class Worker:
    """One trapped worker, at a pixel position, waiting to be found."""

    __slots__ = ("x", "y", "found", "phase")

    def __init__(self, x: int, y: int, phase: int = 0) -> None:
        self.x, self.y = x, y
        self.found = False
        #: Offset into the call cycle, so the room does not shout in chorus.
        self.phase = phase

    # --- calling out -------------------------------------------------------

    def calling(self, frame: int) -> bool:
        """Is this worker shouting right now?

        **A shout is not a light.** It shows you roughly where somebody is
        without lighting them, so it costs the player nothing and draws nothing
        -- Clegs respond to light and only to light, and a voice is not on that
        list. It is the counterpart of the Clegs' own sonar: the room is full of
        information you cannot see, and both sides of it reach you by ear.

        Without this the only way to find anybody is to sweep the whole room
        with a light you cannot afford to keep on, which is a chore rather than
        a decision. A call gives you a bearing and makes the light a *choice*
        about where to point it.
        """
        if self.found:
            return False
        return (frame + self.phase) % CALL_PERIOD < CALL_FRAMES

    def call_cells(self) -> list[tuple[int, int]]:
        """Where the word sits: above their head, or below if there is no room.

        Kept inside the play area, so a worker against a wall still gets heard
        rather than having their shout run off the edge of the screen.
        """
        head = self.y // CELL
        row = head - 1
        if row < 0:
            row = (self.y + HEIGHT - 1) // CELL + 1
        row = max(0, min(PLAY_ROWS - 1, row))
        left = max(0, min(COLS - len(CALL), self.x // CELL - 1))
        return [(left + i, row) for i in range(len(CALL))]

    def cells(self) -> set[tuple[int, int]]:
        """Every cell the figure stands in."""
        return {
            (cx, cy)
            for cx in range(self.x // CELL, (self.x + WIDTH - 1) // CELL + 1)
            for cy in range(self.y // CELL, (self.y + HEIGHT - 1) // CELL + 1)
        }


class Rescue:
    """The people still to be found."""

    def __init__(self, positions) -> None:
        # Phases spread evenly round the cycle, so calls arrive one at a time
        # and each is a separate piece of news rather than a chorus.
        count = max(1, len(positions))
        self.workers = [Worker(x, y, phase=i * CALL_PERIOD // count)
                        for i, (x, y) in enumerate(positions)]

    @property
    def remaining(self) -> int:
        return sum(1 for w in self.workers if not w.found)

    @property
    def found(self) -> int:
        return sum(1 for w in self.workers if w.found)

    @property
    def all_found(self) -> bool:
        return self.remaining == 0

    def waiting(self) -> list[Worker]:
        return [w for w in self.workers if not w.found]

    def calling(self, frame: int) -> list[Worker]:
        """Everybody shouting this frame."""
        return [w for w in self.workers if w.calling(frame)]

    def reach(self, cells) -> Worker | None:
        """Has the player got to somebody? Returns them the once.

        `cells` is every cell the *player* occupies, not the one cell they
        stand on. A spotlight is picked up by the feet cell alone, because a
        light lies on the floor and you would otherwise collect one beside your
        head. A person is not on the floor: two figures whose bodies overlap are
        touching, and requiring their feet to land in the same cell meant
        walking through somebody chest-first and not reaching them.

        Both are 8x16, so at an arbitrary pixel offset each spans up to six
        cells. Testing the boxes is what a player expects and it is no more
        work: two small sets, intersected.
        """
        standing = set(cells)
        for worker in self.workers:
            if not worker.found and standing & worker.cells():
                worker.found = True
                return worker
        return None
