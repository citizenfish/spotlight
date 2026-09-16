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
    assert len(screens.BADGE_LEGEND) == 4 and "SAFE" in line
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


# --- the strip has air (issue #96) ---------------------------------------------

def test_every_readout_on_the_strip_has_a_cell_clear_of_the_next():
    """The user called the strip cluttered: three badges abreast after the
    blood bar, hard against LIGHT. Now no two readouts on a row touch, but
    for a flag against its own bar, which is one readout."""
    from spikes.layout import ACTION_LEFT
    spans = []
    for name, region in panel.REGIONS.items():
        left = region.label_col if region.label else region.col
        spans.append((region.row, left, region.col + region.width, name))
    for row, col, label in panel.LABELS:
        spans.append((row, col, col + len(label), "label " + label))
    for row in sorted({s[0] for s in spans}):
        on_row = sorted(s for s in spans if s[0] == row)
        for (_r, l1, r1, n1), (_r2, l2, r2, n2) in zip(on_row, on_row[1:]):
            gap = l2 - r1
            if "lit" in (n1, n2):
                assert gap == 0, "the light bar and its flag are one readout"
            elif "keys" in (n1, n2):
                assert gap >= 0                # the key flag, as it always sat
            else:
                assert gap >= 1, f"{n1} runs into {n2} on row {row}"
        assert on_row[-1][2] <= COLS
    # And the status half ends before the kit half begins, with air.
    for name in ("with", "left", "dead", "rescued"):
        region = panel.REGIONS[name]
        assert region.col + region.width < ACTION_LEFT, name


# --- Look and feel 3: the fly's red, in the dark only (issue #98) --------------

def test_a_fly_is_red_only_where_its_cell_is_dark():
    """A fly in a DARK cell is bright red; in a LIT or DIM cell it wears
    what the paint gave the cell, and a fly standing on a lit person leaves
    the person's cells in the room's hue."""
    from spikes import lighting as L
    run = Session(seed=1)
    fly = _fly_in_the_dark(run)
    screen = Screen()
    run.draw(screen)
    assert unpack_attr(screen.get_attr(fly.cx, fly.cy))[:3] == (2, 0, True)
    # Park the fly on a lit cell in front of the torch.
    run.step(Intent(torch=True))
    lit = [(cx, cy) for cy in range(22) for cx in range(32)
           if run.field.level_at(cx, cy) == L.LIT and not run.place.room.is_solid(cx, cy)]
    assert lit
    # What the paint gives the cell with no fly on it is what it keeps with
    # one: the housing's white, a sign's red and the floor's hue alike.
    fly.cx, fly.cy = 0, 0
    without = Screen()
    run.draw(without)
    fly.cx, fly.cy = lit[0]
    screen = Screen()
    run.draw(screen)
    assert screen.get_attr(fly.cx, fly.cy) == without.get_attr(fly.cx, fly.cy), \
        "a fly on a lit cell was recoloured"
    assert unpack_attr(screen.get_attr(fly.cx, fly.cy))[2], "not lit at all"
    # And on a dim cell: the paint's dim attribute, unbright, room hue.
    run.step(Intent(torch=False))
    for _ in range(3):
        run.step()
    dim = [(cx, cy) for cy in range(22) for cx in range(32)
           if run.field.level_at(cx, cy) == L.DIM and not run.place.room.is_solid(cx, cy)]
    if dim:
        fly.cx, fly.cy = 0, 0
        without = Screen()
        run.draw(without)
        fly.cx, fly.cy = dim[0]
        screen = Screen()
        run.draw(screen)
        assert screen.get_attr(fly.cx, fly.cy) == without.get_attr(fly.cx, fly.cy)


# --- Look and feel 3: the player in white (issue #99) --------------------------

def test_the_player_is_bright_white_in_both_rooms_and_the_tail_is_not():
    from spikes import sprites
    from test_spike_doorway import at_door, walk
    for room in (scene.NEAR, scene.FAR):
        run = Session(seed=1)
        if room == scene.FAR:
            at_door(run)
            walk(run, 1, 16)
            assert run.here == scene.FAR
        run.step()
        screen = Screen()
        run.draw(screen)
        for cx, cy in sprites.cells_spanned(run.player.x, run.player.y, 16):
            assert unpack_attr(screen.get_attr(cx, cy))[:3] == (7, 0, True), (room, cx, cy)


def test_a_follower_keeps_the_rooms_hue_and_a_fly_on_you_does_not_turn_you_red():
    from spikes import sprites
    run = Session(seed=1)
    _free_everybody(run)
    for _ in range(60):
        run.step(Intent(dx=1))
    fly = C.Cleg(run.player.cx, run.player.cy, seed=3)
    run.place.swarm.clegs.append(fly)
    screen = Screen()
    run.draw(screen)
    mine = set(sprites.cells_spanned(run.player.x, run.player.y, 16))
    for cell in mine:
        assert unpack_attr(screen.get_attr(*cell))[0] == 7, "a fly turned you red"
    tail = [c for w in run.rescue.tail if w.room == run.here for c in w.cells()
            if c not in mine]
    assert tail
    for cx, cy in tail:
        assert unpack_attr(screen.get_attr(cx, cy))[0] != 7, "a follower went white"


# --- Look and feel 3: the strip's marks (issue #103) ------------------------------

def test_the_three_marks_are_the_bytes_the_issue_drew():
    from spikes import sprites
    assert font.DEAD_MARK == (0x00, 0x66, 0x3C, 0x18, 0x3C, 0x66, 0x00, 0x00)
    assert font.WITH_MARK == (0x00, 0x3C, 0x7E, 0x7E, 0x66, 0x66, 0x24, 0x00)
    assert font.LIT == (0x00, 0x3C, 0x7E, 0x7E, 0x7E, 0x7E, 0x3C, 0x00)
    assert font.LIT_OFF == (0x00, 0x3C, 0x42, 0x42, 0x42, 0x42, 0x3C, 0x00)
    # The X is no fly frame: the issue's row-by-row criterion was not
    # satisfiable by its own bytes (the mid-beat fly's wings are 0x66 and
    # 0x3C), so the pin is the whole mark against the whole frame, which is
    # what a reader compares, and that the dagger's vertical stroke is gone.
    assert all(tuple(font.DEAD_MARK) != tuple(frame) for frame in sprites.CLEG_FRAMES)
    assert 0x10 not in font.DEAD_MARK and 0x38 not in font.DEAD_MARK


def test_the_light_flag_is_a_lamp_filled_on_and_hollow_off():
    run = Session(seed=1)
    region = panel.REGIONS["lit"]
    def cell(screen):
        return [screen.pixels[(region.row * CELL + dy) * 256 + region.col * CELL + dx]
                for dy in range(CELL) for dx in range(CELL)]
    def rows(glyph):
        return [1 if glyph[dy] & (0x80 >> dx) else 0 for dy in range(CELL) for dx in range(CELL)]
    run.step()
    screen = Screen(); run.draw(screen)
    assert cell(screen) == rows(font.LIT_OFF), "off: not the hollow lamp"
    run.step(Intent(torch=True))
    screen = Screen(); run.draw(screen)
    assert cell(screen) == rows(font.LIT), "on: not the filled lamp"
    # Repainted on the change and not otherwise.
    run.step()
    assert "lit" not in run.panel.dirty
    run.step(Intent(torch=True))
    assert not run.cone.lit and "lit" in run.panel.dirty
