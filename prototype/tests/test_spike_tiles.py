"""Walls made of something, doorways that look like doorways, painted signs.

Issue #48, the second slice of the look-and-feel round, from *Art Direction*
section 3 and *Screen Layout*.

**What was wrong before, and must not come back.** A wall was one line --
`fill_cell_pixels(on=True)` -- and everything below is a consequence of it:

* A remembered wall was as solid as a lit one, so most of what was on screen
  most of the time was 64 pixels of white and a figure standing against it
  disappeared into it. `test_a_remembered_wall_is_a_line_and_a_person_is_not`
  is the one that would catch that coming back.
* A one-cell doorway was an *absence*, and an absence in a dark room is
  indistinguishable from a room that stops there.
* A sign ate the wall it was painted on, because `font.draw_glyph` clears the
  pixels it does not set. Measured at row 15 of room A, where three 64-pixel
  wall cells came back at 10 to 17 --
  `test_a_sign_is_painted_on_the_wall_and_does_not_punch_through_it` pins both
  the fix and the fault, by drawing the old way on a copy of the same frame.

The criterion the art is drawn to, and the one to argue with if any of this is
ever changed:

    **Pattern is a property of light. Shape is a property of the building.**
"""

from spikes import font, lighting, scene, sprites, tiles
from spikes.layout import PLAY_ROWS
from spikes.session import Intent, Session
from spotlight.core.constants import CELL, COLS, SCREEN_W
from spotlight.core.screen import Screen

#: The masonry interior, from the derivation in *Screen Layout*: two mortar
#: courses four pixels apart with the vertical joint staggered half a brick
#: between them.
INTERIOR = (0x10, 0xFF, 0x01, 0x01, 0x01, 0xFF, 0x10, 0x10)

#: The ink counts the vault publishes for each mask, lit and dim. They are
#: pinned here because they are the numbers the design argues from -- "8 to 28
#: pixels against a person's 44" is the whole claim of the slice -- and a table
#: quoted in one place and drawn in another is a table that can drift.
LIT_INK = (52, 41, 44, 34, 36, 31, 34, 28, 41, 31, 36, 29, 31, 25, 29, 22)
DIM_INK = (48, 28, 28, 15, 28, 16, 15, 8, 28, 15, 16, 8, 15, 8, 8, 0)


# --- the mask ---------------------------------------------------------------

def test_the_mask_is_north_east_south_west_in_bits_one_two_four_eight():
    """The order is not arbitrary: the tiles are stored in mask order so that
    the game indexes the table with the mask and needs no lookup at all. Get
    the bit order wrong and every tile is somebody else's."""
    def walls(*cells):
        return lambda cx, cy: (cx, cy) in cells

    assert tiles.mask_at(walls((5, 4)), 5, 5) == tiles.NORTH == 1
    assert tiles.mask_at(walls((6, 5)), 5, 5) == tiles.EAST == 2
    assert tiles.mask_at(walls((5, 6)), 5, 5) == tiles.SOUTH == 4
    assert tiles.mask_at(walls((4, 5)), 5, 5) == tiles.WEST == 8
    assert tiles.mask_at(lambda cx, cy: True, 5, 5) == 15
    assert tiles.mask_at(lambda cx, cy: False, 5, 5) == 0


def test_off_the_room_counts_as_wall():
    """So the outer wall shows one face -- inward -- and nothing is drawn
    against the screen edge. `Room.is_wall` carries the rule, which is what
    lets `mask_at` stay four bit tests."""
    room = scene.ROOM_NEAR
    assert room.is_wall(-1, 5) and room.is_wall(COLS, 5)
    assert room.is_wall(5, -1) and room.is_wall(5, PLAY_ROWS)
    # The top-left corner of the room: north and west are off the room, and
    # east and south are its own walls, so it is a cell with no face at all.
    assert tiles.mask_at(room.is_wall, 0, 0) == 15


def test_the_mask_does_not_reach_through_a_doorway_into_the_next_room():
    """`Room.is_solid` delegates the column past a doorway to the room next
    door, because walking through it is ordinary movement. The tile mask must
    not: off the room counts as wall, and a mask that reached across a
    threshold would cost the Z80 a door-table lookup per wall cell per frame to
    change what a handful of cells at the screen edge look like.
    """
    room = scene.ROOM_NEAR
    door_row = scene.DOOR_ROWS[1]
    assert not room.is_solid(COLS, door_row), "the doorway is walkable"
    assert room.is_wall(COLS, door_row), "but for drawing it is the edge"
    assert tiles.mask_at(room.is_wall, COLS - 1, door_row) & tiles.EAST


