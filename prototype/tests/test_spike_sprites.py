"""Sprites: pixel positioning, and never touching an attribute."""

from spikes import bots, floor, lighting as L, sprites as SP
from spikes.layout import PLAY_ROWS, STRIP_TOP
from spikes.session import Session
from spotlight.core.constants import CELL, COLS, SCREEN_W, YELLOW
from spotlight.core.screen import Screen


def octets(sprite) -> list:
    """Every byte of a sprite, in order, whatever its width.

    An 8-wide row is a bare byte and a 16-wide row is a pair of them, so a test
    that walks the ink needs one call to stop caring which it has. **Written
    because the alternative is silent**: `any(sprite)` is true of a blank
    16-wide sprite, since every row of it is a non-empty tuple, and a test that
    cannot fail is worse than no test.
    """
    return [b for row in sprite for b in SP.row_bytes(row)]


def _lit_left_half(boundary_cx: int, left=(L.LIT, L.CHARGE_LIT),
                   right=(L.DIM, L.CHARGE_DIM)) -> L.LightField:
    """A field split down a cell column, so sprites can straddle a boundary.

    Each half is a (level, memory) pair, as a source gives them.
    """
    f = L.LightField()
    f.begin()
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            f.add(cx, cy, *(left if cx < boundary_cx else right))
    f.commit()
    return f


# --- the colour rule -------------------------------------------------------

def test_drawing_never_writes_an_attribute():
    """The whole clash guarantee rests on this."""
    s = Screen()
    before = bytes(s.attrs)
    for name, sprite in SP.SPRITES.items():
        for x, y in ((0, 0), (3, 5), (100, 60), (250, 180), (-2, -2)):
            SP.draw(s, sprite, x, y)
    assert bytes(s.attrs) == before, "sprite drawing touched the attribute grid"


def test_a_sprite_straddling_a_light_boundary_is_two_toned():
    """Half bright, half dim -- each cell keeping its own colour."""
    s = Screen()
    field = _lit_left_half(boundary_cx=10)
    field.paint(s, YELLOW)
    attrs_before = bytes(s.attrs)

    # x=76 puts the sprite across the boundary at cell column 10 (x=80).
    SP.draw(s, SP.PLAYER_A, 76, 40)

    assert bytes(s.attrs) == attrs_before, "drawing changed colours"
    assert s.get_attr(9, 5) == L.attr_for(L.LIT, YELLOW)
    assert s.get_attr(10, 5) == L.attr_for(L.DIM, YELLOW)
    # And it really is spanning both columns.
    spanned = SP.cells_spanned(76, 40, len(SP.PLAYER_A))
    assert {(9, 5), (10, 5)} <= spanned


def test_a_sprite_in_a_dark_cell_is_swallowed_not_recoloured():
    """DARK is black ink on black paper, so pixels there simply do not show."""
    s = Screen()
    field = L.LightField()          # nothing lit at all
    field.paint(s, YELLOW)
    SP.draw(s, SP.CLEG_A, 40, 40)
    ink, paper, _, _ = __import__(
        "spotlight.core.screen", fromlist=["unpack_attr"]
    ).unpack_attr(s.get_attr(5, 5))
    assert ink == paper, "an unlit cell must render its pixels invisible"


# --- pixel positioning -----------------------------------------------------

def test_sprites_position_by_pixel_not_by_cell():
    a, b = Screen(), Screen()
    SP.draw(a, SP.CLEG_A, 40, 40)
    SP.draw(b, SP.CLEG_A, 43, 40)
    assert bytes(a.pixels) != bytes(b.pixels)


def test_an_8x8_sprite_can_span_four_cells():
    spanned = SP.cells_spanned(43, 45, 8)
    assert len(spanned) == 4, spanned


def test_a_cell_aligned_sprite_spans_the_minimum():
    assert len(SP.cells_spanned(40, 40, 8)) == 1
    assert len(SP.cells_spanned(40, 40, 16)) == 2


def test_a_person_spans_more_rows_than_a_cleg():
    assert len(SP.cells_spanned(40, 40, len(SP.PLAYER_A))) == 2
    assert len(SP.cells_spanned(40, 40, len(SP.CLEG_A))) == 1


# --- clipping --------------------------------------------------------------

def test_sprites_are_clipped_at_the_screen_edges():
    for x, y in ((-6, 40), (SCREEN_W - 2, 40), (40, -6)):
        s = Screen()
        SP.draw(s, SP.PLAYER_A, x, y)        # must not raise or wrap
        for py in range(0, 8):
            row = s.pixels[py * SCREEN_W:(py + 1) * SCREEN_W]
            assert len(row) == SCREEN_W


def test_a_sprite_does_not_wrap_around_the_right_edge():
    s = Screen()
    SP.draw(s, SP.CLEG_A, SCREEN_W - 3, 40)
    for py in range(40, 48):
        assert not s.point(0, py), "sprite wrapped onto the left edge"


def test_sprites_cannot_be_drawn_into_the_status_strip():
    s = Screen()
    SP.draw(s, SP.PLAYER_A, 40, PLAY_ROWS * CELL - 4)
    for py in range(STRIP_TOP * CELL, 192):
        for px in range(SCREEN_W):
            assert not s.point(px, py), "a sprite leaked into the strip"


# --- compositing -----------------------------------------------------------

