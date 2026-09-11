"""The legibility contract: what has to be true of two shapes that mean
different things.

**This test is worth more than the sprites it pins**, and that is the reason it
exists rather than a compliment to it. Twice now a pair of drawings has been
signed off on a sprite sheet and then failed in front of somebody looking at a
played screen -- the player against a follower, and the open door against a
locked one -- and both times the fault was the same one: **a pair that differs
in fill rather than in outline.** Neither was caught by looking, because the
sheet is where art is *named* and the played screen is where it is *judged*.
So the rule goes here, where the next redraw has to get past it.

Five assertions, over every pair of the four figures and over the door pair:

1. Some row differs by **at least three pixels** -- the measured failure was
   two.
2. The difference is **not confined to columns 0, 1, 6 and 7** -- width alone
   is not a silhouette.
3. The **topmost drawn row** differs, or the ink in rows 0-2 differs by at
   least three pixels -- the top of a figure is what you see first in a glow.
4. A pair of states that means something differs in **outline**, not in fill.
5. **A figure that means something different differs in *aspect*, and never in
   pose.** Added 2026-09-11 (issue #59), and it is the line that would have
   caught the third failure of exactly this kind.

**Assertion 5 is the general form of 1 to 4.** All four of those compare two
drawings *inside one box*, and they can only ever be as strong as the box
allows: the body was 8x16, it passed every one of them against all three living
figures, and a cold reader still called it a person twice in one session and
was confident both times. What it differed by was **pose** -- a head lolled off
the axis, an arm flung higher than the other -- and pose is a sprite-sheet
property that does not survive to six pixels across on a stippled floor. The
box was the problem, not the drawing in it, and no assertion that reads eight
bytes against eight bytes can say so.

`test_the_old_body_passes_the_first_three_assertions_and_fails_the_fifth`
keeps the old bytes and proves both halves of that sentence, so nobody has to
take it on trust.

And two clauses about the player's two marks, one for each ground he has to be
seen against: `test_the_mark_on_lit_floor_is_five_pixels_of_solid_ink` and
`test_the_lamp_is_the_mark_that_needs_no_floor`. Both are pinned by deleting
the mark and watching this file fail, which is the only way to know a test of
this kind is awake.

**Two scoping notes, without which a literal reading condemns art the design
asks for.** Both are written here rather than left as skipped cases, so that
whoever reopens them can see what they are reopening:

* **The five-pixel clause is about a mark added to a figure that stands on lit
  floor**, which is the player's bar. It is not a rule about everything drawn:
  the lamp is four pixels and is kept deliberately, and a door's jambs are two.
* **Assertion 4 is applied to the door pair and not to the lamp pair.**
  `LAMP_OFF` and `LAMP_ON` share a silhouette on purpose, and the exemption has
  a reason rather than being an oversight: **a burning lamp sits inside the pool
  of light it is making**, and that pool is a far larger cue than the eight
  bytes in the middle of it. It is the only state pair in the game with a
  second channel of its own. If a session ever reports a spare being mistaken
  for a burning one, that is the paragraph that gets reopened -- and
  `test_the_lamp_pair_shares_a_silhouette_and_that_is_the_exemption` is where
  the exemption is asserted rather than assumed, so it cannot rot into an
  accident.
"""

from itertools import combinations

from spikes import sprites as SP

WIDTH = SP.WIDTH

#: The columns the 2026-09-09 failure lived in: two pixels of shoulder width at
#: each edge, and nothing anywhere else. Assertion 2 is that a difference must
#: reach outside them.
EDGE_COLUMNS = 0xC3
MIDDLE_COLUMNS = 0xFF ^ EDGE_COLUMNS


def bits(row: int) -> int:
    return bin(row).count("1")


def ink_pixels(sprite) -> set:
    return {(x, y) for y, row in enumerate(sprite)
            for x in range(WIDTH) if row & (0x80 >> x)}


def outside(sprite) -> set:
    """Every clear pixel reachable from beyond the edge of the box.

    A flood fill, four-connected, starting outside the corner. What it answers
    is whether a hole in a shape is **open to the world or enclosed by it**,
    which is the difference between a doorway and a panel.
    """
    height = len(sprite)
    solid = ink_pixels(sprite)
    seen, stack = set(), [(-1, -1)]
    while stack:
        point = stack.pop()
        x, y = point
        if point in seen or point in solid:
            continue
        if not (-1 <= x <= WIDTH and -1 <= y <= height):
            continue
        seen.add(point)
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return seen


