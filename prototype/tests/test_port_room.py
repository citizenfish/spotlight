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


#: What a frame actually has to repaint, measured off the prototype over
#: **204,825 frames** -- four bots, eight seeds, Level 9, three minutes each
#: (issue #154, `2026-10-05 what a cell costs/repaints.py`). A cell needs
#: redrawing when what it shows changes, which is what `LightField.display` is,
#: plus the cells figures and flies stand in and the ones they just left.
#:
#: Arrivals are excluded, **including the run's own first frame**: unexcluded,
#: the worst frame is 59 cells of light and it is frame one on every seed and
#: every bot, the beam appearing out of nothing. That is `enter_room`'s work and
#: counting it would have set this bar at twice the real figure.
WORST_FRAME_CELLS = 58
NINETY_NINTH_CELLS = 34


def test_a_cell_costs_what_the_beam_can_afford(blob):
    """How many cells a frame can repaint is the port's real currency, because
    that is what a moving beam does.

    **434 T-states a cell, from 1,926 -- 4.44x** (issue #154), by caching each
    cell's tile index on arrival instead of deriving it per frame. The worst
    frame the prototype produces is 58 cells, which is **77% of
    `ENTITY_CEILING`** and 36% of a 50Hz frame; the 99th percentile is 34 cells
    at 45% of the ceiling.

    **The gate is the 99th percentile inside the ceiling, and the worst frame
    inside a whole frame.** Those are different bars on purpose. The 99th is
    what governs whether the game feels smooth and it has to leave room for
    everything that is not drawing. The 58-cell frame happens about twice an
    hour -- it is the beam changing station, which lights a whole new disc and
    darkens the old one -- and one frame of jitter twice an hour is not worth
    buying margin for; what matters is that it cannot overrun a frame and drop
    one.
    """
    _machine, cost = portharness.run("draw_cell", blob)
    ninety_ninth = NINETY_NINTH_CELLS * cost
    worst = WORST_FRAME_CELLS * cost
    assert ninety_ninth < ENTITY_CEILING, (
        f"a cell costs {cost:,} T-states, so the 99th-percentile frame of "
        f"{NINETY_NINTH_CELLS} cells costs {ninety_ninth:,} against a ceiling "
        f"of {ENTITY_CEILING:,}")
    assert worst < FRAME_TSTATES, (
        f"the worst frame of {WORST_FRAME_CELLS} cells costs {worst:,} "
        f"T-states and a 50Hz frame is {FRAME_TSTATES:,}")


def test_the_cached_index_is_geometry_and_not_lighting(blob):
    """The cache holds a **tile index**, not a tile pointer, and that is the
    whole reason it can be built once on arrival.

    A wall cell's index is its four-neighbour mask (0-15); a floor cell's is
    16 + `(cy & 3) * 4 + (cx & 3)`, which is a function of where the cell is and
    so is just as fixed as the mask. Which *table* the index is read from -- lit
    now, remembered later -- is the light field's to choose, and it is the next
    slice's. Had the cache held a pointer it would have baked in the light level
    and needed rebuilding every frame, which is the cost this removes.

    Checked against the prototype's own `tiles.mask_at` rather than recomputed
    here, so the two machines cannot disagree about what a cell is.
    """
    from spikes import building as B, tiles
    machine, _cost = portharness.run("enter_room", blob, limit=1_500_000)
    base = portharness.symbol("IDX")
    rows = portharness.shell_rows()

    def solid(cx, cy):
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return True
        return rows[cy][cx] == B.WALL

    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            got = machine.memory[base + cy * COLS + cx]
            if solid(cx, cy):
                want = tiles.mask_at(solid, cx, cy)
            else:
                want = 16 + (cy & 3) * 4 + (cx & 3)
            assert got == want * 2, (cx, cy, got, want * 2)


def test_the_cache_is_accounted_for_in_48k(blob):
    """704 bytes of working store, after the saved image so it costs nothing on
    tape, and nowhere near the constraint: the whole thing is 3,520 bytes with
    29,248 free above it."""
    start = portharness.symbol("IDX")
    end = portharness.symbol("IDX_END")
    assert end - start == COLS * PLAY_ROWS == 704
    assert start >= portharness.ORIGIN + len(blob), \
        "the cache overlaps the code"
    assert end < 0xFF00, "the cache runs into the stack"
