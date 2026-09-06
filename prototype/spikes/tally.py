"""Counters for the play evaluation, so a run can be reported rather than recalled.

Issue #10 asks for answers in writing, and memory of a tense two minutes in the
dark is not evidence. This keeps the handful of numbers that say what a run
actually cost: how long it took, how much light was spent, and what the light
was paid for in blood.

The ratio worth watching is **blood per worker**. If it is near zero the light is
free and there is no bargain; if the whole budget goes before the room is
cleared, light is unaffordable and the room is not playable. The design claims
the interesting play is in between, and this is what shows whether it is.
"""

FRAME_RATE = 50


class Tally:
    """What one run cost."""

    __slots__ = ("frames", "lit_frames", "blood_lost", "attachments",
                 "sprays", "found", "swatted")

    def __init__(self) -> None:
        self.frames = 0
        self.lit_frames = 0        # frames with the carried spotlight burning
        self.blood_lost = 0
        self.attachments = 0
        self.sprays = 0
        self.found = 0
        self.swatted = 0           # Clegs killed by spray

    def frame(self, lit: bool, drained: int) -> None:
        self.frames += 1
        self.lit_frames += 1 if lit else 0
        self.blood_lost += drained

    @property
    def seconds(self) -> int:
        return self.frames // FRAME_RATE

    @property
    def lit_seconds(self) -> int:
        return self.lit_frames // FRAME_RATE

    @property
    def lit_percent(self) -> int:
        return 100 * self.lit_frames // max(1, self.frames)

    @property
    def blood_per_worker(self) -> int:
        """Tenths, to keep it integer. The number the evaluation turns on."""
        return 10 * self.blood_lost // max(1, self.found)

    def report(self) -> list[str]:
        """The run, as lines to print."""
        cost = self.blood_per_worker
        return [
            f"time            {self.seconds}s",
            f"workers found   {self.found}",
            f"light on        {self.lit_seconds}s ({self.lit_percent}% of the run)",
            f"blood lost      {self.blood_lost}",
            f"attachments     {self.attachments}",
            f"clegs sprayed   {self.swatted} for {self.sprays} charges",
            f"blood per rescue {cost // 10}.{cost % 10}",
        ]