def outline(sprite) -> frozenset:
    """The shape's **silhouette**: the ink you would see if it were a cut-out.

    Every ink pixel that touches air reachable from outside the box. Ink walled
    in behind other ink -- the locked door's leaf, a burning lamp's filled
    middle -- is *fill* and not outline, which is exactly the distinction the
    two misreads turned on: at 1:1 across a room, a bright middle and a dark
    middle inside the same eight-by-sixteen frame are the same object.
    """
    air = outside(sprite)
    return frozenset(
        (x, y) for x, y in ink_pixels(sprite)
        if any((x + dx, y + dy) in air
               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))))


def topmost(sprite) -> int:
    """The first row with anything drawn in it, or the height if none."""
    for i, row in enumerate(sprite):
        if row:
            return i
    return len(sprite)


def longest_run(row: int) -> int:
    """The longest unbroken run of set pixels in one row."""
    best = run = 0
    for i in range(WIDTH):
        run = run + 1 if row & (0x80 >> i) else 0
        best = max(best, run)
    return best


# --- the three assertions, over every pair of the four figures --------------

def assertion_1(a, b) -> bool:
    return any(bits(x ^ y) >= 3 for x, y in zip(a, b))


def assertion_2(a, b) -> bool:
    differing = 0
    for x, y in zip(a, b):
        differing |= x ^ y
    return bool(differing & MIDDLE_COLUMNS)


def assertion_3(a, b) -> bool:
    if topmost(a) != topmost(b):
        return True
    return sum(bits(x ^ y) for x, y in zip(a[:3], b[:3])) >= 3


def aspect(sprite) -> tuple:
    """A drawing's box: how wide and how tall, in pixels."""
    return SP.width_of(sprite), len(sprite)


def pairs():
    """Every pair of figures that shares a box, and so is told apart inside it.

    The three on their feet. **A body is not compared this way since issue
    #59** and could not be: assertions 1 to 3 read one byte against another,
    and there is no meaningful pairing of a 16x8 row with an 8x16 one. It is
    covered by assertion 5, which is a stronger claim than any of them --
    differing in the box is the largest difference two drawings can have.
    """
    for one, two in combinations(SP.STANDING, 2):
        yield one, two, SP.SPRITES[one], SP.SPRITES[two]


def test_some_row_of_every_pair_of_figures_differs_by_three_pixels():
    """Assertion 1. **The measured failure was two.**

    PLAYER and FOLLOWER differed in sixteen pixels and never more than two in a
    row, and a reader looking at them labelled, side by side, on a blank
    screen, said they still could not call it. Two pixels is not a silhouette
    at 1:1 and no amount of them in the right places makes one.
    """
    for one, two, a, b in pairs():
        worst = max(bits(x ^ y) for x, y in zip(a, b))
        assert assertion_1(a, b), \
            f"{one} and {two} never differ by more than {worst} pixels in a row"


def test_no_pair_of_figures_differs_only_at_the_edges_of_its_column():
    """Assertion 2. **Width alone is not a silhouette.**

    Every one of the sixteen pixels that told the player from a follower was in
    columns 0, 1, 6 and 7 -- the figure was two pixels broader and nothing
    else. A difference has to reach the middle of the column, where the eye is
    already looking.
    """
    for one, two, a, b in pairs():
        assert assertion_2(a, b), \
            f"{one} and {two} differ only at the edges of their column"


def test_every_pair_of_figures_differs_where_the_eye_lands_first():
    """Assertion 3. **The top of a figure is what you see first in a glow.**

    Either the topmost drawn row differs -- one figure starts higher than the
    other -- or there are three pixels of difference in the top three rows.
    The player passes on the first clause because of his lamp; the worker and
    the follower pass on the second, because their arms are in different places
    above the shoulders.
    """
    for one, two, a, b in pairs():
        assert assertion_3(a, b), \
            f"{one} and {two} look the same at the top, where a glow finds them"


def test_all_three_pairs_pass_all_three():
    """Said once as a whole, because the contract is the conjunction.

    A drawing that satisfied two assertions out of three would still be the
    fault this exists to prevent, and reading three separate failures is not
    the same as being told the pair is illegible.
    """
    for one, two, a, b in pairs():
        failed = [n for n, check in enumerate(
            (assertion_1, assertion_2, assertion_3), start=1)
            if not check(a, b)]
        assert not failed, f"{one} against {two} fails assertion(s) {failed}"


# --- assertion 5: aspect, not pose ------------------------------------------

