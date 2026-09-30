"""The walls are authored, the contents still roll (issues #132 and #133).

*The plateau and the rooms*, rulings 2 to 5. Until this, a `roll:` template's
shell was the full rectangular border and nothing else, and `CLEAR = 3` held
every rolled solid two floor cells clear of that border -- so no seed on any
level could make a bay, a division, a chamber, a dead end or a room within a
room. Every room in the game was one open hall with furniture standing apart
in it.

Three things had to be true together before a wall could touch the border:

1. **A fly follows a wall to its end** (issue #131). Without it a wall that
   reached the border was a shield: a statue behind one survived five and a
   half seconds longer, so every wall added would have made the game easier.
2. **The walls stop rolling** (#132), because a seed-independent proof needs
   one shape to point at.
3. **The proof is the bare shell** (#133) -- `swarming.strands_a_shell`, which
   is a theorem and not a sample.

**The two-structure cap is authoring guidance, and this module is what
enforces it** -- not by classifying shapes, which is a job for a person, but
by catching the consequence. A shell that shuts a fly out fails the gate, and
the one-doored chamber below is here to show the gate biting on the shape the
round refused.
"""

import os

import pytest

from spikes import building as B, levels, roller, swarming
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import COLS

SEEDS = int(os.environ.get("SPOTLIGHT_ROLL_SEEDS",
                           "128" if os.environ.get("SPOTLIGHT_SLOW") else "16"))
FIRST = 0xBEEF

EAST_ONLY = ((B.EAST, (10, 11, 12)),)


def grid(*, walls=()):
    """A bare shell: four borders, floor between, plus `walls`."""
    rows = [[B.WALL] * COLS]
    rows += [[B.WALL] + [B.FLOOR] * (COLS - 2) + [B.WALL]
             for _ in range(PLAY_ROWS - 2)]
    rows.append([B.WALL] * COLS)
    for cx, cy in walls:
        rows[cy][cx] = B.WALL
    return tuple("".join(r) for r in rows)


#: A **division**: a wall border to border with a three-cell gap in it.
DIVISION = grid(walls=[(14, cy) for cy in range(1, PLAY_ROWS - 1)
                       if cy not in (9, 10, 11)])

#: A **bay**: a wall in from the top border, stopping well short of the
#: bottom one.
BAY = grid(walls=[(20, cy) for cy in range(1, 12)])

#: A **chamber with two doors on opposite walls**, which is the shape ruling 3
#: allowed.
CHAMBER_TWO = grid(walls=(
    [(cx, 6) for cx in range(9, 21)] + [(cx, 15) for cx in range(9, 21)]
    + [(9, cy) for cy in range(6, 16) if cy != 10]
    + [(20, cy) for cy in range(6, 16) if cy != 11]))

#: The same chamber with **one** door, which ruling 3 refused. Kept because
#: what it measures is not what the ruling assumed -- see
#: `test_an_authored_one_doored_chamber_is_fair_and_the_refusal_is_a_design_one`.
CHAMBER_ONE = grid(walls=(
    [(cx, 6) for cx in range(9, 21)] + [(cx, 15) for cx in range(9, 21)]
    + [(9, cy) for cy in range(6, 16)]
    + [(20, cy) for cy in range(6, 16) if cy != 11]))

#: A chamber the gate **does** catch: its door is cut in the room's own south
#: border, so the door opens into brick and the inside is sealed. This is the
#: authoring mistake the gate is for -- the retro-gamer broke three shells out
#: of four by hand, in this way and two others.
CHAMBER_SEALED = grid(walls=(
    [(cx, 13) for cx in range(10, 19)]
    + [(10, cy) for cy in range(13, PLAY_ROWS)]
    + [(18, cy) for cy in range(13, PLAY_ROWS)]
    + [(cx, PLAY_ROWS - 1) for cx in range(10, 19) if cx != 14]))

FAIR = {"a division": DIVISION, "a bay": BAY, "a two-doored chamber": CHAMBER_TWO}


def doors(shell=EAST_ONLY):
    return [B.Doorway(side, rows, to=0) for side, rows in shell]


def template(shells, **kw):
    kw.setdefault("segments", (2, 3))
    kw.setdefault("length", (4, 8))
    kw.setdefault("pieces", (1, 2))
    kw.setdefault("band", (6, 24))
    kw.setdefault("away", 8)
    kw.setdefault("workers", (90, 60))
    kw.setdefault("clegs", 2)
    kw.setdefault("doorways", EAST_ONLY)
    kw.setdefault("start", (24, 96))
    return roller.Template(shells=shells, **kw)