def test_sprites_touch_nothing_outside_their_mask():
    """A sprite composites over the room; it does not punch a box-shaped hole
    in it. Since issue #70 it clears its halo, and the halo is inside the box,
    so the pixel diagonally outside the corner of the box is untouched -- as
    is every pixel of the box its mask does not name."""
    s = Screen()
    s.fill_cell_pixels(5, 5, on=True)
    s.fill_cell_pixels(6, 5, on=True)
    s.fill_cell_pixels(5, 6, on=True)
    s.fill_cell_pixels(6, 6, on=True)
    SP.draw(s, SP.CLEG_A, 41, 41)
    assert s.point(40, 40), "a pixel outside the box was cleared"
    mask = SP.MASK_OF[SP.CLEG_A]
    for dy in range(8):
        for dx in range(8):
            if not mask[dy] & (0x80 >> dx):
                assert s.point(41 + dx, 41 + dy), \
                    f"({dx}, {dy}) is outside the mask and was cleared"


# --- the halo mask (issue #70) ----------------------------------------------

def _stipple(screen, cells) -> None:
    """Lit floor under a test, drawn with the game's own stipple."""
    for cx, cy in cells:
        for dy, bits in enumerate(floor.STIPPLE_LIT):
            for dx in range(CELL):
                if bits & (0x80 >> dx):
                    screen.plot(cx * CELL + dx, cy * CELL + dy)


def _ink_pixels(sprite) -> set:
    return {(dx + 8 * octet, dy)
            for dy, row in enumerate(sprite)
            for octet, bits in enumerate(SP.row_bytes(row))
            for dx in range(8) if bits & (0x80 >> dx)}


def test_every_sprite_has_a_mask_the_size_of_its_own_box():
    """The size table gains the masks and is not weakened by them: a mask is
    the same width and height as the sprite it belongs to, and every sprite
    the game draws has one."""
    for name, sprite in SP.SPRITES.items():
        mask = SP.MASK_OF.get(sprite)
        assert mask is not None, f"{name} has no mask"
        assert len(mask) == len(sprite), name
        assert SP.width_of(mask) == SP.width_of(sprite), name


def test_a_sprite_on_lit_stipple_leaves_no_dot_within_a_pixel_of_its_ink():
    """**The thing that was wrong before.** On lit floor a figure was made of
    the stipple it stood on: every dot inside its box survived and the ink
    joined up with it. Now, inside the box, every pixel within one of the ink
    -- the eight neighbours -- is clear; the ink is set; and a dot further
    from the ink than that is still there, because the mask is a halo and
    not a box."""
    for name, sprite in SP.SPRITES.items():
        s = Screen()
        x, y = 8 * CELL, 4 * CELL
        _stipple(s, SP.cells_spanned(x, y, len(sprite), SP.width_of(sprite)))
        SP.draw(s, sprite, x, y)
        ink = _ink_pixels(sprite)
        w, h = SP.width_of(sprite), len(sprite)
        for dy in range(h):
            for dx in range(w):
                near = any((dx + ex, dy + ey) in ink
                           for ex in (-1, 0, 1) for ey in (-1, 0, 1))
                want = (dx, dy) in ink
                if near:
                    assert s.point(x + dx, y + dy) == want, \
                        f"{name}: ({dx}, {dy}) is {'ink' if want else 'halo'}"
        # And the halo is a halo: at least one stipple dot in the box is out
        # of its reach and survives, for every sprite whose box has room.
        outside = {(dx, dy) for dy in range(h) for dx in range(w)
                   if not any((dx + ex, dy + ey) in ink
                              for ex in (-1, 0, 1) for ey in (-1, 0, 1))}
        dots = {(dx, dy) for dx, dy in outside
                if floor.STIPPLE_LIT[dy % CELL] & (0x80 >> (dx % CELL))}
        for dx, dy in dots:
            assert s.point(x + dx, y + dy), f"{name}: a dot at ({dx}, {dy}) " \
                f"outside the halo was cleared"


def test_a_half_visible_sprite_clears_nothing_in_its_invisible_half():
    """**What a coder gets wrong**, from the vault: the mask is under the
    `visible` test exactly as the ink is. A worker straddling the edge of a
    beam is drawn in the lit column and *not cleared* in the dark one; a
    hole punched in the dark half would show, by the hole, where they were."""
    s = Screen()
    x, y = 10 * CELL + 4, 5 * CELL        # straddling columns 10 and 11
    _stipple(s, [(10, 5), (11, 5), (10, 6), (11, 6)])
    before = bytes(s.pixels)
    SP.draw(s, SP.WORKER_A, x, y, visible=lambda cx, cy: cx == 10)
    for py in range(y, y + 16):
        for px in range(11 * CELL, 12 * CELL):
            assert s.pixels[py * SCREEN_W + px] == before[py * SCREEN_W + px], \
                f"({px}, {py}) in the dark column was touched"
    # And the lit column really was masked: a dot next to the ink is gone.
    ink = _ink_pixels(SP.WORKER_A)
    cleared = [(dx, dy) for dy in range(16) for dx in range(4)
               if (dx, dy) not in ink
               and any((dx + ex, dy + ey) in ink
                       for ex in (-1, 0, 1) for ey in (-1, 0, 1))
               and floor.STIPPLE_LIT[(y + dy) % CELL] & (0x80 >> ((x + dx) % CELL))]
    assert cleared, "no dot to clear in the lit half; the test proves nothing"
    assert not any(s.point(x + dx, y + dy) for dx, dy in cleared)


