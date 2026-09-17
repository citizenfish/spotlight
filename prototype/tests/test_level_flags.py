"""`--level N` and `--room M` on the window, the driver, the demo and the
gallery (issue #109, The rooms AM). Default level 3, default room the
building's start, so with no flags every command does what it did."""

import pygame
import pytest

from screenreader import rows
from spikes import (
    levels, scene, screens, session as session_mod, spike1, spike_demo,
    spike_driver as driver, spike_gallery as gallery,
)
from spotlight.core.screen import Screen


# --- the picker ---------------------------------------------------------------

def test_the_default_is_level_three_and_the_scene():
    assert levels.DEFAULT_LEVEL == 3
    building, start = levels.pick()
    assert building is scene.BUILDING and start is None
    assert scene.building(3) is scene.BUILDING


def test_a_room_starts_the_building_there():
    building, start = levels.pick(3, 1)
    assert building is scene.BUILDING and start == 1


def test_solo_plays_one_room_with_its_doorways_bricked_up():
    building, start = levels.pick(3, 1, solo=True)
    assert len(building) == 1 and building[0].doorways == () and start is None
    assert building.level == 3 and building.title == scene.BUILDING.title
    # And no room means the level's own start room, alone.
    alone, _ = levels.pick(3, solo=True)
    assert alone[0].name == scene.BUILDING[scene.BUILDING.start[0]].name


def test_a_level_that_does_not_exist_is_said_in_one_line():
    missing = max(levels.levels()) + 1
    with pytest.raises(ValueError, match=f"no level {missing}"):
        levels.pick(missing)
    with pytest.raises(ValueError, match="no room 9"):
        levels.pick(3, 9)


def test_the_window_reads_the_same_flags_from_a_bare_argv():
    assert levels.from_argv([]) == (3, None, False)
    assert levels.from_argv(["--scale", "2", "--level", "3", "--room", "1",
                             "--solo"]) == (3, 1, True)
    with pytest.raises(ValueError, match="--room needs a number"):
        levels.from_argv(["--room"])
    with pytest.raises(ValueError, match="--level needs a number"):
        levels.from_argv(["--level", "three"])


# --- the driver ---------------------------------------------------------------

def test_the_driver_starts_in_the_room_asked_for(capsys):
    seen = {}
    real = driver.drive

    def spy(bot, **kw):
        run = real(bot, **kw)
        seen["run"] = run
        return run
    driver.drive = spy
    try:
        code = driver.main(["--level", "3", "--room", "1", "--frames", "2",
                            "--no-files"])
    finally:
        driver.drive = real
    assert code == 0
    run = seen["run"]
    assert run.start_room == 1
    assert "on Level 3 Rescue, the far room" in capsys.readouterr().out


def test_the_driver_records_where_it_started_at_sixteen_eighty():
    run = driver.drive(None, seed=1, frames=1, building=scene.BUILDING,
                       start_room=1)
    assert run.here == 1
    # Nobody pressed anything, so the player is still at the far room's own
    # start, which the level file says is (16, 80).
    assert (run.player.x, run.player.y) == (16, 80)


def test_the_oracle_gets_everyone_out_of_the_far_room_alone(capsys):
    code = driver.main(["--level", "3", "--room", "1", "--solo",
                        "--bot", "oracle", "--no-files"])
    assert code == 0
    out = capsys.readouterr().out
    assert "all four of them" in out or "Got out" in out
    assert "the far room" in out


def test_a_missing_level_exits_two_not_a_traceback(capsys):
    missing = max(levels.levels()) + 1
    assert driver.main(["--level", str(missing), "--no-files"]) == 2
    assert f"no level {missing}" in capsys.readouterr().err
    assert spike1.main(["--level", str(missing)]) == 2


def test_the_report_names_the_level():
    run = driver.drive(None, seed=1, frames=1)
    assert run.where == "Level 3 Rescue"
    run = driver.drive(None, seed=1, frames=1, building=scene.BUILDING,
                       start_room=1)
    assert run.where == "Level 3 Rescue, the far room"
    run = driver.drive(None, seed=1, frames=1,
                       building=scene.BUILDING.solo(0))
    assert run.where == "Level 3 Rescue, the main room"


