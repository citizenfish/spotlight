"""Sprites: pixel positioning, and never touching an attribute."""

from spikes import lighting as L, sprites as SP
from spikes.layout import PLAY_ROWS, STRIP_TOP
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
    SP.draw(s, SP.PLAYER, 76, 40)

    assert bytes(s.attrs) == attrs_before, "drawing changed colours"
    assert s.get_attr(9, 5) == L.attr_for(L.LIT, YELLOW)
    assert s.get_attr(10, 5) == L.attr_for(L.DIM, YELLOW)
    # And it really is spanning both columns.
    spanned = SP.cells_spanned(76, 40, len(SP.PLAYER))
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
    assert len(SP.cells_spanned(40, 40, len(SP.PLAYER))) == 2
    assert len(SP.cells_spanned(40, 40, len(SP.CLEG_A))) == 1


# --- clipping --------------------------------------------------------------

def test_sprites_are_clipped_at_the_screen_edges():
    for x, y in ((-6, 40), (SCREEN_W - 2, 40), (40, -6)):
        s = Screen()
        SP.draw(s, SP.PLAYER, x, y)          # must not raise or wrap
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
    SP.draw(s, SP.PLAYER, 40, PLAY_ROWS * CELL - 4)
    for py in range(STRIP_TOP * CELL, 192):
        for px in range(SCREEN_W):
            assert not s.point(px, py), "a sprite leaked into the strip"


# --- compositing -----------------------------------------------------------

def test_sprites_set_pixels_without_clearing_the_background():
    s = Screen()
    s.fill_cell_pixels(5, 5, on=True)
    SP.draw(s, SP.CLEG_A, 41, 41)
    assert s.point(40, 40), "background pixel was cleared"


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
    """
    for name in SP.STANDING:
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
    player, worker = _edges(SP.PLAYER), _edges(SP.WORKER)
    assert player and worker
    # The worker's width is all above the head; the player's is all shoulders
    # and below. They overlap on one row and are opposite everywhere else.
    assert min(worker) < min(player) and max(worker) < max(player)
    assert len(set(worker) & set(player)) <= 1
    assert sum(1 for a, b in zip(SP.PLAYER, SP.WORKER) if a != b) >= 8


def test_only_the_player_has_anything_above_his_head_and_it_is_his_lamp():
    """Seen from above a head is the topmost thing and there is no hat on it.

    **The player is the one exception and it is deliberate** (issue #49). The
    rule exists so that no hat, brim, hair or face makes a figure read as
    front-facing; a centred block on a helmet reads as a fitting rather than a
    face, and **it is an object rather than anatomy**. It is what identifies
    him where there is no floor under his feet to draw his bar on -- on a wall
    cell, in a doorway, and on the sprite sheet.

    The rest keep two blank rows, which is also what keeps the box 8x16 while
    the drawing is eleven or twelve rows of it.

    **It is a rule about figures on their feet**, so the body is not in it
    (issue #59). A figure lying down has no head at the top of its box -- its
    head is at one end of a row -- and the rule exists to stop a hat, a brim or
    a face making a standing figure read as front-facing. A corpse is in no
    danger of reading as front-facing, and the arm flung back over its head is
    the first row of its box on purpose.
    """
    for name in SP.STANDING:
        if name == "player":
            continue
        assert SP.SPRITES[name][:2] == (0x00, 0x00), name
    assert SP.PLAYER[0] == 0x00, "the lamp is inside the box, not on its edge"
    assert SP.PLAYER[1] == SP.PLAYER[2] == 0x3C, \
        "the lamp is four pixels wide, two rows, centred"


def test_the_living_are_symmetric_and_the_dead_are_not():
    """Asymmetry is no longer *the* tell for a body, and it has not been spent.

    The aspect ratio is the tell since issue #59. This is kept because the
    player's lamp was deliberately drawn centred and symmetric in order not to
    cost the body the only tell it had at the time, and a property paid for
    once should not be given away later by accident. A figure symmetric about
    its centre column reads as standing to attention; a corpse does not.
    """
    def mirror(row, width):
        return sum(1 << (width - 1 - i) for i in range(width)
                   if row & (1 << i))

    for name in SP.STANDING:
        sprite = SP.SPRITES[name]
        assert all(row == mirror(row, 8) for row in sprite), \
            f"{name} is not symmetric about its centre column"
    # The body is 16 wide, so its mirror runs across both bytes of a row: the
    # left byte reversed becomes the right one and vice versa.
    for left, right in SP.BODY:
        if not (left or right):
            continue
        assert (left, right) != (mirror(right, 8), mirror(left, 8)), \
            "the body is symmetric somewhere, which reads as somebody standing"


def test_a_follower_has_its_arms_down_and_a_waiting_worker_has_them_up():
    """Raised arms mean "I still need reaching", so somebody already walking
    behind you must not be drawn making the signal."""
    assert _edges(SP.WORKER), "a waiting worker's hands reach both edges"
    assert not _edges(SP.FOLLOWER), "a follower is still signalling"


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


def test_the_cleg_is_the_widest_thing_at_its_waist():
    """Its full-width middle with thin legs is what makes it read as an insect
    rather than as debris. True of both wing frames."""
    for frame in SP.CLEG_FRAMES:
        assert 0xFF in frame
        assert frame[0] == 0x00, "the fly is inside its box"
    assert SP.CLEG_A[1] == 0x42, "splayed legs, not a solid top"


def test_the_two_cleg_frames_are_the_same_body_at_the_same_weight():
    """**Same body, same ink count, different silhouette.** A wingbeat that
    changed the fly's mass would read as the fly getting bigger, which is what
    a Cleg does by walking towards you and must not do by flapping."""
    a, b = SP.CLEG_A, SP.CLEG_B
    assert a != b, "the second frame is the first one"
    ink = [sum(bin(row).count("1") for row in f) for f in (a, b)]
    assert ink[0] == ink[1], f"the frames weigh {ink[0]} and {ink[1]}"
    # The body -- the three rows that make it an insect -- is untouched.
    assert a[3:6] == b[3:6], "the wingbeat moved the body"


# --- the fade remembers the building, not its inhabitants (issue #12) ------

def test_a_sprite_is_drawn_only_in_cells_its_test_allows():
    s = Screen()
    SP.draw(s, SP.WORKER, 10 * CELL, 5 * CELL, visible=lambda cx, cy: cx == 10)
    drawn = {(px % SCREEN_W) // CELL
             for px, on in enumerate(s.pixels) if on}
    assert drawn == {10}


def test_a_person_can_be_cut_in_half_by_the_edge_of_a_light():
    """Half in the beam is drawn half, the same way two-tone works."""
    s = Screen()
    x = 10 * CELL + 4                      # straddling columns 10 and 11
    SP.draw(s, SP.WORKER, x, 5 * CELL, visible=lambda cx, cy: cx == 10)
    rows = [px // SCREEN_W for px, on in enumerate(s.pixels) if on]
    cols = {(px % SCREEN_W) for px, on in enumerate(s.pixels) if on}
    assert rows, "nothing drawn at all"
    assert all(c < 11 * CELL for c in cols), "drew outside the lit cell"


def test_no_test_means_drawn_everywhere_as_before():
    lit, masked = Screen(), Screen()
    SP.draw(lit, SP.WORKER, 10 * CELL + 3, 5 * CELL)
    SP.draw(masked, SP.WORKER, 10 * CELL + 3, 5 * CELL,
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