def test_a_fly_over_a_person_clears_a_ring_and_the_person_drawn_after_restores_it():
    """The Knight Lore look, and the vault calls it correct: a fly landing on
    somebody takes a ring of them with its halo. Drawn the other way round the
    person's halo takes the ring off the fly. Whoever is drawn last wins, and
    nothing is lost -- the person's ink comes back whole.

    **The ring stops at the fly's box.** The fly's legs are on its bottom row,
    so the person's pixels on the row under the fly are within one pixel of
    its ink and are *not* cleared -- the mask is clipped to the box, and the
    first draft of this test forgot that and failed on exactly those pixels.
    A halo that reached out of the box would be the third byte per row the
    port refused, so the pin says so."""
    s = Screen()
    x, y = 12 * CELL, 6 * CELL
    fly_at = 4
    SP.draw(s, SP.WORKER_A, x, y)
    person = bytes(s.pixels)
    SP.draw(s, SP.CLEG_A, x, y + fly_at)
    fly_ink = {(dx, dy + fly_at) for dx, dy in _ink_pixels(SP.CLEG_A)}
    near_fly = {(dx, dy) for dx, dy in _ink_pixels(SP.WORKER_A)
                if (dx, dy) not in fly_ink
                and any((dx + ex, dy + ey) in fly_ink
                        for ex in (-1, 0, 1) for ey in (-1, 0, 1))}
    in_box = {(dx, dy) for dx, dy in near_fly if fly_at <= dy < fly_at + 8}
    under = near_fly - in_box
    assert in_box, "the fly does not overlap the person; the test proves nothing"
    assert under, "no person pixel under the fly's box; the clip is untested"
    assert not any(s.point(x + dx, y + dy) for dx, dy in in_box), \
        "the fly's halo did not clear the person around it"
    assert all(s.point(x + dx, y + dy) for dx, dy in under), \
        "the fly's halo reached outside its box"
    assert bytes(s.pixels) != person, "the fly was never drawn"
    SP.draw(s, SP.WORKER_A, x, y)
    for dx, dy in _ink_pixels(SP.WORKER_A):
        assert s.point(x + dx, y + dy), f"the person's ink at ({dx}, {dy}) " \
            f"did not come back"
    # And whatever the fly left inside the person's mask is gone with it: a
    # person drawn over a fly is the person, whole, and the fly's ink shows
    # only where the person's halo does not reach.
    for dx, dy in fly_ink:
        if SP.MASK_OF[SP.WORKER_A][dy] & (0x80 >> dx):
            assert s.point(x + dx, y + dy) == ((dx, dy) in _ink_pixels(SP.WORKER_A))


def test_columns_governs_the_mask_as_it_governs_the_ink():
    """A body in a one-cell gap is its head end alone: the second byte of the
    mask is not drawn any more than the second byte of the ink is."""
    s = Screen()
    _stipple(s, [(5, 9), (6, 9)])
    before = bytes(s.pixels)
    SP.draw(s, SP.BODY, 5 * CELL, 9 * CELL, columns=1)
    for py in range(9 * CELL, 10 * CELL):
        for px in range(6 * CELL, 7 * CELL):
            assert s.pixels[py * SCREEN_W + px] == before[py * SCREEN_W + px]


def test_an_explicit_empty_mask_draws_by_or_and_none_looks_the_sprites_own_up():
    a, b, c = Screen(), Screen(), Screen()
    for screen in (a, b, c):
        _stipple(screen, [(5, 5)])
    SP.draw(a, SP.CLEG_A, 5 * CELL, 5 * CELL, mask=())
    SP.draw(b, SP.CLEG_A, 5 * CELL, 5 * CELL)
    SP.draw(c, SP.CLEG_A, 5 * CELL, 5 * CELL, mask=SP.MASK_OF[SP.CLEG_A])
    assert bytes(b.pixels) == bytes(c.pixels)
    assert bytes(a.pixels) != bytes(b.pixels), "the mask did nothing"
    # By OR: every stipple dot in the cell survives under the unmasked one.
    for dy, bits in enumerate(floor.STIPPLE_LIT):
        for dx in range(CELL):
            if bits & (0x80 >> dx):
                assert a.point(5 * CELL + dx, 5 * CELL + dy)


def _run_drawn(seed: int, frames: int, masked: bool, monkeypatch):
    """A listener run, drawn every frame, with the masks as built or with
    every sprite's mask taken away -- which is what the commit before did.
    Returns the run, a hash of every frame's pixels, and the attribute grid
    at the end."""
    if not masked:
        monkeypatch.setattr(SP, "MASK_OF", {})
    run = Session(seed=seed, metrics=True)
    screen = Screen()
    bot = bots.make("listener", seed=seed, light=True)
    frames_seen = []
    for _ in range(frames):
        run.step(bot.intent(run))
        if run.over is not None:
            break
        run.draw(screen)
        frames_seen.append(hash(bytes(screen.pixels)))
    return run, frames_seen, bytes(screen.attrs)


