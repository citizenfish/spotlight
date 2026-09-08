"""The proximity sonar: how often it clicks, given how close they are.

You hear them before you see them, and this is load-bearing rather than
decorative. Clegs are only drawn where a light is on them, so in the dark they
are genuinely invisible -- being drained by something you had no way to
anticipate is not tension, it is a coin flip. This is what turns darkness from
arbitrary into information you cannot see.

**Clicks, not a drone.** A continuous buzz was tried and was horrible: a tone
that never stops stops being heard, and it fights everything else the machine
might want to say. A click is a single flip of the speaker -- the cheapest sound
a Spectrum can make -- and a *rate* of clicks carries urgency far better than a
pitch does, because the ear reads tempo without having to compare against
anything. It is a sonar, or a Geiger counter: slow ticking is a rumour, fast
ticking is a problem.

The rate is the whole of the portable part, and it is the only thing here. The
speaker lives in `spike_buzz`, which is Pygame and does not port.

**Two speakers now, and one machine to make the noise** (issue #33). A body
ticks while it can still be saved, and a nest is what happens if it is not --
so the room has a second thing to say by ear and a Spectrum has one beeper to
say it with. `Sonar` and `Ticker` are the same counter with different sources
for the interval; **the sonar wins when both want the speaker**, which the
session arbitrates, and the body's tick simply drops the beat. The collision is
rare -- at most one body ticks at a time, for twenty seconds, once per death --
and a dropped beat still leaves the player hearing that something is wrong.
"""

#: Cells at which a Cleg first becomes audible. Comfortably further than the
#: carried spotlight reaches, so the warning arrives before the sighting -- if
#: you could see it coming, the sonar would only confirm what you knew.
REACH = 12

#: Frames between clicks at the edge of hearing, and on contact. A click a
#: second is a rumour you can ignore; six a second is not.
SLOWEST = 50
FASTEST = 8

#: Silence.
NEVER = 0


def interval_for(distance: int | None, reach: int = REACH,
                 slowest: int = SLOWEST, fastest: int = FASTEST) -> int:
    """Frames between clicks for the nearest Cleg, or NEVER for silence.

    Linear in distance, in integers: at the edge of hearing it ticks slowly,
    on contact it rattles. Computed once a frame from one distance, not once
    per Cleg.
    """
    if distance is None or distance >= reach:
        return NEVER
    if distance <= 0:
        return fastest
    return fastest + (slowest - fastest) * distance // reach


class Ticker:
    """Counts frames against an interval handed to it. Knows nothing about sound.

    The body's tick (issue #33). Where the sonar works out its own interval
    from a distance, this is given one -- a body's tick period is a property of
    how long the body has lain there, which is `rescue.Worker.tick_period` and
    belongs with the body rather than here.

    `NEVER` is silence, and a silence resets the count: a body that is doused,
    turns, or is left behind in a room the tick cannot carry from stops ticking
    rather than pausing mid-beat.
    """

    __slots__ = ("interval", "_tick", "ticks")

    def __init__(self) -> None:
        self.interval = NEVER
        self.ticks = 0
        self._tick = 0

    def update(self, interval: int) -> bool:
        """Advance a frame. Returns whether this frame should tick.

        A quickening interval fires sooner rather than restarting the count,
        exactly as the sonar's does, so the tempo tightens the moment the body
        gets closer to turning instead of after one more wait.
        """
        self.interval = interval
        if interval == NEVER:
            self._tick = 0
            return False
        self._tick += 1
        if self._tick >= interval:
            self._tick = 0
            self.ticks += 1
            return True
        return False


class Sonar:
    """Counts frames and says when to click. Knows nothing about sound."""

    __slots__ = ("interval", "_tick", "clicks")

    def __init__(self) -> None:
        self.interval = NEVER
        self.clicks = 0
        self._tick = 0

    def update(self, distance: int | None) -> bool:
        """Advance a frame. Returns whether this frame should click.

        Closing the distance clicks sooner rather than restarting the count, so
        the tempo tightens the moment they close instead of after one more wait.
        """
        interval = interval_for(distance)
        self.interval = interval
        if interval == NEVER:
            self._tick = 0
            return False
        self._tick += 1
        if self._tick >= interval:
            self._tick = 0
            self.clicks += 1
            return True
        return False
