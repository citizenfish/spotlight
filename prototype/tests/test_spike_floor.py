"""Stippling lit floor: the densities, and the noise tile they are arranged in.

Issue #71, from *The light trail* in the vault. **What was wrong before**: the
lit floor was one 8x8 pattern, four dots on a four-pixel pitch, and every lit
region read as a rectangle of dots whatever its outline was -- a set pixel had
another four to its right eight times in ten. The fix is an arrangement and
nothing else: a 32x32 tile, sixteen blocks, four dots in every one, chosen by
the cell's position. The densities are the same, the light field is the same,
and the event log across the change was byte-identical on seventy runs.

The tests here pin three things separately, because they can fail separately:
the *art* (the blocks are the tile the vault ruled, at the densities it kept),
the *index* (a cell wears the block its position picks), and the *rule* (a
painted cell wears none).
"""

import pathlib

import pytest

from spikes import floor, lighting as L, scene, session as session_mod
from spikes import spike_gallery as gallery
from spotlight.core.constants import CELL, COLS
from spotlight.core.screen import Screen

ASSET = pathlib.Path(__file__).resolve().parents[2] / "assets" / "tiles" / \
    "floor.txt"


def _never_solid(cx, cy):
    return False


def _pixels_in_cell(s, cx, cy):
    return sum(1 for dy in range(CELL) for dx in range(CELL)
               if s.point(cx * CELL + dx, cy * CELL + dy))


def _dots(rows):
    """Where the pixels are, as (row, column) pairs, bit 7 leftmost."""
    return [(y, x) for y, bits in enumerate(rows)
            for x in range(8) if bits & (0x80 >> x)]


def _assembled(table) -> list:
    """The sixteen blocks put back together as thirty-two rows of text."""
    grid = []
    for ty in range(floor.TILE):
        for r in range(CELL):
            line = ""
            for tx in range(floor.TILE):
                bits = table[ty * floor.TILE + tx][r]
                line += "".join("#" if bits & (0x80 >> c) else "."
                                for c in range(CELL))
            grid.append(line)
    return grid


# --- what was always true ---------------------------------------------------

def test_lit_floor_is_denser_than_dim_floor():
    """This is the contrast step the palette cannot give us."""
    s, f = Screen(), L.LightField()
    f.begin(); f.add(1, 1, L.LIT, L.CHARGE_LIT); f.add(3, 1, L.DIM, L.CHARGE_DIM); f.commit()
    floor.draw(s, f, _never_solid)
    assert _pixels_in_cell(s, 1, 1) > _pixels_in_cell(s, 3, 1) > 0


def test_dark_floor_is_left_bare():
    s, f = Screen(), L.LightField()
    floor.draw(s, f, _never_solid)
    assert not any(s.pixels)


def test_solid_cells_are_not_stippled():
    """A wall is already drawn; dotting it would only muddle the shape."""
    s, f = Screen(), L.LightField()
    f.begin(); f.add(2, 2, L.LIT, L.CHARGE_LIT); f.commit()
    floor.draw(s, f, lambda cx, cy: (cx, cy) == (2, 2))
    assert _pixels_in_cell(s, 2, 2) == 0


def test_stipple_stays_inside_its_own_cell():
    s, f = Screen(), L.LightField()
    f.begin(); f.add(4, 4, L.LIT, L.CHARGE_LIT); f.commit()
    floor.draw(s, f, _never_solid)
    assert _pixels_in_cell(s, 4, 4) > 0
    for cx, cy in ((3, 4), (5, 4), (4, 3), (4, 5)):
        assert _pixels_in_cell(s, cx, cy) == 0


# --- the densities did not move ---------------------------------------------

def test_every_lit_block_has_four_dots_and_every_dim_block_one():
    """**The densities are the tuned decision and this is their pin.** Four
    against one is the contrast step that carries the fade, the five-pixel
    clause on the player's mark is measured against four, and issue #71 was
    allowed to move the arrangement *because* it moved neither number. A
    denser lit floor and a two-dot dim floor were both ruled held."""
    assert len(floor.FLOOR_LIT) == len(floor.FLOOR_DIM) == floor.BLOCKS == 16
    for n in range(floor.BLOCKS):
        assert len(_dots(floor.FLOOR_LIT[n])) == 4, f"lit block {n}"
        assert len(_dots(floor.FLOOR_DIM[n])) == 1, f"dim block {n}"