def test_the_mask_is_drawing_state_and_the_log_cannot_see_it(monkeypatch):
    """**The pin for the acceptance criterion**, in the shape issue #60 used
    for the walk. The same seed and bot, drawn every frame with the masks and
    without them: the event log, the positions, the blood and the repaint
    figures are identical -- the counter prices cells changing light level
    and a mask clears pixels in cells the sprite was already dirtying -- and
    the two screens differ, which is the masks having been there at all."""
    with_masks, drawn, drawn_attrs = _run_drawn(7, 1500, True, monkeypatch)
    without, plain, plain_attrs = _run_drawn(7, 1500, False, monkeypatch)
    assert with_masks.over is None and without.over is None
    assert [(e.frame, e.kind, e.who, e.count, e.room) for e in with_masks.log] \
        == [(e.frame, e.kind, e.who, e.count, e.room) for e in without.log]
    assert with_masks.log, "the runs did nothing worth logging"
    assert (with_masks.player.x, with_masks.player.y) == \
        (without.player.x, without.player.y)
    assert with_masks.blood == without.blood
    assert with_masks.repaint.stats() == without.repaint.stats()
    assert drawn != plain, "the masks changed nothing on screen, all run"
    assert drawn_attrs == plain_attrs, "a mask touched an attribute"


# --- silhouettes -----------------------------------------------------------

def test_the_living_are_8x16_the_dead_are_16x8_and_objects_are_8x8():
    """Size says whether a thing is a person; **orientation says whether it is
    upright** (issue #59).

    It used to read "people are 8x16 whether or not they are alive, and pose
    says which". That was half right and the wrong half was load-bearing: a
    lying figure in an 8-wide box is exactly as long as a standing figure is
    wide, so the box could not say a person was down and pose had to -- and
    pose is a sprite-sheet property. A cold reader called a corpse the person
    they were hunting and the player a bystander, in two different rooms in one
    session.

    **A door is the one 8x16 thing that is not a person** (issue #49), because
    it is the person-shaped hole you walk out through. It is never confused
    with one: it does not move, and it stands in a wall.

    **Six 8x16 people blocks since issue #60** -- three figures, two walk
    frames each -- and the count is asserted rather than left to the loop, so
    that a frame going missing from the table, or a third frame arriving
    without a ruling, is a failure with a number in it. The size table is not
    weakened by the walk: a frame is the same 8x16 box as the figure.
    """
    standing = [name for name in SP.SPRITES
                if name.rsplit("_", 1)[0] in SP.STANDING]
    assert len(standing) == 6, standing
    assert all(len(frames) == 2 for frames in SP.STANDING.values())
    for name in standing:
        sprite = SP.SPRITES[name]
        assert (SP.width_of(sprite), len(sprite)) == (8, 16), name
    body = SP.SPRITES["body"]
    assert (SP.width_of(body), len(body)) == (SP.WIDE, 8) == (16, 8), \
        "a body is not laid down across two cells"
    for name in SP.DOORS:
        assert (SP.width_of(SP.SPRITES[name]), len(SP.SPRITES[name])) \
            == (8, 16), name
    objects = set(SP.SPRITES) - set(SP.PEOPLE) - set(SP.DOORS)
    assert objects, "every sprite became a person or a door"
    for name in objects:
        assert (SP.width_of(SP.SPRITES[name]),
                len(SP.SPRITES[name])) == (8, 8), name


def test_the_body_is_the_only_drawable_wider_than_it_is_tall():
    """**That is the whole of the tell**, so it is worth one line of its own.

    A second wide drawable would not break anything by itself, but it would
    mean the aspect ratio had stopped saying *this person is lying on the
    floor* -- which is the property the redraw of 2026-09-11 bought and the
    only thing standing between a corpse and the person you are looking for.
    """
    wide = [name for name, sprite in SP.SPRITES.items()
            if SP.width_of(sprite) > len(sprite)]
    assert wide == ["body"], f"something else is wider than it is tall: {wide}"


def test_every_silhouette_is_distinct():
    """Colour carries no information, so shape has to."""
    seen = {}
    for name, sprite in SP.SPRITES.items():
        key = (SP.width_of(sprite), tuple(sprite))
        assert key not in seen, f"{name} is identical to {seen.get(key)}"
        seen[key] = name


# --- drawn from above (issue #31) ------------------------------------------

def _edges(sprite):
    """Which rows of a figure touch both edges of its 8-pixel column."""
    return [i for i, row in enumerate(sprite) if row & 0x80 and row & 0x01]


def test_which_figure_is_yours_is_a_body_and_not_a_hat():
    """The old pair differed at the helmet, which is one row of eight pixels.

    They are near-inverses now: the player is empty at the top edges and full
    at the shoulders, a waiting worker the other way round. That is the whole
    of item 1 of issue #31 -- *a different body, not a different hat*.
    """
    for player_frame in SP.PLAYER_FRAMES:
        for worker_frame in SP.WORKER_FRAMES:
            player, worker = _edges(player_frame), _edges(worker_frame)
            assert player and worker
            # The worker's width is all above the head; the player's is all
            # shoulders and below. They overlap on one row and are opposite
            # everywhere else.
            assert min(worker) < min(player) and max(worker) < max(player)
            assert len(set(worker) & set(player)) <= 1
            assert sum(1 for a, b in zip(player_frame, worker_frame)
                       if a != b) >= 8