# --- the ending screen ------------------------------------------------------

def test_the_ending_screen_names_the_level_and_the_room():
    screen = Screen()
    screens.draw_ending(screen, session_mod.ENDING_TEXT[session_mod.ALL_OUT],
                        7, 0, 0, 7, 90, where="Level 3 Rescue, the far room")
    text = rows(screen)
    assert "LEVEL 3 RESCUE, THE FAR ROOM" in text[9]
    plain = Screen()
    screens.draw_ending(plain, session_mod.ENDING_TEXT[session_mod.ALL_OUT],
                        7, 0, 0, 7, 90)
    assert rows(plain)[9].strip() == ""


def test_the_shell_hands_the_run_its_building_and_room():
    shell = spike1.Shell(Screen(), strobe=False, building=scene.BUILDING,
                         start_room=1)
    shell.key(pygame.K_s)
    assert shell.run.here == 1 and shell.run.start_room == 1
    shell.key(pygame.K_ESCAPE)


# --- the demo -----------------------------------------------------------------

def test_the_demo_cycles_the_levels_it_is_given():
    shell = spike1.Shell(Screen(), seed=1)
    demo = spike_demo.Demo(shell, bot="statue", runs=3, title_seconds=1,
                           ending_seconds=1, cycle=(3, 3))
    for _ in range(spike_demo.FRAME_RATE):
        demo.frame()
    assert shell.state == spike1.PLAY
    assert shell.building is scene.building(3)
    assert shell.run.building is scene.BUILDING


def test_the_demo_left_alone_plays_the_shells_building():
    shell = spike1.Shell(Screen(), seed=1)
    demo = spike_demo.Demo(shell, bot="statue", runs=1, title_seconds=1,
                           ending_seconds=1)
    for _ in range(spike_demo.FRAME_RATE):
        demo.frame()
    assert shell.building is None and shell.run.building is scene.BUILDING


# --- the gallery ------------------------------------------------------------

def test_the_gallery_takes_a_level():
    run, screen = gallery.lit_room(1, level=3)
    assert run.here == 1 and run.building is scene.BUILDING
    same_run, _ = gallery.lit_room(1)
    assert same_run.here == 1


def test_the_gallery_walks_a_chain_of_doorways(monkeypatch):
    """Three rooms in a row: the far one is reached through the middle one,
    and each crossing is a real one."""
    from spikes import building as B
    a, b = scene.BUILDING[0], scene.BUILDING[1]
    # a - b - c, where c is b over again and b gains an east doorway.
    rows_b = [list(r) for r in b.rows]
    for cy in (10, 11, 12):
        rows_b[cy][31] = B.DOORWAY
    rooms = [
        B.Room(a.name, a.rows, ink=a.ink, workers=a.workers, clegs=a.clegs,
               spotlights=a.spotlights, searchlight=a.searchlight,
               lights=a.lights, player_start=a.player_start,
               doorways=(B.Doorway(B.EAST, (10, 11, 12), 1),)),
        B.Room("the middle room", ("".join(r) for r in rows_b), ink=b.ink,
               workers=b.workers, clegs=b.clegs, spotlights=b.spotlights,
               lights=b.lights, player_start=b.player_start,
               doorways=(B.Doorway(B.WEST, (10, 11, 12), 0),
                         B.Doorway(B.EAST, (10, 11, 12), 2))),
        B.Room("the end room", b.rows, ink=a.ink,
               workers=b.workers, clegs=b.clegs, spotlights=b.spotlights,
               lights=b.lights,
               doorways=(B.Doorway(B.WEST, (10, 11, 12), 1),)),
    ]
    chain = B.Building(rooms)
    run = session_mod.Session(seed=gallery.GALLERY_SEED, building=chain)
    gallery.enter(run, 2)
    assert run.here == 2 and run.crossings == 2