def test_each_dim_block_keeps_the_first_of_its_lit_blocks_dots():
    """Lit -> dim is a thinning, not a shuffle: the one dot you remember is
    one of the four you saw, and it is the first in reading order so that the
    choice is a rule and not sixteen opinions."""
    for n in range(floor.BLOCKS):
        lit, dim = _dots(floor.FLOOR_LIT[n]), _dots(floor.FLOOR_DIM[n])
        assert dim == [lit[0]], f"block {n}: dim dot {dim} is not lit's first"


# --- the arrangement is the tile the vault ruled -----------------------------

def test_the_sixteen_blocks_reassemble_to_the_tile_in_the_asset_header():
    """The tile is the source and the blocks are cut from it. The asset file
    draws the whole 32x32 in its header so it can be read as a picture; this
    is what makes that picture true rather than decorative. Byte for byte."""
    text = ASSET.read_text().splitlines()
    drawn = [line[4:] for line in text
             if line.startswith(";   ") and len(line) == 36
             and set(line[4:]) <= {"#", "."}]
    assert len(drawn) == 32, "the header does not carry the 32x32 tile"
    assert _assembled(floor.FLOOR_LIT) == drawn


def test_no_two_dots_in_the_lit_tile_are_adjacent_even_across_the_wrap():
    """A pair of touching dots is a dash, and the reference's dashes were a
    fifth of its dots; this tile has none, so that four dots is four dots in
    every cell and never three and a blob. The wrap counts: the tile repeats
    every four cells in both axes, so a dot on the right edge is next to one
    on the left edge of the copy beside it.

    The issue said *within a Chebyshev distance of 2*. The tile it gave has
    pairs at exactly 2, so the rule it can honestly pin is *never at 1* --
    which is the rule that matters, since 1 is the dash.
    """
    size = floor.TILE * CELL
    dots = [(y, x) for y, line in enumerate(_assembled(floor.FLOOR_LIT))
            for x, ch in enumerate(line) if ch == "#"]
    assert len(dots) == 64
    for i, (ay, ax) in enumerate(dots):
        for by, bx in dots[i + 1:]:
            dy = min(abs(ay - by), size - abs(ay - by))
            dx = min(abs(ax - bx), size - abs(ax - bx))
            assert max(dx, dy) >= 2, f"{(ay, ax)} touches {(by, bx)}"


def test_the_lattice_is_gone():
    """**The thing that was wrong, measured.** On the old pattern a set pixel
    had another four to its right and four below it every time it was on a
    row that had any -- 0.82 over a played frame -- and one eight to the right
    0.79 of the time. The tile is judged by the same count: at the four-pixel
    pitch fewer than one dot in ten has a twin, at eight fewer than one in
    seven. The issue said *nothing* lines up at eight; the tile it gave has
    eight of sixty-four with a twin eight to the right, so that is the number
    pinned, and the reference measured one in twenty."""
    size = floor.TILE * CELL
    grid = _assembled(floor.FLOOR_LIT)
    dots = [(y, x) for y, line in enumerate(grid)
            for x, ch in enumerate(line) if ch == "#"]

    def twins(dy, dx):
        return sum(1 for y, x in dots
                   if grid[(y + dy) % size][(x + dx) % size] == "#")

    for pitch, most in ((4, 6), (8, 9), (16, 9)):
        assert twins(0, pitch) <= most, f"{twins(0, pitch)} twins {pitch} right"
        assert twins(pitch, 0) <= most, f"{twins(pitch, 0)} twins {pitch} down"


def test_no_lit_block_can_imitate_the_players_mark():
    """The five-pixel clause, from the floor's side. The player's bar is an
    unbroken run of five or more on lit floor, and the legibility suite pins
    the figure; this pins the ground -- no row of any lit block has two dots
    in a row, let alone five -- so the clause survives the noise tile without
    being re-measured."""
    for n, rows in enumerate(floor.FLOOR_LIT):
        for r, bits in enumerate(rows):
            assert not (bits & (bits << 1)), f"block {n} row {r} has a dash"


# --- the index: a cell wears the block its position picks -------------------