def test_the_playtest_building_exercises_nearly_every_mask():
    """Fifteen of the sixteen, in room A alone -- which is why all sixteen have
    to be distinct rather than merely mostly distinct."""
    room = scene.ROOM_NEAR
    used = {tiles.mask_at(room.is_wall, cx, cy)
            for cy in range(PLAY_ROWS) for cx in range(COLS)
            if room.is_wall(cx, cy)}
    assert len(used) >= 15


# --- the tiles --------------------------------------------------------------

def test_all_sixteen_masks_are_distinct_in_both_variants():
    """**Not automatic, and this is the test that says so.**

    An earlier masonry interior put a mortar course on row 7. That made *south
    open* invisible -- the mortar and the boundary line were the same pixels --
    and collapsed four pairs of masks onto each other, so a wall that ended
    looked exactly like a wall that carried on.
    """
    for name, table in (("lit", tiles.WALL_LIT), ("dim", tiles.WALL_DIM),
                        ("doorway", tiles.DOORWAY)):
        seen: dict = {}
        for mask, rows in enumerate(table):
            assert rows not in seen, \
                f"{name}: mask {mask} is identical to mask {seen[rows]}"
            seen[rows] = mask


def test_a_lit_wall_is_its_dim_wall_plus_masonry():
    """Lit draws outline plus masonry; dim draws the outline alone. So every
    pixel of the dim tile is in the lit one, and the difference is the brick.

    This is what makes a remembered wall read as the same wall rather than as a
    different object, and it is what lets a painted cell swap to the dim tile
    without the outline moving."""
    for mask in range(tiles.MASKS):
        lit, dim = tiles.WALL_LIT[mask], tiles.WALL_DIM[mask]
        for row, (a, b) in enumerate(zip(lit, dim)):
            assert b & ~a == 0, f"mask {mask} row {row}: dim is not in lit"
        assert tiles.ink_of(lit) > tiles.ink_of(dim) or mask == 0


def test_the_ink_counts_are_the_ones_the_vault_publishes():
    for mask in range(tiles.MASKS):
        assert tiles.ink_of(tiles.WALL_LIT[mask]) == LIT_INK[mask], mask
        assert tiles.ink_of(tiles.WALL_DIM[mask]) == DIM_INK[mask], mask


def test_a_wall_deep_inside_a_mass_remembers_nothing():
    """Mask 15 has no outline, so there is nothing of it to remember: dim draws
    nothing at all. It is not an oversight and it is what makes a remembered
    room a plan rather than a filled shape."""
    assert tiles.WALL_DIM[15] == (0,) * 8
    assert tiles.WALL_LIT[15] == INTERIOR, "lit, it is pure masonry"


def test_a_remembered_wall_is_a_line_and_a_person_is_not():
    """**The Atic Atac property the build was missing.**

    A remembered wall is 8 to 28 pixels; a waiting worker is 44. Before this a
    wall was 64 against a figure's 60 to 68, so a figure standing against one
    was inside it. If a future slice makes the dim tiles heavier, this is the
    test that should stop it.

    The player is 84 since the slice C redraw -- the lamp and the bar took him
    from 60 -- which is nearly twice the ink of anybody else in the room and
    three times the heaviest remembered wall. Either way the figure is the
    heavier thing on the cell.
    """
    inks = [tiles.ink_of(rows) for rows in tiles.WALL_DIM]
    assert min(inks) == 0 and max(inks) == 48, "mask 0 is a free-standing cell"
    # Every tile that is a wall *run* rather than a lone block: 8 to 28.
    runs = [ink for mask, ink in enumerate(inks) if mask not in (0,)]
    assert max(runs) <= 28
    assert max(runs) < tiles.ink_of(sprites.WORKER) == 44
    assert tiles.ink_of(sprites.PLAYER) == 84


