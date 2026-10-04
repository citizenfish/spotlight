"""The port's first slice: a 50Hz loop that draws one room (issue #153).

Two claims, and they are the two the port will be held to for ever after:

* **the picture is the prototype's picture**, byte for byte, in the 6,144 bytes
  the ULA actually reads;
* **a frame fits the frame**, in T-states the simulator counts rather than in
  an estimate written down in a vault note.

Everything here runs headless off `skoolkit.simulator`, so it needs no emulator
and no window; `portharness` skips the lot if sjasmplus is not installed, which
keeps the prototype's suite green on a machine with no Z80 toolchain.
"""

import pytest

from spikes.building import ENTITY_CEILING
from spotlight.core.constants import COLS
from spikes.layout import PLAY_ROWS

portharness = pytest.importorskip("portharness")

#: A 50Hz frame on a 3.5MHz Z80. `ENTITY_CEILING` is the smaller budget the
#: design holds entities to -- see *2026-09-06 The 48K cycle budget* -- and it
#: is the one that matters, because the frame also owes time to everything that
#: is not drawing.
FRAME_TSTATES = 70_000


@pytest.fixture(scope="module")
def blob():
    return portharness.assemble()


def test_the_port_draws_the_same_room_as_the_prototype(blob):
    """**The whole point of the harness.** The port's walls come from four bit
    tests against an 88-byte solidity bitmap and sixteen tiles; the prototype's
    come from `tiles.mask_at` and the same sixteen, generated from the same
    authored grid. Its floor picks a block by `(cy & 3) * 4 + (cx & 3)` on both
    machines. Its player clears a halo and sets its ink on both.

    If any of those disagreed this comparison would fail, and the port would be
    the one that was wrong -- the prototype is the reference by construction.
    """
    machine, _cost = portharness.run("draw_all", blob, limit=400_000)
    got = bytes(machine.memory[portharness.SCREEN_AT:
                               portharness.SCREEN_AT + 6144])
    want = portharness.display_file(portharness.reference())
    assert portharness.play_area(got) == portharness.play_area(want)


def test_the_play_area_wears_one_attribute_and_the_strip_is_untouched(blob):
    """The light field is the next slice; until it exists the room is drawn lit,
    and the strip's two rows are not this slice's to write."""
    machine, _cost = portharness.run("draw_all", blob, limit=400_000)
    attrs = machine.memory[portharness.ATTRS_AT:portharness.ATTRS_AT + 768]
    assert set(attrs[:COLS * PLAY_ROWS]) == {portharness.PLAY_ATTR}
    assert set(attrs[COLS * PLAY_ROWS:]) == {0}, "the strip was written"


def test_one_frame_is_inside_the_entity_ceiling(blob):
    """A frame's work is erasing the player and drawing them again: the two
    cells they stood on put back as room, then the sprite composited over it.

    **Measured 3,743 T-states, 11.4% of `ENTITY_CEILING`** and 5.3% of a 50Hz
    frame. The bar is the ceiling itself rather than the measured figure, so
    that the next slice has room to spend -- and the light field will spend it.
    """
    _machine, cost = portharness.run("draw_frame", blob)
    assert cost < ENTITY_CEILING, f"a frame costs {cost:,} T-states"


def test_arriving_in_a_room_is_not_a_frames_work(blob):
    """**The slice's real finding, asserted so it cannot be forgotten.**

    Drawing all 704 cells costs about **909,000 T-states -- thirteen frames** --
    so a Z80 cannot repaint a room at 50Hz. It never has to: the game reveals a
    room through the beam a few cells at a time, and a room nobody is looking at
    keeps its charge and not its picture (issue #136). The whole-room draw is
    what it costs to arrive somewhere.

    This test exists to stop anybody quietly calling `enter_room` from the loop.
    """
    _machine, cost = portharness.run("enter_room", blob, limit=400_000)
    assert cost > FRAME_TSTATES, \
        "enter_room got cheap enough to be per-frame work -- re-read #136 " \
        "before moving it into the loop"


def test_a_cell_costs_what_the_beam_can_afford(blob):
    """How many cells a frame can be repainted is the port's real currency,
    because that is what a moving beam does.

    **1,926 T-states a cell, so seventeen cells inside `ENTITY_CEILING`.** The
    beam's disc is thirty-seven cells (`sources.disc_widths`, 3 5 7 7 7 5 3), so
    a step of the beam repaints its leading and trailing edges and not the whole
    disc -- which is affordable, but only just, and the next slice should expect
    to make this cheaper. `tiles.mask_at` costs the four bit tests at about 120
    T-states; this pays five calls of `is_solid` with three register pairs saved
    each time, so there is a lot of it to win back.
    """
    _machine, cost = portharness.run("draw_cell", blob)
    assert ENTITY_CEILING // cost >= 12, \
        f"a cell costs {cost:,} T-states, so only " \
        f"{ENTITY_CEILING // cost} fit in a frame"
