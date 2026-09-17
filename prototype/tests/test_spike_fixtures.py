"""The four things the screen had never shown, and the one that must not become
a light.

Issue #49. Three of these were in the design notes for months and had no draw
call anywhere in the game:

* **A spotlight lying on the floor.** Room A authors two and room B one, and
  none of the three had ever been drawn -- so an unlit spare was invisible and
  a burning one was a disc of stipple with nothing in the middle. The whole
  pick-up-and-swap economy, on which a weak spotlight being a trap and baiting
  the swarm being a level-design feature both rest, had never been on screen.
* **The way out.** A `D` cell is floor in every mechanical respect, so the exit
  was four magenta stipple dots per cell.
* **The searchlight's housing.** A moving pool with no emitter reads as *the
  lighting* rather than as a fixture installed in this room, and a player read
  its absence in the far room as the game malfunctioning.

**And the trap, which is what most of this file is about.** The housing is one
permanently lit cell, and the obvious way to build it -- a `sources.Source` at
the mount corner -- is a new *permanent lure* at the corner the beam is bolted
to. Clegs steer for the nearest lit lure they can notice, so that is a change to
where the swarm goes, and every difficulty figure the vault holds would move
with it. It is a direct write into the room's field with `reveals=False`,
exactly like the exit sign's cell, and the tests below are what stop it
quietly becoming a light later.
"""

from spikes import lighting, scene, sources, sprites
from spikes.layout import PLAY_ROWS
from spikes.session import Intent, Session
from spikes.spike_gallery import lit_room
from spotlight.core.constants import CELL, COLS, WHITE
from spotlight.core.screen import Screen
from spikes.player import HEIGHT as PERSON_HEIGHT


def drawn_at(screen: Screen, cx: int, cy: int, sprite) -> bool:
    """Is every pixel of `sprite` set in the cell at (cx, cy)?

    A superset test rather than an equality one, and deliberately: sprites
    composite over whatever is already in the cell, so a lamp lying on lit
    floor has the floor's stipple dots around it. What is being asked is
    whether the thing was drawn, not whether it is alone.
    """
    for dy, bits in enumerate(sprite):
        for dx in range(sprites.WIDTH):
            if not bits & (0x80 >> dx):
                continue
            if not screen.point(cx * CELL + dx, cy * CELL + dy):
                return False
    return True


def pixel_in_cell(screen: Screen, cx: int, cy: int, dx: int, dy: int) -> bool:
    return bool(screen.point(cx * CELL + dx, cy * CELL + dy))


# The dropped spotlight and its three tests went with the torch (issue #119).


# --- the way out ------------------------------------------------------------

def test_the_exit_is_a_door_and_not_four_dots():
    """The loudest object in the game, and it had no sprite.

    `exit_cell` is the top of the two-cell opening a person fits through, and
    an 8x16 door covers exactly that.
    """
    run, screen = lit_room(scene.NEAR)
    ex, ey = run.place.room.exit_cell()
    assert drawn_at(screen, ex, ey, sprites.DOOR_OPEN)
    # Open at both ends: nothing solid across the top of the frame or the
    # bottom of it, which is what the pair differs by.
    top = sum(pixel_in_cell(screen, ex, ey, dx, 0)
              for dx in range(sprites.WIDTH))
    assert top < sprites.WIDTH, "the open door has a head, so it reads shut"


def test_the_far_room_authors_no_way_out_and_draws_none():
    """The building has one exit and it is in room A. A door drawn in a room
    that has none would be a way out that is not one."""
    assert not scene.BUILDING[scene.FAR].has_exit
    far = Session(seed=1).places[scene.FAR]
    assert all(spr is not sprites.DOOR_OPEN for spr, _x, _y in far.fixtures)


# --- the searchlight's housing ----------------------------------------------

def test_every_room_draws_its_searchlights_housing():
    """**The fixture is drawn where the light is bolted**, which is what went
    wrong when a player read a room without one as broken. Since issue
    #118 every room has a searchlight, so every room draws a housing."""
    for index in (scene.NEAR, scene.FAR):
        run, screen = lit_room(index)
        housing = run.place.housing
        assert housing is not None, f"room {index} has no housing"
        assert drawn_at(screen, housing[0], housing[1], sprites.HOUSING)


