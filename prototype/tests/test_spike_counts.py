"""The tail is seen, the strip counts the people, and two look flags.

Issues #90 and #91, from the user watching the demo loop: seven followers
were not showing behind the player; a counter is wanted for the dead, the
following and the still-to-find; and two things to test by eye, luminous
Clegs and no light trail from the player.
"""

from spikes import clegs as C, font, panel, scene, screens, session as S
from spikes.session import Intent, Session
from spotlight.core.constants import CELL, COLS
from spotlight.core.screen import Screen, unpack_attr
from screenreader import rows


def _ink_in(screen: Screen, x: int, y: int, height: int = 16) -> int:
    return sum(screen.pixels[(y + dy) * 256 + x + dx]
               for dy in range(height) for dx in range(CELL)
               if 0 <= y + dy < 22 * CELL and 0 <= x + dx < 256)


def _free_everybody(run: Session) -> None:
    from test_session import touch
    for worker in list(run.rescue.workers):
        touch(run, worker)
        run.step()


# --- the tail is seen -----------------------------------------------------------

def test_a_follower_in_the_dark_is_drawn_and_a_waiting_worker_is_not():
    run = Session(seed=1)
    _free_everybody(run)
    # Walk on until the tail stretches out behind, well past the glow.
    for _ in range(120):
        run.step(Intent(dx=1))
    tail = [w for w in run.rescue.tail if w.room == run.here]
    far = [w for w in tail if not any(run.field.reveals_at(*c) for c in w.cells())
           and all(run.field.level_at(*c) == 0 for c in w.cells())]
    assert far, "no follower ended up in the dark; the tail is not long enough"
    screen = Screen()
    run.draw(screen)
    for worker in far:
        assert _ink_in(screen, worker.x, worker.y) > 0, \
            f"the follower at {worker.cell()} is not drawn in the dark"
    # And the prey rule is untouched: a follower in the dark is not prey.
    assert not any(w in run._lit_people(run.place) for w in far)


def test_a_waiting_worker_in_the_dark_is_still_not_drawn():
    run = Session(seed=1)
    run.step()
    screen = Screen()
    run.draw(screen)
    dark = [w for w in run.rescue.alive_waiting(run.here)
            if not any(run.field.reveals_at(*c) for c in w.cells())]
    assert dark
    for worker in dark:
        assert _ink_in(screen, worker.x, worker.y) == 0


# --- the strip counts the people ---------------------------------------------------

def test_the_three_badges_and_the_tally_add_up_to_seven_every_frame():
    from spikes import bots
    run = Session(seed=1)
    bot = bots.make("listener", seed=1)
    while run.over is None and run.frame < 3000:
        run.step(bot.intent(run))
        v = run.panel.values
        assert v["with"] + v["dead"] + v["left"] + v["rescued"] == run.total, \
            (run.frame, dict(v))
        assert v["with"] == len(run.rescue.tail)
        assert v["dead"] == run.lost
        assert v["left"] == len(run.rescue.alive_waiting())


def test_the_badges_are_drawn_as_a_mark_and_a_digit_in_their_own_colours():
    run = Session(seed=1)
    run.step()
    screen = Screen()
    run.draw(screen)
    text = rows(screen)
    for name, ink in (("with", 4), ("dead", 2), ("left", 7)):
        region = panel.REGIONS[name]
        assert region.kind == panel.BADGE and region.width == 2
        cx, cy = region.col, region.row
        assert unpack_attr(screen.get_attr(cx, cy))[0] == ink, name
        assert unpack_attr(screen.get_attr(cx + 1, cy))[0] == ink, name
        # The mark's pixels are the glyph's; the digit is the count.
        drawn = [screen.pixels[(cy * CELL + dy) * 256 + cx * CELL + dx]
                 for dy in range(CELL) for dx in range(CELL)]
        wanted = [1 if region.glyph[dy] & (0x80 >> dx) else 0
                  for dy in range(CELL) for dx in range(CELL)]
        assert drawn == wanted, f"the {name} mark is not its glyph"
    # Seven to find at the start, none with you, none dead -- and the digit
    # cells say so in the font's own digits.
    assert run.panel.values["left"] == 7 and run.panel.values["with"] == 0
    left = panel.REGIONS["left"]
    drawn = [screen.pixels[(left.row * CELL + dy) * 256 + (left.col + 1) * CELL + dx]
             for dy in range(CELL) for dx in range(CELL)]
    seven = [1 if font.GLYPHS["7"][dy] & (0x80 >> dx) else 0
             for dy in range(CELL) for dx in range(CELL)]
    assert drawn == seven, "the count is not drawn as its digit"