def test_the_derivation_reproduces_every_tile():
    """The tiles are authored in `assets/tiles/` and that is the source. This
    is the check that they are what the derivation says they are, so a tile can
    be checked rather than merely believed -- and it is the reason a coder may
    generate the files, as *2026-09-10 The asset pipeline* allows.

    The rule, from *Screen Layout*: draw a line on every open side, and **the
    line is two pixels when the two sides perpendicular to it are both open**,
    which is an end cap and is what makes a wall run *end* rather than stop.
    """
    def wall(mask, interior):
        rows = list(interior)
        closed = lambda bit: bool(mask & bit)          # noqa: E731
        def thick(a, b):
            return 1 if closed(a) or closed(b) else 2
        if not closed(tiles.NORTH):
            for r in range(thick(tiles.EAST, tiles.WEST)):
                rows[r] |= 0xFF
        if not closed(tiles.SOUTH):
            for r in range(8 - thick(tiles.EAST, tiles.WEST), 8):
                rows[r] |= 0xFF
        if not closed(tiles.WEST):
            bits = 0x80 if thick(tiles.NORTH, tiles.SOUTH) == 1 else 0xC0
            rows = [r | bits for r in rows]
        if not closed(tiles.EAST):
            bits = 0x01 if thick(tiles.NORTH, tiles.SOUTH) == 1 else 0x03
            rows = [r | bits for r in rows]
        return tuple(rows)

    def returns(mask):
        rows = [0] * 8
        if mask & tiles.NORTH:
            rows[0] |= 0xC3
        if mask & tiles.SOUTH:
            rows[7] |= 0xC3
        for r in (0, 1, 6, 7):
            if mask & tiles.WEST:
                rows[r] |= 0x80
            if mask & tiles.EAST:
                rows[r] |= 0x01
        return tuple(rows)

    for mask in range(tiles.MASKS):
        assert wall(mask, INTERIOR) == tiles.WALL_LIT[mask], mask
        assert wall(mask, (0,) * 8) == tiles.WALL_DIM[mask], mask
        assert returns(mask) == tiles.DOORWAY[mask], mask


def test_an_end_cap_is_two_pixels_and_a_face_is_one():
    """The difference between a wall that ends and a wall that merely stops.

    Mask 5 is a north-south run: its west and east faces are one pixel, because
    the run carries on past them. Mask 1 has only a wall to the north, so its
    south line is an end cap and is two pixels deep.
    """
    assert tiles.WALL_DIM[5][3] == 0x81, "one pixel each side of a run"
    assert tiles.WALL_DIM[1][6:] == (0xFF, 0xFF), "an end cap, two deep"
    assert tiles.WALL_DIM[4][:2] == (0xFF, 0xFF)


# --- the masonry tiles, in both axes ----------------------------------------

def _patch(cells, table, cols, rows) -> Screen:
    """Draw a rectangle of tiles into a fresh screen."""
    screen = Screen()
    for cy in range(rows):
        for cx in range(cols):
            tiles.blit(screen, cx, cy, table[cells(cx, cy)])
    return screen


def test_the_masonry_has_no_seam_in_either_axis():
    """A three-by-three block of interior cells, drawn, and read back as
    pixels rather than as bytes.

    Two things have to be true and neither is visible in a table of hex: the
    mortar courses have to run unbroken across a cell boundary sideways, and
    the vertical joints have to continue across one downwards. The staggering
    is checked too -- half a brick, four pixels -- because a joint that lined
    up with the one above it would read as a column rather than as brickwork.
    """
    screen = _patch(lambda cx, cy: 15, tiles.WALL_LIT, 3, 3)

    def row_pixels(py):
        return [screen.pixels[py * SCREEN_W + px] for px in range(3 * CELL)]

    # The mortar courses: rows 1 and 5 of every cell, unbroken all the way.
    for cy in range(3):
        for course in (1, 5):
            assert all(row_pixels(cy * CELL + course)), \
                f"the course at row {course} of cell row {cy} has a gap"

    # The vertical joints, and that they cross the boundary between cell rows.
    def joint_columns(py):
        return {px for px in range(3 * CELL)
                if screen.pixels[py * SCREEN_W + px]}

    upper = joint_columns(2)             # between the two courses
    lower = joint_columns(6)             # below the second course
    assert upper == {7, 15, 23}, upper
    assert lower == {3, 11, 19}, lower
    # ...and the joint below a course continues into the cell beneath it, so
    # the three pixels at rows 6, 7 and 0-of-the-next are one line.
    assert joint_columns(7) == lower
    assert joint_columns(CELL) == lower, "the joint stops at the cell boundary"
    # Half a brick between the courses: four pixels, which is what stops the
    # joints stacking into a column.
    assert {(c + 4) % 8 for c in upper} == {c % 8 for c in lower}


# --- drawing ----------------------------------------------------------------

