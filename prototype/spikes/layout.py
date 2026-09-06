"""Screen regions.

The screen is 32x24 cells. The bottom two rows are a status strip; everything
above is the play area. Every cell spent on instrumentation is a cell an author
cannot build in, so the strip is as shallow as it can usefully be.

22 play rows is also an even number, which matters: people are 8x16, two cells
tall, so a 22-row room is exactly 11 whole sprite heights with no ragged
half-row at the bottom.
"""

from spotlight.core.constants import COLS, ROWS

STRIP_ROWS = 2
PLAY_ROWS = ROWS - STRIP_ROWS          # 22

PLAY_TOP = 0
PLAY_BOTTOM = PLAY_ROWS                # exclusive
STRIP_TOP = PLAY_ROWS                  # 22
STRIP_BOTTOM = ROWS                    # 24, exclusive

#: The strip splits down the middle: status left, action right.
HALF = COLS // 2                       # 16
STATUS_LEFT = 0
ACTION_LEFT = HALF

PLAY_CELLS = COLS * PLAY_ROWS          # 704
STRIP_CELLS = COLS * STRIP_ROWS        # 64
