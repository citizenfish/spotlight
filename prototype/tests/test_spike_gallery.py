"""The look-and-feel gallery: the sheets a reviewer is handed, and what is on them.

Issue #45. `--snap` photographs a run; this is everything a run never shows --
the title and ending screens, the sprites at the size they are drawn, and each
room both fully lit and as it looks while you are in it.

The faults worth guarding against here are all the same shape: **a sheet that
is a picture of something other than the game.** A room reached by setting a
variable rather than walking through the door; a reveal invented for the
gallery instead of the one the game already has; a portrait of a room with the
player half off the edge of it. Each of those produces a perfectly good PNG
that a reviewer would take an opinion from and could not check, so each is
pinned below.
"""

import pygame

from spikes import moments, scene, sources, sprites, tiles
from spikes import spike_gallery as gallery
from spikes.layout import PLAY_ROWS
from spotlight.core.constants import CELL, COLS, ROWS, SCREEN_H, SCREEN_W
from spotlight.core.screen import Screen

import screenreader


def cell_is_full(screen: Screen, cx: int, cy: int) -> bool:
    """Are all 64 pixels of this cell set? That is how a wall is drawn."""
    return all(screen.pixels[(cy * CELL + dy) * SCREEN_W + cx * CELL + dx]
               for dy in range(CELL) for dx in range(CELL))


def cell_holds(screen: Screen, cx: int, cy: int, rows) -> bool:
    """Is every pixel of `rows` set in this cell? Extra pixels are allowed."""
    return all(
        screen.pixels[(cy * CELL + dy) * SCREEN_W + cx * CELL + dx]
        for dy, bits in enumerate(rows)
        for dx in range(CELL) if bits & (0x80 >> dx))


def lit_cells(screen: Screen) -> int:
    """Cells in the play area with anything drawn in them at all."""
    return sum(
        any(screen.pixels[(cy * CELL + dy) * SCREEN_W + cx * CELL + dx]
            for dy in range(CELL) for dx in range(CELL))
        for cy in range(PLAY_ROWS) for cx in range(COLS))


# --- the sheets exist, at the sizes they claim ------------------------------

def test_the_gallery_writes_every_sheet(tmp_path):
    """One command, and everything a look-and-feel review needs is in one
    directory. The list is the issue's, and it is the list because a reviewer
    who has to ask for a second command will review whatever they were sent."""
    paths = gallery.write(str(tmp_path))
    names = {p.rsplit("/", 1)[-1] for p in paths}
    for sheet in ("title", "title-flashed", "ending", "sprites", "tiles",
                  "furniture"):
        assert f"{sheet}_x1.png" in names and f"{sheet}_x3.png" in names
    for room in scene.BUILDING.rooms:
        stem = f"room-{gallery.slug(room.name)}"
        assert f"{stem}-lit_x1.png" in names
        # The same played instant on each of the four strides (issue #72; a
        # pair for the two frames before it, issue #60), because a still of a
        # walk is one stride and the four are the walk. There is no fifth,
        # as-played picture: it would be one of the four with the walkers on
        # mixed strides, and a reviewer given five near-identical frames
        # would compare the wrong pair.
        for stride in range(4):
            assert f"{stem}-played-{stride}_x1.png" in names
        assert f"{stem}-played_x1.png" not in names
        assert f"{stem}-played-a_x1.png" not in names
    # The people sheet (issue #72): every frame labelled, and the walk.
    assert "people_x1.png" in names and "people_x3.png" in names
    # The swapped-lamp and torch-off sheets went with the torch (issue #119).
    near_slug = gallery.slug(scene.BUILDING[scene.NEAR].name)
    assert not any(n.startswith(f"room-{near_slug}-swapped") for n in names)
    assert not any(n.startswith(f"room-{near_slug}-torch-off") for n in names)
    # A moment's flash, in both halves of the cycle (issue #52).
    freed = f"room-{gallery.slug(scene.BUILDING[scene.NEAR].name)}-freed"
    assert f"{freed}_x1.png" in names and f"{freed}_x3.png" in names
    assert f"{freed}-flashed_x1.png" in names
    # No surge sheet and no room-flash sheet (issue #79): neither is in the
    # game. The `N-M-flash` sheets below are the opening strobe's (issue
    # #94), which is.
    assert not any(name.startswith("surge") for name in names)
    assert not any(name.startswith("room-") and "-flash_" in name
                   for name in names)
    # **Every level's rooms, three ways, and a plan strip** (issue #114).
    from spikes import levels
    for number in levels.levels():
        for index in range(len(levels.level(number))):
            for kind in ("lit", "flash", "seen"):
                assert f"{number}-{index + 1}-{kind}_x1.png" in names
                assert f"{number}-{index + 1}-{kind}_x3.png" in names
        assert f"{number}-plan_x2.png" in names
    # **A body in a played room** (issue #59). The sprite sheet is where a
    # sprite is named and the played screen is where it is judged, and the body
    # is the drawing that proved it: sprawled and obvious on the sheet for three
    # rounds, a person-shaped smudge in a room.
    body = f"room-{gallery.slug(scene.BUILDING[scene.NEAR].name)}-body"
    assert f"{body}_x1.png" in names and f"{body}_x3.png" in names
    # Seven sheets (the people since issue #72, the furniture since #74) and
    # three set-up frames at two scales, and a lit shot plus four strides
    # per room. The flash frame and the surge's two went with issue #79; the
    # torch-off frame and the swapped lamp with the torch, issue #119.
    per_level = sum(6 * len(levels.level(n)) + 1 for n in levels.levels())
    assert len(paths) == len(names) == \
        20 + 10 * len(scene.BUILDING.rooms) + per_level


