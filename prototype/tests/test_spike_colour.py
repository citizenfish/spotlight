"""What colour the game is, read off the screen it actually draws.

Issue #47, the first slice of the look-and-feel round.

**What was wrong before.** Every cell in the play area was white ink on black:
a wall, a floor, a key and a room light all wore the same attribute, so nothing
on screen said which room you were standing in. Holding the building's geography
is the loudest complaint any tester has made about this game, and colour is the
cheapest answer available -- an attribute byte costs exactly the same whatever
colour it holds.

These tests read the drawn attributes rather than the palette tables, because a
palette that agreed with itself and was never consulted would pass every test in
`test_spike_scene.py` and change nothing on screen.

Two rules they exist to keep:

* **Light decides brightness, contents decide hue, and nothing decides both.**
  One chooser per cell is what makes attribute clash impossible, and per-room
  colour does not weaken it: a room hue is a property of a cell's contents like
  any other.
* **Black paper throughout.** A dark cell is black ink on black paper, which is
  invisible rather than merely dim, and every lit cell is ink on the same black.
"""

from spikes import lighting, panel as panel_mod, scene
from spikes.layout import PLAY_ROWS
from spikes.session import Intent, Session
from spotlight.core.constants import (
    BLACK, CELL, COLS, CYAN, GREEN, MAGENTA, RED, WHITE, YELLOW,
)
from spotlight.core.screen import Screen, unpack_attr

DOOR_ROW = scene.DOOR_ROWS[1]


def lit_room(index: int, walk_in: int = 0) -> tuple[Session, Screen]:
    """A session with one room fully revealed and drawn.

    The reveal is `opening.hold`, the debug view the game already has, rather
    than a second way to light a room invented for a test -- the same argument
    the gallery makes. Room B is reached by *walking* through the doorway, so
    the picture is of a room the game put the player in.
    """
    run = Session(seed=1)
    if index != run.here:
        run.here = scene.NEAR
        run.player.x = (COLS - 1) * CELL
        run.player.y = (DOOR_ROW - 1) * CELL
        for _ in range(16):
            run.step(Intent(dx=1))
        assert run.here == index, "the player would not walk into the far room"
    for _ in range(walk_in):
        run.step(Intent(dx=1))
    run.place.opening.hold(True)
    run.step()
    screen = Screen()
    run.draw(screen)
    return run, screen


def ink_at(screen: Screen, cx: int, cy: int) -> int:
    return unpack_attr(screen.get_attr(cx, cy))[0]


def cells_of(run, kind: str):
    """Every cell of one kind in the room on screen."""
    return [(cx, cy) for cy, line in enumerate(run.place.room.rows)
            for cx, c in enumerate(line) if c == kind]


def spoken_for(run) -> set:
    """Cells whose hue is chosen by something standing on them rather than by
    the room: a shout, the exit sign, poison.

    They are the *contents* choosing the hue, which is the same rule the floor
    and the walls follow -- and a shout is written wherever the word fits, so
    it lands on walls and on doorways as readily as on floor.
    """
    return set(run.call_cells) | set(run.place.sign_cells) | \
        set(run.spray.cells_in(run.here))


# --- the two rooms are told apart by their floors ---------------------------

def test_the_floor_says_which_room_you_are_in():
    """**The floor carries the room.** It is the biggest lit area on screen
    and it shows the instant any light falls anywhere, so it is where room
    identity is cheapest to read. Yellow in A, cyan in B, on the screen the
    game draws and not merely in the table it draws from."""
    for index, expected in ((scene.NEAR, YELLOW), (scene.FAR, CYAN)):
        run, screen = lit_room(index)
        floors = cells_of(run, scene.FLOOR)
        assert floors, "the room has no floor to colour"
        inks = {ink_at(screen, cx, cy) for cx, cy in floors}
        # Sprites, spray and the shouts stand on floor and are allowed their
        # own hue; what matters is that the room's own colour is what the
        # floor is drawn in and that it is this room's colour.
        assert expected in inks
        other = CYAN if expected is YELLOW else YELLOW
        assert other not in inks, "the other room's colour is on this floor"


def test_every_wall_in_the_building_is_drawn_white():
    """WHITE means *solid*, and it means it in both rooms. Walking into a wall
    is the one mistake that must not depend on which room you are in."""
    for index in (scene.NEAR, scene.FAR):
        run, screen = lit_room(index)
        written_on = spoken_for(run)
        for cx, cy in cells_of(run, scene.WALL):
            if (cx, cy) in written_on:
                continue          # `HELP` is written wherever the word fits
            assert ink_at(screen, cx, cy) == WHITE, \
                f"{run.place.room.name} has a wall at {cx},{cy} that is not white"


def test_the_room_light_zone_is_the_rooms_own_colour():
    """Room B's emergency lighting is floor that is always lit, not a
    different place. It is the one room-light zone in the building."""
    run, screen = lit_room(scene.FAR)
    zone = cells_of(run, scene.ROOM_LIGHT)
    assert zone, "room B authors the only room light in the building"
    written_on = spoken_for(run)
    for cx, cy in zone:
        if (cx, cy) in written_on:
            continue              # the zone sits on the doorway, where a
            # shout from the room next door is written
        assert ink_at(screen, cx, cy) == CYAN