def test_a_tile_sets_pixels_and_never_clears_or_colours_anything():
    """The same rule as a sprite. It is what lets a sign be painted over a wall
    and a figure composite into one, and it is the whole of the reason
    attribute clash is impossible: only the light and the room's palette ever
    choose a cell's colour."""
    screen = Screen()
    screen.plot(3, 3)
    before = bytes(screen.attrs)
    tiles.blit(screen, 0, 0, tiles.WALL_DIM[15])       # an empty tile
    assert screen.point(3, 3), "an empty tile cleared what was under it"
    tiles.blit(screen, 0, 0, tiles.WALL_LIT[5])
    assert screen.point(3, 3), "a tile cleared what was under it"
    assert bytes(screen.attrs) == before, "a tile wrote an attribute"


def test_a_dark_cell_draws_nothing_at_all():
    """It would be invisible anyway -- DARK is black ink on black paper -- so
    this is the same picture for less work, and it is the picture the port
    draws. It also means an unlit room costs nothing to redraw.

    Frame zero is the run before it has run: the light field is built during a
    step, so nothing in the room is lit and nothing in it should be drawn. The
    exit sign is the exception and stays one -- it has its own battery, and it
    is written whatever the light is doing.
    """
    run = Session(seed=1)
    screen = Screen()
    run.draw(screen)                       # frame zero: no light anywhere yet
    assert not any(run.place.field.levels()), "the field should be dark"
    room, sign = run.place.room, set(run.place.sign_cells)
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            building = room.is_wall(cx, cy) or room.is_doorway(cx, cy)
            if not building or (cx, cy) in sign:
                continue
            assert not any(_cell_bytes(screen, cx, cy)), \
                f"{(cx, cy)} was drawn in a room with no light in it"


def _lit_room(index: int = scene.NEAR, frames: int = 1):
    """A session with one room revealed and drawn, and the screen it drew on.

    `opening.hold` is the debug reveal the game already has, rather than a
    second way to light a room invented for a test -- the same argument the
    gallery makes.
    """
    run = Session(seed=1)
    if index != run.here:
        run.player.x = (COLS - 1) * CELL
        run.player.y = (scene.DOOR_ROWS[1] - 1) * CELL
        for _ in range(16):
            run.step(Intent(dx=1))
        assert run.here == index
    run.place.opening.hold(True)
    screen = Screen()
    for _ in range(frames):
        run.step()
        run.draw(screen)
    return run, screen


def _cell_bytes(screen, cx, cy):
    """What is actually drawn in a cell, as eight bytes."""
    return tuple(
        sum(0x80 >> dx for dx in range(CELL)
            if screen.pixels[(cy * CELL + dy) * SCREEN_W + cx * CELL + dx])
        for dy in range(CELL))


def test_a_lit_wall_is_drawn_as_the_tile_its_own_mask_chooses():
    run, screen = _lit_room()
    room = run.place.room
    painted = set(run.place.sign_cells) | set(run.call_cells)
    checked = 0
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            if not room.is_wall(cx, cy) or (cx, cy) in painted:
                continue
            mask = tiles.mask_at(room.is_wall, cx, cy)
            assert _cell_bytes(screen, cx, cy) == tiles.WALL_LIT[mask], \
                f"the wall at {(cx, cy)} is not mask {mask}"
            checked += 1
    assert checked > 100, "this did not look at many walls"


def test_a_remembered_wall_shows_the_outline_and_none_of_the_masonry():
    """The slice, in one assertion: the same cell, lit and then remembered."""
    room = scene.ROOM_NEAR
    cell = (0, 5)                          # in the west wall
    mask = tiles.mask_at(room.is_wall, *cell)

    # A field each, because a charge is a memory: topping one cell up to LIT
    # and then adding a dim source to the same field leaves it reading lit for
    # another thirty frames, which is the fade working correctly and would make
    # this test a liar.
    field = lighting.LightField()
    field.begin()
    field.add(*cell, lighting.LIT, lighting.CHARGE_LIT)
    field.commit()
    lit = Screen()
    tiles.draw(lit, room, field)
    assert _cell_bytes(lit, *cell) == tiles.WALL_LIT[mask]

    field = lighting.LightField()
    field.begin()
    field.add(*cell, lighting.DIM, lighting.CHARGE_DIM)
    field.commit()
    dim = Screen()
    tiles.draw(dim, room, field)
    assert _cell_bytes(dim, *cell) == tiles.WALL_DIM[mask]
    assert tiles.ink_of(_cell_bytes(dim, *cell)) < \
        tiles.ink_of(_cell_bytes(lit, *cell))