#: The body as it was drawn from 2026-09-07 to 2026-09-11: 8x16, and told from
#: a living figure by its **pose**. Kept here, and nowhere else, because the
#: tests below are the argument that it was not enough -- and because an idea
#: this obvious gets had twice. It is the drawing two cold readers approved on
#: the sprite sheet and a third misread twice in one played session.
OLD_BODY = (
    0x00, 0x00,
    0x60,       # .##.....   the head, rolled off the centre line
    0xF0,       # ####....
    0x70,       # .###....
    0x38,       # ..###...   shoulders
    0x3F,       # ..######   one arm flung out
    0x38,       # ..###...   trunk
    0xF8,       # #####...   the other arm, lower and bent
    0x38, 0x38, 0x38,
    0x7C,       # .#####..   hips
    0xC6,       # ##...##.   legs, splayed unevenly
    0x83,       # #.....##
    0x00,
)


def test_a_figure_that_means_something_different_differs_in_aspect():
    """Assertion 5, over every pair of the four figures.

    The three on their feet mean the same *kind* of thing -- a person standing
    up -- and are told apart inside one box by assertions 1 to 3. The body
    means the opposite thing, the one figure in the game you are trying not to
    find, and it is told from all three **by the box**: sixteen wide and eight
    tall against eight wide and sixteen tall.

    Seen from above, a fallen person is *longer* than a standing one. An
    eight-pixel box cannot express length, which is why pose was the only tell
    available while the box was 8x16 and why pose was never going to be enough.
    """
    for one, two in combinations(SP.PEOPLE, 2):
        a, b = SP.SPRITES[one], SP.SPRITES[two]
        if aspect(a) != aspect(b):
            continue
        assert one in SP.STANDING and two in SP.STANDING, (
            f"{one} and {two} share a box and mean different things, so the "
            f"only thing left to tell them apart is what is drawn in it")
        assert all(check(a, b) for check in
                   (assertion_1, assertion_2, assertion_3))


def test_the_dead_and_the_living_never_share_a_box():
    """Said as its own line, because it is the whole of the 2026-09-11 ruling.

    *Size says whether a thing is a person* still stands. *Pose says whether it
    is alive* is withdrawn, and **orientation says whether it is upright** in
    its place.
    """
    for name in SP.STANDING:
        assert aspect(SP.SPRITES[name]) != aspect(SP.BODY), \
            f"{name} and a corpse are the same shape of box again"
    assert aspect(SP.BODY) == (16, 8)


def test_the_old_body_passes_the_first_three_assertions_and_fails_the_fifth():
    """**The pin, and the thing that was wrong before.**

    The contract was green on the day a reader called a corpse the person they
    were hunting. This is why: the old body satisfied every assertion the
    contract had, against all three living figures, because all three
    assertions compare drawings inside one box and the box was the fault.

    Both halves are asserted. If assertion 5 is ever weakened, the second half
    of this fails and whoever weakened it reads the first half.
    """
    for name in SP.STANDING:
        other = SP.SPRITES[name]
        assert len(OLD_BODY) == len(other)
        failed = [n for n, check in enumerate(
            (assertion_1, assertion_2, assertion_3), start=1)
            if not check(OLD_BODY, other)]
        assert not failed, (
            f"the old body failed assertion(s) {failed} against {name}, so "
            f"this test no longer says what it was written to say")
        assert aspect(OLD_BODY) == aspect(other), \
            "the old body shared a box with the living, which was the fault"


