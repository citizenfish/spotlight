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

from spikes import scene, sources, sprites, spike_gallery as gallery, tiles
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
    for sheet in ("title", "title-flashed", "ending", "sprites", "tiles"):
        assert f"{sheet}_x1.png" in names and f"{sheet}_x3.png" in names
    for room in scene.BUILDING.rooms:
        stem = f"room-{gallery.slug(room.name)}"
        assert f"{stem}-lit_x1.png" in names
        assert f"{stem}-played_x1.png" in names
    # The one frame that is set up rather than played: a spotlight burning
    # where somebody put it down. No bot has ever swapped one.
    swapped = f"room-{gallery.slug(scene.BUILDING[scene.NEAR].name)}-swapped"
    assert f"{swapped}_x1.png" in names and f"{swapped}_x3.png" in names
    assert len(paths) == len(names) == 12 + 4 * len(scene.BUILDING.rooms)


def test_every_sheet_is_written_at_both_scales(tmp_path):
    """1:1 is the honest view of the pixels and x3 is the one a person can
    look at. A gallery of one or the other loses an argument it should not."""
    for path in gallery.write(str(tmp_path)):
        size = pygame.image.load(path).get_size()
        expect = (SCREEN_W, SCREEN_H) if path.endswith("_x1.png") else \
            (SCREEN_W * 3, SCREEN_H * 3)
        assert size == expect, path


# --- the sprite sheet -------------------------------------------------------

def test_the_sprite_sheet_names_every_sprite():
    """Every entry in `sprites.SPRITES`, labelled, read back off the screen.

    Read back rather than compared against the constants, because a caption
    list that agreed with itself and drew nothing would pass -- and a sprite
    added to the game and left off the sheet is exactly the drift the sheet
    exists to prevent.
    """
    screen = Screen()
    gallery.draw_sprite_sheet(screen)
    text = " ".join(screenreader.rows(screen))
    for name in sprites.SPRITES:
        assert gallery.label(name) in text, f"{name} is not named on the sheet"


def test_no_caption_on_the_sprite_sheet_runs_over_its_block():
    """**The sheet is where art is named**, so a name that printed over its
    neighbour would take out the only thing on it that is not a picture.

    Thirty-two columns, three blocks, and DOOR LOCKED is eleven characters --
    which fits only in the right-hand block, where the last column of the
    screen is going spare. `sprites.SPRITES` is ordered to put it there. This
    is what fails if somebody inserts a sprite ahead of it without a thought
    about the layout.
    """
    for n, name in enumerate(sprites.SPRITES):
        cx, _cy = gallery.block_at(n)
        width = gallery.block_width(n)
        assert len(gallery.label(name)) <= width, \
            f"{name} needs {len(gallery.label(name))} columns and has {width}"
        assert cx + width <= COLS, f"{name}'s block runs off the screen"


def test_the_sprite_sheet_fits_between_its_heading_and_its_legend():
    """Fourteen entries at three across is five rows, and the sheet has to
    hold them without printing into the legend at the bottom."""
    rows = -(-len(sprites.SPRITES) // gallery._ACROSS)
    last = gallery._TOP + rows * gallery._BLOCK_H
    assert last <= ROWS - 3, f"the sheet needs {last} rows and has {ROWS - 3}"


def test_the_sprite_sheet_draws_every_sprite():
    """The picture, not only the caption. Each block has the sprite's own
    pixels in it."""
    screen = Screen()
    gallery.draw_sprite_sheet(screen)
    for n, sprite in enumerate(sprites.SPRITES.values()):
        cx, cy = gallery.block_at(n)
        px, py = (cx + 3) * CELL, gallery.sprite_top(cy, len(sprite))
        for dy, bits in enumerate(sprite):
            for dx in range(sprites.WIDTH):
                want = 1 if bits & (0x80 >> dx) else 0
                got = screen.pixels[(py + dy) * SCREEN_W + px + dx]
                assert got == want, f"sprite {n} differs at row {dy}"


def test_every_sprite_on_the_sheet_stands_on_its_own_caption():
    """Which name goes with which picture, and it is not obvious by accident.

    Three rows to a block leaves no blank row between one caption and the next
    block's sprite, so an object drawn at the top of its block sits nearer the
    name above it than the one below. Bottom-aligning every box on the row
    above its caption settles it, and keeps the size difference visible: a
    person fills both rows of the block, an object fills the lower one.
    """
    for n, (name, sprite) in enumerate(sprites.SPRITES.items()):
        _cx, cy = gallery.block_at(n)
        bottom = gallery.sprite_top(cy, len(sprite)) + len(sprite)
        assert bottom == (cy + gallery._BLOCK_H - 1) * CELL, \
            f"{name} does not stand on its caption"


def test_the_people_get_twice_the_height_of_the_objects():
    """**Size is how the game tells a person from a thing** -- a sprite may not
    choose its own colour, so 8x16 against 8x8 is the whole distinction. A
    sheet that tidied everything to one size would hide the property the art
    most has to get right.

    A door is 8x16 without being a person, and the sheet shows that too: it is
    the person-shaped hole you walk out through, and it is the size it is for
    that reason.
    """
    tall = set(sprites.PEOPLE) | set(sprites.DOORS)
    for name, sprite in sprites.SPRITES.items():
        assert len(sprite) == (16 if name in tall else 8), name


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
    """**Not `run.here = 1`.** Entering a room fires its opening flash, moves
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
    """`sources.Flash.hold`, the debug view the `F` key has used since the
    spike -- not a new draw-everything path.

    A second way to light a room is a second thing that can disagree with the
    game about what is in one, and these images are worth having only because
    they are what the game draws.
    """
    held = []
    real = sources.Flash.hold
    monkeypatch.setattr(sources.Flash, "hold",
                        lambda self, on: held.append(on) or real(self, on))
    gallery.room_screen(scene.NEAR, lit=True)
    assert held == [True], "the lit sheet did not go through Flash.hold"


def test_the_lit_shot_shows_the_whole_room_and_the_played_one_does_not():
    """The two pictures are for two questions: what did the designer draw, and
    what does a player actually see of it. If they came out the same, one of
    them is broken."""
    lit = gallery.room_screen(scene.NEAR, lit=True)
    played = gallery.room_screen(scene.NEAR, lit=False)
    assert lit_cells(lit) > lit_cells(played) * 2


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
        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                if not room.is_wall(cx, cy):
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


def test_the_gallery_is_the_same_pictures_every_time(tmp_path):
    """One seed, one set of files. A gallery that changed under you could not
    be used to review a change to the art, which is the only thing it is for."""
    first = gallery.write(str(tmp_path / "one"))
    second = gallery.write(str(tmp_path / "two"))
    for a, b in zip(first, second):
        assert open(a, "rb").read() == open(b, "rb").read(), a
