"""The opening flash shows who is in the room, and the flies do not get told.

Issue #64, from the user's ruling on *After look-1* item 8 and the amended
*Light and Darkness*. **What was wrong before:** the flash lit every cell of
the room and hid every person in it, on the room lights' rule, and the user
saw a room light up fully and empty and then found people in it -- which
reads as a fault to the person the game is for.

**What was tempting and is wrong:** `reveals=True` on the flash. Reveal and
prey were one bit, so that would have made every worker and every Cleg prey
for twelve frames on every room entry and moved every event log in the
project. The fix is a second bit beside `reveals` -- `prey` -- and the flash
is the one source that sets the first and not the second.

**And what had been wrong all along, found on the way:** `Flash.hold()`, the
`F` debug view, set that one bit too, so everybody under the held view was
prey while its docstring said it changed nothing about the swarm. It reveals
without prey now, and the tests below say so.

The event log is byte-identical to the commit before **by construction** --
the prey list is what the swarm reads and the prey list does not change --
and `test_the_flash_showing_people_changes_no_event_log` is the pin, over
every bot on the seeds the look round was checked against.
"""

import ast

import pytest

from spikes import bots, lighting, report, sources, spike1
from spikes.session import Intent, Session
from spotlight.core.constants import CELL, SCREEN_W
from spotlight.core.screen import Screen


def _ink_in(screen: Screen, x: int, y: int, height: int = 16) -> int:
    """Pixels set inside an 8-wide box at pixel (x, y)."""
    return sum(screen.pixels[(y + dy) * SCREEN_W + x + dx]
               for dy in range(height) for dx in range(CELL)
               if 0 <= y + dy < 22 * CELL and 0 <= x + dx < SCREEN_W)


def _flash_out(run: Session) -> None:
    """Step until the opening flash has gone out."""
    for _ in range(sources.FLASH_FRAMES + 1):
        run.step()
    assert not run.place.opening.enabled


def _prey_with_flash(seed: int, frames: int, reveals: bool | None = None,
                     prey: bool | None = None) -> list:
    """Who is prey on a frame inside the flash, with the flash's bits as
    built or forced. Forcing `reveals=False` is the commit before; forcing
    `prey=True` is option 1 of the ruling, the one that was not taken."""
    run = Session(seed=seed)
    for _ in range(frames):
        if reveals is not None:
            run.place.opening.reveals = reveals
        if prey is not None:
            run.place.opening.prey = prey
        run.step()
    assert run.place.opening.enabled, "the flash has gone out"
    return [run.rescue.workers.index(w) for w in run._lit_people(run.place)]


# --- the flash reveals without prey ------------------------------------------

def test_a_worker_in_the_flash_is_drawn_and_is_not_prey():
    """The ruling, on a real frame: the run's second frame, inside the
    opening flash, with the room's workers standing where they are authored.
    Every one of them is under a revealing light, every one of them has ink
    on the screen, and none of them is in the swarm's prey list."""
    run = Session(seed=1)
    run.step()
    assert run.place.opening.enabled, "the flash is not on"
    screen = Screen()
    run.draw(screen)
    here = [w for w in run.rescue.workers if w.room == run.here]
    assert len(here) == 3
    for worker in here:
        assert all(run.field.reveals_at(*c) for c in worker.cells()), \
            "the flash does not reveal the worker"
        assert _ink_in(screen, worker.x, worker.y) > 0, \
            "the worker is revealed and not drawn"
    # **The prey list is what it was before the flash showed anybody.** Not
    # necessarily empty: room A's searchlight is sweeping from frame one and
    # a worker under it is prey by the standing rule, flash or no flash. What
    # the flash may not do is add anyone -- and with its prey bit on, it adds
    # everybody in the room.
    as_built = _prey_with_flash(1, 2)
    assert as_built == _prey_with_flash(1, 2, reveals=False), \
        "the flash handed somebody to the swarm"
    assert as_built == [run.rescue.workers.index(w)
                        for w in run._lit_people(run.place)]
    assert set(_prey_with_flash(1, 2, prey=True)) == \
        {run.rescue.workers.index(w) for w in here}, \
        "the prey bit is not what decides prey"


def test_the_clegs_are_drawn_in_the_flash_too():
    """The user's words were *the workers and cleggs*. A fly under the flash
    is drawn like a person under it, and lured by nothing -- a light that is
    everywhere has no *toward*."""
    run = Session(seed=1)
    run.step()
    screen = Screen()
    run.draw(screen)
    swarm = run.place.swarm
    assert swarm.clegs, "no flies in the room to draw"
    for cleg in swarm.clegs:
        assert run.field.reveals_at(cleg.cx, cleg.cy)
        assert _ink_in(screen, cleg.cx * CELL, cleg.cy * CELL, 8) > 0
    assert run.place.opening.lure() is None


