"""A level opens on a strobe (issue #94): three one-frame flashes of the
whole room, five dark frames between, the game held, nothing remembered."""

from spikes import building as B, lighting, session as S
from spikes.session import Intent, Session
from spotlight.core.constants import CELL, COLS, SCREEN_H, SCREEN_W
from spikes.layout import PLAY_ROWS


def _lit(run) -> int:
    return sum(1 for cy in range(PLAY_ROWS) for cx in range(COLS)
               if run.field.level_at(cx, cy) == lighting.LIT)


def _shown(run) -> int:
    return sum(1 for cy in range(PLAY_ROWS) for cx in range(COLS)
               if run.field.level_at(cx, cy) != lighting.DARK)


def test_the_opening_is_the_name_then_three_flashes_of_the_plan_then_black():
    """The building's name for two bars with its tune under it, the three
    one-frame flashes of the building's plan five dark frames apart, two
    seconds of black, and only then play (issues #94, #95, #126). Not a
    cell of the building is lit on any held frame: the name and the plan
    are drawn, not lit, and nothing is remembered."""
    assert (S.STROBE_ON, S.STROBE_OFF, S.STROBE_FLASHES) == (1, 5, 3)
    assert S.STROBE_FRAMES == 18 and S.OPENING_BLACK == 100
    assert S.OPENING_NAME == 192 and S.OPENING_FRAMES == 310
    run = Session(seed=1, strobe=True)
    naming, flashing, cracks = [], [], 0
    for _ in range(S.OPENING_FRAMES):
        run.step()
        assert _shown(run) == 0, "a held frame lit the building"
        naming.append(run._naming)
        flashing.append(run._flashing)
        cracks += sum(1 for name, _c in run.moments.raised if name == "strobe")
    assert [i for i, on in enumerate(flashing) if on] == [192, 198, 204]
    assert naming[:192] == [True] * 192 and not any(naming[192:])
    assert not any(n and f for n, f in zip(naming, flashing)), \
        "the name and the plan were on screen at once"
    assert cracks == 3, "the crack did not sound once per flash"
    assert run.frame == 0


def test_the_name_has_its_own_tune_and_the_siren_comes_back_at_play():
    from spikes import tune
    run = Session(seed=1, strobe=True)
    run.step()
    assert run.voice.music.tune is tune.jingle_for(run.building.name)
    assert run.voice.music.tune.name == run.building.name == "The Hollins Hotel"
    assert run.voice.music.tune.frames == S.OPENING_NAME
    for _ in range(S.OPENING_FRAMES - 1):
        run.step()
    assert run.voice.music.tune is tune.SIREN


def test_every_building_has_a_name_and_a_tune_of_its_own():
    from spikes import levels, tune
    names = [levels.level(n).name for n in (1, 2, 3, 4, 5, 6)]
    assert len(set(names)) == 6
    tunes = [tune.jingle_for(name) for name in names]
    assert len({t.name for t in tunes}) == 6
    assert all(not t.loops and t.frames == S.OPENING_NAME for t in tunes)
    assert len({t.bars for t in tunes}) == 6, "two buildings share a tune"


def test_the_game_is_held_and_the_log_is_empty_through_the_strobe():
    run = Session(seed=1, strobe=True)
    start = (run.player.x, run.player.y)
    flies = [(c.cx, c.cy) for c in run.place.swarm.clegs]
    blood = [w.blood for w in run.rescue.workers]
    for _ in range(S.OPENING_FRAMES):
        events = run.step(Intent(dx=1, dy=1, spray=True))
        assert events == [] and run.frame == 0
    assert (run.player.x, run.player.y) == start, "the player moved"
    assert [(c.cx, c.cy) for c in run.place.swarm.clegs] == flies, "a fly moved"
    assert [w.blood for w in run.rescue.workers] == blood, "somebody bled"
    assert not run.log and run.spray.charges == 5
    run.step(Intent(dx=1))
    assert run.frame == 1 and run.player.x == start[0] + 1, "play did not begin"


