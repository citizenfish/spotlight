"""Screenshots: the colour has to be the window's colour, and the pixels the
window's pixels.

Issue #45. **Nobody in this project had ever seen a frame of the game.** Every
playtest note so far was written from a run's `.json` and `.txt`, because the
headless driver opens no window and the playtester agents cannot open one; the
look-and-feel round is about to ask two of them to judge the art from PNGs.

So the failure these tests exist to prevent is not a crash. It is a picture
that is subtly *not the game*: colour resolved by a second copy of the ink and
paper rules, or a screenshot smoothed on the way out. Either would be believed,
and either would send a reviewer after a fault that is not there -- or, worse,
would hide one that is. Hence:

* the frame goes through `frontend.display.resolve`, the window's own call, and
  a saved PNG is compared byte for byte against what `Display.render` puts up;
* an integer scale repeats pixels and invents no colours;
* the hardware flash phase is a parameter, because a still can only show one
  half of the cycle and the title screen's prompt is a flashing cell.

And it all has to happen with no window and no display device at all, which is
the whole point: the machines that need these pictures have no screen.
"""

import os

import pygame
import pytest

from spikes import spike_driver as driver, spike_snap
from spotlight.core.constants import (
    BLUE, CELL, SCREEN_H, SCREEN_W, WHITE, YELLOW, rgb,
)
from spotlight.core.screen import Screen, attr_byte
from spotlight.frontend.display import FLASH_PERIOD, Display


def a_screen() -> Screen:
    """One cell of bright white on blue, with a diagonal drawn in it.

    A diagonal because it is the shape any smoothing gives itself away on: an
    interpolated edge grows colours that are in neither the ink nor the paper.
    """
    screen = Screen()
    screen.set_attr(0, 0, attr_byte(ink=WHITE, paper=BLUE, bright=True))
    for i in range(CELL):
        screen.plot(i, i, True)
    return screen


# --- the colour is the window's colour --------------------------------------

def test_a_known_screen_resolves_to_known_colours():
    """Ink where a pixel is set, paper where it is not, at the bright level."""
    surf = spike_snap.surface(a_screen())
    assert surf.get_size() == (SCREEN_W, SCREEN_H), "not the real resolution"
    assert surf.get_at((0, 0))[:3] == rgb(WHITE, bright=True)
    assert surf.get_at((1, 0))[:3] == rgb(BLUE, bright=True)
    assert surf.get_at((7, 7))[:3] == rgb(WHITE, bright=True)


def test_the_whole_cell_shares_one_ink_and_one_paper():
    """Attribute clash, in a screenshot. If a snapshot could give two pixels of
    a cell different colours it would be a picture of a machine that does not
    exist, and the clash is the constraint the whole look is designed around."""
    surf = spike_snap.surface(a_screen())
    lit = {surf.get_at((i, i))[:3] for i in range(CELL)}
    dark = {surf.get_at((i, (i + 1) % CELL))[:3] for i in range(CELL)}
    assert len(lit) == 1 and len(dark) == 1


def test_the_snapshot_is_pixel_identical_to_what_the_window_draws():
    """The acceptance criterion, and the reason `resolve` was lifted out of
    `Display.render` rather than copied.

    A screenshot that could disagree with the window is worth less than no
    screenshot at all, because somebody would act on it. Compared as raw RGB
    bytes rather than cell by cell, so nothing can be right on the samples and
    wrong in between.
    """
    pygame.init()
    try:
        display = Display(scale=1)
        screen = a_screen()
        display.render(screen)
        window = pygame.image.tostring(display.surface, "RGB")
        shot = pygame.image.tostring(spike_snap.surface(screen), "RGB")
    finally:
        pygame.quit()
    assert shot == window


def test_a_saved_png_is_pixel_identical_to_the_frame(tmp_path):
    """...and it survives the round trip through the file. PNG is lossless and
    this is what says so, because a reviewer looks at the file, not the
    surface."""
    screen = a_screen()
    path = spike_snap.save(screen, str(tmp_path / "frame.png"))
    loaded = pygame.image.load(path)
    assert (pygame.image.tostring(loaded, "RGB")
            == pygame.image.tostring(spike_snap.surface(screen), "RGB"))


# --- the flash phase --------------------------------------------------------