# --- the gate ----------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(FAIR))
def test_every_allowed_shape_strands_nothing_on_its_bare_walls(name):
    """The gate, on the vocabulary ruling 3 allowed. No seed is involved."""
    assert swarming.strands_a_shell(FAIR[name], doors()) == []


def test_the_gate_catches_a_chamber_whose_door_opens_into_the_border():
    """The gate biting, on a real authoring mistake rather than a made-up one.

    The chamber's door is cut in the room's own south wall, so it opens into
    brick and the inside is sealed. A flood fill would catch this one too; the
    gate catches it *and* the ones a flood fill would call fine, and it does
    both without running a seed.
    """
    stranded = swarming.strands_a_shell(CHAMBER_SEALED, doors())
    assert stranded, "a sealed chamber passed, which cannot be right"
    assert all(cy >= 14 and 11 <= cx <= 17 for cx, cy in stranded), stranded


def test_an_authored_one_doored_chamber_is_fair_and_the_refusal_is_a_design_one():
    """**Ruling 3's fairness argument does not survive ruling 5, and this is
    where that is written down.**

    Ruling 3 refused a chamber with one door -- the inner box the playtest
    building had for ten days -- on a measured 17 unfair rooms in 256. That
    figure was taken when the *chambers themselves rolled*: width six to nine,
    height four to six, a random position and a random door side, so one
    placement in fifteen came out badly. Ruling 5 then stopped the walls
    rolling, and an authored shell is one placement that an author chose and
    the gate checked.

    Measured after both: this one-doored chamber strands nothing on its bare
    walls and nothing on 256 rolled seeds, and so does every sensible
    placement tried -- door east, west or north, in the middle of the room or
    tucked in a corner. The only one the gate catches is the one whose door
    opens into the room's own border, which is broken for a different reason
    and is the test above.

    So the refusal stands on the half of ruling 3 that was never about
    fairness -- *there is no room in this building you can only get into one
    way* -- and that is a design preference, which is the user's to keep or
    drop. **It is not a safety rule and this test exists so that nobody later
    finds a fairness reason in it that is not there.**
    """
    assert swarming.strands_a_shell(CHAMBER_ONE, doors()) == []
    t = template([CHAMBER_ONE])
    seed = FIRST
    for _ in range(SEEDS):
        rolled = roller.roll(t, seed, "one-doored chamber")
        room = B.Room("rolled", rolled.rows, workers=rolled.workers,
                      clegs=rolled.clegs, player_start=t.start,
                      doorways=doors(), searchlight=B.Searchlight(3, False))
        assert swarming.unswarmable(room) == [], f"seed {seed:#x}"
        seed = rolled.seed


def test_the_gate_is_a_theorem_and_agrees_with_the_rolled_truth():
    """Bare-shell pass must imply rolled pass, for every seed.

    The argument is that `_reached` unions over starts and a rolled fly is an
    extra start, so adding contents can only grow what the swarm reaches.
    Checked here against the thing it claims to predict: on a shell the gate
    passes, no seed produces a room `unswarmable` complains about.
    """
    t = template([DIVISION])
    seed = FIRST
    assert swarming.strands_a_shell(DIVISION, doors()) == []
    for _ in range(SEEDS):
        rolled = roller.roll(t, seed, "a division")
        room = B.Room("rolled", rolled.rows, workers=rolled.workers,
                      clegs=rolled.clegs, player_start=t.start,
                      doorways=doors(), searchlight=B.Searchlight(3, False))
        assert swarming.unswarmable(room) == [], f"seed {seed:#x}"
        seed = rolled.seed


# --- the mechanism -----------------------------------------------------------

def interior_walls(rows):
    """The wall cells inside the border: what tells one shell from another."""
    return frozenset((cx, cy) for cy in range(1, PLAY_ROWS - 1)
                     for cx in range(1, COLS - 1) if rows[cy][cx] == B.WALL)


def test_the_roll_picks_between_the_shells_it_is_given():
    """Two shells, and across seeds both of them get built.

    Compared on the *interior* walls, because a rolled room also carries
    segments -- which are pipes and risers, not walls -- and because the exit
    and the doorways are cut through the border afterwards.
    """
    t = template([DIVISION, BAY])
    want = {"division": interior_walls(DIVISION), "bay": interior_walls(BAY)}
    seen, seed = set(), FIRST
    for _ in range(SEEDS):
        rolled = roller.roll(t, seed, "two shells")
        got = interior_walls(rolled.rows)
        for name, walls in want.items():
            if walls == got:
                seen.add(name)
        seed = rolled.seed
    assert seen == {"division", "bay"}, f"only built {sorted(seen)}"