def test_every_sheet_is_written_at_both_scales(tmp_path):
    """1:1 is the honest view of the pixels and x3 is the one a person can
    look at. A gallery of one or the other loses an argument it should not."""
    for path in gallery.write(str(tmp_path)):
        if path.endswith("-plan_x2.png"):
            continue                    # a level's rooms side by side, at x2
        size = pygame.image.load(path).get_size()
        expect = (SCREEN_W, SCREEN_H) if path.endswith("_x1.png") else \
            (SCREEN_W * 3, SCREEN_H * 3)
        assert size == expect, path


# --- the sprite sheet -------------------------------------------------------

def test_the_sprite_sheet_names_every_sprite():
    """Every entry in `sprites.SPRITES`, labelled, read back off the screen
    -- the objects, the doors and the body on the sprite sheet, and every
    standing frame on the people sheet, by its figure and its caption.

    Read back rather than compared against the constants, because a caption
    list that agreed with itself and drew nothing would pass -- and a sprite
    added to the game and left off the sheet is exactly the drift the sheet
    exists to prevent. The two sheets between them cover the whole table,
    and a sprite on neither fails here.
    """
    screen = Screen()
    gallery.draw_sprite_sheet(screen)
    text = " ".join(screenreader.rows(screen))
    on_sheet = [name for name, _sprite in gallery.sheet_entries()]
    for name in on_sheet:
        assert gallery.label(name) in text, f"{name} is not named on the sheet"
    for name in sprites.FRAMES:
        assert gallery.label(name) not in text, f"{name} is on the wrong sheet"
    people = Screen()
    gallery.draw_people_sheet(people)
    rows = screenreader.rows(people)
    for figure, top in gallery.people_rows():
        assert figure.upper() in rows[top], f"{figure} is not named"
        captions = rows[top + 3]
        for caption in gallery._FRAME_CAPTIONS[figure]:
            assert caption in captions, f"{figure}'s {caption} is not captioned"
    assert set(on_sheet) | set(sprites.FRAMES) == set(sprites.SPRITES)


def test_no_caption_on_the_sprite_sheet_runs_over_its_block():
    """**The sheet is where art is named**, so a name that printed over its
    neighbour would take out the only thing on it that is not a picture.

    Thirty-two columns, three blocks, and DOOR LOCKED is eleven characters --
    which fits only in the right-hand block, where the last column of the
    screen is going spare. `sprites.SPRITES` is ordered to put it there. This
    is what fails if somebody inserts a sprite ahead of it without a thought
    about the layout.

    **And a caption that fills its block touches the next one** (issue #60):
    FOLLOWER A is ten characters in a ten-column block, and the first sheet
    with the walk frames on it read `FOLLOWER AFOLLOWER B` across the middle
    and right blocks. A caption in a left or middle block has to leave a
    column before its neighbour; only the last block in a row may run to its
    edge, because nothing follows it.
    """
    for n, (name, _sprite) in enumerate(gallery.sheet_entries()):
        cx, _cy = gallery.block_at(n)
        width = gallery.block_width(n)
        last = n % gallery._ACROSS == gallery._ACROSS - 1
        room = width if last else width - 1
        assert len(gallery.label(name)) <= room, \
            f"{name} needs {len(gallery.label(name))} columns and has {room}"
        assert cx + width <= COLS, f"{name}'s block runs off the screen"