def test_a_sprite_takes_the_hue_of_the_cell_it_stands_in():
    """A sprite sets pixels and never an attribute, so everybody in room A is
    yellow and everybody in room B is cyan. That is not a loss: colour has
    never been allowed to tell entities apart, and telling you which room you
    are in is the strongest use left for it."""
    for index, expected in ((scene.NEAR, YELLOW), (scene.FAR, CYAN)):
        run, screen = lit_room(index, walk_in=24)
        cx, cy = run.player.x // CELL, run.player.y // CELL
        assert run.place.room.rows[cy][cx] == scene.FLOOR
        assert (cx, cy) not in spoken_for(run)
        assert ink_at(screen, cx, cy) == expected


# --- one chooser per cell ---------------------------------------------------

def test_the_whole_play_area_is_ink_on_black_paper():
    """Black paper throughout, in both rooms and at every light level. It is
    what makes a dark cell invisible rather than dim, and it is half of the
    reason two colours per cell is enough."""
    for index in (scene.NEAR, scene.FAR):
        _run, screen = lit_room(index)
        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                _ink, paper, _bright, flash = unpack_attr(
                    screen.get_attr(cx, cy))
                assert paper == BLACK, f"paper at {cx},{cy} in room {index}"
                assert not flash, "nothing in the play area flashes"


def test_a_cells_brightness_is_the_light_and_its_ink_is_the_contents():
    """The split, checked cell by cell against the two things that decide it.

    This is the test that would catch colour being implemented as light. The
    attribute of every play-area cell has to be exactly what the level table
    says for its level and what the frame's ink map says for its hue -- so a
    palette that quietly lit a cell, or a light that quietly coloured one,
    fails here.
    """
    for index in (scene.NEAR, scene.FAR):
        run, screen = lit_room(index)
        levels = run.field.levels()
        inks = run.place.room.ink_map()
        specials = spoken_for(run)
        for cy in range(PLAY_ROWS):
            for cx in range(COLS):
                if (cx, cy) in specials:
                    continue          # a shout, the sign, poison: own hue
                idx = cy * COLS + cx
                assert screen.get_attr(cx, cy) == lighting.attr_for(
                    levels[idx], inks[idx]), f"cell {cx},{cy} in room {index}"


# --- the hues that mean a thing rather than a place -------------------------

def test_the_exit_sign_is_red_and_the_door_it_names_is_magenta():
    """Both were already true and both had to stay true when the light stopped
    supplying hues: the sign's red used to be passed to `field.add` as well as
    to the ink map, and the ink map is the one that was winning."""
    run, screen = lit_room(scene.NEAR)
    sign = run.place.sign_cells
    assert sign, "the near room carries the exit sign"
    for cx, cy in sign:
        assert ink_at(screen, cx, cy) == RED
    doors = cells_of(run, scene.EXIT)
    assert doors, "the way out of the building is in room A"
    for cx, cy in doors:
        assert ink_at(screen, cx, cy) == MAGENTA


def test_a_shout_is_green_wherever_it_is_written():
    """`HELP` over a caller's head and `HELP` over the doorway are the same
    word in the same green, and it comes from the frame's ink map.

    The green used to be given to the light as well. Removing that changed
    nothing on screen, which is exactly what this pins -- a voice is a voice
    whichever side of the wall it is on.
    """
    run = Session(seed=1)
    screen = Screen()
    for _ in range(9000):
        run.step()
        if run.call_cells:
            break
        assert run.over is None, "the run ended before anybody called"
    assert run.call_cells, "nobody called for help"
    run.draw(screen)
    for cx, cy in run.call_cells:
        assert ink_at(screen, cx, cy) == GREEN


def test_sprayed_ground_is_cyan_in_both_rooms():
    """Cyan is the player's poison and nothing else -- which is what taking it
    off the key bought. In room B it lies on a cyan floor and is told apart by
    pattern, droplets against the four-dot stipple: a deliberate trade, and the
    only collision the two-room palette produces."""
    for index in (scene.NEAR, scene.FAR):
        run, _screen = lit_room(index)
        run.step(Intent(spray=True))
        screen = Screen()
        run.draw(screen)
        sprayed = list(run.spray.cells_in(run.here))
        assert sprayed, "the spray laid nothing down"
        for cx, cy in sprayed:
            assert ink_at(screen, cx, cy) == CYAN


# --- the strip ---------------------------------------------------------------

def test_the_safe_value_is_green_and_its_label_is_white():
    """The tally is the score and it was the hardest readout on screen to
    find. **The values carry the colour and the labels do not** -- the instinct
    the ending screen already had. One attribute byte."""
    run = Session(seed=1)
    screen = Screen()
    run.step()
    run.draw(screen)
    region = panel_mod.REGIONS["rescued"]
    for i in range(region.width):
        assert ink_at(screen, region.col + i, region.row) == GREEN
    for i in range(len(region.label)):
        assert ink_at(screen, region.label_col + i, region.row) == WHITE
