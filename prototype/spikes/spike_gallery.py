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

Issue #49 added the fourth room shot, and it is the one thing here that is set
up rather than played. **`LAMP_ON` cannot be photographed from a bot run**:
every authored spotlight starts unlit, a floor light only lights by being
swapped for a burning one, and `spotlight_swaps` is 0 in every run any bot has
ever made. `swapped_room` makes the swap happen with the game's own rule and
the game's own code rather than lighting one in the level data, which would be
a change to where the light in this building is. **And the sheet is where art
is named, not where it is judged** -- both faults that slice fixed passed on a
black-paper sprite sheet and failed on a lit floor, because a floor stipple is
itself a fill, so the room shots are what a reviewer looks at.
"""

import os

from spotlight.core.constants import (
    BLACK, CELL, COLS, CYAN, ROWS, SCREEN_H, SCREEN_W, WHITE, YELLOW,
)
from spotlight.core.screen import Screen, attr_byte

from . import bots, moments, player as player_mod, screens, scene, sprites
from . import session as session_mod, tiles
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

#: Blocks across the sheet, and how big each is in cells.
#:
#: Three across at ten wide leaves the right-hand block eleven columns of the
#: thirty-two, which is what DOOR LOCKED needs -- `sprites.SPRITES` is ordered
#: so the door pair lands there, and `test_spike_gallery` fails if a caption
#: ever overruns its block. Three rows per block: two for the sprite, because
#: the 8x16 ones fill both, and one for its name underneath.
#:
#: The blank row the blocks used to carry went when the sheet grew from eight
#: entries to fourteen. Fourteen is five rows of three, which needs every row
#: between the heading and the legend.
_ACROSS = 3
_BLOCK_W = 10
_BLOCK_H = 3
_LEFT = 1
_TOP = 3


def block_at(n: int) -> tuple[int, int]:
    """Where the nth entry's block starts, in cells."""
    return (_LEFT + (n % _ACROSS) * _BLOCK_W,
            _TOP + (n // _ACROSS) * _BLOCK_H)


def block_width(n: int) -> int:
    """How many columns the nth entry's caption may use.

    The last block in a row gets whatever is left of the screen, which is one
    column more than the others -- and that column is the difference between
    DOOR LOCKED fitting and printing over its neighbour.
    """
    if n % _ACROSS == _ACROSS - 1:
        return COLS - (_LEFT + (_ACROSS - 1) * _BLOCK_W)
    return _BLOCK_W


def sprite_top(cy: int, height: int) -> int:
    """The y, in pixels, of a sprite of that height in a block starting at `cy`.

    **Every sprite stands on its own caption**: the box's bottom edge is the
    row above the name, whatever height the box is. An 8x16 figure therefore
    fills both rows of the block and an 8x8 object fills the lower one.

    Top-aligning them was tried first and read wrong. With three rows to a
    block, a top-aligned 8x8 object sits one row under the *previous* block's
    caption and two rows above its own, so the eye pairs it with the wrong
    name -- which on the one sheet in the game whose job is naming things is
    the whole of the job.
    """
    return (cy + _BLOCK_H - 1) * CELL - height


def label(name: str) -> str:
    """What an entry is called on the sheet.

    The key from `sprites.SPRITES`, upper-cased, with the underscore as a
    space, because the game's font has no underscore in it and a missing glyph
    would print as the error block.
    """
    return name.upper().replace("_", " ")


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
        cx, cy = block_at(n)
        # Three cells in, so the 8-pixel sprite sits over the middle of its
        # caption rather than at one end of it.
        px, py = (cx + 3) * CELL, sprite_top(cy, len(sprite))
        # clip_bottom is the play area's floor in the game and there is no play
        # area here, so it is opened up to the whole screen; without that the
        # bottom row of the grid would be cut off mid-sprite.
        sprites.draw(screen, sprite, px, py, clip_bottom=SCREEN_H)
        people = name in sprites.PEOPLE
        for scx, scy in sprites.cells_spanned(px, py, len(sprite)):
            screen.set_attr(scx, scy, _attr(WHITE, bright=True))
        screens.write(screen, cx, cy + 2, label(name),
                      YELLOW if people else CYAN, bright=True)

    legend = (("YELLOW - PEOPLE, 8X16", YELLOW),
              ("CYAN - OBJECTS 8X8, DOORS 8X16", CYAN))
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


#: How far the player walks off the light they have just put down, so that the
#: burning lamp is photographed rather than the player's boots. Three cells is
#: clear of an 8x16 figure and still inside the pool it is making.
SWAP_STEPS = 24

#: And how long to stand there afterwards. The opening flash lights the whole
#: room and the memory of it takes about three seconds to go out, so a frame
#: taken straight after the swap is a picture of a fully lit room with a lamp
#: in it -- which shows the sprite and hides the thing the sprite is for. Held
#: until the flash has faded, so what is on screen is the pool the lamp itself
#: is making.
SWAP_SETTLE = 200


def swapped_room(index: int = scene.NEAR) -> Screen:
    """A spotlight **burning on the floor**, which no bot has ever produced.

    `LAMP_ON` cannot be photographed from a played run and that is a fact about
    the game rather than about the gallery: every authored spotlight starts
    unlit, a floor light only lights by being swapped for a burning one, and
    `spotlight_swaps` is 0 in every run any bot has ever made. So the picture
    is set up here instead.

    **Nothing about the level moves to get it.** Lighting one in the level data
    would be a change to where the light in this building is, which is a
    level-design dial and a gameplay change this round forbids. What happens
    instead is the game's own swap rule, fired by the game's own code: the
    player is stood on the room's first authored spotlight -- the same
    convenience `enter` uses to stand them in a doorway -- the torch is
    switched on, and `Spotlights.tick` leaves the burning light behind exactly
    as it would if somebody had walked there. Then the player walks off it, so
    the lamp is not underneath a figure.

    It raises rather than returning a picture of nothing if the swap does not
    happen, because a sheet that quietly showed an unlit spare would be worse
    than no sheet at all -- it is the one image on it nobody can check against
    a run.
    """
    run = session_mod.Session(seed=GALLERY_SEED)
    enter(run, index)
    lights = [l for l in run.kit.floor if l.room == index]
    if not lights:
        raise ValueError(f"room {index} authors no spotlight to swap")
    light = lights[0]
    # Standing on it: x is the cell, y is the cell the *feet* are in.
    run.player.x = light.cx * CELL
    run.player.y = (light.cy + 1) * CELL - player_mod.HEIGHT
    run.step(session_mod.Intent(torch=True))
    if not light.burning:
        raise RuntimeError(
            "the swap did not leave a burning light on the floor, so there is "
            "nothing here to photograph")
    for _ in range(SWAP_STEPS):
        run.step(session_mod.Intent(dx=1))
    for _ in range(SWAP_SETTLE):
        run.step()
    screen = Screen()
    run.draw(screen)
    return screen


#: Frames of ordinary play before the freeing, so that the room has been lit
#: once and is remembered. **A moment tests the light when it is raised**, and
#: on frame one no light has been cast at all -- the field is built at the end
#: of a step -- so a freeing on the first frame would raise no flash and the
#: sheet would be a picture of the rule working, captioned as a picture of it
#: failing.
FREE_SETTLE = 20

#: And how many frames after it the picture is taken, out of the flash's
#: sixteen. Enough that the player has walked off the cells and the flash is
#: visibly *where it happened* rather than where anybody is standing.
FREE_WALK = 10


def freed_room(index: int = scene.NEAR) -> Screen:
    """A moment's flash, on a played frame, set up the way a swap is.

    Issue #52. A flash is the one thing on screen that a still cannot show by
    itself -- it is two halves of a hardware cycle -- so the gallery writes both
    halves of one, exactly as it has done for the title screen's prompt since
    that prompt was first reviewed as though it were plain white text.

    **Nothing about the level or the rules moves to get it.** The player is
    stood on a waiting worker -- the same convenience `enter` uses to stand them
    in a doorway -- and then the game's own `Rescue.reach` frees them and the
    session's own `_moment` raises `M_FREED` over the two cells they were
    standing in. Then the player walks away from those cells, which is the
    picture worth having: **a flash marks where a thing happened and follows
    nothing**, so the two cells go on flashing behind them.

    It raises rather than returning a picture of nothing if the freeing does not
    happen, for the same reason `swapped_room` does: a sheet that quietly showed
    an ordinary frame would be the one image on it nobody could check.
    """
    run = session_mod.Session(seed=GALLERY_SEED)
    enter(run, index)
    for _ in range(FREE_SETTLE):
        run.step()
    waiting = run.rescue.alive_waiting(index)
    if not waiting:
        raise ValueError(f"room {index} has nobody waiting to be freed")
    worker = waiting[0]
    run.player.x, run.player.y = worker.x, worker.y
    # The torch goes on in the same step, because the picture is of a lit room
    # and because the sheet's other played shots hold it on too.
    run.step(session_mod.Intent(torch=True))
    raised = [name for name, _cells in run.moments.raised]
    if moments.M_FREED not in raised:
        raise RuntimeError(
            "nobody was freed, so there is no moment here to photograph")
    for _ in range(FREE_WALK):
        run.step(session_mod.Intent(dx=1))
    screen = Screen()
    run.draw(screen)
    if not any(attr & moments.FLASH_BIT for attr in screen.attrs):
        raise RuntimeError(
            "the flash had gone by the time the picture was taken")
    return screen


#: How long the gallery will play a run looking for a frame with a nest on it.
#:
#: A nest is a body twenty seconds after a death, so it is the one thing on the
#: surge plan that a run has to be played *into* rather than set up: the statue
#: on the gallery seed turns its first at frame 4,000. The limit is generous
#: rather than tight because what it guards against is an infinite loop, not a
#: slow one -- and if the game ever stops producing a nest in two minutes of
#: play, that is a finding rather than a broken sheet.
SURGE_LIMIT = 6000


def surge_screen() -> Screen:
    """The mains surge, on a played frame: the whole building plan.

    Issue #53. **The one picture in the game that shows both rooms at once**,
    and the beat the whole memorisation premise rests on -- so the sheet has to
    show it with something in it. A plan of two empty rooms would be a picture
    of the geometry working and would say nothing about the thing the surge is
    for, which is that it hands you *the people* as well as the building.

    So the run is played until there is a nest in the building, because a nest
    is the one mark on the plan that cannot be set up: it is a body twenty
    seconds after a death, and both halves of that have to actually happen. The
    workers, the flies and the player are there from the first frame.

    **The statue plays it**, which is the one choice here worth arguing. The
    listener reaches the same state at frame 3,200 and rescues five people on
    the way, so its plan has one green mark left on it -- a truthful frame of a
    good run and a poor picture of what a surge hands over. The statue saves
    nobody, so the plan carries five people in both rooms, a nest, the swarm
    and a player standing on open floor, which is what a reviewer has to be able
    to look at. Nothing about the level or the rules moves either way.

    **The surge is drawn by the game's own code on an ordinary frame** --
    `Session.draw_surge`, exactly as the shell calls it -- rather than by
    anything this module knows about plans. It is not scheduled: waiting for a
    real one would mean playing a run until its own seed said so, and the
    picture would then be of whatever frame that landed on rather than of a
    frame with a nest in it. What is photographed is the drawing, which is what
    the sheet is for.

    It raises rather than returning a picture of nothing if the run never
    produces one, for the same reason `swapped_room` does: a sheet that quietly
    showed an empty plan would be the one image on it nobody could check.
    """
    run = session_mod.Session(seed=GALLERY_SEED)
    playing = bots.make("statue", seed=GALLERY_SEED)
    for _ in range(SURGE_LIMIT):
        run.step(playing.intent(run))
        if run.over is not None:
            break
        if run.rescue.nests() and run.rescue.alive_waiting():
            break
    if not (run.rescue.nests() and run.rescue.alive_waiting()):
        raise RuntimeError(
            f"no nest and somebody alive in {SURGE_LIMIT} frames of the "
            f"gallery run, so the plan would be photographed without them")
    screen = Screen()
    # The ordinary frame first and the plan over the top of it, which is what
    # the shell does: the play area is replaced and the status strip is left
    # exactly where it is, still reading out the run underneath.
    run.draw(screen)
    run.draw_surge(screen)
    return screen


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
    # The one thing on the sprite sheet that a played frame cannot otherwise
    # show: a spotlight burning where somebody put it down.
    sheet(f"room-{slug(scene.BUILDING[scene.NEAR].name)}-swapped",
          swapped_room(scene.NEAR))
    # A moment's flash, in both halves of the cycle (issue #52). A still can
    # only ever show one half, and a reviewer given one half of a flash reads it
    # as a cell that is simply the wrong colour.
    freed = freed_room(scene.NEAR)
    near = slug(scene.BUILDING[scene.NEAR].name)
    sheet(f"room-{near}-freed", freed)
    sheet(f"room-{near}-freed-flashed", freed, flashing=True)
    # The mains surge (issue #53), in both halves of the cycle for the same
    # reason: the player's mark and the nests are drawn with the FLASH bit, and
    # a still can only ever show one half of it. **The half where the player is
    # inverted is the half you find yourself in**, so a reviewer given only the
    # other one would be looking at a plan with no player on it.
    surged = surge_screen()
    sheet("surge", surged)
    sheet("surge-flashed", surged, flashing=True)
    return paths
