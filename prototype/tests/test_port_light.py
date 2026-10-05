"""The light field on the Z80 (issue #155): the mechanic the design rests on.

What is asserted here is that **the port's picture is the prototype's picture**,
pixels and attributes, after any number of frames of fading -- which is a much
tighter gate than #153 and #154 had, because those drew the whole play area one
flat colour and compared pixels alone.

The beam's *position* is an input, not something the port works out yet: its
motion is the run's xorshift and the station order, and that is a slice of its
own. So the reference forces the prototype's beam to the same cell.
"""

import pytest

from spikes import lighting
from spikes.layout import PLAY_ROWS
from spikes.building import ENTITY_CEILING
from spotlight.core.constants import COLS

portharness = pytest.importorskip("portharness")

FRAME_TSTATES = 70_000

#: Frame counts worth looking at, and why each one: the first frame, the frame
#: the floor's `CHARGE_SWEEP` runs out (10), either side of the wall's drop from
#: LIT to DIM at half rate (60), and past the wall's whole 300-frame life.
FRAMES = (1, 2, 5, 10, 11, 40, 59, 60, 61, 160, 299, 300, 400)


@pytest.fixture(scope="module")
def blob():
    return portharness.assemble()


#: A beam that sweeps the west wall and then walks away east, one cell every
#: six frames as `pace: 6` has it. **The default beam never touches a wall** --
#: the dogleg's are at column 12 and the border, and the disc at (6,5) holds
#: none -- so without a path like this the half-rate wall fade and `linger` are
#: never exercised at all, and the byte-identity tests pass either way.
WALL_SWEEP = ([(3, 5)] * 12 + [(4, 5)] * 6 + [(5, 5)] * 6 + [(6, 5)] * 6
              + [(8, 5)] * 6 + [(10, 5)] * 400)


@pytest.mark.parametrize("frames", FRAMES)
def test_the_port_shows_what_the_prototype_shows_as_a_wall_is_swept(blob, frames):
    """The same comparison with the beam crossing the **west wall** and leaving.

    This is the case the stationary beam cannot reach, and it is the one that
    matters most: a wall takes `CHARGE_WALL` where floor takes `CHARGE_SWEEP`,
    fades at half rate, and is the only way a room is known with no torch. It is
    also where the prototype's `linger` runs and where #148's dip lives.
    """
    machine, _cost = portharness.light_run(blob, frames, beam=WALL_SWEEP)
    reference = portharness.reference(frames=frames, beam=WALL_SWEEP)
    got = bytes(machine.memory[portharness.SCREEN_AT:
                               portharness.SCREEN_AT + 6144])
    assert portharness.play_area(got) == \
        portharness.play_area(portharness.display_file(reference))
    attrs = bytes(machine.memory[portharness.ATTRS_AT:
                                 portharness.ATTRS_AT + COLS * PLAY_ROWS])
    assert attrs == portharness.attrs_of(reference)


@pytest.mark.parametrize("frames", FRAMES)
def test_the_port_shows_what_the_prototype_shows(blob, frames):
    """Pixels **and** attributes, against `LightField` driven the same way.

    This is the whole slice. If the charge, the thresholds, the half-rate wall
    fade, the lit/remembered tile choice or the attribute rule were wrong in any
    cell, these bytes would differ -- and while it was being built they did,
    four times over, each for a different reason.
    """
    machine, _cost = portharness.light_run(blob, frames)
    reference = portharness.reference(frames=frames)
    got = bytes(machine.memory[portharness.SCREEN_AT:
                               portharness.SCREEN_AT + 6144])
    assert portharness.play_area(got) == \
        portharness.play_area(portharness.display_file(reference))
    attrs = bytes(machine.memory[portharness.ATTRS_AT:
                                 portharness.ATTRS_AT + COLS * PLAY_ROWS])
    assert attrs == portharness.attrs_of(reference)


def test_the_level_table_is_the_prototypes(blob):
    """`charge -> level`, byte for byte against `lighting._LEVEL_OF`.

    It is built in the assembler as the **sum of two comparisons**, which needs
    no conditional -- and sjasmplus's comparisons yield **-1** for true, so the
    unnegated sum made a table of 0, 255, 254 and every lit cell read as a level
    nothing recognised. A table that is wrong the same way everywhere is
    invisible in a picture until you compare it, so it is compared.
    """
    base = portharness.symbol("LEVEL_OF") - portharness.ORIGIN
    assert bytes(blob[base:base + 256]) == lighting._LEVEL_OF