def test_the_blood_bar_is_six_cells_and_reads_full_at_capacity():
    run = Session(seed=1)
    run.step()
    assert panel.REGIONS["blood"].width == 6
    assert run.panel.values["blood"] == 6, "a full blood does not fill the bar"
    # Nothing on the status half runs into the action half.
    for name in ("blood", "with", "dead", "left"):
        region = panel.REGIONS[name]
        assert region.col + region.width <= 19, name


def test_the_title_teaches_the_three_badges():
    screen = Screen()
    screens.draw_title(screen)
    line = rows(screen)[screens.BADGE_LEGEND_ROW]
    for _mark, _ink, word in screens.BADGE_LEGEND:
        assert word in line, line
    # Each mark wears its own colour and sits before its word.
    marks = [(cx, unpack_attr(screen.get_attr(cx, screens.BADGE_LEGEND_ROW))[0])
             for cx in range(COLS)
             if screen.pixels[(screens.BADGE_LEGEND_ROW * CELL + 3) * 256 + cx * CELL + 3]
             and unpack_attr(screen.get_attr(cx, screens.BADGE_LEGEND_ROW))[0] != 7]
    assert {ink for _cx, ink in marks} >= {4, 2}


# --- two look flags ----------------------------------------------------------------

def _fly_in_the_dark(run):
    run.step()
    for fly in run.place.swarm.clegs:
        if not run.field.reveals_at(fly.cx, fly.cy):
            return fly
    fly = C.Cleg(2, 2, seed=5)
    run.place.swarm.clegs.append(fly)
    run.step()
    assert not run.field.reveals_at(fly.cx, fly.cy)
    return fly


def test_luminous_clegs_are_drawn_in_the_dark_and_ordinary_ones_are_not():
    for luminous in (False, True):
        run = Session(seed=1, luminous=luminous)
        fly = _fly_in_the_dark(run)
        screen = Screen()
        run.draw(screen)
        ink = _ink_in(screen, fly.cx * CELL, fly.cy * CELL, 8)
        assert (ink > 0) == luminous, f"luminous={luminous}: ink {ink}"


def test_without_a_trail_the_cell_you_left_is_dark_the_frame_after():
    for trail in (True, False):
        run = Session(seed=1, trail=trail)
        run.step()
        behind = (run.player.cx - 1, run.player.cy)
        assert run.field.level_at(*behind), "the glow does not reach the cell behind"
        for _ in range(3 * CELL):
            run.step(Intent(dx=1))
        assert (run.field.level_at(*behind) > 0) == trail, f"trail={trail}"


def test_the_looks_default_on_and_the_old_ones_reach_the_shell():
    import pygame
    from spikes import spike1
    assert Session(seed=1).luminous is True and Session(seed=1).trail is False
    shell = spike1.Shell(Screen(), luminous=False, trail=True)
    shell.key(pygame.K_s)
    assert not shell.run.luminous and shell.run.trail
    assert spike1.DARK_CLEGS_FLAG == "--dark-clegs"
    assert spike1.TRAIL_FLAG == "--trail"


def test_a_luminous_cleg_is_red_and_a_follower_in_the_dark_wears_the_rooms_hue():
    """Pixels alone show nothing in a dark cell -- black ink on black paper
    -- which is what the first cut got wrong (issue #92). A luminous fly's
    cell is bright red wherever it is; a follower's dark cells wear the
    room's own hue, unbright."""
    run = Session(seed=1)
    fly = _fly_in_the_dark(run)
    screen = Screen()
    run.draw(screen)
    ink, _paper, bright, _flash = unpack_attr(screen.get_attr(fly.cx, fly.cy))
    assert (ink, bright) == (2, True), "a luminous fly is not bright red"
    run = Session(seed=1)
    _free_everybody(run)
    for _ in range(120):
        run.step(Intent(dx=1))
    dark = [w for w in run.rescue.tail if w.room == run.here
            and all(run.field.level_at(*c) == 0 for c in w.cells())]
    assert dark, "no follower in the dark"
    screen = Screen()
    run.draw(screen)
    hue = run.place.inks[dark[0].cell()[1] * COLS + dark[0].cell()[0]]
    for cx, cy in dark[0].cells():
        ink, _paper, bright, _flash = unpack_attr(screen.get_attr(cx, cy))
        assert ink == hue and not bright, "a follower in the dark is invisible"