# --- doorways ---------------------------------------------------------------

def test_a_doorway_cell_draws_returns_into_the_opening():
    """Room A's inner door at (15, 7): a one-cell gap in a horizontal wall.

    It is the case the character was added for -- *"the inner one-cell door is
    not a door-shaped thing at 8x8"* -- and what it draws is the two walls
    either side of it continued into the opening.
    """
    run, screen = _lit_room()
    room = run.place.room
    cx, cy = scene.INNER_DOOR
    assert room.is_doorway(cx, cy), "the inner door is not marked as one"
    mask = tiles.mask_at(room.is_wall, cx, cy)
    assert mask == tiles.EAST | tiles.WEST, "a gap with a jamb either side"
    drawn = _cell_bytes(screen, cx, cy)
    # The returns, plus whatever the floor stipple put in the same cell: a `d`
    # is floor in every mechanical respect and is stippled like any other.
    for row, bits in enumerate(tiles.DOORWAY[mask]):
        assert drawn[row] & bits == bits, f"row {row} of the returns is missing"


def test_a_doorway_is_stippled_like_the_floor_it_is():
    """`d` changes the picture and nothing else. It is walkable, it is
    remembered, and it takes the floor's stipple -- if it ever stops, the level
    has been changed by a drawing character."""
    from spikes import floor
    run, screen = _lit_room()
    cx, cy = scene.INNER_DOOR
    drawn = _cell_bytes(screen, cx, cy)
    for row, bits in enumerate(floor.STIPPLE_LIT):
        assert drawn[row] & bits == bits, "the doorway lost its stipple"


def test_the_jambs_either_side_of_a_gap_come_free():
    """A doorway is a pair of drawn jambs with returns between them, and the
    jambs are not drawn by the doorway: the wall cells either side already get
    their inward faces outlined by their own mask. This is why `d` costs one
    table and no special case."""
    room = scene.ROOM_NEAR
    cx, cy = scene.INNER_DOOR
    for jamb in ((cx - 1, cy), (cx + 1, cy)):
        mask = tiles.mask_at(room.is_wall, *jamb)
        face = tiles.EAST if jamb[0] < cx else tiles.WEST
        assert not mask & face, "the jamb thinks the doorway is wall"
        assert tiles.ink_of(tiles.WALL_DIM[mask]) > 0, \
            "a jamb with nothing to remember is not a jamb"


# --- signs are painted, not punched -----------------------------------------

def _shouting_on_a_wall(run, screen, limit: int = 400):
    """Step until somebody is shouting on a wall cell, and say which cells."""
    room = run.place.room
    for _ in range(limit):
        run.step()
        run.draw(screen)
        walls = [c for c in run.call_cells if room.is_wall(*c)]
        if walls:
            return walls
    return []


def test_a_sign_is_painted_on_the_wall_and_does_not_punch_through_it():
    """**The fault this fixes, and the fix, on the same frame.**

    `font.draw_glyph` clears the pixels it does not set, which is right on the
    status strip and was wrong everywhere in the play area: at row 15 of room A
    three 64-pixel wall cells came back at 10 to 17 ink. `paint_glyph` sets
    pixels and clears nothing, and the cell draws the *dim* wall tile under the
    word, so the outline runs unbroken through it and only the masonry is lost.

    The old routine is run on a copy of the same frame, so the two numbers in
    the docstring are numbers this test takes rather than numbers it quotes.
    """
    run, screen = _lit_room()
    room = run.place.room
    painted = [c for c in run.place.sign_cells if room.is_wall(*c)]
    painted += _shouting_on_a_wall(run, screen)
    assert painted, "no word landed on a wall, so this test proved nothing"

    for cx, cy in painted:
        mask = tiles.mask_at(room.is_wall, cx, cy)
        outline = tiles.WALL_DIM[mask]
        drawn = _cell_bytes(screen, cx, cy)
        for row, bits in enumerate(outline):
            assert drawn[row] & bits == bits, \
                f"the wall outline at {(cx, cy)} is broken by the word"
        # ...and the masonry is gone where the paint is: a painted cell is the
        # dim tile plus a glyph, never the lit tile plus a glyph.
        assert tiles.ink_of(drawn) < tiles.ink_of(tiles.WALL_LIT[mask]) + 20

    # What the old way did to the same cells, measured rather than remembered.
    before = Screen()
    before.pixels[:] = screen.pixels
    for cx, cy in painted:
        font.draw_glyph(before, cx, cy, font.GLYPHS["E"])
    punched = [tiles.ink_of(_cell_bytes(before, cx, cy)) for cx, cy in painted]
    assert max(punched) <= 20, (
        "the old routine is supposed to be the destructive one; if this fails "
        "the comparison is no longer measuring what it claims")