def test_a_wall_remembers_twice_as_long_as_the_floor_it_stands_on(blob):
    """The half-rate wall fade, read off the port's own field.

    `fade: 2` is how Levels 1 to 6 ship: three seconds of wall memory becomes
    six, because with no torch a swept wall is the only way a room is known. The
    prototype adds a charge back on even frames (`linger`); the port divides the
    elapsed time instead, which is the same curve and **cannot suffer the dip**
    #148 found, because nothing is ever added back.
    """
    rows = portharness.shell_rows()
    solid = portharness.solid_of(rows)
    wall, floor = (0, 5), (3, 5)
    assert solid(*wall) and not solid(*floor), "the fixture moved"

    def level(machine, cell):
        attr = machine.memory[portharness.ATTRS_AT + cell[1] * COLS + cell[0]]
        if not attr:
            return lighting.DARK
        return lighting.LIT if attr & 0x40 else lighting.DIM

    # Under the beam both read lit, though what they *remember* differs by
    # fifteen times: `CHARGE_SWEEP` is 10 against `CHARGE_WALL`'s 150.
    machine, _ = portharness.light_run(blob, 1, beam=WALL_SWEEP)
    assert level(machine, floor) == lighting.LIT, "the beam is on it"
    assert level(machine, wall) == lighting.LIT

    # The beam reaches (10,5) at frame 31, and **its disc is seven cells wide**
    # -- `3 5 7 7 7 5 3` -- so column 3 is only clear of it from there. Ten
    # frames after that the floor it crossed is dark: `CHARGE_SWEEP` is a fifth
    # of a second, which is what makes the beam read as a hole punched through
    # the dark rather than a bar painted across it.
    machine, _ = portharness.light_run(blob, 45, beam=WALL_SWEEP)
    assert level(machine, floor) == lighting.DARK, "the wake outlived the beam"

    # ...and the wall it swept is still lit, because 150 at half rate stays
    # above the threshold for sixty frames.
    assert level(machine, wall) == lighting.LIT

    # Then remembered, for twice the floor's whole fade.
    machine, _ = portharness.light_run(blob, 100, beam=WALL_SWEEP)
    assert level(machine, wall) == lighting.DIM, "still lit after a hundred"
    machine, _ = portharness.light_run(blob, 299, beam=WALL_SWEEP)
    assert level(machine, wall) == lighting.DIM
    machine, _ = portharness.light_run(blob, 320, beam=WALL_SWEEP)
    assert level(machine, wall) == lighting.DARK, \
        "a wall outlived three hundred frames"


def test_the_fade_is_a_ledger_and_not_a_pass(blob):
    """**The measurement that fixed the design.** Decaying all 704 cells costs
    40,857 T-states a frame -- 124% of `ENTITY_CEILING` -- before anything is
    drawn; through a translate table it is worse, 45,388, because `ex de,hl`
    twice a cell costs more than the jump it saves. A counter costs 48.

    So the charge is never stored decayed: a frame counter advances and a cell's
    charge is computed from the frame it was written at. This asserts the
    per-frame fade stays a counter -- if `light_frame` ever grows a field-wide
    pass, this is what says so.
    """
    _machine, cost = portharness.run("fade_tick", blob, limit=600_000)
    assert cost < 100, f"the fade costs {cost:,} T-states a frame"
    # And the figure it is being held against, so the comparison is on the
    # record rather than in a commit message.
    assert cost * 400 < 40_857, "a whole-field decay would be cheaper than this"


@pytest.mark.xfail(reason="issue #156: the repaint set is found by scanning all "
                          "704 cells, which costs ten times the budget",
                   strict=True)
def test_a_frame_fits_the_frame(blob):
    """**The gate this slice does not meet, recorded rather than quietly
    dropped.**

    The picture is right and the fade is a ledger, but `paint_changed` finds the
    cells that changed by asking all 704 of them, at about 400 T-states each:
    **349,731 T-states a frame, 1,065% of `ENTITY_CEILING` and five whole
    frames.**

    The cells that actually change are few -- measured off the prototype over
    204,825 frames, a median of 8 and a worst of 58 (issue #154). So this is the
    cost of *finding* the set, not of drawing it, and the remedy is to schedule
    each cell's next level change when it is written rather than search for it.
    That is issue #156.
    """
    _machine, cost = portharness.light_run(blob, 2)
    assert cost < FRAME_TSTATES, f"a frame costs {cost:,} T-states"


def test_what_a_light_frame_costs_today(blob):
    """The two halves, recorded so #156 has a before to beat.

    `beam_emit` writes the disc's 37 cells at **25,447 T-states**, 78% of the
    ceiling -- most of it address arithmetic done four times a cell, since
    `add_light` computes the charge's address, the journal's, and the index
    cache's separately. `paint_changed` is **277,322**, which is the 704-cell
    search for the 8 cells that moved.

    Neither is asserted as a target; they are asserted as *recorded*, so that a
    change which makes either dramatically worse fails here.
    """
    _machine, emit = portharness.run("beam_emit", blob, limit=900_000)
    _machine, paint = portharness.run("paint_changed", blob, limit=900_000)
    assert emit < 40_000, f"beam_emit grew to {emit:,} T-states"
    assert paint < 400_000, f"paint_changed grew to {paint:,} T-states"
