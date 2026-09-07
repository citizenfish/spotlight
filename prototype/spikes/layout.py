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

#: The strip splits into status left, action right -- but **not down the
#: middle**, which is where it split until issue #31. The status half carries
#: three readouts to the kit half's two-and-a-flag, and the third of them is
#: the rescue tally, which had to grow a word: `*3/7` left a first-timer to
#: guess what was being counted, and a word is the only thing that does not
#: have to be guessed at.
#:
#: The kit half is given exactly what it needs and not a cell more: label, gap,
#: six bar cells, and the lit flag **against the bar rather than a cell clear of
#: it**, which is the thirteenth cell and the one the word was paid for with.
#: The flag and the bar are the same readout -- how much light, and whether it
#: is burning -- so they are the right two things to have touch. The alternative
#: was the tally butting into SPRAY, which is two different readouts running
#: together on the row a first-timer reads for their score.
ACTION_LEFT = COLS - 13                # 19
STATUS_LEFT = 0

PLAY_CELLS = COLS * PLAY_ROWS          # 704
STRIP_CELLS = COLS * STRIP_ROWS        # 64