def test_the_exit_sign_composites_over_the_floor_it_is_written_on():
    """One rule, both cases: **paint hides texture and never shape.**

    In room A as it stands the exit sign lands on floor rather than on wall --
    the door is in the west wall and the word is written beside it, into the
    room. On floor there is no outline to protect, so what the rule protects is
    the stipple: the sign used to blank the four dots in each of its cells, and
    a lit cell with nothing in it is indistinguishable from an unlit one.
    """
    from spikes import floor
    run, screen = _lit_room()
    sign = run.place.sign_cells
    assert sign, "room A has no exit sign, so this proved nothing"
    for cx, cy in sign:
        drawn = _cell_bytes(screen, cx, cy)
        for row, bits in enumerate(floor.STIPPLE_LIT):
            assert drawn[row] & bits == bits, \
                f"the sign at {(cx, cy)} blanked the floor under it"


def test_the_status_strip_still_writes_over_itself():
    """`draw_glyph` is kept, and kept destructive, because a readout has to
    erase its own last value. Only the play area changed."""
    screen = Screen()
    screen.fill_cell_pixels(4, 22, on=True)
    font.draw_glyph(screen, 4, 22, font.GLYPHS[" "])
    assert not any(_cell_bytes(screen, 4, 22))


# --- the geometry has not moved ---------------------------------------------

def test_no_cell_changed_from_wall_to_floor_or_back():
    """**The slice changes what a wall costs to redraw, not how many there
    are.** The repaint figures are compared against slice A on the same seeds
    and the solid-cell count must match, so if room geometry moves the
    comparison is worthless. These two numbers are the geometry.
    """
    counts = {r.name: sum(r.solid_map()) for r in scene.BUILDING.rooms}
    assert counts == {scene.NEAR_NAME: 151, scene.FAR_NAME: 157}


def test_the_far_rooms_light_still_covers_its_side_of_the_doorway():
    """**The one place `d` was asked for and refused, pinned so it stays a
    decision rather than a slip.**

    *Art Direction* asks for room B's three cells at column 0 to be `d`. They
    are `L`: the room light block sits exactly on them, a cell holds one
    character, and marking them `d` would take three cells out of the zone and
    move the lure's origin -- which is a change to what a light reaches and
    where the swarm gathers, and issue #48 is forbidden from making one. The
    jambs above and below still outline the opening; what it does not get is
    the returns.

    If the vault rules that the block moves a column, this test moves with it.
    Until then it is what stops the ruling being made by accident.
    """
    zones = scene.ROOM_FAR.light_zones()
    assert zones == [(0, 10, 3, 3)], zones
    assert all(scene.ROOM_FAR.rows[cy][0] == scene.ROOM_LIGHT
               for cy in scene.DOOR_ROWS)


def test_a_doorway_character_is_not_solid_anywhere_it_is_asked():
    """Three questions, three callers, one answer. The level check, the
    collision rule and the swarm-reachability check all treat `d` as floor --
    which is what keeps the next slice's repaint comparison meaningful."""
    from spikes import building, swarming
    room = scene.ROOM_NEAR
    cx, cy = scene.INNER_DOOR
    assert building.DOORWAY not in building.SOLID
    assert not room.is_solid(cx, cy)
    assert (cx, cy) not in swarming.unswarmable(room)
    scene.validate()                       # the level check itself


def test_walking_through_a_doorway_still_works_both_ways():
    """The drawing character must not have changed the crossing. Walked in the
    real loop, both directions, because `d` sits in the cells the crossing is
    made of and a mistake there would be a mistake in the level rather than in
    the picture."""
    run = Session(seed=1)
    run.player.x = (COLS - 1) * CELL
    run.player.y = (scene.DOOR_ROWS[1] - 1) * CELL
    for _ in range(16):
        run.step(Intent(dx=1))
    assert run.here == scene.FAR
    for _ in range(16):
        run.step(Intent(dx=-1))
    assert run.here == scene.NEAR