def test_the_chosen_shells_walls_are_there_byte_for_byte():
    """Whatever rolls inside it, a shell's own wall cells are all present.

    The exit and the doorways are cut into the shell afterwards and are the
    one thing allowed to overwrite it, because `door:` lines are the single
    source of truth for where a doorway is.
    """
    t = template([DIVISION], exit=True)
    rolled = roller.roll(t, FIRST, "a division")
    cut = {(0, cy) for cy in roller.EXIT_ROWS}
    cut |= {(COLS - 1, cy) for cy in (10, 11, 12)}
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            if DIVISION[cy][cx] == B.WALL and (cx, cy) not in cut:
                assert rolled.rows[cy][cx] == B.WALL, \
                    f"the shell's wall at {(cx, cy)} was overwritten"


def test_a_template_with_no_shell_rolls_exactly_what_it_did_before():
    """The unconverted template is untouched, which is what lets the levels be
    converted one at a time in a later slice."""
    plain = template([])
    assert plain.shells == ()
    rolled = roller.roll(plain, FIRST, "plain")
    # The plain rectangle: border all round and no interior wall at all.
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            edge = cx in (0, COLS - 1) or cy in (0, PLAY_ROWS - 1)
            if not edge:
                assert rolled.rows[cy][cx] != B.WALL, \
                    f"a wall appeared at {(cx, cy)} in a shell-less roll"


def test_which_shell_is_drawn_before_anything_else_rolls():
    """One draw, taken first, so adding a second shell to a template does not
    reshuffle the furniture in the first."""
    one = roller.roll(template([DIVISION]), FIRST, "one")
    two = roller.roll(template([DIVISION, DIVISION]), FIRST, "two")
    # Both shells are the same grid, so only the extra draw could differ --
    # and it does, which is the honest statement of the cost: the pick is a
    # draw and a draw moves the stream.
    assert one.rows[0] == two.rows[0]
    assert roller.shell(template([DIVISION]), roller._Dice(FIRST))[3] == \
        list(DIVISION[3])


# --- the clearance rule, with the border exemption ---------------------------

@pytest.mark.parametrize("name", sorted(FAIR))
def test_no_rolled_solid_comes_within_two_cells_of_an_interior_wall(name):
    """`CLEAR = 3` is kept and only the border is exempt (ruling 2).

    A shell's wall may run to the edge; a *rolled* solid still stands two
    floor cells off everything solid, and the shell's interior walls are now
    among them. That is what keeps a division walkable on both sides and what
    the retro-gamer's *architecture eats furniture* is the price of.
    """
    shell = FAIR[name]
    interior = {(cx, cy) for cy in roller.INTERIOR_ROWS
                for cx in roller.INTERIOR_COLS if shell[cy][cx] == B.WALL}
    t = template([shell])
    seed = FIRST
    for _ in range(SEEDS):
        rolled = roller.roll(t, seed, name)
        for cy in range(1, PLAY_ROWS - 1):
            for cx in range(1, COLS - 1):
                if rolled.rows[cy][cx] in B.SOLID and shell[cy][cx] != B.WALL:
                    for wx, wy in interior:
                        assert max(abs(wx - cx), abs(wy - cy)) >= roller.CLEAR, \
                            (f"seed {seed:#x}: a rolled solid at {(cx, cy)} is "
                             f"{max(abs(wx - cx), abs(wy - cy))} from the wall "
                             f"at {(wx, wy)}")
        seed = rolled.seed