#: The lamp's columns: the middle four of the eight. Row 1 and row 2 of the
#: player's box are `..####..`, and this is the mask that says so.
LAMP_COLUMNS = 0x3C


def test_only_the_player_has_anything_over_the_crown_and_it_is_his_lamp():
    """Seen from above a head is the topmost thing and there is no hat on it.

    **The player is the one exception and it is deliberate** (issue #49). The
    rule exists so that no hat, brim, hair or face makes a figure read as
    front-facing; a centred block on a helmet reads as a fitting rather than a
    face, and **it is an object rather than anatomy**. It is what identifies
    him where there is no floor under his feet to draw his bar on -- on a wall
    cell, in a doorway, and on the sprite sheet.

    **Narrowed by the plan-view redraw** (issue #60), and the narrowing is
    worth stating because the wider claim was in this docstring: it used to
    say the rest keep two blank rows. The waiting worker's raised hands are now
    two blobs at the *edges* of rows 1 and 2 -- from above, a raised arm is a
    hand beside the crown and nothing else -- so those rows are no longer the
    lamp's alone. What is exactly true, and what identifies him, is narrower:
    **the top of the lamp -- row 1, in the four middle columns -- is ink no
    other figure has in any frame**, and the top row of every box is empty.
    The follower's crown starts on row 2, under the lamp's second row and
    inside its columns, which is why the claim is about row 1 and not rows
    1-2; the player's `..####..` and the worker's `##....##` are inverses on
    both rows, which is a larger difference than a blank row would have been.

    **It is a rule about figures on their feet**, so the body is not in it
    (issue #59). A figure lying down has no head at the top of its box -- its
    head is at one end of a row -- and the rule exists to stop a hat, a brim or
    a face making a standing figure read as front-facing. A corpse is in no
    danger of reading as front-facing, and the arm flung back over its head is
    the first row of its box on purpose.
    """
    for name, frames in SP.STANDING.items():
        if name == "player":
            continue
        for frame in frames:
            assert frame[0] == 0x00, f"{name} draws on the top row of its box"
            assert not any(row & LAMP_COLUMNS for row in frame[:2]), \
                f"{name} has ink where the top of the player's lamp is"
    for frame in SP.FOLLOWER_FRAMES:
        assert frame[:2] == (0x00, 0x00), "the follower has something on its head"
    for frame in SP.PLAYER_FRAMES:
        assert frame[0] == 0x00, "the lamp is inside the box, not on its edge"
        assert frame[1] == frame[2] == LAMP_COLUMNS, \
            "the lamp is four pixels wide, two rows, centred"


def mirror(row: int, width: int) -> int:
    return sum(1 << (width - 1 - i) for i in range(width) if row & (1 << i))


def test_each_walk_frame_is_the_other_in_the_mirror():
    """**The walk spends the symmetry the living figures used to have, and it
    spends it as a pair** (issue #60).

    Until 2026-09-11 every living figure was symmetric about its centre column
    so that the one figure that was not read as dead. That reservation was
    lifted when the body was laid down (issue #59) -- its tell is its aspect
    now -- and the walk is the first thing to spend it on: a stride has one
    hand forward and one foot back, which no symmetric drawing can say.

    What is kept instead is that **frame B is frame A reflected**, row for
    row. The two strides are the same figure with the other foot forward, so
    across a cycle the figure stays centred over its column and never leans,
    lists or drifts -- and a redraw that made B a different drawing from A
    rather than A's reflection would fail here, before anybody had to look at
    it walking.
    """
    for name, (a, b) in SP.STANDING.items():
        assert a != b, f"{name}'s second frame is the first one"
        assert all(mirror(ra, 8) == rb for ra, rb in zip(a, b)), \
            f"{name}'s frame B is not frame A in the mirror"
        # And so a frame that is symmetric on its own is one the walk did
        # not reach: the still rows are the same in both, and every row that
        # differs is one that is asymmetric in each.
        assert any(row != mirror(row, 8) for row in a), \
            f"{name} takes no stride at all"


def test_the_lamp_stays_symmetric_and_the_dead_stay_asymmetric():
    """The two things the walk was not allowed to spend.

    The lamp is centred and symmetric so that it says nothing about facing and
    reads as a fitting rather than a face; the walk moves hands and feet and
    leaves it alone, in both frames. The body is asymmetric everywhere, as it
    was: that is no longer *the* tell, and it has not been given away either.
    """
    for frame in SP.PLAYER_FRAMES:
        assert frame[1] == frame[2] == mirror(frame[1], 8), \
            "the walk moved the lamp"
    # The body is 16 wide, so its mirror runs across both bytes of a row: the
    # left byte reversed becomes the right one and vice versa.
    for left, right in SP.BODY:
        if not (left or right):
            continue
        assert (left, right) != (mirror(right, 8), mirror(left, 8)), \
            "the body is symmetric somewhere, which reads as somebody standing"


def test_the_strides_differ_in_the_hands_and_feet_and_nowhere_else():
    """A walk is the bottom of the figure moving under a head and shoulders
    that do not. If the head or the shoulders differed between frames the
    figure would appear to change size as it walked, which is what a Cleg
    does by approaching and must not do by stepping -- and the player's lamp
    and mark are pinned separately because they are what identify him.
    """
    still_rows = {"player": range(0, 9), "worker": range(0, 11),
                  "follower": range(0, 8)}
    for name, (a, b) in SP.STANDING.items():
        for row in still_rows[name]:
            assert a[row] == b[row], f"{name} row {row} moves between frames"
        moving = [i for i, (ra, rb) in enumerate(zip(a, b)) if ra != rb]
        assert moving, f"{name} does not move"
        assert max(moving) - min(moving) <= 3, \
            f"{name}'s stride spans rows {moving}, which is more than a stride"