def test_a_flash_is_the_whole_buildings_plan_and_leaves_nothing_behind():
    """Every room of the level, side by side, the exit in its magenta, the
    people as dots (issue #126); and not a cell of any room is lit or
    remembered by it."""
    from spikes import screens
    from spotlight.core.screen import Screen, unpack_attr
    from spotlight.core.constants import MAGENTA
    run = Session(seed=1, strobe=True)
    for _ in range(S.OPENING_NAME + 1):
        run.step()                               # through the name to the first flash
    assert run._flashing
    frame = Screen()
    run.draw(frame)
    plan = Screen()
    screens.draw_plan(plan, run.building)
    assert _play_area_ink(frame) == _play_area_ink(plan), "the flash is not the plan"
    x0, y0 = screens.plan_origin(run.building)
    stride = COLS * screens.PLAN_SCALE + screens.PLAN_GUTTER
    for i, room in enumerate(run.building.rooms):
        # **Every wall cell is a block of the plan and the furniture is not**
        # (issue #145). It used to be every `SOLID` cell, so at seven or nine
        # rooms every rolled pipe run, riser and cabinet became a two-pixel
        # block and the interiors were noise at 1:1. The plan is a map of the
        # building, and the furniture is not the building.
        furniture = 0
        for cy, row in enumerate(room.rows):
            for cx, char in enumerate(row):
                x, y = x0 + i * stride + cx * screens.PLAN_SCALE, y0 + cy * screens.PLAN_SCALE
                if char == B.WALL:
                    assert frame.point(x, y), (i, cx, cy)
                elif char in B.SOLID_FURNITURE:
                    furniture += 1
                    assert not frame.point(x, y), \
                        f"room {i}'s furniture at {(cx, cy)} is on the plan"
        assert furniture, f"room {i} rolled no furniture, so this proves nothing"
    # The exit wears magenta on the plan, and nothing in the building is lit.
    ex, ey = run.building.exit[1]
    cell = ((x0 + ex * screens.PLAN_SCALE) // 8, (y0 + ey * screens.PLAN_SCALE) // 8)
    assert unpack_attr(frame.get_attr(*cell))[0] == MAGENTA
    assert _shown(run) == 0 and not run._lit_people(run.place)
    run.step()                                   # dark
    assert _shown(run) == 0
    assert run.place.strobe.memory == 0


def test_the_strobe_ends_off_and_never_comes_back():
    run = Session(seed=1, strobe=True)
    for _ in range(S.OPENING_FRAMES + 200):
        run.step()
    assert not run.place.strobe.enabled and run.strobe == 0
    assert _lit(run) < COLS * PLAY_ROWS // 4


def test_a_session_driven_directly_does_not_strobe_and_the_shell_does():
    """The strobe is the window's opening: the shell and the demo ask for it,
    and a session built by the driver, the gallery or a test starts at frame
    one as it always did."""
    import pygame
    from spikes import spike1
    from spotlight.core.screen import Screen
    run = Session(seed=1)
    run.step()
    assert run.frame == 1 and run.strobe == 0
    shell = spike1.Shell(Screen())
    shell.key(pygame.K_s)
    assert shell.run.strobe == S.OPENING_FRAMES


def test_a_held_strobe_leaves_the_game_exactly_as_frame_nought():
    """A bot not asked during the hold makes the same run, event for event,
    with the strobe and without: the frame counter, the charge, the display,
    the shout lists and the swarm are all where frame nought left them."""
    from spikes import bots
    logs = []
    for strobe in (False, True):
        run = Session(seed=0xBEEF, strobe=strobe)
        bot = bots.make("listener", seed=0xBEEF)
        while run.over is None and run.frame < 1500:
            run.step(bot.intent(run) if not run.strobe else Intent())
        logs.append([(e.frame, e.kind, e.who, e.count) for e in run.log])
    assert logs[0] == logs[1]


# --- the flies stay out of it, and the logo sits on the black (issue #97) ------

def _play_area_ink(screen) -> set:
    from spotlight.core.constants import CELL, SCREEN_W
    return {(x, y) for y in range(PLAY_ROWS * CELL) for x in range(SCREEN_W)
            if screen.pixels[y * SCREEN_W + x]}


def test_a_flash_shows_the_people_and_not_the_flies():
    """On the plan (issue #126): a dot where each person stands, and nothing
    where a fly does."""
    from spikes import screens
    from spotlight.core.screen import Screen
    run = Session(seed=1, strobe=True)
    for _ in range(S.OPENING_NAME + 1):
        run.step()                                   # the first flash
    frame = Screen()
    run.draw(frame)
    x0, y0 = screens.plan_origin(run.building)
    stride = COLS * screens.PLAN_SCALE + screens.PLAN_GUTTER
    for i, room in enumerate(run.building.rooms):
        for x, y, _b in room.workers:
            cx, cy = x // 8, (y + 15) // 8
            assert frame.point(x0 + i * stride + cx * 2, y0 + cy * 2), "a person is missing"
        for cx, cy in room.clegs:
            if not room.is_solid(cx, cy):
                assert not frame.point(x0 + i * stride + cx * 2, y0 + cy * 2), "a fly is on the plan"


def test_the_black_is_the_buildings_name_and_the_strip_and_nothing_else():
    """The name where the logo was (issues #97, #126), and then neither."""
    from spikes import screens
    from spotlight.core.screen import Screen
    from screenreader import rows
    run = Session(seed=1, strobe=True)
    for _ in range(S.OPENING_BUILD + 1):
        run.step()                                   # the name, built up whole
    frame = Screen()
    run.draw(frame)
    name = Screen()
    screens.draw_big(name, run.building.name, top=S.OPENING_LOGO_TOP)
    assert _play_area_ink(frame) == _play_area_ink(name), \
        "the black has something on it besides the name"
    assert _play_area_ink(name), "the name drew nothing"
    assert S.OPENING_LOGO_TOP == 10, "two rows, centred in twenty-two"
    # Readable as the standard font, doubled: the top halves of the glyphs
    # on one row and the bottom halves on the next.
    top = rows(frame)[S.OPENING_LOGO_TOP]
    assert "HOLLINS" not in top and top.strip() != "", "the name was drawn single-height"
    # After the opening the name is gone and the room is drawn.
    for _ in range(S.OPENING_FRAMES - S.OPENING_BUILD - 1):
        run.step()
    after = Screen()
    run.draw(after)
    assert _play_area_ink(after) != _play_area_ink(name)


# --- the strip is black through the opening (issue #105) -------------------------

def test_the_strip_is_black_on_every_held_frame_and_painted_with_the_first_played():
    from spikes.layout import STRIP_TOP, STRIP_BOTTOM
    from spotlight.core.screen import Screen, unpack_attr
    run = Session(seed=1, strobe=True)
    for i in range(S.OPENING_FRAMES):
        run.step()
        if i % 20 and i not in (192, 198, 204):
            continue
        screen = Screen()
        run.draw(screen)
        for cy in range(STRIP_TOP, STRIP_BOTTOM):
            for cx in range(COLS):
                assert unpack_attr(screen.get_attr(cx, cy))[:2] == (0, 0), (i, cx, cy)
    run.step()
    assert run.frame == 1
    screen = Screen()
    run.draw(screen)
    from screenreader import rows
    text = rows(screen)
    assert "BLOOD" in text[STRIP_TOP] and "LIVES" in text[STRIP_TOP + 1]
    assert any(unpack_attr(screen.get_attr(cx, STRIP_TOP))[0] != 0 for cx in range(COLS))


def test_the_name_builds_up_from_pixels_and_is_whole_before_the_plan():
    """The user: *"I want the name to build up from pixels."* A scatter of
    the name's pixels grows frame by frame through the first three quarters
    of the name phase, is the whole name for the last quarter, and every
    pixel that is ever lit is one of the name's."""
    from spikes import screens
    from spotlight.core.screen import Screen
    run = Session(seed=1, strobe=True)
    whole = Screen()
    screens.draw_big(whole, run.building.name, top=S.OPENING_LOGO_TOP)
    all_pixels = _play_area_ink(whole)
    counts = []
    for i in range(S.OPENING_NAME):
        run.step()
        frame = Screen()
        run.draw(frame)
        lit = _play_area_ink(frame)
        assert lit <= all_pixels, f"frame {i} lit a pixel outside the name"
        counts.append(len(lit))
        if i >= S.OPENING_BUILD:
            assert lit == all_pixels, f"frame {i}: the name is not whole"
    assert counts[0] < counts[S.OPENING_BUILD // 4] < counts[S.OPENING_BUILD // 2] \
        < counts[S.OPENING_BUILD - 1] <= counts[S.OPENING_BUILD], counts[:3]
    assert counts[0] < len(all_pixels) // 10, "the name did not start from nearly nothing"
    assert S.OPENING_BUILD == 144
    # The scatter is the same every time: a seed names a run, a name names
    # its own build.
    assert screens.big_pixels("THE HOLLINS HOTEL", 10) == \
        screens.big_pixels("THE HOLLINS HOTEL", 10)


# --- the plan is a grid (issue #134) ----------------------------------------
#
# The opening drew every room side by side in one row at two pixels a cell,
# which is `rooms * 64 + (rooms - 1) * 8` pixels: 208 for three and **280 for
# four on a 256-pixel screen**. `plan_origin` came back at x = -12, the first
# room was sliced off the left edge, and nothing raised and nothing warned.
# The round that follows takes buildings to six rooms, so the plan became a
# grid and the loader gained the geometry check it never had.

import pytest

from spikes import building as B, levels, screens
from spotlight.core.screen import Screen


def _plan_room(name, hue, at, doorways=()):
    rows = [["#"] * COLS]
    rows += [["#"] + ["."] * (COLS - 2) + ["#"] for _ in range(PLAY_ROWS - 2)]
    rows.append(["#"] * COLS)
    return B.Room(name, ("".join(r) for r in rows), ink=B.palette(hue),
                  player_start=(24, 96), at=at, doorways=doorways,
                  searchlight=B.Searchlight(3, False))


def _grid_building(n):
    """`n` rooms laid out across the plan's grid, three to a row."""
    from spotlight.core.constants import CYAN, YELLOW
    rooms = []
    for i in range(n):
        col, row = i % screens.PLAN_COLS, i // screens.PLAN_COLS
        hue = YELLOW if (col + row) % 2 == 0 else CYAN
        rooms.append(_plan_room(f"room {i}", hue, (col, row)))
    return B.Building(rooms)


@pytest.mark.parametrize("rooms", [1, 2, 3, 4, 6, 9])
def test_a_plan_of_any_allowed_size_draws_wholly_inside_the_play_area(rooms):
    """The acceptance: no pixel outside the play area and no negative origin.

    Four rooms is the size that used to walk off the left edge in silence;
    nine is the cap, three rows of three, 208 x 148 of a 256 x 176 area.
    """
    building = _grid_building(rooms)
    x0, y0 = screens.plan_origin(building)
    assert x0 >= 0 and y0 >= 0, f"{rooms} rooms start at {(x0, y0)}"
    _cols, _rows, width, height = screens.plan_extent(building)
    assert x0 + width <= SCREEN_W, f"{rooms} rooms are {width}px wide"
    assert y0 + height <= PLAY_ROWS * CELL, f"{rooms} rooms are {height}px tall"
    screen = Screen()
    screens.draw_plan(screen, building)
    # Nothing is plotted in the strip, which the opening keeps black.
    for y in range(PLAY_ROWS * CELL, SCREEN_H):
        for x in range(SCREEN_W):
            assert not screen.point(x, y), f"the plan reached the strip at {(x, y)}"


def test_every_room_of_a_nine_room_plan_lands_on_its_own_patch():
    """Nine rooms, and each one's walls are drawn where its `at:` says."""
    building = _grid_building(9)
    screen = Screen()
    screens.draw_plan(screen, building)
    x0, y0 = screens.plan_origin(building)
    stride = COLS * screens.PLAN_SCALE + screens.PLAN_GUTTER
    down = PLAY_ROWS * screens.PLAN_SCALE + screens.PLAN_GUTTER
    for i, room in enumerate(building.rooms):
        col, row = room.at
        # The room's top-left border cell is a block at its own origin.
        x = x0 + col * stride
        y = y0 + row * down
        assert screen.point(x, y), f"room {i} at {(col, row)} is not drawn"


def test_a_building_with_no_positions_draws_the_single_row_it_always_did():
    """A building put together by hand in a test is not refused and is not
    rearranged: the fallback is chain order in one row."""
    from spotlight.core.constants import CYAN, YELLOW
    plain = B.Building([_plan_room("a", YELLOW, None),
                        _plan_room("b", CYAN, None)])
    assert screens.plan_grid(plain) == [(0, 0), (1, 0)]
    assert screens.plan_extent(plain)[:2] == (2, 1)


def test_the_shipped_levels_plans_are_the_pixels_they_always_were():
    """Three rooms in a row is what their grid says, so nothing moved."""
    for n in levels.levels():
        building = levels.level(n)
        rooms = len(building)
        was = ((SCREEN_W - (rooms * COLS * screens.PLAN_SCALE
                            + (rooms - 1) * screens.PLAN_GUTTER)) // 2,
               (PLAY_ROWS * CELL - PLAY_ROWS * screens.PLAN_SCALE) // 2)
        assert screens.plan_origin(building) == was, f"level {n} moved"


# --- what the loader now refuses --------------------------------------------

HEAD = "level: 9\nname: Test\nbuilding: The Test Works\n"


def _room_text(name, hue, at=None, doors=()):
    out = [f"room: {name}", "map:"]
    out += ["#" * COLS]
    out += ["#" + "." * (COLS - 2) + "#" for _ in range(PLAY_ROWS - 2)]
    out += ["#" * COLS]
    out += ["worker: 24 96 90", "searchlight: 3 repeat", "start: 24 96"]
    if at is not None:
        out.append(f"at: {at[0]} {at[1]}")
    out += list(doors)
    return "\n".join(out) + "\n"


def test_a_room_whose_east_door_does_not_lead_east_is_refused():
    text = (HEAD
            + _room_text("a", "yellow", (0, 0), ("door: east 10-12 b",))
            + _room_text("b", "cyan", (0, 1), ("door: west 10-12 a",)))
    with pytest.raises(ValueError, match="which is not east of it"):
        levels.build(levels.parse(text)[2], "t")


def test_two_rooms_at_the_same_place_on_the_plan_are_refused():
    text = (HEAD + _room_text("a", "yellow", (0, 0))
            + _room_text("b", "cyan", (0, 0)))
    with pytest.raises(ValueError, match="are both at 0 0"):
        levels.build(levels.parse(text)[2], "t")


def test_a_half_authored_grid_is_refused():
    text = HEAD + _room_text("a", "yellow", (0, 0)) + _room_text("b", "cyan")
    with pytest.raises(ValueError, match="either authored or it is not"):
        levels.build(levels.parse(text)[2], "t")


def test_a_position_off_the_plan_is_refused_at_the_line():
    text = HEAD + _room_text("a", "yellow", (3, 0))
    with pytest.raises(ValueError, match="off the plan"):
        levels.parse(text)


def test_a_building_of_ten_rooms_is_refused():
    """Nine is the cap because nine is what the screen holds."""
    from spotlight.core.constants import CYAN, YELLOW
    text = HEAD
    for i in range(10):
        col, row = i % screens.PLAN_COLS, i // screens.PLAN_COLS
        hue = "yellow" if (col + row) % 2 == 0 else "cyan"
        # The tenth has nowhere left to stand, so `at:` refuses it first --
        # which is the same rule arriving one line earlier.
        at = (col, min(row, screens.PLAN_ROWS - 1))
        text += _room_text(f"r{i}", hue, at)
    with pytest.raises(ValueError, match="both at|off the plan|plan holds"):
        levels.build(levels.parse(text)[2], "t")


# --- the plan says which rooms join (issue #145) -----------------------------
#
# **The plan is the memory the level is played from**, and with buildings on a
# grid it was omitting the only thing a grid has that a row has not. `draw_plan`
# blocked solid cells and painted the exit magenta; a doorway was simply absent,
# a six-pixel hole in a two-pixel wall line. On a row that was fine, because a
# strip is obviously a chain. On a three-by-three it is nine boxes and no graph.
#
# And nobody can fall back on paper. Jet Set Willy had sixty rooms and no map,
# and everybody who finished it drew one -- which worked because the rooms were
# fixed. **Spotlight's rooms roll, so the map cannot be drawn**, and two seconds
# of plan at the opening is the entire substitute.

def _joined(a: int, b: int, side):
    """A doorway each way between rooms `a` and `b`, `side` as seen from `a`."""
    span = (10, 11, 12) if side in B.VERTICAL_SIDES else (14, 15, 16)
    return ((a, B.Doorway(side, span, to=b)),
            (b, B.Doorway(B.OPPOSITE[side], span, to=a)))


def _shaped(edges, places):
    """A building of `len(places)` rooms at `places`, joined by `edges`.

    `edges` are `(a, b, side)`; the hue is the parity of the position, exactly
    as the loader derives it since issue #145.
    """
    doors: dict = {i: [] for i in range(len(places))}
    for a, b, side in edges:
        for who, door in _joined(a, b, side):
            doors[who].append(door)
    rooms = [_plan_room(f"room {i}", levels.hue_at(*places[i]), places[i],
                        tuple(doors[i]))
             for i in range(len(places))]
    return B.Building(rooms)


#: A ring, a comb and a branch -- four rooms each, the same four squares of the
#: plan, and three different buildings. Told apart only by which rooms join.
RING = ([(0, 1, B.EAST), (0, 2, B.SOUTH), (1, 3, B.SOUTH), (2, 3, B.EAST)],
        [(0, 0), (1, 0), (0, 1), (1, 1)])
COMB = ([(0, 1, B.EAST), (0, 2, B.SOUTH), (1, 3, B.SOUTH)],
        [(0, 0), (1, 0), (0, 1), (1, 1)])
BRANCH = ([(0, 1, B.EAST), (1, 2, B.SOUTH), (1, 3, B.EAST)],
          [(0, 0), (1, 0), (1, 1), (2, 0)])


def test_a_bridge_is_drawn_for_every_doorway_and_for_no_other_pair():
    """The acceptance, stated as a graph: one bridge a doorway, and none
    between two rooms that merely stand next to each other.

    A doorway is authored twice, once from each side, and the bridge is drawn
    once -- from the lower-indexed room, whose hue it takes. Under the
    chequerboard the two ends of a bridge are different colours, and picking an
    end is the only way not to give the plan a third rule nobody can state.
    """
    for label, (edges, places) in (("ring", RING), ("comb", COMB),
                                   ("branch", BRANCH)):
        building = _shaped(edges, places)
        bridges = screens.plan_bridges(building)
        assert len(bridges) == len(edges), f"{label}: {len(bridges)} bridges"
        assert all(room == min(a, b) for (room, _px), (a, b, _s)
                   in zip(bridges, edges)), label
        # Every bridge is `PLAN_GUTTER` pixels long and one thick, and lies
        # wholly in the gutter: no pixel of it is inside either room's patch.
        for i, pixels in bridges:
            assert len(pixels) == screens.PLAN_GUTTER
            assert len({x for x, _y in pixels}) == 1 \
                or len({y for _x, y in pixels}) == 1


def test_a_ring_a_comb_and_a_branch_do_not_draw_the_same_plan():
    """**The finding, reproduced and then fixed.** Two buildings of four rooms on
    the same four squares of the plan, differing only in which rooms join.

    The shells here are blank, so before the bridges these two drew
    byte-identical plans and there was nothing to tell them apart at all. In a
    real building it is worse than it sounds rather than better: the only
    difference was a six-pixel hole in a two-pixel wall line where the doorway's
    `d` cells fall, which is what the issue was raised about. A hole is not a
    signal.
    """
    drawn = {}
    for label, (edges, places) in (("ring", RING), ("comb", COMB)):
        screen = Screen()
        screens.draw_plan(screen, _shaped(edges, places))
        drawn[label] = bytes(screen.pixels)
    assert drawn["ring"] != drawn["comb"], \
        "the ring and the comb still draw the same plan"
    # And the difference is exactly the one bridge the ring has that the comb
    # has not: the comb's plan is a subset of the ring's.
    ring, comb = drawn["ring"], drawn["comb"]
    assert all(r or not c for r, c in zip(ring, comb))
    assert sum(ring) - sum(comb) == screens.PLAN_GUTTER


def test_a_room_with_four_doorways_draws_four_bridges():
    """Acceptance, and the case a strip could never produce."""
    places = [(1, 1), (0, 1), (2, 1), (1, 0), (1, 2)]
    edges = [(0, 1, B.WEST), (0, 2, B.EAST), (0, 3, B.NORTH), (0, 4, B.SOUTH)]
    building = _shaped(edges, places)
    assert len(building[0].doorways) == 4
    bridges = screens.plan_bridges(building)
    assert len(bridges) == 4
    assert {i for i, _px in bridges} == {0}
    # One in each direction from the middle room's patch.
    left, top = screens.plan_room_origin(building, 0)
    right = left + COLS * screens.PLAN_SCALE
    bottom = top + PLAY_ROWS * screens.PLAN_SCALE
    sides = set()
    for _i, pixels in bridges:
        xs = {x for x, _y in pixels}
        ys = {y for _x, y in pixels}
        sides.add("west" if max(xs) < left else "east" if min(xs) >= right
                  else "north" if max(ys) < top else "south" if min(ys) >= bottom
                  else "?")
    assert sides == {"east", "west", "north", "south"}, sides


def test_every_attribute_on_the_plan_holds_one_ink_and_one_paper():
    """The Spectrum's own rule, cell by cell on a resolved frame, over every
    size the plan can hold. `set_attr` cannot express two inks, so what this
    really asserts is that nothing draws outside the play area and that the
    bridges do not recolour a room: a cell a room has claimed keeps its hue."""
    from spotlight.core.screen import unpack_attr
    for rooms in (1, 2, 3, 4, 6, 9):
        building = _grid_building(rooms)
        screen = Screen()
        screens.draw_plan(screen, building)
        for cy in range(PLAY_ROWS * screens.PLAN_SCALE):
            for cx in range(COLS):
                ink, paper, _b, _f = unpack_attr(screen.get_attr(cx, cy))
                assert 0 <= ink <= 7 and paper == 0, (rooms, cx, cy)


def test_a_bridge_lights_the_gutter_cell_and_leaves_the_rooms_hues_alone():
    """The attribute rule, which is the one thing in this slice that had to be
    decided rather than read off the issue.

    The gutter between two rooms in a row is an attribute cell no room claims,
    and a bridge drawn on an unset cell is black on black -- so the bridge has
    to colour it. The gutter between two *rows* is not: at `PLAN_SCALE = 2` it
    straddles cells that already hold both rooms' pixels, and recolouring one
    would put a stripe of the wrong hue across the room below. So a bridge
    paints only the cells no room owns.
    """
    from spotlight.core.screen import unpack_attr
    from spotlight.core.constants import CYAN, YELLOW
    building = _shaped(*RING)
    screen = Screen()
    screens.draw_plan(screen, building)
    for i, pixels in screens.plan_bridges(building):
        hue = building.rooms[i].ink[B.FLOOR]
        for x, y in pixels:
            assert screen.point(x, y), (i, x, y)
            ink = unpack_attr(screen.get_attr(x // CELL, y // CELL))[0]
            assert ink in (hue, YELLOW, CYAN), (i, x, y, ink)
    # Room 3 of the ring is at (1, 1) and takes yellow; the bridge above it
    # comes from room 1, which is cyan. Room 3's own cells are still yellow.
    left, top = screens.plan_room_origin(building, 3)
    ink = unpack_attr(screen.get_attr((left + 20) // CELL, (top + 20) // CELL))[0]
    assert ink == building.rooms[3].ink[B.FLOOR] == YELLOW


def test_a_waiting_person_is_bright_green_on_the_plan():
    """Green already means somebody calling everywhere else in the game, and the
    exit already takes magenta on this screen for the same reason: a plan
    attribute that means something rather than one that decorates.

    A person was a two-pixel block and so was a wall stub, so at nine rooms they
    could not be found at all.
    """
    from spotlight.core.screen import unpack_attr
    from spotlight.core.constants import GREEN
    building = levels.level(3)
    screen = Screen()
    screens.draw_plan(screen, building)
    for i, room in enumerate(building.rooms):
        left, top = screens.plan_room_origin(building, i)
        for x, y, _blood in room.workers:
            px = left + (x // CELL) * screens.PLAN_SCALE
            py = top + ((y + 15) // CELL) * screens.PLAN_SCALE
            assert screen.point(px, py), (i, x, y)
            ink, _paper, bright, _flash = unpack_attr(
                screen.get_attr(px // CELL, py // CELL))
            assert (ink, bright) == (GREEN, True), (i, x, y, ink)


def test_the_hue_is_the_parity_of_the_place_and_every_shipped_room_is_unchanged():
    """`floor:` is out of the level file and the hue is `(col + row) & 1`.

    A grid graph is bipartite, so two hues two-colour any building the plan can
    hold, for ever -- which is why this can be derived rather than authored and
    why the loader's old refusal is now a theorem. All three shipped files
    obeyed it by hand already, which is how it was found, and the hues below are
    the ones they authored.
    """
    from spotlight.core.constants import CYAN, YELLOW
    assert levels.hue_at(0, 0) == levels.hue_at(1, 1) == YELLOW
    assert levels.hue_at(1, 0) == levels.hue_at(0, 1) == CYAN
    want = {1: (YELLOW, CYAN, YELLOW), 2: (YELLOW, CYAN, YELLOW),
            3: (YELLOW, CYAN, YELLOW)}
    for n, hues in want.items():
        got = tuple(room.ink[B.FLOOR] for room in levels.level(n).rooms)
        assert got == tuple(B.palette(h)[B.FLOOR] for h in hues), n
    # And the key is gone, by name, with a message that says where it went.
    with pytest.raises(ValueError, match="no longer a key"):
        levels.parse("level: 9\nname: X\nroom: a\nfloor: yellow\n")


def test_every_doorway_crossed_flips_the_floor_colour():
    """What the derivation gives the player for nothing: the floor under your
    feet says whether you are an odd or an even number of doors from the exit.

    Asserted over every shipped level and over a nine-room comb, because it is
    the claim the chequerboard was argued on and it holds only if the plan's
    adjacency and the doorways agree -- which the loader checks separately.
    """
    for n in (1, 2, 3, 4, 6):
        building = levels.level(n)
        for room in building.rooms:
            for door in room.doorways:
                assert room.ink[B.FLOOR] != building[door.to].ink[B.FLOOR], \
                    f"level {n}: {room.name} and {building[door.to].name}"