def test_the_block_repeats_every_four_cells_and_neighbours_differ():
    """`(cx, cy)` and `(cx + 4, cy + 4)` wear the same block; `(cx + 1, cy)`
    does not. For lit and for dim, on the screen and not only in the index,
    so that a `draw` that ignored the index would fail here."""
    for level in (L.LIT, L.DIM):
        for cx, cy in ((0, 0), (5, 3), (31, 21), (17, 9)):
            same = floor.tile_index(cx, cy)
            assert floor.tile_index(cx + 4, cy + 4) == same
            assert floor.tile_index(cx + 1, cy) != same
            assert floor.tile_index(cx, cy + 1) != same
            assert floor.tile_at(level, cx + 4, cy + 4) is \
                floor.tile_at(level, cx, cy)
    # And drawn: two cells four apart hold the same pixels, and two cells
    # side by side hold different ones.
    s, f = Screen(), L.LightField()
    f.begin()
    for cx, cy in ((2, 2), (6, 6), (3, 2)):
        f.add(cx, cy, L.LIT, L.CHARGE_LIT)
    f.commit()
    floor.draw(s, f, _never_solid)
    cell = lambda cx, cy: [s.point(cx * CELL + dx, cy * CELL + dy)
                           for dy in range(CELL) for dx in range(CELL)]
    assert cell(2, 2) == cell(6, 6)
    assert cell(2, 2) != cell(3, 2)


def test_the_index_is_row_major_over_the_low_two_bits():
    """Block 0 is the top-left cell of the tile, 3 the top-right, 15 the
    bottom-right -- reading order, which is the order the asset cuts them in
    and the order `(cy & 3) * 4 + (cx & 3)` gives. On the port that is a
    mask, a shift and an add."""
    assert floor.tile_index(0, 0) == 0
    assert floor.tile_index(3, 0) == 3
    assert floor.tile_index(0, 1) == 4
    assert floor.tile_index(3, 3) == 15
    assert floor.tile_index(4, 4) == 0
    assert sorted(floor.tile_index(cx, cy) for cy in range(4)
                  for cx in range(4)) == list(range(16))


def test_every_block_is_worn_somewhere_on_a_lit_screen():
    """All sixteen appear on a whole lit play area -- a table with an
    unreachable entry would be bytes the port carries for nothing."""
    s, f = Screen(), L.LightField()
    f.begin()
    for cy in range(4):
        for cx in range(4):
            f.add(cx, cy, L.LIT, L.CHARGE_LIT)
    f.commit()
    floor.draw(s, f, _never_solid)
    seen = set()
    for cy in range(4):
        for cx in range(4):
            got = tuple(s.point(cx * CELL + dx, cy * CELL + dy)
                        for dy in range(CELL) for dx in range(CELL))
            seen.add(got)
    assert len(seen) == 16, "two cells of the tile draw alike"


def test_dot_at_answers_for_screen_pixels():
    """The helper the sprite and gallery tests lean on: a screen pixel is a
    dot iff the block its cell wears has that bit set."""
    for level in (L.LIT, L.DIM):
        rows = floor.tile_at(level, 5, 3)
        for dy in range(CELL):
            for dx in range(CELL):
                assert floor.dot_at(level, 5 * CELL + dx, 3 * CELL + dy) == \
                    bool(rows[dy] & (0x80 >> dx))
    assert not floor.dot_at(L.DARK, 0, 0)


# --- a painted cell draws no stipple ----------------------------------------

def test_a_painted_cell_draws_no_stipple_at_either_level():
    """**The rule the mock found.** The lattice fell between the letters of a
    sign on the floor and the noise does not -- `E:X:I:T` -- so a painted
    cell sits on black, as a glyph on a wall already sits on the dim outline.
    Paint hides texture, on both grounds."""
    for level in (L.LIT, L.DIM):
        s, f = Screen(), L.LightField()
        f.begin()
        f.add(7, 7, level, L.CHARGE_LIT)
        f.add(8, 7, level, L.CHARGE_LIT)
        f.commit()
        floor.draw(s, f, _never_solid, painted={(7, 7)})
        assert _pixels_in_cell(s, 7, 7) == 0, "the painted cell was stippled"
        assert _pixels_in_cell(s, 8, 7) > 0, "the unpainted one was not"