def test_a_follower_has_its_arms_down_and_a_waiting_worker_has_them_up():
    """Raised arms mean "I still need reaching", so somebody already walking
    behind you must not be drawn making the signal."""
    for frame in SP.WORKER_FRAMES:
        assert _edges(frame), "a waiting worker's hands reach both edges"
    for frame in SP.FOLLOWER_FRAMES:
        assert not _edges(frame), "a follower is still signalling"
        assert not any(row & 0x81 for row in frame), \
            "a follower reaches the edge of its column, which is the player's"


def test_no_sprite_is_blank():
    for name, sprite in SP.SPRITES.items():
        assert any(octets(sprite)), f"{name} is empty"


#: The lamp family: one silhouette, three meanings, told apart by their
#: middles -- empty is dark, filled is burning, a lens is bolted down. They are
#: exempt from the pairwise silhouette rule below, deliberately and with a
#: reason: a burning lamp sits inside the pool of light it is making, a housing
#: is bolted to a wall corner and never lies on the floor, and neither of those
#: cues is in the eight bytes. See `assets/sprites/lamp.txt`.
LAMP_FAMILY = ("lamp_off", "lamp_on", "housing")


def test_silhouettes_differ_by_more_than_a_row_or_two():
    """Exact inequality is too weak. Shapes carrying all the information have
    to be distinguishable at a glance, not by one pixel."""
    same_size = [(n, s) for n, s in SP.SPRITES.items()
                 if len(s) == 8 and SP.width_of(s) == 8
                 and n not in LAMP_FAMILY]
    for i, (name_a, a) in enumerate(same_size):
        for name_b, b in same_size[i + 1:]:
            differing = sum(1 for ra, rb in zip(a, b) if ra != rb)
            assert differing >= 3, (
                f"{name_a} and {name_b} differ in only {differing} rows"
            )


def test_no_sprite_is_a_solid_block():
    """A filled rectangle reads as a blob, not a thing."""
    for name, sprite in SP.SPRITES.items():
        assert not all(b == 0xFF for b in octets(sprite) if b), name


def test_the_cleg_has_a_head_a_body_and_wings_in_both_frames():
    """A fly seen from above: a head on the axis, wings off it. Wings out is
    the full width in one row; wings back reaches both edges lower down, at
    the tips. Either way it reads as an insect and not as debris."""
    for frame in SP.CLEG_FRAMES:
        assert frame[0] == 0x00, "the fly is inside its box"
        assert frame[1] == 0x18, "the head is on the axis"
        assert any(row & 0x80 and row & 0x01 for row in frame), \
            "the wings never reach both edges"
    assert 0xFF in SP.CLEG_A, "wings out is the whole width"
    assert 0xFF not in SP.CLEG_B, "wings back is not the whole width"


def test_the_two_cleg_frames_differ_by_twenty_pixels_below_the_head():
    """**The thing that was wrong before** (issue #61). The first pair differed
    by eight corner pixels, one of them under a lit stipple dot, and the tester
    measured that a flip coincident with an eight-pixel jump of the whole
    sprite read as no animation at all. So: twenty or more, none of them in the
    head, none of them on a stipple dot, and the ink counts deliberately
    unequal so the flip pulses -- the previous test here pinned them equal, and
    that pin is withdrawn with the ruling."""
    a, b = SP.CLEG_A, SP.CLEG_B
    differing = [(r, c) for r in range(8) for c in range(8)
                 if (a[r] ^ b[r]) & (0x80 >> c)]
    assert len(differing) >= 20, f"the frames differ by {len(differing)} pixels"
    assert all(r >= 2 for r, _ in differing), "the head moves between frames"
    # The lit stipple's dots, for a cell-aligned sprite: `floor.STIPPLE_LIT`.
    from spikes import floor
    dots = {(r, c) for r in range(8) for c in range(8)
            if floor.STIPPLE_LIT[r] & (0x80 >> c)}
    assert not dots & set(differing), \
        f"a differing pixel sits on a stipple dot: {sorted(dots & set(differing))}"
    ink = [sum(bin(row).count("1") for row in f) for f in (a, b)]
    assert ink[0] != ink[1], "no pulse: the frames weigh the same"
    assert abs(ink[0] - ink[1]) <= 6, \
        f"a pulse of {abs(ink[0] - ink[1])} would read as the fly changing size"


def test_neither_cleg_frame_is_the_nests_silhouette():
    """A nest is a squat solid mass; a Cleg is a thin cross or a dart. Both
    frames have to keep clear of it, since either may be the one on screen
    next to a nest."""
    nest = SP.NEST
    for name, frame in (("A", SP.CLEG_A), ("B", SP.CLEG_B)):
        differing = sum(1 for ra, rb in zip(frame, nest) if ra != rb)
        assert differing >= 6, f"CLEG_{name} is {differing} rows off the nest"
        ink = sum(bin(row).count("1") for row in frame)
        assert ink < sum(bin(row).count("1") for row in nest) - 8, \
            f"CLEG_{name} is as heavy as a nest"