def test_the_housing_is_white_at_full_brightness():
    """The brightest single cell in the room, and it never moves.

    White because it means *fixture* here for the same reason it means *solid*
    on a wall: it belongs to the building rather than to the room, so it does
    not take the room's floor hue.
    """
    run, screen = lit_room(scene.NEAR)
    cx, cy = run.place.housing
    assert screen.get_attr(cx, cy) == lighting.attr_for(lighting.LIT, WHITE)


def test_the_housing_cell_is_lit_on_every_frame_and_never_moves():
    """A fixture that blinks reads as broken, and one that wanders is not
    bolted to anything. Room A's beam repeats rather than varies, so its mount
    is the one it starts with for the whole run."""
    run = Session(seed=1)
    where = run.place.housing
    for _ in range(200):
        run.step()
        assert run.place.housing == where, "the housing moved"
        assert run.field.level_at(*where) == lighting.LIT, \
            "the housing went out"


def test_the_housing_is_not_in_the_rooms_list_of_lights():
    """**The trap this issue flagged, pinned.**

    The room's lights are `Place.fixed` -- the held debug view, the opening
    strobe's light (issue #94, off but for eighteen held frames a run), the
    authored room lights, and the searchlight. Nothing else was added to
    that list, and nothing may be: a `Source` at the mount corner is a
    permanent lure at the corner the beam is bolted to, and the swarm would
    gather there for the rest of the run.
    """
    for place in Session(seed=1).places:
        expected = 2 + len(place.room_lights) + (place.roaming is not None)
        assert len(place.fixed) == expected, \
            "something was added to a room's list of lights"
        if place.housing is None:
            continue
        for source in place.fixed:
            lure = source.lure()
            if lure is None:
                continue
            assert (lure[0], lure[1]) != place.housing, \
                "there is a light source sitting on the housing"


def test_nothing_is_lured_to_the_housing_and_nobody_is_prey_under_it():
    """The two ways a light shows in the simulation, and the housing does
    neither.

    A lure is what a Cleg steers for; `prey_at` is what makes somebody standing
    in a light worth biting. The housing's write carries `reveals=False`, so a
    worker standing in the corner is no more visible to the swarm than one
    standing in the dark -- which is the same rule the exit sign and a shout
    already follow.
    """
    run = Session(seed=1)
    for _ in range(30):
        run.step()
    place = run.place
    housing = place.housing
    lures = run._own_lures(place)
    assert all((lx, ly) != housing for lx, ly, _reach, _kind in lures), \
        "a Cleg can steer for the housing"
    assert place.field.level_at(*housing) == lighting.LIT
    assert not place.field.prey_at(*housing), \
        "standing under the housing makes you prey"
    assert not place.field.reveals_at(*housing), \
        "the housing reveals people, so it is a light after all"


def test_a_varying_searchlight_takes_its_housing_with_it():
    """In varying mode the mount moves between circuits and the housing moves
    with it, which is free information the design intends to give: you can see
    which corner this circuit is mirrored into.

    Room A repeats rather than varies, so this asks the light directly.
    """
    roam = sources.Roaming(0, 0, radius=3, step_every=1, vary=True)
    seen = set()
    for _ in range(12):
        target = roam.cycles + 1
        while roam.cycles < target:
            roam.update()
        assert roam.housing == sources.HOUSING_CORNERS[roam.mount]
        seen.add(roam.housing)
    assert len(seen) > 1, "the housing is bolted to one corner in vary mode"


def test_every_mount_corner_is_a_cell_of_the_play_area():
    """One cell in from each corner, so a housing stands on the room's own
    floor rather than inside the masonry."""
    assert len(set(sources.HOUSING_CORNERS)) == 4
    for cx, cy in sources.HOUSING_CORNERS:
        assert 0 < cx < COLS - 1 and 0 < cy < PLAY_ROWS - 1
        assert not scene.BUILDING[scene.NEAR].is_solid(cx, cy), \
            "room A's searchlight is bolted into a wall"