def test_a_one_cell_heap_would_be_refused_because_it_spends_the_nests_tell():
    """Recorded because it was drawn, looked at and rejected (issue #59).

    The cheap answer to *a body reads as a person* is to stop drawing a person:
    a low wide heap inside one cell stops reading as one immediately. It is
    refused because **a nest is told from a body by being one cell tall**, and
    a body becoming a nest is a thing the player has to be able to see happen.
    Trading a body/person confusion for a body/nest confusion is a move and not
    a fix.

    The second refusal has no test because it is a judgement a test cannot
    make: a sprawl with the limbs flung wider reads at 1:1 as a Cleg.
    """
    def cells_of(sprite):
        """The area of a drawing in whole attribute cells, drawn aligned."""
        return (SP.width_of(sprite) // 8) * (len(sprite) // 8)

    assert cells_of(SP.BODY) == 2, "a body is two cells, or a nest is its size"
    assert cells_of(SP.NEST) == 1
    assert cells_of(SP.BODY) > cells_of(SP.NEST), \
        "a body no longer visibly shrinks when it turns into a nest"


# --- assertion 4: outline, not fill -----------------------------------------

def test_the_door_pair_differs_in_outline_and_not_in_fill():
    """Assertion 4, on the pair that taught it.

    Both states were an 8x16 magenta rectangle, one with a bright middle and
    one with a dark one, and a first-timer read them backwards -- not because
    the metaphor was wrong (they guessed *hollow means you can walk through*
    correctly) but because at 1:1 across a room the two are the same object.

    An open door is now **where the wall stops and returns**: two jambs, a
    four-pixel gap, no head and no sill, so the outline is open at both ends
    where the locked one's is closed at both.
    """
    assert outline(SP.DOOR_OPEN) != outline(SP.DOOR_LOCKED), \
        "the two door states have the same silhouette, which is the fault"


def test_you_can_see_through_the_door_you_can_walk_through():
    """The metaphor, checked as geometry rather than as a caption.

    The open door's gap reaches the outside of its box; the locked door's
    middle is enclosed by its own frame. That is what "hollow means you can
    walk through it" means when it is drawn rather than said.
    """
    height = len(SP.DOOR_OPEN)
    gap = [(x, y) for x, y in outside(SP.DOOR_OPEN)
           if 0 <= x < WIDTH and 0 <= y < height]
    assert len(gap) == 4 * height, "the open door has no way through it"
    shut = [(x, y) for x, y in outside(SP.DOOR_LOCKED)
            if 0 <= x < WIDTH and 0 <= y < len(SP.DOOR_LOCKED)]
    assert not shut, "the locked door has a hole in it"
    assert SP.DOOR_OPEN[0] != 0xFF and SP.DOOR_OPEN[-1] != 0xFF, \
        "the open door has a head or a sill, which closes its outline"
    assert SP.DOOR_LOCKED[0] == SP.DOOR_LOCKED[-1] == 0xFF, \
        "the locked door is not closed at both ends"


def test_a_three_pixel_jamb_would_be_refused():
    """Recorded because it was drawn, looked at and rejected.

    Three-pixel jambs leave a two-pixel slot, and **a two-pixel slot closes up
    at 1:1** -- which is the fault being fixed, reintroduced by the fix. The
    gap is four pixels, half the door.
    """
    for row in SP.DOOR_OPEN:
        assert row == 0xC3, "the jambs are not two pixels with four between"


def test_the_lamp_pair_shares_a_silhouette_and_that_is_the_exemption():
    """**The exemption, asserted rather than skipped.**

    `LAMP_OFF` and `LAMP_ON` would fail assertion 4 and are meant to: a burning
    lamp sits inside the pool of light it is making, which is a much larger cue
    than the eight bytes in the middle of it, and it is the only state pair in
    the game with a second channel of its own.

    Written as a test so that the day somebody redraws the family and the
    silhouettes drift apart, this fails and they read the reason before
    deciding whether it still holds.
    """
    assert outline(SP.LAMP_OFF) == outline(SP.LAMP_ON), \
        "the lamp pair no longer shares one silhouette -- read the docstring"
    assert outline(SP.HOUSING) == outline(SP.LAMP_OFF), \
        "the housing left the family's silhouette"
    # And the middles are what tell them apart: empty, filled, a lens.
    assert sum(bits(r) for r in SP.LAMP_OFF) \
        < sum(bits(r) for r in SP.HOUSING) \
        < sum(bits(r) for r in SP.LAMP_ON)


def test_the_batten_is_not_an_octagon_and_that_is_the_point():
    """**A thing you walk under must not look like a thing you can pick up.**

    The ceiling fixture over a room light is the fourth of the lamp family and
    is deliberately outside its silhouette -- a hollow bar, a strip light seen
    from above.
    """
    for name in ("lamp_off", "lamp_on", "housing"):
        assert outline(SP.BATTEN) != outline(SP.SPRITES[name]), \
            f"the batten reads as a {name}, which you could try to pick up"


# --- the player's two marks, one for each ground ---------------------------

def test_the_mark_on_lit_floor_is_five_pixels_of_solid_ink():
    """The companion rule, and **it is about a mark on a figure standing on lit
    floor** -- not about everything drawn.

    The lit floor stipple puts a dot every four pixels. A mark four pixels wide
    is the same width as the gap between two dots, so the eye pools it with the
    floor: **nothing narrower than five pixels of solid ink is a mark on this
    ground.** The player's bar is eight, twice the stipple's spacing, and it is
    in the bottom two rows of the box, which every other figure leaves blank.

    The one clear row above it is not decoration: without it the bar reads as
    feet rather than as ground.

    **The narrow claim is the one pinned, and it stays pinned** (issue #59).
    The design note used to say the bar sits in "the bottom two rows, which
    every other figure leaves blank", and that was true of three figures out of
    four: the old 8x16 BODY put its lower splayed leg on row 14. Laying the
    body down was expected to make the wider claim true again -- and **it does
    not, quite, and the difference is worth writing down rather than
    discovering later.** A body's box is eight rows, so it has no row 14 or 15
    of its own; but it is drawn in one cell row, and the second-from-bottom row
    of that cell holds four pixels of trailing leg. A body lying in the cell
    row a player is standing in therefore still puts ink on the same *pixel*
    row as the top half of his bar.

    What is exactly true, on the screen rather than in the box, is the thing
    the mark rests on and the thing this pins: **the player is the only figure
    with an unbroken run of five pixels in the bottom two rows of its box, and
    the last row is his alone.** Two pixels of splayed leg, or two pairs of
    them, is a floor dot; eight pixels of ink is ground.
    """
    bar = [row for row in SP.PLAYER[-2:]]
    assert all(longest_run(row) >= 5 for row in bar), \
        "the player's bar is narrower than the floor's own dot spacing"
    assert SP.PLAYER[-3] == 0x00, "no clear row, so the bar reads as feet"
    for name in SP.PEOPLE:
        if name == "player":
            continue
        # A 16-wide row is two bytes and either of them could hold a run, so
        # the rows are flattened rather than assumed to be single bytes.
        rows = [SP.row_bytes(row) for row in SP.SPRITES[name][-2:]]
        assert not any(rows[-1]), \
            f"{name} draws on the last row, which is the player's alone"
        assert max(longest_run(b) for row in rows for b in row) < 5, \
            f"{name} has a mark of its own where the player's bar is"


def test_the_lamp_is_the_mark_that_needs_no_floor():
    """The second mark, and **why two are needed rather than one.**

    The bar only works where there is floor to be ground against. On a wall
    cell, in a doorway and on the sprite sheet there is none -- and there is no
    stipple to compete with either, so four pixels is enough there. The lamp is
    the only ink any figure in this game has above the top of everybody else's
    head, which is where a glow finds a figure first.

    It is centred, so it says nothing about facing, and symmetric, because a
    lamp in one hand would have quietly cost the BODY the only tell it had at
    the time. That tell is no longer the one doing the work -- the aspect ratio
    is -- and the lamp stays symmetric anyway: a property bought once should
    not be given away later by accident.

    **The clause is about figures on their feet.** A body has no head at the
    top of its box, because it is not upright, and the arm flung back over its
    head is the first row of that box on purpose.
    """
    assert SP.PLAYER[1] == SP.PLAYER[2] == 0x3C, "the lamp is not four centred"
    for name in SP.STANDING:
        if name == "player":
            continue
        assert SP.SPRITES[name][:2] == (0x00, 0x00), \
            f"{name} has ink in the rows the player's lamp has to itself"
    mirrored = sum(1 << (7 - i) for i in range(8) if SP.PLAYER[1] & (1 << i))
    assert mirrored == SP.PLAYER[1], "the lamp is not symmetric"


# --- the pins: delete a mark and this file has to notice --------------------

def without_rows(sprite, rows) -> tuple:
    """The same figure with those rows blanked. For pinning, not for drawing."""
    return tuple(0 if i in rows else row for i, row in enumerate(sprite))


def test_deleting_the_bar_fails_the_contract():
    """**The pin.** A test of this kind is only worth having if it is awake.

    The bar is what the player is told by on lit floor, and taking it off is
    exactly the drawing the first-timer called a coin flip. Note *which* clause
    catches it: assertions 1 to 3 still pass without the bar, because the lamp
    carries them -- which is the whole reason the five-pixel clause had to be
    written down as well.
    """
    stripped = without_rows(SP.PLAYER, {14, 15})
    assert not all(longest_run(row) >= 5 for row in stripped[-2:]), \
        "the five-pixel clause did not notice the bar being deleted"


def test_deleting_the_lamp_fails_the_contract():
    """**The other pin.** Take the lamp off and the player has no mark at all
    on a wall cell, in a doorway or on the sheet, where the bar has no ground
    to sit on.

    Again the clause that catches it is named rather than assumed: with the
    lamp gone the player is no longer the only figure drawing above everybody
    else's head, and rows 0-2 of the box go empty.
    """
    stripped = without_rows(SP.PLAYER, {1, 2})
    assert stripped[:2] != SP.PLAYER[:2]
    assert stripped[1] == 0x00 and stripped[2] == 0x00, \
        "the lamp clause did not notice the lamp being deleted"
    assert topmost(stripped) > topmost(SP.PLAYER), \
        "the player still draws where the lamp was"