# --- the fade remembers the building, not its inhabitants (issue #12) ------

def test_a_sprite_is_drawn_only_in_cells_its_test_allows():
    s = Screen()
    SP.draw(s, SP.WORKER_A, 10 * CELL, 5 * CELL, visible=lambda cx, cy: cx == 10)
    drawn = {(px % SCREEN_W) // CELL
             for px, on in enumerate(s.pixels) if on}
    assert drawn == {10}


def test_a_person_can_be_cut_in_half_by_the_edge_of_a_light():
    """Half in the beam is drawn half, the same way two-tone works."""
    s = Screen()
    x = 10 * CELL + 4                      # straddling columns 10 and 11
    SP.draw(s, SP.WORKER_A, x, 5 * CELL, visible=lambda cx, cy: cx == 10)
    rows = [px // SCREEN_W for px, on in enumerate(s.pixels) if on]
    cols = {(px % SCREEN_W) for px, on in enumerate(s.pixels) if on}
    assert rows, "nothing drawn at all"
    assert all(c < 11 * CELL for c in cols), "drew outside the lit cell"


def test_no_test_means_drawn_everywhere_as_before():
    lit, masked = Screen(), Screen()
    SP.draw(lit, SP.WORKER_A, 10 * CELL + 3, 5 * CELL)
    SP.draw(masked, SP.WORKER_A, 10 * CELL + 3, 5 * CELL,
            visible=lambda cx, cy: True)
    assert bytes(lit.pixels) == bytes(masked.pixels)


# --- the art is in assets/, and only there (issues #31, #48) ---------------

def _assets():
    """`assets/sprites/`, which is the source-of-truth art in editable form."""
    from pathlib import Path
    return Path(__file__).resolve().parents[2] / "assets" / "sprites"


def _authored() -> set:
    """Every block name authored under `assets/sprites/`.

    Read with the converter's own parser, so this asks the question the way the
    build does: a file may hold a family -- the lamp's four, the Cleg's two --
    and the block name is the identity.
    """
    import importlib.util
    from pathlib import Path
    tool = Path(__file__).resolve().parents[2] / "tools" / "bitmaps.py"
    spec = importlib.util.spec_from_file_location("bitmaps_tool", tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {block.name for block in module.read_tree([str(_assets())])}


def test_every_sprite_is_authored_in_assets_and_generated_from_there():
    """**One source, not two agreeing copies** (issue #48).

    This used to compare the hex in `sprites.py` against the grid in
    `assets/sprites/` and fail if they disagreed -- which could say they had
    drifted but never which of them was right. The bytes are now generated from
    the grid by `tools/bitmaps.py`, so `sprites.py` declares none of its own and
    the question cannot be asked. What is left to check is that the module the
    game imports really is the generated one, and that every sprite the game
    draws is authored somewhere under `assets/sprites/`.

    **Checked block by block rather than file by file.** It used to require a
    file per sprite, `player.txt` for PLAYER; the lamp family and the two Cleg
    frames are families that belong in one file each, exactly as the sixteen
    doorway tiles do. The file name is documentation and `name:` is the
    identity, which is the tool's own rule.
    """
    from spikes import bitmaps_gen
    authored = _authored()
    for name, sprite in SP.SPRITES.items():
        block = name.upper()
        assert block in authored, f"{name} is drawn in code and nowhere else"
        assert tuple(sprite) == bitmaps_gen.BITMAPS[block], \
            f"{name} is not the generated bitmap"


def test_the_assets_directory_holds_nothing_the_game_does_not_draw():
    """Art nobody draws is art nobody maintains, and the suite should say so.

    The one thing this would wrongly refuse is a sprite drawn ahead of the code
    that uses it. There is none: DOOR_LOCKED is unexercised by the playtest
    building -- nothing in it is locked -- but it is on the sprite sheet, which
    is a draw call like any other.
    """
    drawn = {name.upper() for name in SP.SPRITES}
    assert _authored() == drawn, "art nobody draws, or a sprite with no source"


def test_sprites_py_declares_no_bytes_of_its_own():
    """The rule the pipeline rests on, checked mechanically.

    A hex tuple creeping back into this module would be a second copy of a
    picture, and second copies drift. If a new sprite needs adding, it is added
    to `assets/sprites/` and regenerated.
    """
    import re
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "spikes"
              / "sprites.py").read_text()
    assert not re.search(r"0x[0-9A-Fa-f]{2},", source), \
        "sprites.py has bytes in it again; they belong in assets/sprites/"


# --- the two-cell class: 16 wide, cell-aligned (issue #59) ------------------

def _cells_with_ink(screen) -> set:
    """Which attribute cells have any pixel set in them."""
    return {(px // CELL, py // CELL)
            for py in range(PLAY_ROWS * CELL) for px in range(SCREEN_W)
            if screen.point(px, py)}


def test_a_body_is_drawn_across_exactly_two_cells_of_one_row():
    """The first drawable in the game that is not eight pixels wide.

    Two cells of area is one of the three properties the redraw had to keep:
    **a nest is one cell and a body is two**, so a body visibly shrinks when it
    turns into a nest. Lose the second cell and the shrink goes with it.
    """
    s = Screen()
    SP.draw(s, SP.BODY, 5 * CELL, 9 * CELL)
    assert _cells_with_ink(s) == {(5, 9), (6, 9)}


def test_the_right_hand_cell_of_a_body_is_the_second_byte_of_each_row():
    """Bit 7 of the *second* byte is the ninth pixel, not the first again.

    A two-byte row is where a converter or a drawing routine gets the order
    backwards, and the failure is invisible on the left half of the sprite.
    """
    s = Screen()
    SP.draw(s, SP.BODY, 0, 0)
    # Row 2 is `.######.####....`: the second byte is 0xF0, so pixels 8-11.
    assert [x for x in range(16) if s.point(x, 2)] == [1, 2, 3, 4, 5, 6,
                                                       8, 9, 10, 11]


def test_a_body_needs_no_pre_shift_because_it_is_drawn_cell_aligned():
    """The port's reason for the class existing at all.

    A body does not move, so it is drawn at a multiple of eight and each of its
    two bytes goes into one cell whole -- no shift, no mask, no pre-shift
    table. This is the property, checked at every column the sprite can be
    drawn at: two cells, never three.
    """
    for cx in range(COLS - 1):
        s = Screen()
        SP.draw(s, SP.BODY, cx * CELL, 3 * CELL)
        assert len(_cells_with_ink(s)) == 2, cx


def test_a_body_in_a_one_cell_gap_is_drawn_as_its_head_end_alone():
    """`columns=1`: the case where both neighbours are wall.

    One cell of body reads as somebody huddled in a doorway, which is the
    honest picture of what happened. It is the only case in which a body is one
    cell, and it must not silently become a nest-sized heap anywhere else --
    hence the test above that every other case is two.
    """
    s = Screen()
    SP.draw(s, SP.BODY, 5 * CELL, 9 * CELL, columns=1)
    assert _cells_with_ink(s) == {(5, 9)}
    assert any(s.point(5 * CELL + x, 9 * CELL + 2) for x in range(8)), \
        "the head end is the end that is drawn"


def test_a_wide_sprite_is_clipped_at_the_right_edge_and_does_not_wrap():
    s = Screen()
    SP.draw(s, SP.BODY, SCREEN_W - CELL, 40)
    for py in range(40, 48):
        for px in range(0, CELL):
            assert not s.point(px, py), "the body wrapped onto the left edge"


def test_a_wide_sprite_never_writes_an_attribute_either():
    """The clash guarantee is not weakened by a sprite being two cells wide."""
    s = Screen()
    before = bytes(s.attrs)
    for x in (0, 3, 100, SCREEN_W - 4):
        SP.draw(s, SP.BODY, x, 40)
    assert bytes(s.attrs) == before


# --- which cell a body lies into (issue #59) -------------------------------
#
# The rule is authored -- in the vault decision and in assets/sprites/body.txt
# -- and not invented here. These pin it in the order the rule is written in.

def test_a_body_lies_the_way_the_room_is_wider_when_both_sides_are_floor():
    """With floor either side, the choice is away from the nearer wall.

    A room is exactly the play area, so this is one compare against the middle
    column, which is what it costs on the Z80.
    """
    assert SP.body_cells(3, 5) == ((3, 5), (4, 5)), "the left half lies east"
    assert SP.body_cells(28, 5) == ((27, 5), (28, 5)), \
        "the right half lies west"


def test_a_body_lies_into_the_cell_with_floor_in_it():
    """A wall on the preferred side sends it the other way -- the same rule the
    spray's footprint uses when a cell is refused."""
    wall_east = lambda cx, cy: cx == 4
    assert SP.body_cells(3, 5, wall_east) == ((2, 5), (3, 5))
    wall_west = lambda cx, cy: cx == 27
    assert SP.body_cells(28, 5, wall_west) == ((28, 5), (29, 5))


def test_a_body_in_a_one_cell_gap_keeps_its_own_cell_and_nothing_else():
    """Both neighbours wall. It is drawn as its head end, in its own cell."""
    walled = lambda cx, cy: cx in (2, 4)
    assert SP.body_cells(3, 5, walled) == ((3, 5),)


def test_a_body_at_the_screen_edge_lies_inwards():
    """The edge refuses a cell as firmly as a wall does.

    Checked here rather than left to the room, because `Room.is_solid` answers
    for the room next door at the column past a doorway -- which is somewhere
    this room's drawing cannot go.
    """
    assert SP.body_cells(0, 5) == ((0, 5), (1, 5))
    assert SP.body_cells(COLS - 1, 5) == ((COLS - 2, 5), (COLS - 1, 5))


def test_the_body_always_keeps_the_cell_it_fell_in():
    """**The stored position does not move; only the drawing snaps to a cell.**

    Every mechanic that reads a body -- the tally, the doused check, the nest's
    turn, the flash -- reads `Worker.cell()`, and this is the guarantee that
    the drawing is still over it whichever way the body lies and however the
    walls fall.
    """
    for cx in range(COLS):
        for solid in (None, lambda x, y: x == cx + 1,
                      lambda x, y: x == cx - 1,
                      lambda x, y: x in (cx - 1, cx + 1)):
            cells = SP.body_cells(cx, 7, solid)
            assert (cx, 7) in cells, (cx, cells)
            assert 1 <= len(cells) <= 2
            assert all(cy == 7 for _cx, cy in cells), "a body lies in one row"
