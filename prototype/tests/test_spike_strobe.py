"""A level opens on a strobe (issue #94): three one-frame flashes of the
whole room, five dark frames between, the game held, nothing remembered."""

from spikes import lighting, session as S
from spikes.session import Intent, Session
from spotlight.core.constants import COLS
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
        # Every solid cell of every room is a block of the plan, and every
        # floor cell without a person on it is not.
        for cy, row in enumerate(room.rows):
            for cx, char in enumerate(row):
                x, y = x0 + i * stride + cx * screens.PLAN_SCALE, y0 + cy * screens.PLAN_SCALE
                if room.is_solid(cx, cy):
                    assert frame.point(x, y), (i, cx, cy)
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
