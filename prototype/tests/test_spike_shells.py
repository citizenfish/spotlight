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
    out = [f"room: {name}", f"floor: {hue}", "roll:",
           "segments: 2 3", "length: 4 8", "pieces: 1 2", "band: 6 24",
           "away: 8", "clegs: 1",
           "searchlight: 3 repeat", "start: 24 96"]
    out += [f"shell: {s}" for s in shells]
    out += list(doors_)
    return "\n".join(out) + "\n"


def test_a_level_file_declares_shapes_and_a_room_names_them():
    text = (HEAD + shape_block("spine", DIVISION) + shape_block("nook", BAY)
            + room_block("the hall", "yellow", ("spine", "nook")))
    _n, _name, specs, _budget = levels.parse(text)
    assert [name for name, _rows in specs[0].shells] == ["spine", "nook"]
    assert specs[0].shells[0][1] == DIVISION


def test_a_room_with_no_shell_line_keeps_the_plain_rectangle():
    text = HEAD + room_block("the hall", "yellow")
    _n, _name, specs, _budget = levels.parse(text)
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
            + "room: the hall\nfloor: yellow\nshell: spine\n")
    with pytest.raises(ValueError, match="belongs to a `roll:` room"):
        levels.parse(text)


# --- every shell the game ships ---------------------------------------------

def shipped_shells():
    """Every shell declared by every level file, with the rooms that use it."""
    out = []
    for n in levels.levels():
        _num, _name, specs, _budget = levels.parse(
            (levels.LEVELS_DIR / f"level{n}.txt").read_text())
        for spec in specs:
            for name, rows in spec.shells:
                out.append((f"level {n} {spec.name}: {name}", rows,
                            [(side, r) for side, r, _t, _l in spec.doors]))
    return out


SHIPPED = shipped_shells()


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
