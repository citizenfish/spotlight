"""One command that writes everything somebody judging the look has to see.

Issue #45. The look-and-feel round asks two playtester agents and the user to
have an opinion about the art, and until now the only way to see any of it was
to be sitting at the user's keyboard. `--snap` on the driver photographs a run;
this is the other half -- the things that are **not** a run and would otherwise
never be photographed at all: the two screens either side of the game, the
sprites at the size they are actually drawn, and each room both fully lit and
as it looks when you are in it with a torch.

Three choices worth stating, because each of them is the sheet being useful
rather than merely correct:

* **The lit shots use `sources.Flash.hold`**, the debug reveal the `F` key has
  used since the spike, rather than a new "draw everything" path. A second way
  to light a room is a second thing that can disagree with the game about what
  is in the room -- and the whole value of these images is that they are what
  the game draws.
* **The played shots hold the torch on.** With it off the honest picture is
  very nearly a black rectangle, which is true to the game and no use for
  judging art; the dark is reviewed from a run's own `--snap` frames, where it
  belongs.
* **The ending screen's numbers are invented, and deliberately.** They are
  chosen to fill every row -- somebody out, somebody dead, somebody still
  inside, and a time with two digits in the minutes place -- so the sheet shows
  the layout under load. Taking them from a real run instead would repaint this
  image every time a constant moved, and a gallery whose files churn is a
  gallery nobody can diff between rounds.

Host-side, named `spike_*` so the portability suite exempts it: it exists to
make PNGs for people, and nothing on a Spectrum will ever run it.

The tile sheet arrived with issue #48: every wall and doorway tile at both
light levels, and a joined-up plan drawn through the real mask arithmetic, so
that a seam in the masonry is visible in a picture rather than only findable by
somebody counting pixels.
"""

import os

from spotlight.core.constants import (
    BLACK, CELL, CYAN, ROWS, SCREEN_H, SCREEN_W, WHITE, YELLOW,
)
from spotlight.core.screen import Screen, attr_byte

from . import bots, screens, scene, session as session_mod, sprites, tiles
from . import spike_snap
from .building import EAST

#: How many frames into a run the "as played" shot of a room is taken.
#: Six seconds: long enough that the opening flash has faded and the swarm has
#: started moving, short enough that the torch is still lit.
PLAYED_FRAMES = 300

#: The seed every gallery run uses, so the same command twice writes the same
#: pictures. A gallery that changed under you could not be used to review a
#: change to the art.
GALLERY_SEED = 1

#: The ending the sheet shows, and the counts underneath it. See the module
#: docstring for why these are invented rather than played.
ENDING = session_mod.NO_LIVES
ENDING_COUNTS = dict(rescued=2, lost=4, inside=1, total=7, seconds=154)


def _attr(ink: int, bright: bool = False) -> int:
    return attr_byte(ink=ink, paper=BLACK, bright=bright)


# --- the sprite sheet -------------------------------------------------------

#: Blocks across the sheet. Three fits the longest name (FOLLOWER, eight cells)
#: with a gap either side inside thirty-two columns.
_ACROSS = 3
_BLOCK_W = 10
_BLOCK_H = 4
_LEFT = 1
_TOP = 3


