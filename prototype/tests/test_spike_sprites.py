"""Sprites: pixel positioning, and never touching an attribute."""

from spikes import lighting as L, sprites as SP
from spikes.layout import PLAY_ROWS, STRIP_TOP
from spotlight.core.constants import CELL, COLS, SCREEN_W, YELLOW
from spotlight.core.screen import Screen


def _lit_left_half(boundary_cx: int, left=L.LIT, right=L.DIM) -> L.LightField:
    """A field split down a cell column, so sprites can straddle a boundary."""
    f = L.LightField()
    f.begin()
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            f.add(cx, cy, left if cx < boundary_cx else right)
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

def test_people_are_8x16_and_everything_else_is_8x8():
    assert len(SP.PLAYER) == len(SP.WORKER) == 16
    for name in ("cleg", "body", "nest", "key"):
        assert len(SP.SPRITES[name]) == 8, name


def test_every_silhouette_is_distinct():
    """Colour carries no information, so shape has to."""
    seen = {}
    for name, sprite in SP.SPRITES.items():
        key = tuple(sprite)
        assert key not in seen, f"{name} is identical to {seen.get(key)}"
        seen[key] = name


def test_player_and_worker_differ_in_the_top_row_of_the_head():
    """The helmet is what tells you which is which at a glance."""
    assert SP.PLAYER[:3] != SP.WORKER[:3]


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
