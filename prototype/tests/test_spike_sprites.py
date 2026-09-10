"""Sprites: pixel positioning, and never touching an attribute."""

from spikes import lighting as L, sprites as SP
from spikes.layout import PLAY_ROWS, STRIP_TOP
from spotlight.core.constants import CELL, COLS, SCREEN_W, YELLOW
from spotlight.core.screen import Screen


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

def test_people_are_8x16_alive_or_dead_and_the_objects_are_8x8():
    """The size rule lost its exception when the body became a person.

    It used to read "people are 8x16, everything else is 8x8", and a body was
    an 8x8 slab -- which is what made it read as debris. Seen from above,
    somebody lying down has the same plan as somebody standing up, so size
    cannot be the tell and pose has to be: **size says whether a thing is a
    person, pose says whether it is still alive.**

    **A door is the one 8x16 thing that is not a person** (issue #49), because
    it is the person-shaped hole you walk out through. It is never confused
    with one: it does not move, and it stands in a wall.
    """
    for name in SP.PEOPLE:
        assert len(SP.SPRITES[name]) == 16, name
    for name in SP.DOORS:
        assert len(SP.SPRITES[name]) == 16, name
    objects = set(SP.SPRITES) - set(SP.PEOPLE) - set(SP.DOORS)
    assert objects, "every sprite became a person or a door"
    for name in objects:
        assert len(SP.SPRITES[name]) == 8, name


def test_every_silhouette_is_distinct():
    """Colour carries no information, so shape has to."""
    seen = {}
    for name, sprite in SP.SPRITES.items():
        key = tuple(sprite)
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
    """
    for name in SP.PEOPLE:
        if name == "player":
            continue
        assert SP.SPRITES[name][:2] == (0x00, 0x00), name
    assert SP.PLAYER[0] == 0x00, "the lamp is inside the box, not on its edge"
    assert SP.PLAYER[1] == SP.PLAYER[2] == 0x3C, \
        "the lamp is four pixels wide, two rows, centred"


def test_the_living_are_symmetric_and_the_dead_are_not():
    """The tell for a body is pose, because from above the plan is the same."""
    def mirror(row):
        return sum(1 << (7 - i) for i in range(8) if row & (1 << i))

    for name in ("player", "worker", "follower"):
        sprite = SP.SPRITES[name]
        assert all(row == mirror(row) for row in sprite), \
            f"{name} is not symmetric about its centre column"
    assert not any(row == mirror(row) for row in SP.BODY if row), \
        "the body is symmetric somewhere, which reads as somebody standing"


def test_a_follower_has_its_arms_down_and_a_waiting_worker_has_them_up():
    """Raised arms mean "I still need reaching", so somebody already walking
    behind you must not be drawn making the signal."""
    assert _edges(SP.WORKER), "a waiting worker's hands reach both edges"
    assert not _edges(SP.FOLLOWER), "a follower is still signalling"


def test_no_sprite_is_blank():
    for name, sprite in SP.SPRITES.items():
        assert any(sprite), f"{name} is empty"


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
                 if len(s) == 8 and n not in LAMP_FAMILY]
    for i, (name_a, a) in enumerate(same_size):
        for name_b, b in same_size[i + 1:]:
            differing = sum(1 for ra, rb in zip(a, b) if ra != rb)
            assert differing >= 3, (
                f"{name_a} and {name_b} differ in only {differing} rows"
            )


def test_no_sprite_is_a_solid_block():
    """A filled rectangle reads as a blob, not a thing."""
    for name, sprite in SP.SPRITES.items():
        assert not all(row == 0xFF for row in sprite if row), name


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