def test_the_flash_phase_swaps_ink_and_paper():
    """A flashing cell has two appearances and a still can only show one.

    The gallery photographs the title screen both ways round because PRESS ANY
    KEY is a flashing cell: photographed one way only, it would be reviewed as
    though it were plain text, which is a thing that has already happened to it
    in a design conversation.
    """
    screen = Screen()
    screen.set_attr(0, 0, attr_byte(ink=YELLOW, paper=BLUE, flash=True))
    screen.plot(0, 0, True)

    normal = spike_snap.surface(screen, flashing=False)
    flashed = spike_snap.surface(screen, flashing=True)
    assert normal.get_at((0, 0))[:3] == rgb(YELLOW)
    assert normal.get_at((1, 0))[:3] == rgb(BLUE)
    assert flashed.get_at((0, 0))[:3] == rgb(BLUE), "ink did not invert"
    assert flashed.get_at((1, 0))[:3] == rgb(YELLOW), "paper did not invert"


def test_a_cell_without_the_flash_bit_ignores_the_phase():
    """Only cells that asked to flash flash. Otherwise half the snapshots of
    any screen would come out inverted."""
    screen = Screen()
    screen.set_attr(0, 0, attr_byte(ink=YELLOW, paper=BLUE))
    screen.plot(0, 0, True)
    assert (pygame.image.tostring(spike_snap.surface(screen, True), "RGB")
            == pygame.image.tostring(spike_snap.surface(screen, False), "RGB"))


# --- scaling ----------------------------------------------------------------

def test_an_integer_scale_repeats_pixels_and_nothing_else():
    """Nearest neighbour, so every source pixel becomes a solid square.

    `transform.scale` and `transform.smoothscale` differ by one word, and the
    smoothed one would blur every screenshot the look-and-feel round is judged
    from -- softening exactly the hard pixel edges that are under review, and
    inventing colours the Spectrum cannot make.
    """
    big = spike_snap.enlarge(spike_snap.surface(a_screen()), 3)
    assert big.get_size() == (SCREEN_W * 3, SCREEN_H * 3)
    for dy in range(3):
        for dx in range(3):
            assert big.get_at((dx, dy))[:3] == rgb(WHITE, bright=True)
            assert big.get_at((3 + dx, dy))[:3] == rgb(BLUE, bright=True)


def test_scaling_invents_no_colours():
    """The strongest form of the same rule: the enlarged frame uses exactly the
    colours the frame used, and a diagonal is where a blur would show up."""
    small = spike_snap.surface(a_screen())
    big = spike_snap.enlarge(small, 3)

    def colours(surf):
        raw = pygame.image.tostring(surf, "RGB")
        return {raw[i:i + 3] for i in range(0, len(raw), 3)}

    assert colours(big) == colours(small)


def test_a_scale_below_one_is_refused():
    """There is no honest way to shrink a 1-bit display: it would have to throw
    pixels away or average them, and both lie about the art."""
    with pytest.raises(ValueError):
        spike_snap.enlarge(spike_snap.surface(Screen()), 0)


def test_both_default_scales_are_written(tmp_path):
    """1:1 is the only honest view of the pixels; x3 is what a person can
    actually look at. Both, every time, so the reviewer picks."""
    paths = spike_snap.save_scales(Screen(), str(tmp_path / "shot"))
    assert [os.path.basename(p) for p in paths] == ["shot_x1.png",
                                                    "shot_x3.png"]
    assert pygame.image.load(paths[0]).get_size() == (SCREEN_W, SCREEN_H)
    assert pygame.image.load(paths[1]).get_size() == (SCREEN_W * 3,
                                                      SCREEN_H * 3)


# --- no window, no display device -------------------------------------------

def test_it_writes_a_png_with_no_display_initialised(tmp_path):
    """The whole reason this exists: the machines that need the pictures have
    no screen.

    `pygame.display` is shut down first and checked to be still shut down
    after, so a snapshot cannot quietly start depending on a window that the
    tests happen to have opened for something else.
    """
    pygame.display.quit()
    path = spike_snap.save(a_screen(), str(tmp_path / "headless.png"), scale=3)
    assert not pygame.display.get_init(), "saving a PNG opened a display"
    assert os.path.getsize(path) > 0


# --- the driver's --snap ----------------------------------------------------