def test_the_same_worker_under_the_lit_cone_is_both_drawn_and_prey():
    """The rule the flash is the exception to: under the player's torch, *if
    you can see them, so can the flies*. Same worker, after the flash has
    gone out, two cells ahead of the player with the torch on."""
    run = Session(seed=1)
    _flash_out(run)
    worker = next(w for w in run.rescue.workers if w.room == run.here)
    cx, cy = worker.cell()
    run.player.x, run.player.y = (cx - 2) * CELL, worker.y
    run.player.facing = sources.RIGHT
    run.step(Intent(torch=True))
    assert run.cone.lit
    assert any(run.field.reveals_at(*c) for c in worker.cells())
    assert worker in run._lit_people(run.place)


def test_the_same_worker_under_a_room_light_is_neither():
    """Room lights are untouched (option 2 of the ruling was not taken): they
    show the room and not who is in it, to the player and to the flies."""
    run = Session(seed=1)
    _flash_out(run)
    worker = next(w for w in run.rescue.workers if w.room == run.here)
    cx, cy = worker.cell()
    run.place.room_lights.append(sources.RoomLight(cx - 1, cy - 2, 3, 3))
    run.step()
    assert all(run.field.level_at(*c) == lighting.LIT for c in worker.cells())
    assert not any(run.field.reveals_at(*c) for c in worker.cells())
    assert worker not in run._lit_people(run.place)


def _prey_held(seed: int, frames: int, hold: bool, prey: bool = False):
    """Who is prey after `frames` steps, with the debug view held or not."""
    run = Session(seed=seed)
    _flash_out(run)
    run.place.opening.hold(hold)
    for _ in range(frames):
        run.place.opening.prey = prey
        run.step()
    return run, [run.rescue.workers.index(w)
                 for w in run._lit_people(run.place)]


def test_the_held_debug_view_reveals_and_makes_no_prey():
    """**The thing that had been wrong all along.** `F` held the room lit and
    everybody in it drawn, and made every one of them prey, because the reveal
    bit was the prey bit. Its docstring said the swarm behaved as it would in
    the dark. Now it does: the same frame with and without the hold has the
    same prey list, and with the old one-bit behaviour put back it has
    everybody in the room on it."""
    held, prey = _prey_held(1, 5, hold=True)
    here = [w for w in held.rescue.workers if w.room == held.here]
    for worker in here:
        assert all(held.field.reveals_at(*c) for c in worker.cells()), \
            "the held view shows nobody"
    _dark, in_the_dark = _prey_held(1, 5, hold=False)
    assert prey == in_the_dark, "the hold changed who is prey"
    _old, old_way = _prey_held(1, 5, hold=True, prey=True)
    assert set(old_way) == {held.rescue.workers.index(w) for w in here}, \
        "the prey bit is not what the hold used to set"


def test_the_prey_flag_is_cleared_every_frame_like_the_reveal_flag():
    """No state survives the frame. The fade is still one byte per cell."""
    f = lighting.LightField()
    f.begin(); f.add(5, 5, lighting.LIT, lighting.CHARGE_LIT); f.commit()
    assert f.prey_at(5, 5) and f.reveals_at(5, 5)
    f.begin(); f.commit()
    assert not f.prey_at(5, 5) and not f.reveals_at(5, 5)
    assert f.level_at(5, 5) == lighting.LIT, "the memory is the fade's"


def test_prey_reads_the_prey_flag_and_nothing_else():
    """A source that reveals and does not make prey, at full brightness, on
    a cell nobody else lights: revealed, not prey. And the other way round is
    not a thing -- a light cannot make prey of somebody it does not show."""
    f = lighting.LightField()
    f.begin()
    f.add(5, 5, lighting.LIT, lighting.CHARGE_LIT, reveals=True, prey=False)
    f.commit()
    assert f.reveals_at(5, 5) and not f.prey_at(5, 5)
    f.begin()
    f.add(5, 5, lighting.LIT, lighting.CHARGE_LIT, reveals=False, prey=True)
    f.commit()
    assert not f.reveals_at(5, 5)
    # `prey=True` on a hiding light is allowed by the signature and asked
    # for by nobody; it is recorded here as a combination no source uses.
    assert f.prey_at(5, 5)


def test_every_source_but_the_flash_sets_both_bits():
    """The rule, source by source, so a new one cannot quietly split them."""
    assert sources.Glow().reveals and sources.Glow().prey
    assert sources.Cone().reveals and sources.Cone().prey
    roam = sources.Roaming(0, 0, radius=3)
    assert roam.reveals and roam.prey
    room = sources.RoomLight(0, 0, 3, 3)
    assert not room.reveals and not room.prey
    flash = sources.Flash()
    flash.fire()
    assert flash.reveals and not flash.prey


# --- the event log is byte-identical, by construction, and pinned -----------

#: The seeds the look round was checked against: the retro-gamer's three
#: listener seeds from `DEFAULT_SEED`, and the casual-gamer's seed 7.
LOOK_ROUND_SEEDS = (0xBEEF, 0xBEEF + 1, 0xBEEF + 2, 7)

#: Enough frames to enter both rooms and take the first bites. The flash is
#: frames 1 to 12 of every room entry, so a prey bit on it would show in the
#: first attachments; the full-length comparison is the tester's re-take.
PIN_FRAMES = 1500