def draw_sprite_sheet(screen: Screen) -> None:
    """Every sprite in the game, on a grid, named in the game's own font.

    **The sizes are shown, not stated.** Each block is two cell rows tall, so
    the 8x16 people fill it and the 8x8 objects fill half of it, and the
    difference between a person and a thing is visible in the picture rather
    than only in the caption. That difference is load-bearing -- `sprites` tells
    entities apart by size first and silhouette second, because a sprite may not
    choose its own colour -- so a sheet that lined everything up neatly would be
    hiding the one property the art has to get right.

    Labelled in the game's font rather than anything prettier, for the same
    reason the rest of the sheet is drawn through `core.Screen`: what a reviewer
    is looking at has to be made of the things the Spectrum can make.
    """
    screen.clear(_attr(WHITE))
    heading = "SPRITE SHEET"
    screens.write(screen, screens.centre(heading), 1, heading, YELLOW,
                  bright=True)

    for n, (name, sprite) in enumerate(sprites.SPRITES.items()):
        cx = _LEFT + (n % _ACROSS) * _BLOCK_W
        cy = _TOP + (n // _ACROSS) * _BLOCK_H
        # Three cells in, so the 8-pixel sprite sits over the middle of its
        # caption rather than at one end of it.
        px, py = (cx + 3) * CELL, cy * CELL
        # clip_bottom is the play area's floor in the game and there is no play
        # area here, so it is opened up to the whole screen; without that the
        # bottom row of the grid would be cut off mid-sprite.
        sprites.draw(screen, sprite, px, py, clip_bottom=SCREEN_H)
        people = name in sprites.PEOPLE
        for scx, scy in sprites.cells_spanned(px, py, len(sprite)):
            screen.set_attr(scx, scy, _attr(WHITE, bright=True))
        screens.write(screen, cx, cy + 2, name.upper(),
                      YELLOW if people else CYAN, bright=True)

    legend = (("YELLOW - PEOPLE, 8X16", YELLOW),
              ("CYAN - OBJECTS, 8X8", CYAN))
    for i, (line, ink) in enumerate(legend):
        screens.write(screen, screens.centre(line), ROWS - 3 + i, line, ink,
                      bright=True)


# --- the tile sheet ---------------------------------------------------------

#: The plan at the bottom of the tile sheet, drawn once lit and once dim.
#:
#: **It is there to show the seams**, and it is chosen so that every one of them
#: is in the picture: borders four cells deep so that there are interior cells
#: with masonry on all four sides and joints that have to line up across a cell
#: boundary in both axes, a void so that faces and end caps are drawn, and a
#: one-cell-thick partition with a `d` gap in it, which is the case the doorway
#: character was added for -- room A's inner door. If the masonry ever stops
#: tiling, it shows here as a broken course or a doubled joint.
PLAN = (
    "################################",
    "####.........d..............####",
    "####.........#..............####",
    "################################",
)

#: Where the plan is drawn: lit first, then the same plan remembered.
_PLAN_LIT_TOP = ROWS - 8
_PLAN_DIM_TOP = ROWS - 4

#: The tile rows: a label, the sixteen tiles two columns apart, and the mask
#: number under each in hexadecimal -- one character, because a tile is one
#: cell wide and a two-digit label would not sit under it.
_TILE_TOP = 3
_TILE_BLOCK = 4
_TILE_STEP = 2


def plan_is_wall(cx: int, cy: int) -> bool:
    """`PLAN`'s solidity, with **off the plan counting as wall**.

    The same rule a room follows, written out here rather than borrowed, so
    that the sheet is drawn by the same mask arithmetic the game uses and can
    disagree with it if it ever breaks.
    """
    if not (0 <= cy < len(PLAN) and 0 <= cx < len(PLAN[0])):
        return True
    return PLAN[cy][cx] == "#"


def draw_plan(screen: Screen, top: int, table, doorways: bool = True) -> None:
    """One copy of the plan, drawn with `table` for its walls."""
    for cy, row in enumerate(PLAN):
        for cx, char in enumerate(row):
            mask = tiles.mask_at(plan_is_wall, cx, cy)
            if char == "#":
                rows = table[mask]
            elif char == "d" and doorways:
                rows = tiles.DOORWAY[mask]
            else:
                continue
            tiles.blit(screen, cx, top + cy, rows)
            screen.set_attr(cx, top + cy,
                            _attr(WHITE, bright=table is tiles.WALL_LIT))


def draw_tile_sheet(screen: Screen) -> None:
    """Every wall and doorway tile, and a plan built out of them.

    Three things a reviewer has to be able to see and could not before:

    * **that all sixteen masks are distinct in both variants** -- an earlier
      masonry interior put a mortar course on row 7, which made *south open*
      invisible and collapsed four pairs of masks onto each other;
    * **that a remembered wall is a line and a lit one is made of something**,
      which is the whole of the slice, side by side and at the same size; and
    * **that the masonry has no seam in either axis**, which no table of bytes
      will ever show anybody.
    """
    screen.clear(_attr(WHITE))
    heading = "TILE SHEET"
    screens.write(screen, screens.centre(heading), 1, heading, YELLOW,
                  bright=True)

    variants = (("WALL, LIT - OUTLINE AND MASONRY", tiles.WALL_LIT, True),
                ("WALL, DIM - THE OUTLINE ALONE", tiles.WALL_DIM, False),
                ("DOORWAY - RETURNS INTO A GAP", tiles.DOORWAY, True))
    for n, (label, table, bright) in enumerate(variants):
        top = _TILE_TOP + n * _TILE_BLOCK
        screens.write(screen, 0, top, label, CYAN, bright=True)
        for mask in range(len(table)):
            cx = mask * _TILE_STEP
            tiles.blit(screen, cx, top + 1, table[mask])
            screen.set_attr(cx, top + 1, _attr(WHITE, bright=bright))
            # The mask in hexadecimal, so it is one character and sits under
            # its own tile. The tiles are in mask order, which is the whole
            # reason the game needs no lookup, and the labels say so.
            screens.write(screen, cx, top + 2, f"{mask:X}", YELLOW)

    label = "JOINED UP: LIT, THEN REMEMBERED"
    screens.write(screen, 0, _PLAN_LIT_TOP - 1, label, CYAN, bright=True)
    draw_plan(screen, _PLAN_LIT_TOP, tiles.WALL_LIT)
    draw_plan(screen, _PLAN_DIM_TOP, tiles.WALL_DIM)


# --- the rooms --------------------------------------------------------------

def enter(run, index: int):
    """Get the player into room `index`, by walking through the door.

    Teleporting `here` would be one line, and it would be a picture of a room
    the game never put the player in: entering a room fires its opening flash,
    migrates any fly riding the player, and logs the crossing. So the player is
    stood in the doorway -- which is the same convenience the doorway tests use
    -- and then *walks*, and every rule about arriving somewhere runs.

    Only rooms with a door straight from the one the run starts in can be
    reached this way. The playtest building is two rooms and that is enough;
    a third room reached only through a second would need a route, and the day
    that exists is the day to write one.
    """
    if run.here == index:
        return run
    door = scene.BUILDING[run.here].doorway_to(index)
    if door is None:
        raise ValueError(
            f"no doorway from room {run.here} to room {index}; "
            "the gallery cannot walk somewhere it cannot walk")
    run.player.x = door.column * CELL
    run.player.y = (door.middle - 1) * CELL
    facing = 1 if door.side == EAST else -1
    for _ in range(32):
        run.step(session_mod.Intent(dx=facing))
        if run.here == index:
            return run
    raise RuntimeError(f"the player would not walk into room {index}")


def lit_room(index: int) -> tuple:
    """One room fully revealed, as `(run, screen)`.

    The run comes back as well as the picture because what is *painted* on a
    wall -- the exit sign, and anybody shouting -- is a property of the frame
    and not of the room, and a caller checking the walls has to know which
    cells were painted over. Nothing else needs it, which is why `room_screen`
    keeps the simpler signature.
    """
    run = session_mod.Session(seed=GALLERY_SEED)
    enter(run, index)
    screen = Screen()
    # The debug reveal, held: the room and everybody in it, which is what a
    # reviewer needs and what the player is deliberately never given.
    run.place.opening.hold(True)
    run.step()
    run.draw(screen)
    return run, screen


def room_screen(index: int, lit: bool, frames: int = PLAYED_FRAMES) -> Screen:
    """One room, drawn: fully revealed, or as it looks after `frames` of play.

    A fresh session each time. Sharing one would mean the second picture was of
    a building the first had already spent a torch and a swarm on, and a shot
    labelled "the far room" would quietly be a shot of the far room *after the
    near one had gone wrong*.
    """
    if lit:
        return lit_room(index)[1]
    run = session_mod.Session(seed=GALLERY_SEED)
    enter(run, index)
    screen = Screen()

    bot = bots.make("listener", seed=GALLERY_SEED, light=True)
    kept = None
    for _ in range(frames):
        run.step(bot.intent(run))
        if run.over is not None:
            break
        # The bot is free to walk back out of the room it was put in, and the
        # picture has to be of the room on the label. Walking it back in costs
        # a crossing and nothing else.
        if run.here != index:
            enter(run, index)
            continue
        run.draw(screen)
        if standing_clear(run):
            kept = copy_of(screen)
    # **The last frame with the player wholly on screen, not simply the last
    # frame.** The listener spends a good part of a sample stood in the doorway
    # deciding, and mid-crossing the figure is half off the edge -- the first
    # version of this sheet photographed the far room with the player at x=-6,
    # which is a real frame of a real run and a useless portrait of a room.
    return kept if kept is not None else copy_of(screen)


def standing_clear(run) -> bool:
    """Is the player far enough from the edges to be a picture of a room?

    A cell in from either side. Only a framing rule -- it decides which frame is
    photographed and nothing about the frame itself.
    """
    return CELL <= run.player.x <= SCREEN_W - 2 * CELL


def copy_of(screen: Screen) -> Screen:
    """A still of a screen. The play area is repainted every frame, so a frame
    that is not copied is gone by the time anybody wants it."""
    still = Screen()
    still.pixels[:] = screen.pixels
    still.attrs[:] = screen.attrs
    return still


def slug(name: str) -> str:
    """A room's name as a filename: 'the far room' -> 'the-far-room'."""
    return "-".join(name.lower().split())


# --- the whole gallery ------------------------------------------------------

def write(out_dir: str, scales=spike_snap.DEFAULT_SCALES) -> list[str]:
    """Write every sheet into `out_dir`. Returns the paths, in order written.

    The order is the order somebody should look at them in: the screen the
    player sees first, the screen they see last, the cast, then the rooms.
    """
    os.makedirs(out_dir, exist_ok=True)
    paths: list[str] = []

    def sheet(name: str, screen: Screen, flashing: bool = False) -> None:
        paths.extend(spike_snap.save_scales(
            screen, os.path.join(out_dir, name), scales, flashing))

    title = Screen()
    screens.draw_title(title)
    sheet("title", title)
    # The same screen with the flash bit inverted, because PRESS ANY KEY is a
    # flashing cell and a still can only ever show one half of the cycle. Both
    # halves are on screen in front of a real player, so both are in the
    # gallery -- the first time this was written, the prompt was reviewed as
    # though it were plain white text.
    sheet("title-flashed", title, flashing=True)

    ending = Screen()
    screens.draw_ending(ending, session_mod.ENDING_TEXT[ENDING],
                        **ENDING_COUNTS)
    sheet("ending", ending)

    sheet_screen = Screen()
    draw_sprite_sheet(sheet_screen)
    sheet("sprites", sheet_screen)

    tile_screen = Screen()
    draw_tile_sheet(tile_screen)
    sheet("tiles", tile_screen)

    for index, room in enumerate(scene.BUILDING.rooms):
        sheet(f"room-{slug(room.name)}-lit", room_screen(index, lit=True))
        sheet(f"room-{slug(room.name)}-played", room_screen(index, lit=False))
    return paths