def test_snap_writes_a_png_per_frame_per_scale(tmp_path, capsys):
    """`--snap 0,300,900` is three frames at two scales: six files, beside the
    two reports and named after the same run."""
    code = driver.main(["--bot", "listener", "--seed", "1",
                        "--snap", "0,300,900", "--out", str(tmp_path)])
    assert code == 0
    pngs = sorted(p.name for p in tmp_path.glob("*.png"))
    assert len(pngs) == 6, pngs
    for frame in ("f00000", "f00300", "f00900"):
        assert any(frame in p and p.endswith("_x1.png") for p in pngs)
        assert any(frame in p and p.endswith("_x3.png") for p in pngs)
    # One run, one name: the pictures and the reports have to sort together or
    # nobody can tell which run a picture came from.
    stem = sorted(tmp_path.glob("*.json"))[0].name[:-len(".json")]
    assert all(p.startswith(stem) for p in pngs)
    assert len(list(tmp_path.glob("*.txt"))) == 1
    out = capsys.readouterr().out
    assert all(name in out for name in pngs), "the paths were not printed"


def test_snap_turns_the_drawing_on_by_itself(tmp_path, monkeypatch):
    """`--snap` implies `--draw`. Making the user pass both would only ever
    produce an empty directory and a puzzled tester."""
    drawn = []
    monkeypatch.setattr(driver, "Snapper", _recording(drawn))
    driver.main(["--bot", "statue", "--frames", "10", "--snap", "5",
                 "--out", str(tmp_path)])
    assert drawn, "nothing was drawn, so --snap did not imply --draw"


def _recording(drawn):
    class Recorder:
        paths: list = []

        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, run, screen):
            drawn.append(run.frame)

        def missed(self):
            return []
    return Recorder


def test_frame_zero_is_the_run_before_it_has_run(tmp_path):
    """A snapshot is named by its session frame, and 0 is the state before the
    first step -- so `--snap 0` is not a request that quietly fails.

    Worth pinning because of what it costs: the light field is built during a
    step, so frame 0 photographs almost black, and the window never shows it at
    all. Frame 1 is the first picture a player would see. Anybody who changes
    this numbering has to change the README paragraph that says so.
    """
    seen = []
    driver.drive(seed=1, frames=3, draw=True,
                 on_frame=lambda run, screen: seen.append(run.frame))
    assert seen == [0, 1, 2, 3]


def test_a_frame_the_run_never_reached_is_said_out_loud(tmp_path, capsys):
    """A run can end before the frame somebody asked for. Saying so beats a gap
    in a directory listing that the reader has to explain to themselves."""
    driver.main(["--bot", "statue", "--frames", "60", "--snap", "30,5000",
                 "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert "no snapshot of 5000" in out
    assert len(list(tmp_path.glob("*.png"))) == 2


class _FakeSnap:
    """Stands in for `spike_snap` so a test can see the flash phase asked for."""

    DEFAULT_SCALES = (1,)

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def save_scales(self, screen, base, scales, flashing):
        self.calls.append((base, flashing))
        return [f"{base}_x1.png"]


class _AtFrame:
    def __init__(self, frame: int) -> None:
        self.frame = frame


def test_a_run_snapshot_uses_the_flash_phase_of_its_own_frame(tmp_path):
    """A run's snapshots are what the player would have been looking at, and
    that includes which half of the flash cycle the hardware was in.

    The window renders once per session frame, which is what lets the frame
    number stand in for the phase. If that ever stops being true -- a frame
    dropped, or a render per two frames -- this is the assumption to revisit.
    """
    snapper = driver.Snapper(str(tmp_path / "run"), [1, FLASH_PERIOD])
    fake = _FakeSnap()
    snapper._snap = fake
    snapper(_AtFrame(1), Screen())
    snapper(_AtFrame(FLASH_PERIOD), Screen())
    assert [flashing for _base, flashing in fake.calls] == [False, True]
    assert snapper.taken == [1, FLASH_PERIOD]
    assert snapper.missed() == []


def test_bad_numbers_are_refused_rather_than_guessed_at(tmp_path, capsys):
    """`--snap 0,three` is a typo, and a tool that guessed would write the
    wrong pictures silently."""
    assert driver.main(["--snap", "0,three", "--out", str(tmp_path)]) == 2
    assert "whole numbers" in capsys.readouterr().err