def test_painted_defaults_to_nothing():
    s, f = Screen(), L.LightField()
    f.begin(); f.add(7, 7, L.LIT, L.CHARGE_LIT); f.commit()
    floor.draw(s, f, _never_solid)
    assert _pixels_in_cell(s, 7, 7) == 4


def _painted_in_the_game(run) -> set:
    """The set `Session.draw` hands to both `tiles.draw` and `floor.draw`,
    built the way it builds it."""
    return set(run.place.sign_cells) | set(run.call_cells)


@pytest.mark.parametrize("index", [scene.NEAR, scene.FAR])
def test_exit_and_help_cells_are_in_the_painted_set_in_both_rooms(index):
    """The set the game passes covers the sign and the shout in each room:
    every EXIT cell is in it, and when somebody is shouting every HELP cell
    is too. Then, on a drawn frame, no such cell on floor holds a stipple
    dot outside its glyph.

    The issue asked for EXIT *in both rooms*; only the near room has an exit,
    so only it has a sign, and the far room is checked on its shouts alone.
    """
    from spikes import font, rescue as rescue_mod

    run = session_mod.Session(seed=gallery.GALLERY_SEED)
    gallery.enter(run, index)
    run.place.opening.hold(True)
    screen = Screen()
    for _ in range(600):
        run.step()
        run.draw(screen)
        if run.call_cells:
            break
    painted = _painted_in_the_game(run)
    sign = run.place.sign_cells
    if run.place.room.has_exit:
        assert len(sign) == len(scene.EXIT_SIGN)
    else:
        assert not sign
    assert set(sign) <= painted, "an EXIT cell is not painted"
    assert run.call_cells, "nobody shouted in 600 frames; nothing was proved"
    assert set(run.call_cells) <= painted, "a HELP cell is not painted"

    room = run.place.room
    words = [(sign, scene.EXIT_SIGN)] + \
        [(r, rescue_mod.CALL) for r in run.shout_runs + run.door_calls]
    checked = 0
    for cells, word in words:
        for i, (cx, cy) in enumerate(cells):
            if room.is_solid(cx, cy):
                continue
            glyph = font.GLYPHS[word[i]]
            for dy in range(CELL):
                for dx in range(CELL):
                    if glyph[dy] & (0x80 >> dx):
                        continue
                    assert not screen.point(cx * CELL + dx, cy * CELL + dy), \
                        f"{word[i]} at {(cx, cy)} has a dot under it"
            checked += 1
    assert checked, "every painted cell was on a wall; nothing was proved"


# --- the tables are the generated ones --------------------------------------

def test_the_tables_are_the_generated_blocks_in_name_order():
    from spikes.bitmaps_gen import BITMAPS
    for n in range(floor.BLOCKS):
        assert floor.FLOOR_LIT[n] is BITMAPS[f"FLOOR_LIT_{n:02d}"]
        assert floor.FLOOR_DIM[n] is BITMAPS[f"FLOOR_DIM_{n:02d}"]
    assert not any(name.startswith("FLOOR_") and name[6:9] not in ("LIT", "DIM")
                   for name in BITMAPS), "an unexpected FLOOR block"
    assert sum(1 for name in BITMAPS if name.startswith("FLOOR_")) == 32


def test_the_sheet_shows_the_whole_tile_at_both_densities():
    """The gallery's tile sheet draws the 32x32 tile lit and dim, beside the
    plans, with block 00 top-left -- read back from the screen, so it is the
    game's own blocks in the game's own arrangement."""
    screen = Screen()
    gallery.draw_tile_sheet(screen)
    left = gallery._FLOOR_LEFT
    assert left % floor.TILE == 0
    for top, level in ((gallery._PLAN_LIT_TOP, L.LIT),
                       (gallery._PLAN_DIM_TOP, L.DIM)):
        assert top % floor.TILE == 0
        for cy in range(floor.TILE):
            for cx in range(floor.TILE):
                rows = floor.TABLES[level][cy * floor.TILE + cx]
                for dy, bits in enumerate(rows):
                    for dx in range(CELL):
                        want = bool(bits & (0x80 >> dx))
                        got = screen.point((left + cx) * CELL + dx,
                                           (top + cy) * CELL + dy)
                        assert got == want, f"{level} block {cy * 4 + cx}"
    # The plan and the tile do not overlap, and the plan is still there.
    assert len(gallery.PLAN[0]) <= left - 1
