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
    SP.draw(s, SP.CLEG, 40, 40)
    ink, paper, _, _ = __import__(
        "spotlight.core.screen", fromlist=["unpack_attr"]
    ).unpack_attr(s.get_attr(5, 5))
    assert ink == paper, "an unlit cell must render its pixels invisible"


# --- pixel positioning -----------------------------------------------------

def test_sprites_position_by_pixel_not_by_cell():
    a, b = Screen(), Screen()
    SP.draw(a, SP.CLEG, 40, 40)
    SP.draw(b, SP.CLEG, 43, 40)
    assert bytes(a.pixels) != bytes(b.pixels)


def test_an_8x8_sprite_can_span_four_cells():
    spanned = SP.cells_spanned(43, 45, 8)
    assert len(spanned) == 4, spanned


def test_a_cell_aligned_sprite_spans_the_minimum():
    assert len(SP.cells_spanned(40, 40, 8)) == 1
    assert len(SP.cells_spanned(40, 40, 16)) == 2


def test_a_person_spans_more_rows_than_a_cleg():
    assert len(SP.cells_spanned(40, 40, len(SP.PLAYER))) == 2
    assert len(SP.cells_spanned(40, 40, len(SP.CLEG))) == 1


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
    SP.draw(s, SP.CLEG, SCREEN_W - 3, 40)
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
    SP.draw(s, SP.CLEG, 41, 41)
    assert s.point(40, 40), "background pixel was cleared"


# --- silhouettes -----------------------------------------------------------

def test_people_are_8x16_alive_or_dead_and_everything_else_is_8x8():
    """The size rule lost its exception when the body became a person.

    It used to read "people are 8x16, everything else is 8x8", and a body was
    an 8x8 slab -- which is what made it read as debris. Seen from above,
    somebody lying down has the same plan as somebody standing up, so size
    cannot be the tell and pose has to be: **size says whether a thing is a
    person, pose says whether it is still alive.**
    """
    for name in SP.PEOPLE:
        assert len(SP.SPRITES[name]) == 16, name
    for name in ("cleg", "nest", "key", "lamp"):
        assert len(SP.SPRITES[name]) == 8, name
    assert set(SP.PEOPLE) | {"cleg", "nest", "key", "lamp"} == set(SP.SPRITES)


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


def test_no_figure_has_anything_above_its_head():
    """Seen from above a head is the topmost thing and there is no hat on it.

    Two blank rows at the top of every figure, which is also what keeps the
    box 8x16 while the drawing is eleven or twelve rows of it.
    """
    for name in SP.PEOPLE:
        assert SP.SPRITES[name][:2] == (0x00, 0x00), name


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


def test_silhouettes_differ_by_more_than_a_row_or_two():
    """Exact inequality is too weak. Shapes carrying all the information have
    to be distinguishable at a glance, not by one pixel."""
    same_size = [(n, s) for n, s in SP.SPRITES.items() if len(s) == 8]
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
    rather than as debris."""
    assert 0xFF in SP.CLEG
    assert SP.CLEG[1] == 0x42, "splayed legs, not a solid top"


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


# --- the art is in assets/ too (issue #31) ---------------------------------

def _assets():
    """`assets/sprites/`, which is the source-of-truth art in editable form."""
    from pathlib import Path
    return Path(__file__).resolve().parents[2] / "assets" / "sprites"


def _read_asset(path):
    rows = [line for line in path.read_text().splitlines()
            if line and not line.startswith(";")]
    return tuple(sum(1 << (7 - i) for i, ch in enumerate(row) if ch == "#")
                 for row in rows)


def test_every_sprite_is_in_the_assets_directory_as_well_as_in_code():
    """`assets/` is the source of truth for art and it was empty.

    A grid of `#` and `.` rather than hex, because it is the form the next
    person can edit -- and because the two representations having to agree is
    the only thing that stops them drifting. The Spectrum's converter reads
    this, not the Python.

    Comments start with `;` rather than `#`, which is what a row of eight set
    pixels starts with. That is not a style choice: the first version of this
    used `#` and silently ate the player's shoulders.
    """
    for name, sprite in SP.SPRITES.items():
        path = _assets() / f"{name}.txt"
        assert path.exists(), f"{name} is drawn in code and nowhere else"
        assert _read_asset(path) == tuple(sprite), \
            f"{name}.txt and sprites.py disagree"


def test_the_assets_directory_holds_nothing_the_game_does_not_draw():
    drawn = {f"{name}.txt" for name in SP.SPRITES}
    on_disk = {p.name for p in _assets().glob("*.txt")}
    assert on_disk == drawn, "art nobody draws, or a sprite with no source"