def _log_and_buckets(run) -> tuple:
    results = report.results(run)
    metrics = results["metrics"]
    buckets = {k: v for k, v in metrics.items()
               if k.startswith("blood_by_") or k.startswith("bites_by_")}
    return results["events"], buckets


def _play(name: str, seed: int, flash_reveals: bool | None):
    """One run, with the flash as built, or with its reveal bit forced off
    every frame -- which is exactly what the commit before this one did."""
    run = Session(seed=seed)
    bot = bots.make(name, seed=seed)
    while run.over is None and run.frame < PIN_FRAMES:
        if flash_reveals is not None:
            for place in run.places:
                place.opening.reveals = flash_reveals
        run.step(bot.intent(run))
    return run


@pytest.mark.parametrize("name", sorted(bots.BOTS))
@pytest.mark.parametrize("seed", LOOK_ROUND_SEEDS)
def test_the_flash_showing_people_changes_no_event_log(name, seed):
    """**The pin.** The same seed and the same bot, once with the flash as
    built and once with its reveal bit held off -- the commit before -- log
    the same events and bill the same blood to the same lures. The bots
    already have the map, and the prey list is what the swarm reads; if this
    ever fails, the flash has set the prey bit.
    """
    built = _play(name, seed, None)
    before = _play(name, seed, False)
    assert _log_and_buckets(built) == _log_and_buckets(before)
    assert built.frame == before.frame and built.over == before.over


def test_the_prey_bit_on_the_flash_is_what_the_pin_guards():
    """The negative control, at the level the swarm reads. With the prey bit
    on -- option 1 of the ruling, `reveals=True` alone in the old one-bit
    world -- every worker in the room is prey for the flash's frames on every
    seed. **Whether that reaches the event log is seed luck**: a fly has to
    be near somebody within twelve frames of a room entry, and on the four
    look-round seeds a 1,500-frame statue run does not move with it. That is
    why the pin above is the prey list's, in `_prey_with_flash`, and the log
    comparison is the tester's full-length re-take rather than this file's
    only evidence."""
    for seed in LOOK_ROUND_SEEDS:
        run = Session(seed=seed)
        here = {run.rescue.workers.index(w)
                for w in run.rescue.workers if w.room == run.here}
        assert set(_prey_with_flash(seed, 2, prey=True)) == here
        assert set(_prey_with_flash(seed, 2)) < here


# --- the flash's length is the user's number ---------------------------------

def test_flash_frames_is_twelve_and_nothing_is_derived_from_it():
    """`FLASH_FRAMES` is provisional and the user's to settle at a keyboard,
    so it has to be one constant with nothing hanging off it -- the same test
    the surge's length has. Walks every spike module for a name bound to an
    expression that mentions it."""
    import os
    derived = []
    root = os.path.join(os.path.dirname(sources.__file__))
    for name in sorted(os.listdir(root)):
        if not name.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(root, name)).read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if "FLASH_FRAMES" in names:
                continue
            if any(isinstance(kid, ast.Name) and kid.id == "FLASH_FRAMES"
                   for kid in ast.walk(node.value)):
                derived.append((name, names))
    assert derived == [], f"something is derived from FLASH_FRAMES: {derived}"
    assert sources.FLASH_FRAMES == 12


def test_the_flash_frames_flag_reaches_the_session():
    """`--flash-frames N`, beside `--surge-frames`: parsed by the shell, kept
    for the sitting, handed to every room's flash by a fresh session."""
    assert spike1.FLASH_FLAG == "--flash-frames"
    assert spike1.flash_frames_from([]) == sources.FLASH_FRAMES
    assert spike1.flash_frames_from(["--flash-frames", "40"]) == 40
    assert spike1.flash_frames_from(
        ["--scale", "2", "--surge-frames", "24", "--flash-frames", "3"]) == 3
    import pygame
    shell = spike1.Shell(Screen(), flash_frames=40)
    shell.key(pygame.K_s)
    assert all(p.opening.frames == 40 for p in shell.run.places)
    run = Session(flash_frames=3)
    assert run.place.opening.frames == 3
    assert run.place.opening.enabled
    for _ in range(3):
        run.step()
    assert not run.place.opening.enabled, "a three-frame flash ran long"


def test_the_report_says_what_the_flash_length_was():
    run = Session(seed=1, flash_frames=20)
    assert report.results(run)["metrics"]["flash_frames"] == 20


def test_a_longer_flash_leaves_a_longer_memory_and_nothing_else():
    """A longer flash is the fade doing its job for longer, not a second
    change: on a frame the default flash has left and a long one has not,
    the room is still lit, the people are still shown, and the prey list is
    the one the default flash would have given."""
    long = Session(seed=1, flash_frames=40)
    short = Session(seed=1)
    for _ in range(20):
        long.step()
        short.step()
    assert long.place.opening.enabled and not short.place.opening.enabled
    assert long.place.opening.reveals and not long.place.opening.prey
    here = [w for w in long.rescue.workers if w.room == long.here]
    assert all(long.field.reveals_at(*c) for w in here for c in w.cells())
    assert [long.rescue.workers.index(w) for w in long._lit_people(long.place)] \
        == [short.rescue.workers.index(w)
            for w in short._lit_people(short.place)]