def test_the_sprite_sheet_fits_between_its_heading_and_its_legend():
    """Twelve entries at three across is four rows, and the sheet has to
    hold them without printing into the legend at the bottom. Six rows is
    every row there is: the people's second frames (issue #60) took the sheet
    from fourteen entries to seventeen, which filled it, and their third
    frames (issue #72) would have needed a seventh row, so the standing
    figures moved to the people sheet and this one has room again -- enough
    for the Cleg's third frame (issue #73) to make it twelve."""
    entries = gallery.sheet_entries()
    assert len(entries) == len(sprites.SPRITES) - len(sprites.FRAMES) == 12
    rows = -(-len(entries) // gallery._ACROSS)
    last = gallery._TOP + rows * gallery._BLOCK_H
    assert last <= ROWS - 3, f"the sheet needs {last} rows and has {ROWS - 3}"


def test_the_people_sheet_fits_and_its_strip_stays_on_screen():
    """Three figures, five rows each, between a heading and a two-line legend;
    and the walk strip's last stride ends inside the screen with a cell of
    floor after it."""
    last_row = gallery.people_rows()[-1][1] + gallery._PEOPLE_BLOCK_H
    assert last_row <= ROWS - 3
    for _name, top in gallery.people_rows():
        cells = gallery.strip_cells(top)
        assert cells.stop <= COLS, "the walk strip runs off the screen"
        frames = max(max(cxs) for cxs in gallery._FRAME_CX.values())
        assert cells.start > frames + 1, \
            "the strip's floor touches the last frame's floor"


def test_the_sprite_sheet_draws_every_sprite_on_stipple_with_its_halo():
    """The picture, not only the caption. Each block has the sprite's own
    pixels in it, **on lit stipple, inside its halo** (issue #70): a pixel of
    the box is set where the ink is, clear where the mask is and the ink is
    not, and the stipple's own dot where the mask does not reach. Beside the
    box the floor carries on unbroken, so the halo can be seen against it."""
    screen = Screen()
    gallery.draw_sprite_sheet(screen)
    for n, (_name, sprite) in enumerate(gallery.sheet_entries()):
        cx, cy = gallery.block_at(n)
        px, py = (cx + 3) * CELL, gallery.sprite_top(cy, len(sprite))
        _assert_drawn_in_its_halo(screen, sprite, px, py, n)
        _assert_plain_floor(screen, cx + 2, cy)


def _assert_drawn_in_its_halo(screen, sprite, px, py, label) -> None:
    """The sprite's ink is set, its halo is clear, and the stipple's own dots
    are where neither reaches."""
    from spikes import floor, lighting
    mask = sprites.MASK_OF[sprite]
    for dy, (row, halo) in enumerate(zip(sprite, mask)):
        # A row is one byte, or two for the body, which is the only thing
        # on the sheet that is sixteen pixels across.
        for octet, (bits, clear) in enumerate(
                zip(sprites.row_bytes(row), sprites.row_bytes(halo))):
            for dx in range(sprites.WIDTH):
                x = px + octet * sprites.WIDTH + dx
                dot = floor.dot_at(lighting.LIT, x, py + dy)
                want = (1 if bits & (0x80 >> dx) else
                        0 if clear & (0x80 >> dx) else
                        1 if dot else 0)
                assert screen.pixels[(py + dy) * SCREEN_W + x] == want, \
                    f"sprite {label} differs at ({dx}, {dy})"


def _assert_plain_floor(screen, cx, cy) -> None:
    """The cell is lit stipple and nothing else, in the block its position
    picks (issue #71)."""
    from spikes import floor, lighting
    for dy, bits in enumerate(floor.tile_at(lighting.LIT, cx, cy)):
        for dx in range(CELL):
            at = (cy * CELL + dy) * SCREEN_W + cx * CELL + dx
            assert screen.pixels[at] == (1 if bits & (0x80 >> dx) else 0)


def test_the_people_sheet_draws_every_frame_on_stipple_with_its_halo():
    """Every unique frame of every standing figure, where the layout says,
    on lit stipple inside its halo, with plain floor to the left of it; and
    the walk strip is the cycle `N A N B` twice, each stride twelve pixels
    on from the last -- the box and the four pixels the figure travelled --
    with plain floor before the first."""
    screen = Screen()
    gallery.draw_people_sheet(screen)
    entries = gallery.people_sheet_entries()
    drawn = {}
    for caption, sprite, px, py in entries:
        if caption is not None:
            drawn[sprite] = (px, py)
            _assert_drawn_in_its_halo(screen, sprite, px, py, caption)
            _assert_plain_floor(screen, px // CELL - 1, py // CELL)
    assert set(drawn) == set(sprites.FRAMES.values()), "a frame is missing"
    for name, top in gallery.people_rows():
        strip = [(sprite, px) for caption, sprite, px, py in entries
                 if caption is None and py == (top + 1) * CELL]
        if name == "worker":
            assert not strip, "the waiting worker does not walk"
            continue
        cycle = {"player": sprites.PLAYER_FRAMES,
                 "follower": sprites.FOLLOWER_FRAMES}[name]
        assert [sprite for sprite, _px in strip] == list(cycle) * 2
        xs = [px for _sprite, px in strip]
        assert xs[0] == gallery._STRIP_CX * CELL
        assert all(b - a == 12 for a, b in zip(xs, xs[1:])), xs
        _assert_plain_floor(screen, gallery._STRIP_CX - 1, top + 1)
        # The strides do not overlap: four pixels of floor between boxes.
        assert all(b - a - sprites.WIDTH == 4 for a, b in zip(xs, xs[1:]))
        # And every stride sits in its halo where it is drawn: the first
        # cell-aligned, the second half a cell across, and so on.
        for k, (sprite, px) in enumerate(strip):
            _assert_drawn_in_its_halo(screen, sprite, px, (top + 1) * CELL,
                                      f"{name} stride {k}")


def test_every_sprite_on_the_sheet_stands_on_its_own_caption():
    """Which name goes with which picture, and it is not obvious by accident.

    Three rows to a block leaves no blank row between one caption and the next
    block's sprite, so an object drawn at the top of its block sits nearer the
    name above it than the one below. Bottom-aligning every box on the row
    above its caption settles it, and keeps the size difference visible: a
    person fills both rows of the block, an object fills the lower one.
    """
    for n, (name, sprite) in enumerate(gallery.sheet_entries()):
        _cx, cy = gallery.block_at(n)
        bottom = gallery.sprite_top(cy, len(sprite)) + len(sprite)
        assert bottom == (cy + gallery._BLOCK_H - 1) * CELL, \
            f"{name} does not stand on its caption"


def test_the_sheet_shows_three_sizes_because_the_game_has_three():
    """**Size is how the game tells a person from a thing**, and since issue
    #59 **orientation is how it tells a person on their feet from one on the
    floor**. A sprite may not choose its own colour, so the boxes are the whole
    distinction, and a sheet that tidied everything to one size would hide the
    property the art most has to get right.

    A door is 8x16 without being a person, and the sheet shows that too: it is
    the person-shaped hole you walk out through, and it is the size it is for
    that reason.

    The body lies along the bottom of its block, sixteen across and eight down;
    the three figures that stand up are on the people sheet, in the same
    two-row box.
    """
    tall = {name for name in sprites.PEOPLE if name != "body"} \
        | set(sprites.DOORS)
    assert len(tall) == 10, "eight people frames and two doors"
    for name, sprite in sprites.SPRITES.items():
        want = (8, 16) if name in tall else (16, 8) if name == "body" else (8, 8)
        assert (sprites.width_of(sprite), len(sprite)) == want, name


def test_the_body_is_photographed_beside_somebody_standing_up():
    """**The picture the sprite sheet could not take** (issue #59).

    A corpse and a living figure in one frame, on the floor they are actually
    seen on, at the light the game gives them. On the sheet they are in
    different blocks with their names underneath, which is why three rounds of
    review passed a drawing a cold reader then misread twice in one session.

    What is asserted here is that the frame really contains the comparison:
    both figures, both lit, and the body wider than it is tall where the player
    is taller than he is wide. Whether it *reads* is a human's judgement and
    this test does not pretend to make it.
    """
    screen = gallery.body_room(scene.NEAR)
    # The picture is taken from a run the function makes itself, so the
    # geometry is read back off the screen rather than out of the session.
    inked = {(cx, cy)
             for cy in range(PLAY_ROWS) for cx in range(COLS)
             if any(screen.pixels[(cy * CELL + dy) * SCREEN_W + cx * CELL + dx]
                    for dy in range(CELL) for dx in range(CELL))}
    assert inked, "the picture is empty"
    # The player is somewhere in it, found by his lamp, helmet and kit: rows
    # 4 to 7 of his box, on whichever stride he is on, and nothing else in
    # the room draws them (issue #78; before it he was found by the top of
    # his box, and before #72 by the bar).
    heads = [list(zip(frame[4:8], sprites.MASK_OF[frame][4:8]))
             for frame in sprites.STANDING["player"]]
    players = [(px, py) for py in range(PLAY_ROWS * CELL - 4)
               for px in range(SCREEN_W - 8)
               if any(all(screen.point(px + dx, py + dy) == bool(row & (0x80 >> dx))
                          for dy, (row, halo) in enumerate(head)
                          for dx in range(8) if halo & (0x80 >> dx))
                      for head in heads)]
    assert players, "the player is not in the picture"
    # ...and a body: a run of ink sixteen pixels wide on one row of cells,
    # which no standing figure can make.
    wide = [(px, py) for py in range(PLAY_ROWS * CELL)
            for px in range(SCREEN_W - 16)
            if all(screen.point(px + dx, py) for dx in range(9))]
    assert wide, "there is no body in the picture"


def test_the_photographed_body_is_lit_enough_to_be_looked_at():
    """A body drawn on a dark cell is black ink on black paper.

    The function raises rather than returning that picture, and this is the
    assertion that says so -- a sheet nobody can check is worse than no sheet.
    """
    screen = gallery.body_room(scene.NEAR)
    # Ink that is the same as its paper shows nothing, so a picture of a body
    # needs at least one cell of play area whose ink differs from its paper.
    from spotlight.core.screen import unpack_attr
    visible = [cell for cell in range(COLS * PLAY_ROWS)
               if unpack_attr(screen.attrs[cell])[0]
               != unpack_attr(screen.attrs[cell])[1]]
    assert visible, "nothing in the play area is visible at all"


# --- the tile sheet ---------------------------------------------------------

def test_the_tile_sheet_shows_all_sixteen_masks_in_both_variants():
    """Every tile in the game, in mask order, read back off the screen.

    Issue #48. The sheet is how a reviewer sees the two things the slice is
    about: that a lit wall is made of something and a remembered one is a line,
    and that all sixteen masks are distinct. Read back rather than trusted,
    because a sheet drawn from a second copy of the tables could agree with
    itself and disagree with the game.
    """
    screen = Screen()
    gallery.draw_tile_sheet(screen)
    for n, table in enumerate((tiles.WALL_LIT, tiles.WALL_DIM,
                               tiles.DOORWAY)):
        top = gallery._TILE_TOP + n * gallery._TILE_BLOCK
        for mask, rows in enumerate(table):
            cx = mask * gallery._TILE_STEP
            for dy, bits in enumerate(rows):
                for dx in range(CELL):
                    want = 1 if bits & (0x80 >> dx) else 0
                    got = screen.pixels[((top + 1) * CELL + dy) * SCREEN_W
                                        + cx * CELL + dx]
                    assert got == want, \
                        f"variant {n}, mask {mask}, row {dy}"


def test_the_tile_sheet_plan_is_drawn_by_the_games_own_mask_arithmetic():
    """The joined-up plan at the bottom. It exists to show the seams, so it has
    to be built the way the game builds a room -- `tiles.mask_at` over a
    solidity test with off-the-plan counting as wall -- and not by hand."""
    screen = Screen()
    gallery.draw_tile_sheet(screen)
    for cy, row in enumerate(gallery.PLAN):
        for cx, char in enumerate(row):
            if char != "#":
                continue
            mask = tiles.mask_at(gallery.plan_is_wall, cx, cy)
            for top, table in ((gallery._PLAN_LIT_TOP, tiles.WALL_LIT),
                               (gallery._PLAN_DIM_TOP, tiles.WALL_DIM)):
                for dy, bits in enumerate(table[mask]):
                    for dx in range(CELL):
                        want = 1 if bits & (0x80 >> dx) else 0
                        got = screen.pixels[((top + cy) * CELL + dy)
                                            * SCREEN_W + cx * CELL + dx]
                        assert got == want, f"plan {(cx, cy)} row {dy}"


def test_the_tile_sheet_plan_has_a_doorway_in_it():
    """Room A's inner door is the case `d` was added for, so the sheet has to
    show one: a one-cell gap in a partition, with its returns."""
    assert any("d" in row for row in gallery.PLAN)
    screen = Screen()
    gallery.draw_tile_sheet(screen)
    for cy, row in enumerate(gallery.PLAN):
        for cx, char in enumerate(row):
            if char != "d":
                continue
            mask = tiles.mask_at(gallery.plan_is_wall, cx, cy)
            assert tiles.DOORWAY[mask] != (0,) * 8, \
                "the plan's doorway draws nothing, so it shows nothing"


# --- the rooms --------------------------------------------------------------

def test_getting_into_a_room_walks_through_the_door(monkeypatch):
    """**Not `run.here = 1`.** Entering a room notes the first entry, moves
    any fly riding the player and logs a crossing; a picture of a room the
    session was teleported into would be a picture of a state the game cannot
    reach. So the crossing is the real one, and the log says so."""
    run = gallery.session_mod.Session(seed=gallery.GALLERY_SEED)
    gallery.enter(run, scene.FAR)
    assert run.here == scene.FAR
    assert run.crossings == 1
    crossed = [e for e in run.log if e.kind == gallery.session_mod.CROSSED]
    assert len(crossed) == 1 and crossed[0].count == scene.FAR


def test_a_room_with_no_door_from_here_is_refused():
    """Two rooms is what the building has. If a third ever needs a route, this
    is where it will say so rather than quietly photographing the wrong room."""
    run = gallery.session_mod.Session(seed=1)
    try:
        gallery.enter(run, 99)
    except ValueError as refused:
        assert "no doorway" in str(refused)
    else:  # pragma: no cover - the failure we are asserting against
        raise AssertionError("it claimed to walk into a room that has no door")


def test_the_lit_shot_uses_the_games_own_reveal(monkeypatch):
    """`sources.Floodlight.hold`, the debug view the `F` key has used since the
    spike -- not a new draw-everything path.

    A second way to light a room is a second thing that can disagree with the
    game about what is in one, and these images are worth having only because
    they are what the game draws.
    """
    held = []
    real = sources.Floodlight.hold
    monkeypatch.setattr(sources.Floodlight, "hold",
                        lambda self, on: held.append(on) or real(self, on))
    gallery.room_screen(scene.NEAR, lit=True)
    assert held == [True], "the lit sheet did not go through Flash.hold"


def test_the_lit_shot_shows_the_whole_room_and_the_played_one_does_not():
    """The two pictures are for two questions: what did the designer draw, and
    what does a player actually see of it. If they came out the same, one of
    them is broken."""
    lit = gallery.room_screen(scene.NEAR, lit=True)
    played = gallery.room_screen(scene.NEAR, lit=False, stride=0)
    assert lit_cells(lit) > lit_cells(played) * 2


def _drawn_cell(screen: Screen, cx: int, cy: int) -> tuple:
    """What is actually in a cell, as eight bytes."""
    return tuple(
        sum(0x80 >> dx for dx in range(CELL)
            if screen.pixels[(cy * CELL + dy) * SCREEN_W + cx * CELL + dx])
        for dy in range(CELL))


def test_the_played_frame_shows_remembered_walls_as_lines():
    """**The picture nobody had taken** (issue #62).

    The user said the walls needed more texture and thought it was a render
    fault. It was not: with the torch off -- most of a run -- a wall beside
    you is the *remembered* tile, and the remembered tile was the outline
    alone. Every mock and every gallery frame before 2026-09-11 had the torch
    on, so the walls were only ever reviewed as masonry. The torch went
    (issue #119) and every played frame is that frame now; what remembers a
    wall is the beam (issue #117).

    Two things are asserted: at least one wall cell in the played frame is
    drawn as the *dim* tile its mask asks for and not the lit one; and that
    dim tile has its courses out of it, which is the change.
    """
    off = gallery.room_screen(scene.NEAR, lit=False)
    room = scene.BUILDING[scene.NEAR]
    remembered = []
    for cy in range(PLAY_ROWS):
        for cx in range(COLS):
            if not room.is_wall(cx, cy):
                continue
            mask = tiles.mask_at(room.is_wall, cx, cy)
            drawn = _drawn_cell(off, cx, cy)
            if drawn == tiles.WALL_DIM[mask] and drawn != tiles.WALL_LIT[mask]:
                remembered.append((cx, cy, mask))
    assert remembered, "no wall in the played frame is drawn remembered"
    # ...and the remembered tile is a line alone again (issue #101, Look and
    # feel 3 row 7): nothing on rows 1 and 5 between the side faces.
    for cx, cy, mask in remembered:
        assert tiles.WALL_DIM[mask][1] & 0x3C == 0 \
            and tiles.WALL_DIM[mask][5] & 0x3C == 0, \
            f"the remembered wall at {(cx, cy)} carries a course"


def test_no_sheet_shows_a_room_whole_but_the_lit_one():
    """Issue #79: the opening flash is gone, so the only whole-room picture
    the gallery can take is the held debug view, and it says so by going
    through `Floodlight.hold`. There is no flash frame to photograph."""
    assert not hasattr(gallery, "flash_room")
    assert not hasattr(gallery, "surge_screen")


def test_each_lit_room_is_the_room_it_is_named_after():
    """The walls in the picture are that room's walls, and nobody else's.

    This is the check that a sheet labelled "the far room" is not a second
    photograph of the near one -- which is exactly what teleporting `here`
    would have produced, silently and with a plausible picture.

    **It used to ask whether the cell was full**, because a wall was 64 pixels
    of ink. Issue #48 took that away: a lit wall is now the masonry tile its
    4-neighbour mask chooses, so the check is that every wall cell contains the
    tile its own mask asks for. That is a stronger claim than the old one -- it
    depends on the room's geometry cell by cell rather than merely on something
    being drawn -- and it is why it can be exact where the old one had to allow
    for three cells that the words punched through.

    A cell with a word painted on it draws the dim variant, and extra pixels
    are allowed on top of any of them: a person standing against a wall
    composites into it.
    """
    for index, room in enumerate(scene.BUILDING.rooms):
        run, screen = gallery.lit_room(index)
        painted = set(run.place.sign_cells) | set(run.call_cells)
        from spikes import building
        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                if not room.is_wall(cx, cy) \
                        or room.rows[cy][cx] in building.FURNITURE:
                    # Furniture draws its own tile (issues #74, #102).
                    continue
                mask = tiles.mask_at(room.is_wall, cx, cy)
                want = (tiles.WALL_DIM if (cx, cy) in painted
                        else tiles.WALL_LIT)[mask]
                assert cell_holds(screen, cx, cy, want), (
                    f"{room.name}: the wall at {(cx, cy)} is not the tile "
                    f"mask {mask} asks for")


def test_a_lit_room_draws_no_wall_where_it_has_floor():
    """The other direction, and it is what catches a picture of another room.

    A floor cell may hold stipple, a sprite, a word or a doorway's returns --
    all of them sparse. What it may never hold is a wall tile's outline, so
    this asks that no floor cell is anywhere near full.
    """
    for index, room in enumerate(scene.BUILDING.rooms):
        _run, screen = gallery.lit_room(index)
        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                if room.is_wall(cx, cy):
                    continue
                assert not cell_is_full(screen, cx, cy), \
                    f"{room.name}: {(cx, cy)} is floor and is drawn solid"


def test_the_two_rooms_do_not_photograph_the_same():
    lit = [bytes(gallery.room_screen(i, lit=True).pixels)
           for i in range(len(scene.BUILDING.rooms))]
    assert len(set(lit)) == len(lit)


def test_the_played_shot_waits_for_the_player_to_be_in_the_room():
    """**The bug this rule fixed**: the far room's first sheet was taken on the
    last frame of the sample, and on that frame the listener was mid-crossing
    at x=-6 -- a real frame of a real run, and a useless portrait of a room. A
    frame is only kept when the player is a clear cell inside both edges."""
    assert not gallery.standing_clear(_At(-6))
    assert not gallery.standing_clear(_At(0))
    assert gallery.standing_clear(_At(SCREEN_W // 2))
    assert not gallery.standing_clear(_At(SCREEN_W - CELL))


class _At:
    """A run with nothing in it but a player's x, which is all the framing
    rule looks at."""

    def __init__(self, x: int) -> None:
        self.player = type("P", (), {"x": x})()


def test_a_kept_frame_is_a_copy_and_not_a_view():
    """The play area is repainted every frame, so a frame that is not copied is
    gone by the time anybody saves it. This is why the sheet is a still."""
    screen = Screen()
    screen.plot(0, 0, True)
    still = gallery.copy_of(screen)
    screen.clear()
    assert still.pixels[0] == 1
    assert still.attrs[0] == gallery.copy_of(still).attrs[0]


# --- the two screens either side of the game --------------------------------

def test_the_ending_sheet_adds_up():
    """The counts on the ending screen are invented for the sheet, so they at
    least have to be a run that could have happened: everybody is accounted
    for, out, dead or still inside."""
    counts = gallery.ENDING_COUNTS
    assert counts["rescued"] + counts["lost"] + counts["inside"] == \
        counts["total"] == 7
    assert gallery.ENDING in gallery.session_mod.ENDING_TEXT


def test_the_title_is_photographed_in_both_flash_phases(tmp_path):
    """PRESS ANY KEY is a flashing cell, and a still can only show one half of
    the cycle. Both halves are in front of a real player, so both are in the
    gallery -- the prompt was once reviewed as though it were plain text."""
    paths = gallery.write(str(tmp_path))
    plain = next(p for p in paths if p.endswith("title_x1.png"))
    flashed = next(p for p in paths if p.endswith("title-flashed_x1.png"))
    assert (pygame.image.tostring(pygame.image.load(plain), "RGB")
            != pygame.image.tostring(pygame.image.load(flashed), "RGB"))


def test_the_title_sheet_shows_the_pool(tmp_path):
    """Issue #104: the pool is on the sheet a reviewer looks at, in the colour
    it is drawn in. One pool cell's first dot is found through `screens` and
    `floor`, and the pixel at that spot in `title_x1.png` is non-bright yellow
    -- the one colour nothing else on the title uses. Both flash phases carry
    it; the pool does not flash."""
    from spikes import floor, screens
    from spotlight.core.constants import YELLOW, rgb

    words = Screen()
    screens.draw_words(words)
    cx, cy = min(screens.pool_cells(words))
    block = floor.FLOOR_LIT[floor.tile_index(cx, cy)]
    dy = next(i for i, bits in enumerate(block) if bits)
    dx = next(i for i in range(CELL) if block[dy] & (0x80 >> i))
    x, y = cx * CELL + dx, cy * CELL + dy

    paths = gallery.write(str(tmp_path), scales=(1,))
    for name in ("title_x1.png", "title-flashed_x1.png"):
        image = pygame.image.load(next(p for p in paths if p.endswith(name)))
        assert tuple(image.get_at((x, y))[:3]) == rgb(YELLOW, bright=False), \
            name


def test_a_played_frame_with_a_flash_in_it(tmp_path):
    """Issue #52. A flash is two halves of a hardware cycle, so a still can only
    ever show one of them -- the same reason the title's prompt is photographed
    twice, and the same fault it was fixing: the first review of that screen
    read a flashing prompt as plain white text.

    The picture is of a freeing, and it is made by the game's own rules: the
    player is stood on a waiting worker, `Rescue.reach` frees them, and the
    session raises `M_FREED` over the two cells they were standing in.
    """
    screen = gallery.freed_room()
    play = COLS * PLAY_ROWS
    flashing = [i for i in range(play) if screen.attrs[i] & moments.FLASH_BIT]
    assert flashing, "the sheet has no flash on it to review"
    # In the play area and nowhere else: this is a moment, not a strip alert.
    assert not any(a & moments.FLASH_BIT for a in screen.attrs[play:])

    paths = gallery.write(str(tmp_path))
    stem = f"room-{gallery.slug(scene.BUILDING[scene.NEAR].name)}-freed"
    plain = next(p for p in paths if p.endswith(f"{stem}_x1.png"))
    flashed = next(p for p in paths if p.endswith(f"{stem}-flashed_x1.png"))
    assert (pygame.image.tostring(pygame.image.load(plain), "RGB")
            != pygame.image.tostring(pygame.image.load(flashed), "RGB"))


def test_the_gallery_is_the_same_pictures_every_time(tmp_path):
    """One seed, one set of files. A gallery that changed under you could not
    be used to review a change to the art, which is the only thing it is for."""
    first = gallery.write(str(tmp_path / "one"))
    second = gallery.write(str(tmp_path / "two"))
    for a, b in zip(first, second):
        assert open(a, "rb").read() == open(b, "rb").read(), a


# --- a level's rooms, three ways (issue #114) --------------------------------

def test_a_room_is_drawn_three_ways_and_they_differ():
    """Lit is everything under the floodlight; the flash is the strobe's one
    lit frame with the strip black and no fly in it; seen is frame one as
    the player has it, which shows less than either."""
    from spikes import levels
    lit = gallery.level_lit(1, 2)
    flash = gallery.level_flash(1, 2)
    seen = gallery.level_seen(1, 2)
    assert lit_cells(seen) < lit_cells(lit)
    assert lit_cells(seen) < lit_cells(flash)
    # The strip is black on the flash frame and drawn on the other two.
    strip = range(PLAY_ROWS * CELL * SCREEN_W, SCREEN_H * SCREEN_W)
    assert not any(flash.pixels[i] for i in strip)
    assert any(lit.pixels[i] for i in strip)
    assert any(seen.pixels[i] for i in strip)
    # The flash shows the room's worker but not its fly: Level 1's second
    # room has one of each.
    room = levels.level(1)[1]
    assert room.clegs and room.workers
    from spotlight.core.constants import BLACK, RED
    from spotlight.core.screen import attr_byte
    red = attr_byte(RED, BLACK, bright=True)
    assert not any(flash.attrs[cy * COLS + cx] == red
                   for cy in range(PLAY_ROWS) for cx in range(COLS)), \
        "a fly is in the flash"


def test_a_room_started_in_is_not_walked_to():
    """A room three doors from the exit costs nothing: the session starts
    there (issue #108) and no crossing is logged."""
    run = gallery.level_session(1, 2)
    assert run.here == 2 and run.crossings == 0


def test_the_level_sheets_go_through_spike_snap(tmp_path, monkeypatch):
    """Every PNG the level sheets write is one `spike_snap` wrote."""
    from spikes import spike_snap
    written = []
    real_save = spike_snap.save
    real_strip = spike_snap.save_strip
    monkeypatch.setattr(spike_snap, "save",
                        lambda *a, **k: written.append(real_save(*a, **k))
                        or written[-1])
    monkeypatch.setattr(spike_snap, "save_strip",
                        lambda *a, **k: written.append(real_strip(*a, **k))
                        or written[-1])
    paths = gallery.write_level(str(tmp_path), 3)
    assert sorted(paths) == sorted(written)
    names = {p.rsplit("/", 1)[-1] for p in paths}
    assert names == {f"3-{i}-{k}_x{s}.png" for i in (1, 2)
                     for k in ("lit", "flash", "seen") for s in (1, 3)} \
        | {"3-plan_x2.png"}
    # The strip is the two rooms side by side with a one-pixel gutter, at x2.
    import pygame
    strip = pygame.image.load(str(tmp_path / "3-plan_x2.png"))
    assert strip.get_size() == ((SCREEN_W * 2 + 1) * 2, SCREEN_H * 2)


def test_the_gallery_command_line_takes_a_level(tmp_path, capsys):
    assert gallery.main(["--level", "1", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "1-plan_x2.png").exists()
    assert gallery.main(["--level", "0", "--out", str(tmp_path)]) == 2
    assert "no level 0" in capsys.readouterr().err


def test_a_rolled_level_is_drawn_for_a_seed(tmp_path):
    """Issue #125: two seeds give two different lit pictures of a level's
    first room; the same seed twice gives the same bytes; the seed names
    the directory."""
    a = gallery.level_lit(1, 0, seed=1)
    b = gallery.level_lit(1, 0, seed=1)
    c = gallery.level_lit(1, 0, seed=2)
    assert bytes(a.pixels) == bytes(b.pixels)
    assert bytes(a.pixels) != bytes(c.pixels)
    assert gallery.main(["--level", "1", "--seed", "2",
                         "--out", str(tmp_path / "g")]) == 0
    assert (tmp_path / "g-seed-2" / "1-plan_x2.png").exists()
    # And Level 4 and on draws the re-rolled Level 3.
    assert gallery.main(["--level", "5", "--out", str(tmp_path / "h")]) == 0
    assert (tmp_path / "h" / "5-2-seen_x1.png").exists()
