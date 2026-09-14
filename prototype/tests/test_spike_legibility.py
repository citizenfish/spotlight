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

Five assertions, over every pair of the four figures and over the door pair --
and since issue #60, **over every frame of one figure against every frame of
another**. Since issue #72 that is three unique frames for each of the two
walkers and two for the waiting worker: three pairs of figures and
**twenty-one pairs of frames**, because a player mid-stride stands beside a
follower on the other stride as often as not, and a waving worker beside
either. The lamp is pinned on all three of the player's frames, because a
stride that took it off would be a stride that made him somebody else for four
pixels in sixteen. Since issue #78 the figures are drawn from directly above
-- a compact mass of head and shoulders in the middle of the box with the
limbs coming out from under it -- and the projection changed, the frames and
the pairs did not. What did change is where a figure *starts*: not row 0 any
more, so assertion 3 reads the first three drawn rows rather than rows 0-2.

1. Some row differs by **at least three pixels** -- the measured failure was
   two.
2. The difference is **not confined to columns 0, 1, 6 and 7** -- width alone
   is not a silhouette.
3. The **topmost drawn row** differs, or the ink in the first three drawn
   rows -- from the higher of the two topmost rows -- differs by at least
   three pixels: the top of a figure is what you see first in a glow. (Rows
   0-2, until issue #78 moved the figures off row 0.)
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

**The player has one mark now, the lamp, and the contract is the whole guard**
(issue #72, kept by #78). From issue #49 to issue #72 he wore two: the lamp,
and a solid bar in the bottom two rows of his box, because the first plan-view
figure eight pixels wide had nothing in its middle columns to tell it from a
follower on lit floor, and the bar's *five unbroken pixels* clause was written
here to keep the bar honest against a stipple with a dot every four pixels.
From directly above, as redrawn for #78, the helmet disc six wide and the
full-width kit tell him from a follower's head disc and six-wide shoulders
where the eye is: the contract passes every frame of him against every frame
of the other two without the bar and -- pinned below -- without the lamp too,
and **the bar and its clause are removed, not kept and skipped.** Assertion
4's five-pixel rule still governs marks meant as marks, which is now the lamp
alone, and the lamp is exempt from it as it always was: it is two pixels wide
on purpose -- the front of a helmet seen from above -- and where it has to
work there is a six-wide helmet under it and no stipple to compete with.

**A scoping note, without which a literal reading condemns art the design
asks for.** **Assertion 4 is applied to the door pair and not to the lamp
pair.** `LAMP_OFF` and `LAMP_ON` share a silhouette on purpose, and the
exemption has a reason rather than being an oversight: **a burning lamp sits
inside the pool of light it is making**, and that pool is a far larger cue than
the eight bytes in the middle of it. It is the only state pair in the game with
a second channel of its own. If a session ever reports a spare being mistaken
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

#: The player's lamp: two centred pixels at the front of his helmet, which
#: seen from directly above (issue #78) is row 4 of his box, the row above the
#: helmet disc.
LAMP = 0x18
LAMP_ROW = 4
#: The lamp and the pixel each side of it: what the lamp's row has to be in
#: the middle four columns for the lamp to read as a thing on the helmet.
LAMP_CLEAR = 0x3C


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
    top = topmost(a)
    return sum(bits(x ^ y) for x, y in zip(a[top:top + 3], b[top:top + 3])) >= 3


def aspect(sprite) -> tuple:
    """A drawing's box: how wide and how tall, in pixels."""
    return SP.width_of(sprite), len(sprite)


#: Every frame of every standing figure, by its sheet name: `player_n`,
#: `worker_w`, and so on. The contract compares frames, not figures.
FRAMES = SP.FRAMES


def figure_of(frame_name: str) -> str:
    """`player_a` -> `player`, `worker_w` -> `worker`, `worker` -> `worker`:
    which figure a frame belongs to."""
    return frame_name.rsplit("_", 1)[0]


def pairs(frames=None):
    """Every pair of frames that shares a box and means a different person.

    **Every frame of one figure against every frame of another** (issue #60):
    twenty-one comparisons since issue #72, and never a figure against its own
    other frame, because a stride -- or the worker's wave -- is meant to look
    like the same person. The three on their feet. **A body is not compared
    this way since issue #59** and could not be: assertions 1 to 3 read one
    byte against another, and there is no meaningful pairing of a 16x8 row
    with an 8x16 one. It is covered by assertion 5, which is a stronger claim
    than any of them -- differing in the box is the largest difference two
    drawings can have.

    `frames` is the table to pair up, the real one by default; the pins below
    pass a doctored copy.
    """
    frames = FRAMES if frames is None else frames
    for one, two in combinations(frames, 2):
        if figure_of(one) == figure_of(two):
            continue
        yield one, two, frames[one], frames[two]


def failures(a, b) -> list:
    """Which of assertions 1 to 3 a pair fails, by number."""
    return [n for n, check in enumerate(
        (assertion_1, assertion_2, assertion_3), start=1) if not check(a, b)]


def test_the_contract_runs_over_twenty_one_frame_pairs():
    """Said as a number, so that a frame dropped from the table -- or the
    contract quietly comparing figures rather than frames again -- fails with
    a count rather than passing on whatever was left. Three of the player,
    three of the follower, two of the worker: 3x3 + 3x2 + 3x2."""
    assert len(FRAMES) == 8
    assert {figure_of(name) for name in FRAMES} == {"player", "worker",
                                                    "follower"}
    assert sum(1 for _ in pairs()) == 21


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
    already looking. It is the assertion that moved the waiting worker's hands
    in from the edge columns before the elevation figures were built, and
    they stayed inboard when the figures went back to plan view (issue #78).
    """
    for one, two, a, b in pairs():
        assert assertion_2(a, b), \
            f"{one} and {two} differ only at the edges of their column"


def test_every_pair_of_figures_differs_where_the_eye_lands_first():
    """Assertion 3. **The top of a figure is what you see first in a glow.**

    Either the topmost drawn row differs -- one figure starts higher than the
    other -- or there are three pixels of difference in the first three drawn
    rows.
    The player passes against the follower on the first clause because of his
    lamp, and against the worker on the second, because the lamp and the
    raised hands are different shapes on the same rows; the worker calling
    passes against the follower on the first clause and waving on the second.
    """
    for one, two, a, b in pairs():
        assert assertion_3(a, b), \
            f"{one} and {two} look the same at the top, where a glow finds them"


def test_all_twenty_one_pairs_pass_all_three():
    """Said once as a whole, because the contract is the conjunction.

    A drawing that satisfied two assertions out of three would still be the
    fault this exists to prevent, and reading three separate failures is not
    the same as being told the pair is illegible.
    """
    for one, two, a, b in pairs():
        failed = failures(a, b)
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
        assert one in FRAMES and two in FRAMES, (
            f"{one} and {two} share a box and mean different things, so the "
            f"only thing left to tell them apart is what is drawn in it")
        if figure_of(one) == figure_of(two):
            continue                    # the same person, mid-stride
        assert all(check(a, b) for check in
                   (assertion_1, assertion_2, assertion_3))


def test_the_dead_and_the_living_never_share_a_box():
    """Said as its own line, because it is the whole of the 2026-09-11 ruling.

    *Size says whether a thing is a person* still stands. *Pose says whether it
    is alive* is withdrawn, and **orientation says whether it is upright** in
    its place. The elevation redraw (issue #72) does not touch it: the body
    is untouched, 16x8, and every standing frame is 8x16.
    """
    for name, frame in FRAMES.items():
        assert aspect(frame) == (8, 16), f"{name} left the 8x16 box"
        assert aspect(frame) != aspect(SP.BODY), \
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
    for name, other in FRAMES.items():
        assert len(OLD_BODY) == len(other)
        failed = failures(OLD_BODY, other)
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


def test_the_worker_pair_differs_in_outline_and_not_in_fill():
    """Assertion 4 on the one state pair issue #72 added: calling and
    waving are the same person with the hands in different places, so the
    silhouette changes and nothing inside it does. A wave that only filled or
    emptied the trunk would be the door fault again."""
    assert outline(SP.WORKER) != outline(SP.WORKER_W)
    still = [row for row in SP.WORKER[6:]]
    assert still == list(SP.WORKER_W[6:]), \
        "the wave changed something below the shoulders"


# --- the player's mark: the lamp, and only the lamp ------------------------

def test_the_lamp_is_the_players_mark_and_no_figure_shares_its_middle():
    """**One mark, where a glow finds a figure first.**

    The lamp is four centred pixels on the top two rows of his box. It is
    symmetric, so it says nothing about facing; it is an object rather than
    anatomy, so it does not make a figure read as a face. And it is what
    identifies him against every ground, because since issue #72 there is no
    bar: the contract below is what says the helmet and the kit do the rest.

    **The clause is about the lamp's two columns on its row** (issue #78:
    the front of the helmet, seen from directly above, is the lamp's row 4).
    No other figure has ink in those two columns on that row in any frame --
    the follower's row 4 is clear across the middle, the waiting worker's
    raised hands are either side of it -- and the columns beside the lamp
    are clear in every player frame, so the lamp is a thing on the helmet
    and not a wider helmet. A stride swings an arm up past the lamp's row
    at the edge of the column and leaves the lamp alone.
    """
    for frame in SP.STANDING["player"]:
        assert frame[LAMP_ROW] & LAMP_CLEAR == LAMP, \
            "the lamp is not two centred pixels with a clear pixel each side"
    for name, frame in FRAMES.items():
        if figure_of(name) == "player":
            continue
        assert not (frame[LAMP_ROW] & LAMP), \
            f"{name} has ink where the player's lamp is"
    for frame in SP.STANDING["follower"]:
        assert not (frame[LAMP_ROW] & LAMP), \
            "the follower has something at the front of its head"


def test_the_lamp_is_exempt_from_the_five_pixel_clause_on_purpose():
    """Assertion 4's five-pixel rule -- nothing narrower than five pixels of
    solid ink is a mark on lit floor, whose stipple puts a dot every four --
    governed the bar and now governs marks meant as marks, which is the lamp
    alone; and the lamp is exempt as it always was. Four pixels is deliberate:
    where the lamp has to work there is no stipple to pool with, and it sits
    over a helmet that is six wide and never at the level of the floor."""
    assert longest_run(LAMP) == 2
    for frame in SP.STANDING["player"]:
        assert longest_run(frame[LAMP_ROW + 1]) >= 5, \
            "nothing under the lamp to sit on"


# --- the pins: take the body away and this file has to notice ---------------

def without_rows(sprite, rows) -> tuple:
    """The same figure with those rows blanked. For pinning, not for drawing."""
    return tuple(0 if i in rows else row for i, row in enumerate(sprite))


def test_the_player_is_a_different_body_and_not_a_different_hat():
    """**The pin.** A test of this kind is only worth having if it is awake.

    Item 1 of issue #31 asked that the player be told from a follower by *a
    different body, not a different hat*, and from directly above (issue
    #78) he is: take the lamp off and the contract still passes every frame
    of him against every frame of the other two, because a helmet disc six
    wide between shoulders eight wide is not a head disc four wide between
    shoulders six wide. Then give him the follower's head and shoulders as
    well -- rows 5 to 7, the mass that never moves -- and standing still he
    fails assertion 3 against the follower standing still: both start on
    the same row and the first three drawn rows are the same. Mid-stride
    his arms still start higher than a follower's, because his shoulders
    are wider and his arm comes from further out, so the strides are told
    by the limbs and the standing figure by the mass, and the contract
    itself catches the mass being taken away; there is no separate mark
    clause left to catch it instead. In elevation (issue #72) the lamp was
    load-bearing and this test pinned that; the body carries him now.
    """
    hatless = dict(FRAMES)
    for name in ("player_n", "player_a", "player_b"):
        rows = list(FRAMES[name])
        rows[LAMP_ROW] &= ~LAMP
        hatless[name] = tuple(rows)
    assert topmost(hatless["player_n"]) > topmost(FRAMES["player_n"])
    assert not any(failures(a, b) for _one, _two, a, b in pairs(hatless)), \
        "the lamp is load-bearing: the player is a hat"
    bodiless = dict(hatless)
    for name, tail in (("player_n", "follower_n"), ("player_a", "follower_a"),
                       ("player_b", "follower_b")):
        bodiless[name] = hatless[name][:5] + FRAMES[tail][5:8] + hatless[name][8:]
    failed = [(one, two, failures(a, b)) for one, two, a, b in pairs(bodiless)
              if failures(a, b)]
    assert failed, "the contract did not notice the body being taken away"
    assert ("player_n", "follower_n", [3]) in failed, failed
    assert {(figure_of(two), tuple(f)) for _one, two, f in failed} \
        == {("follower", (3,))}, failed


def test_the_bar_is_gone_and_would_not_be_missed_by_the_contract():
    """**Recorded so the bar is not put back for the wrong reason.** The
    bottom rows of every figure's box are clear; no frame has a run of five
    pixels there. And the contract is green -- every one of the twenty-one
    pairs -- which is the evidence that the overhead figure needs no second
    mark now that its helmet and kit are wider than a follower's head and
    shoulders (issue #78; the first plan-view figure, #49, had neither). If a
    session loses him against a follower on lit floor, reopen the vault note
    before reaching for the bar: the fix is the helmet, not the ground.
    """
    for name, frame in FRAMES.items():
        assert frame[-1] == 0, f"{name} draws on the last row of its box"
        assert max(longest_run(row) for row in frame[-2:]) < 5, \
            f"{name} has a bar under its feet"
    assert not any(failures(a, b) for _one, _two, a, b in pairs())
