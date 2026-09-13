"""The walk's stride: a counter that advances every four pixels of travel.

Issue #72. Each walking figure -- the player, and a follower on the trail --
carries one of these, and the drawing picks its frame from it:
`sprites.PLAYER_FRAMES[player.stride]` over the four-entry cycle `N A N B`.
It is **drawing state**: nothing in the rules reads it, the event log of a run
is byte-identical with it and without it, and a test pins that by setting it
by hand every frame and comparing the logs.

**The cadence is four pixels of travel, never a frame and never a cell.** The
cell cadence before it (issue #60) flipped one bit when the figure crossed a
cell boundary, which is one change every eight frames of walking, about 6Hz,
and the user played it and it read as a foot twitch under a sliding blob. A
step every four pixels is about 12Hz, four steps over three frames, and it is
what turns a flip into a walk. Per frame would be a 25Hz strobe, which is why
the bit was never per pixel and why this counter is not either.

**"Four pixels along either axis since the last advance"**, and that phrase is
the rule, so it is implemented as written: the counter remembers where the
figure was when it last advanced, and advances when the figure is four or more
pixels from there on the x axis or the y axis. Then it remembers the new place.
Two consequences worth stating:

* A diagonal step moves both axes a pixel a frame, so both reach four on the
  same frame and that is **one** advance, not two. A walk on the diagonal has
  the same cadence as a walk along a wall.
* The corner assist can carry the player up to a whole cell sideways in one
  frame. That is one advance too, not two: the counter is *four or more*, not
  *a multiple of four*. An accumulator that counted every moved pixel was
  tried first and advanced twice on a nudge, which showed as the cycle
  skipping a frame -- `N` straight to `N` -- exactly where the figure was
  already jumping.

A figure that stops holds its stride; there is no still frame and no idle
counter, which is how every 8-bit walker stops. A figure that shuffles three
pixels back and forth never advances, which is right: it has not walked.

**It adds no redraw.** The stride only changes on a frame the figure's pixel
position changed, and on such a frame the figure is being erased and redrawn
anyway. The repaint counter prices cells changing light level and a stride
changes none.

On the Z80 this is three bytes in the figure's record -- the index and the
anchor -- and an advance is two subtractions, two compares and an increment
masked to two bits, once per moved figure per frame.
"""

#: Pixels of travel between one stride and the next.
STRIDE_PIXELS = 4

#: Steps in the cycle: `N A N B`, four entries over three unique frames.
STRIDES = 4


class Stride:
    """One figure's place in the walk cycle, and where it last advanced."""

    __slots__ = ("index", "_x", "_y")

    def __init__(self, x: int, y: int) -> None:
        #: 0-3, the index into the figure's four-entry frame cycle.
        self.index = 0
        # Where the figure was when the counter last advanced, or started.
        self._x, self._y = x, y

    def moved_to(self, x: int, y: int) -> bool:
        """Tell the counter where the figure is now. Returns whether it strode.

        Called after a figure's position for the frame is settled -- after both
        of the player's axes have resolved, or where the trail has placed a
        follower -- and never in between, so a diagonal is judged once.
        """
        if (abs(x - self._x) >= STRIDE_PIXELS
                or abs(y - self._y) >= STRIDE_PIXELS):
            self.index = (self.index + 1) % STRIDES
            self._x, self._y = x, y
            return True
        return False