@pytest.mark.parametrize("name", sorted(FAIR))
def test_the_people_are_still_placed_and_still_inside_their_band(name):
    """A shell with a division or a chamber in it makes the route longer, and
    the band is about the walk -- so this is the test that the band and the
    shape are authored to agree."""
    t = template([FAIR[name]])
    seed = FIRST
    for _ in range(SEEDS):
        rolled = roller.roll(t, seed, name)
        assert len(rolled.workers) == len(t.workers), f"seed {seed:#x}"
        dist = roller.route_distances(rolled.rows, t.start)
        lo, hi = t.band
        for x, y, _blood in rolled.workers:
            cell = (x // 8, (y + 15) // 8)
            assert lo <= dist[cell] <= hi, \
                f"seed {seed:#x}: {cell} is {dist[cell]} from the start"
        seed = rolled.seed


# --- what a shell may contain ------------------------------------------------

def test_a_shell_holding_furniture_is_refused_with_the_row_named():
    bad = list(DIVISION)
    bad[5] = bad[5][:20] + B.CRATE + bad[5][21:]
    with pytest.raises(ValueError, match="row 5"):
        template([tuple(bad)]).validate("a bad shell")


def test_a_shell_of_the_wrong_shape_is_refused():
    with pytest.raises(ValueError, match="rows, need 22"):
        template([DIVISION[:-1]]).validate("short")
    short = list(DIVISION)
    short[7] = short[7][:-1]
    with pytest.raises(ValueError, match="row 7 is 31 cells"):
        template([tuple(short)]).validate("narrow")


# --- the level file ----------------------------------------------------------

HEAD = ("level: 9\nname: Test\nbuilding: The Test Works\n"
        # One clock a room: the roster is the building's (#143).
        "people: 90 90 90\n")


def shape_block(name, shell):
    return f"shape: {name}\n" + "\n".join(shell) + "\n"


def room_block(name, hue, shells=(), doors_=()):
    out = [f"room: {name}", "roll:",
           "segments: 2 3", "length: 4 8", "pieces: 1 2", "band: 6 24",
           "away: 8", "clegs: 1",
           "searchlight: 3 repeat", "start: 24 96"]
    out += [f"shell: {s}" for s in shells]
    out += list(doors_)
    return "\n".join(out) + "\n"


def test_a_level_file_declares_shapes_and_a_room_names_them():
    text = (HEAD + shape_block("spine", DIVISION) + shape_block("nook", BAY)
            + room_block("the hall", "yellow", ("spine", "nook")))
    _n, _name, specs, _budget, _shapes = levels.parse(text)
    assert [name for name, _rows in specs[0].shells] == ["spine", "nook"]
    assert specs[0].shells[0][1] == DIVISION


def test_a_room_with_no_shell_line_keeps_the_plain_rectangle():
    text = HEAD + room_block("the hall", "yellow")
    _n, _name, specs, _budget, _shapes = levels.parse(text)
    assert specs[0].shells == []


def test_naming_a_shape_that_does_not_exist_says_so():
    text = HEAD + room_block("the hall", "yellow", ("missing",))
    with pytest.raises(ValueError, match="no shape called 'missing'"):
        levels.parse(text)


def test_a_shape_after_the_first_room_is_refused():
    text = HEAD + room_block("the hall", "yellow") + shape_block("late", BAY)
    with pytest.raises(ValueError, match="goes before the first `room:`"):
        levels.parse(text)


def test_two_shapes_of_the_same_name_are_refused():
    text = (HEAD + shape_block("spine", DIVISION) + shape_block("spine", BAY)
            + room_block("the hall", "yellow", ("spine",)))
    with pytest.raises(ValueError, match="two shapes called 'spine'"):
        levels.parse(text)


def test_the_same_shell_named_twice_by_one_room_is_refused():
    text = (HEAD + shape_block("spine", DIVISION)
            + room_block("the hall", "yellow", ("spine", "spine")))
    with pytest.raises(ValueError, match="twice"):
        levels.parse(text)


def test_a_shape_of_the_wrong_width_is_refused_at_the_row():
    short = list(DIVISION)
    short[4] = short[4][:-1]
    text = (HEAD + shape_block("spine", short)
            + room_block("the hall", "yellow", ("spine",)))
    with pytest.raises(ValueError, match="row 4 is 31 wide"):
        levels.parse(text)


def test_shell_on_a_mapped_room_is_refused():
    text = (HEAD + shape_block("spine", DIVISION)
            + "room: the hall\nshell: spine\n")
    with pytest.raises(ValueError, match="belongs to a `roll:` room"):
        levels.parse(text)


# --- every shell the game ships ---------------------------------------------

def level_files():
    """Every authored building: the numbered levels **and the ladder**.

    The ladder (issue #146) is not a level -- `levels.levels()` globs
    `level*.txt` and it is not one -- but it is nine authored rooms with
    doorways in all four walls, which makes it the building these gates exist
    for. Leaving it out would have gated three teaching levels and skipped the
    one that needs it.
    """
    out = [(f"level {n}", f"level{n}.txt") for n in levels.levels()]
    return out + [("the ladder", levels.LADDER_FILE)]


def shipped_shells():
    """Every shell declared by every authored building, with the rooms using it."""
    out = []
    for label, filename in level_files():
        _num, _name, specs, _budget, _shapes = levels.parse(
            (levels.LEVELS_DIR / filename).read_text())
        for spec in specs:
            for name, rows in spec.shells:
                out.append((f"{label} {spec.name}: {name}", rows,
                            [(side, r) for side, r, _t, _l in spec.doors]))
    return out


def declared_shapes():
    """Every `shape:` every level file declares, **whether a room names it or
    not** (issue #144).

    A shape no room names used to be invisible: `parse` resolved a room's own
    shells onto its spec and dropped the rest, so nothing could see it and the
    gate could not check it. BU authors four shells for north/south rooms that
    nothing uses until #146, and a shell nobody has checked is worse than no
    shell at all -- the retro-gamer hand-authored four and three were broken.
    """
    out = []
    for label, filename in level_files():
        _num, _name, _specs, _budget, shapes = levels.parse(
            (levels.LEVELS_DIR / filename).read_text())
        for name, rows in sorted(shapes.items()):
            out.append((f"{label}: {name}", name, rows))
    return out


SHIPPED = shipped_shells()
DECLARED = declared_shapes()

#: Every band a doorway can be handed: the middle, which is where they sit up to
#: Level 3, and the six `levels.DOOR_BANDS` the ladder cycles from Level 4. They
#: are read as rows for a vertical doorway and as columns for a horizontal one,
#: because `_beyond` shifts a span without knowing which side it is on.
EVERY_BAND = ((10, 11, 12),) + levels.DOOR_BANDS

#: Which sides a shell is built for, by the axis its own walls run along. A
#: division is a wall *across* a walk on one axis and furniture on the other, so
#: asking a horizontal shell to survive an east doorway is asking the wrong
#: question -- it is the question #144 exists to stop anybody asking of a
#: vertical one.
#: **Four of the twelve are clean on all four sides**, and no more can be: take
#: the union of every lane over four sides and six bands and a wall may only
#: stand in columns 6 to 24 by rows 6 to 14 -- so **a wall in a room with
#: doorways on both axes cannot reach a border at all**, which is the one thing
#: the authored shells of issue #132 were for. Those four live inside that
#: rectangle; the other eight belong to an axis. `test_a_junction_may_only_use_a_four_sided_shell`
#: states it as a property rather than leaving it to this table.
FOUR_SIDED = ("boxroom", "vault", "benches", "pillars")
EVERY_SIDE = (B.EAST, B.WEST, B.NORTH, B.SOUTH)
BUILT_FOR = {
    "spine": (B.EAST, B.WEST), "spine-low": (B.EAST, B.WEST),
    "stubs": (B.EAST, B.WEST, B.SOUTH), "dogleg": (B.EAST, B.WEST, B.SOUTH),
    "rung": (B.NORTH, B.SOUTH), "rung-low": (B.NORTH, B.SOUTH),
    "ledges": (B.NORTH, B.SOUTH), "piers": (B.NORTH, B.SOUTH),
    **{name: EVERY_SIDE for name in FOUR_SIDED},
}


def test_every_shipped_shell_strands_nothing():
    """The gate, over the shells the game actually loads. Seed-independent, so
    this is the whole proof and not a sample of it.

    Vacuous until a level file authors a shell, which is a later slice; it is
    written now because the gate has to exist before the shells do -- the
    retro-gamer hand-authored four shells and three of them were broken, and
    this is what caught all three.
    """
    for label, rows, doorways in SHIPPED:
        stranded = swarming.strands_a_shell(
            rows, [B.Doorway(side, r, to=0) for side, r in doorways])
        assert stranded == [], f"{label} strands {len(stranded)} cells"


def test_every_shipped_shell_strands_nothing_wherever_its_doorways_move_to():
    """The same theorem, on every band the ladder can shift the doorway to.

    **The gate was only ever asked about the doorway as authored**, which is the
    position the room has up to Level 3 and not the one it has from Level 4 --
    `_beyond` moves every span to one of `levels.DOOR_BANDS`. A shell that
    stranded a fly only once its doorway moved off centre would have shipped.
    Every shipped shell passes on every band, measured, so this fails nothing
    today; it is the same hole issue #144 found in the landing rule, closed on
    the swarm gate while it is cheap -- forty milliseconds a shell and no seed.
    """
    for label, rows, doorways in SHIPPED:
        sides = sorted({side for side, _span in doorways})
        for span in EVERY_BAND:
            stranded = swarming.strands_a_shell(
                rows, [B.Doorway(side, span, to=0) for side in sides])
            assert stranded == [], \
                f"{label} strands {len(stranded)} cells with its doorways at {span}"


# --- the landing clause (issue #144) -----------------------------------------

def test_the_two_shipped_spines_block_a_centre_horizontal_landing():
    """**The fault, named so the refusal cannot be lost.**

    `spine` runs a wall down column 15 and `spine-low` down column 16, so a
    centre north or south doorway at columns 14-16 has a wall standing in the
    middle of it. The division runs straight down and stops dead in the doorway
    it is standing in:

        20  #..............#...............#
        21  ##############ddd###############

    A two-room building built from `spine` with a south doorway **loads,
    validates and passes `strands_a_shell`**, because columns 14 and 16 are
    floor and a fly is one cell wide. A person is one cell wide too and the
    movement assist nudges by up to a cell, so they squeeze -- the exact failure
    `DOORWAY_CELLS = 3` exists to prevent.

    Both are fine under the east and west doorways every shipped level actually
    uses, which is why four days of `pytest` never saw it.
    """
    by_name = {name: rows for _label, name, rows in DECLARED}
    for name, column in (("spine", 15), ("spine-low", 16)):
        rows = by_name[name]
        for side in (B.NORTH, B.SOUTH):
            bad = roller.blocks_a_landing(rows, [(side, (14, 15, 16))])
            assert bad, f"{name} no longer blocks a {B.SIDE_NAMES[side]} landing"
            assert {cx for cx, _cy in bad} == {column}, bad
        for side in (B.EAST, B.WEST):
            assert roller.blocks_a_landing(rows, [(side, (10, 11, 12))]) == []


def test_every_shipped_room_clears_the_landings_of_its_own_doorways():
    """**The clause that matters, and it is per room.** For every room of every
    level, for every shell that room may be built from, for every doorway that
    room has, on every band the ladder can shift that doorway to: no wall of the
    shell stands in the lane.

    Per room rather than per shell because a shell has no doorways of its own. A
    spine is perfectly sound in a room whose doors are east and west and unsound
    the moment somebody gives that room a south one -- and `BUILT_FOR` above is
    only an author's statement of intent, which a level file can contradict.
    **This is what will catch it when #146 gives a room a doorway on a new
    side**, and the reason it is worth writing before there is such a room.

    The shipped levels are all east-west, so this passes today. That is the
    point: it passed the day the fault shipped too, and the difference is that
    now it will stop passing.
    """
    for label, rows, doorways in SHIPPED:
        for side, _authored in doorways:
            for span in EVERY_BAND:
                bad = roller.blocks_a_landing(rows, [(side, span)])
                assert bad == [], \
                    f"{label} blocks its own {B.SIDE_NAMES[side]} doorway at " \
                    f"{span}: {bad}"


def test_the_per_room_clause_bites_on_a_spine_with_a_south_doorway():
    """The case the issue was raised for, built: the same shell, the same gate,
    and the only change is which wall the doorway is in.

    A two-room building from `spine` with a south doorway is the thing that
    loads and validates today. The per-room clause refuses it, and the
    refusal names the cells.
    """
    by_name = {name: rows for _label, name, rows in DECLARED}
    spine = by_name["spine"]
    #: Which bands of a south doorway the spine's column 15 stands in. Only the
    #: two that reach it -- the clause is a fact about a wall and a gap, not a
    #: blanket refusal of the shell.
    blocked = [span for span in EVERY_BAND
               if roller.blocks_a_landing(spine, [(B.SOUTH, span)])]
    assert blocked == [(15, 16, 17), (13, 14, 15)], blocked
    # And the centre, which is where every doorway up to Level 3 sits and the
    # band the measurement in the issue was taken on.
    assert [cx for cx, _cy in
            roller.blocks_a_landing(spine, [(B.SOUTH, (14, 15, 16))])] == [15] * 5
    # The swarm gate passes on the same shape, which is why it was never caught:
    # columns 14 and 16 are floor and a fly is one cell wide.
    assert swarming.strands_a_shell(
        spine, [B.Doorway(B.SOUTH, (14, 15, 16), to=0)]) == []


def test_the_clean_shells_are_still_clean():
    """The other three shipped shells pass the new clause unchanged, on the axis
    they are built for. `dogleg` is the one that says why the clause is the
    gap's own lane and not the whole band: its wall stands two columns from a
    centre doorway, which the rolled-furniture band forbids and an author is
    entitled to."""
    by_name = {name: rows for _label, name, rows in DECLARED}
    for name in FOUR_SIDED + ("dogleg", "stubs"):
        for side in BUILT_FOR[name]:
            for span in EVERY_BAND:
                assert roller.blocks_a_landing(by_name[name], [(side, span)]) == [], \
                    f"{name} blocks a {B.SIDE_NAMES[side]} landing at {span}"
    # And the distinction, stated: dogleg's wall is inside the *band* of a
    # centre north doorway and outside its *lane*.
    dogleg = by_name["dogleg"]
    band = roller.landing_band([(B.NORTH, (14, 15, 16))])
    assert any(dogleg[cy][cx] == B.WALL for cx, cy in band)
    assert roller.blocks_a_landing(dogleg, [(B.NORTH, (14, 15, 16))]) == []


def test_every_declared_shell_clears_every_band_it_can_be_handed():
    """The gate proper: every shape every level file declares, against every
    band the ladder can hand it on the axis it is built for -- **and the exit**,
    which is a gap in a wall a tail files out through and would be sealed by a
    wall across it.

    Per room and not per shell, which is the part that is easy to get wrong: a
    shell clear under a centre doorway is not clear under an off-centre one, and
    the bands move by level.
    """
    for label, name, rows in DECLARED:
        assert name in BUILT_FOR, f"{label}: say which sides it is built for"
        for side in BUILT_FOR[name]:
            for span in EVERY_BAND:
                bad = roller.blocks_a_landing(rows, [(side, span)])
                assert bad == [], \
                    f"{label} blocks the {B.SIDE_NAMES[side]} landing at " \
                    f"{span}: {bad}"
        assert roller.blocks_a_landing(rows, [(B.WEST, roller.EXIT_ROWS)]) == [], \
            f"{label} walls off the exit's own landing"


def test_a_junction_may_only_use_a_four_sided_shell():
    """**The constraint issue #146 did not foresee, stated as a property.**

    A doorway's lane is its own span five cells in from the wall it is cut
    through, and from Level 5 a doorway sits at any of six bands. Take the union
    over four sides and six bands and the cells a wall may stand in are a single
    rectangle -- columns 6 to 24 by rows 6 to 14 -- so **a wall in a room with
    doorways on both axes cannot reach a border**, which is what a division and
    a chamber were for.

    It bites on four of the nine-room building's rooms: `B`, `C`, `F` and the
    crossing `D`, which has a doorway in every wall. Hence `vault`, `benches`
    and `pillars` beside `boxroom`: four shells that live inside the rectangle,
    so a junction is not always the same room.
    """
    from spikes.layout import PLAY_ROWS
    lanes = set()
    for side in EVERY_SIDE:
        for span in EVERY_BAND:
            lanes |= set(roller.landing_lane(side, span))
    lanes |= set(roller.landing_lane(B.WEST, roller.EXIT_ROWS))
    free = {(cx, cy) for cy in range(1, PLAY_ROWS - 1) for cx in range(1, COLS - 1)
            if (cx, cy) not in lanes}
    xs = {cx for cx, _cy in free}
    ys = {cy for _cx, cy in free}
    core = {(cx, cy) for cy in range(6, 15) for cx in range(6, 25)}
    assert core <= free, "the rectangle a four-sided shell lives in has moved"
    assert min(xs) > 0 and max(xs) < COLS - 1 and min(ys) > 0 and max(ys) < PLAY_ROWS - 1
    # No free cell touches a border, which is the whole claim.
    assert not any(cx in (1, COLS - 2) or cy in (1, PLAY_ROWS - 2)
                   for cx, cy in free if (cx, cy) in core)
    by_name = {name: rows for _label, name, rows in DECLARED}
    clean = {name for name, rows in by_name.items()
             if all(not roller.blocks_a_landing(rows, [(side, span)])
                    for side in EVERY_SIDE for span in EVERY_BAND)}
    assert clean == set(FOUR_SIDED), clean


def test_the_shells_a_room_names_are_clean_for_that_rooms_own_sides():
    """Per room, and the precise form of it: a shell a room names must be clean
    for **that room's** doorway sides, not for all four.

    A room with a west and a south doorway is fine with `stubs`, whose bays are
    clear of both those lanes -- and that is not a concession, it is the point:
    a shell belongs to the axes a room actually uses. What cannot be done is a
    doorway in every wall, which leaves only the four-sided shells. `the
    crossing` is that room, and the assertion names it.

    This is what will fail if a later slice gives a room a doorway on a new side
    and forgets its shells -- which is exactly how the fault issue #144 was
    raised for got into two shipped shells.
    """
    crossings = 0
    for label, filename in level_files():
        _n, _name, specs, _b, _s = levels.parse(
            (levels.LEVELS_DIR / filename).read_text())
        for spec in specs:
            sides = {side for side, _sp, _t, _l in spec.doors}
            for name, rows in spec.shells:
                for side in sides:
                    for span in EVERY_BAND:
                        assert not roller.blocks_a_landing(rows, [(side, span)]), \
                            f"{label} {spec.name!r} names {name!r}, which blocks " \
                            f"its {B.SIDE_NAMES[side]} doorway at {span}"
            if len(sides) == 4:
                crossings += 1
                assert all(name in FOUR_SIDED for name, _rows in spec.shells), \
                    f"{label} {spec.name!r} has a doorway in every wall and can " \
                    f"only use {FOUR_SIDED}"
    assert crossings == 1, \
        f"{crossings} rooms with a doorway in every wall; the ladder has one"


def test_the_new_shells_run_their_walls_the_other_way_and_pass_both_gates():
    """The second half of the ruling, and the half that gets dropped: a vertical
    division is a wall across an east-west walk and *furniture* in a north-south
    one, so the game had no shell for a room whose traffic runs top to bottom.

    Four, each the turn of one that already existed: `rung` and `rung-low` for
    the two spines, `ledges` for the dogleg, `piers` for the stubs. Each passes
    the bare-shell gate and the landing clause against every band a north or
    south doorway can take, and each rolls a room on every seed tried.
    """
    by_name = {name: rows for _label, name, rows in DECLARED}
    for name in ("rung", "rung-low", "ledges", "piers"):
        rows = by_name[name]
        # A horizontal wall lives in rows 6 to 15: rows 1-5 and 16-20 are the
        # landings of a north and a south doorway.
        walls = {cy for cy, row in enumerate(rows)
                 for cx, ch in enumerate(row)
                 if ch == B.WALL and 0 < cx < COLS - 1}
        assert walls <= {0, PLAY_ROWS - 1} | set(range(6, 16)), \
            f"{name} runs a wall through a doorway's landing rows"
        for span in EVERY_BAND:
            doorways = [B.Doorway(B.NORTH, span, to=0),
                        B.Doorway(B.SOUTH, span, to=0)]
            assert swarming.strands_a_shell(rows, doorways) == [], (name, span)
            for side in (B.NORTH, B.SOUTH):
                assert roller.blocks_a_landing(rows, [(side, span)]) == [], \
                    f"{name} blocks a {B.SIDE_NAMES[side]} landing at {span}"


def test_every_shell_in_the_vocabulary_is_named_by_some_room_or_proved_unused():
    """Twelve shells, and each is either used or deliberately not.

    The four horizontal ones and the four-sided ones were authored unused in
    #144 and #146 uses all eight. The two east-west **divisions** are the ones
    now used by nothing: every room of the ladder has a doorway in a horizontal
    wall, so neither spine is usable there, and Level 1 is open halls. They stay
    declared because a shape nobody names is still checked by the gate, and they
    are the vocabulary's pair for a room whose doorways are east and west only.
    """
    named = {label.rsplit(": ", 1)[1] for label, _rows, _doors in SHIPPED}
    declared = {name for _label, name, _rows in DECLARED}
    assert declared == set(BUILT_FOR), declared ^ set(BUILT_FOR)
    assert named == declared - {"spine", "spine-low"}, declared - named
    # And every four-sided shell is actually used, or the junctions would all be
    # the same room.
    assert set(FOUR_SIDED) <= named, set(FOUR_SIDED) - named


def test_the_roll_never_carves_a_landing_clear():
    """Ruled and refused: the roller must not repair an authored shell.

    A silent carve would turn a division into two stubs and tell nobody, so the
    gate refuses and the author fixes. Stated as a property of the output: a
    room rolled from `spine` with a south doorway still has the wall standing in
    the doorway, and every cell of the shell's wall survives the roll.
    """
    by_name = {name: rows for _label, name, rows in DECLARED}
    shell = by_name["spine"]
    walls = {(cx, cy) for cy, row in enumerate(shell)
             for cx, ch in enumerate(row) if ch == B.WALL}
    doorways = [(B.SOUTH, (14, 15, 16))]
    for seed in range(FIRST, FIRST + 8):
        rolled = roller.roll(
            roller.Template(segments=(0, 0), pieces=(0, 0), band=(6, 26),
                            away=8, workers=(90,), clegs=1, doorways=doorways,
                            start=(120, 96), exit=False, shells=[shell]),
            seed, "spine")
        cut = {cell for cell in roller.landing_lane(B.SOUTH, (14, 15, 16))
               if rolled.rows[cell[1]][cell[0]] == B.DOORWAY}
        for cx, cy in walls:
            if (cx, cy) in cut:
                continue          # the gap itself, which the roll does cut
            assert rolled.rows[cy][cx] != B.FLOOR, \
                f"the roll carved the shell's wall at {(cx, cy)}"
        assert roller.blocks_a_landing(rolled.rows, doorways), \
            "the roll quietly cleared the landing instead of leaving it broken"
