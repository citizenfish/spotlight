"""Demo mode: the game plays itself in the window, like an arcade attract loop.

    python -m spikes.spike_demo                     # the listener, for ever
    python -m spikes.spike_demo --bot oracle --runs 3 --seed 7 --scale 3

Issue #89. The user wants to screen-record the game in action with a voice
over it, so it has to run unattended: the ordinary window and the ordinary
shell, with a bot on the controls instead of a person. Nothing about the game
is different -- the bot presses the same keys a player would, through the
same `Shell.key` and `Shell.frame` -- so what is on screen is the game and
not a rendering of it. On the title it presses `S` after a few seconds; on an
ending screen it reads the tally for a few seconds and presses `SPACE`, with
the next seed, so the loop never shows the same run twice. `ESC` or closing
the window stops it. With no `--level` the runs cycle through every level
there is, in order (issue #109), so a recording of the loop shows the whole
game; `--level N` pins it to one.

Host-side scaffolding, like the driver and the gallery: pygame, argparse and
a clock. The loop itself is a class with no window in it, so a test can run
it headless through a title, a run, an ending and a restart.
"""

import argparse
import sys

import pygame

from spotlight.core.screen import Screen
from spotlight.frontend.display import Display

from . import bots, spike1, spike_sound
from . import levels, session as session_mod

FRAME_RATE = 50

#: How long the title and the ending screens are left up, in seconds. Long
#: enough to read; short enough that a loop is mostly game.
TITLE_SECONDS = 4
ENDING_SECONDS = 6


class Demo:
    """The attract loop: a shell, a bot, and the two waits between runs."""

    def __init__(self, shell: spike1.Shell, bot: str = "listener",
                 runs: int = 0, title_seconds: int = TITLE_SECONDS,
                 ending_seconds: int = ENDING_SECONDS,
                 cycle: tuple[int, ...] = ()) -> None:
        self.shell = shell
        self.bot_name = bot
        self.bot = None
        #: The levels the runs cycle through, or none to leave the shell's
        #: building alone. Each start hands the shell the next one.
        self.cycle = tuple(cycle)
        #: Runs still to play; zero means for ever.
        self.runs_left = runs
        self.forever = runs == 0
        self.played = 0
        self.title_frames = title_seconds * FRAME_RATE
        self.ending_frames = ending_seconds * FRAME_RATE
        #: Frames spent on the current title or ending screen.
        self.waited = 0

    @property
    def done(self) -> bool:
        return not self.forever and self.runs_left <= 0

    def frame(self) -> None:
        """One frame of the loop: a key or two, then the shell's own frame."""
        shell = self.shell
        if shell.state == spike1.TITLE:
            self.waited += 1
            if self.waited >= self.title_frames and not self.done:
                self._start()
            shell.frame()
            return
        if shell.state == spike1.ENDED:
            self.waited += 1
            if self.waited >= self.ending_frames and not self.done:
                shell.seed += 1
                self._start(pygame.K_SPACE)
            shell.frame()
            return
        # In play: the bot's intent, pressed as a player would press it. A
        # torch or spray in the intent is an edge -- one press -- exactly as
        # `Intent` says, and `Shell.key` treats it so.
        intent = self.bot.intent(shell.run)
        if intent.torch:
            shell.key(pygame.K_t)
        if intent.spray:
            shell.key(pygame.K_SPACE)
        shell.frame(intent.dx, intent.dy)

    def _start(self, key: int = pygame.K_s) -> None:
        if self.cycle:
            number = self.cycle[self.played % len(self.cycle)]
            self.shell.building, self.shell.start_room = levels.pick(number)
        self.shell.key(key)
        self.bot = bots.make(self.bot_name, seed=self.shell.seed)
        self.waited = 0
        self.played += 1
        if not self.forever:
            self.runs_left -= 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the game unattended in the window, a bot on the "
                    "controls, looping through runs like an attract mode.")
    parser.add_argument("--bot", default="listener", choices=sorted(bots.BOTS),
                        help="who plays (default: listener)")
    parser.add_argument("--seed", type=int, default=session_mod.DEFAULT_SEED,
                        help="the first run's seed; each run after adds one")
    parser.add_argument("--runs", type=int, default=0,
                        help="how many runs before quitting; 0 loops for ever")
    parser.add_argument("--title-seconds", type=int, default=TITLE_SECONDS)
    parser.add_argument("--ending-seconds", type=int, default=ENDING_SECONDS)
    parser.add_argument("--scale", type=int, default=3)
    parser.add_argument("--border", default=None,
                        help="a Spectrum colour name for the window's margin")
    parser.add_argument("--dark-clegs", dest="luminous", action="store_false",
                        help="the old look: Clegs drawn only where lit (#92)")
    parser.add_argument("--level", type=int, default=None,
                        help="play this level only (default: cycle through "
                             "every level there is)")
    parser.add_argument("--trail", dest="trail", action="store_true",
                        help="the old look: the player's lights leave a memory")
    args = parser.parse_args(argv)

    border_argv = ["--border", args.border] if args.border else []
    try:
        border = spike1.border_from(border_argv)
        cycle = () if args.level is not None else tuple(levels.levels())
        building, _ = levels.pick(args.level if args.level is not None
                                  else levels.DEFAULT_LEVEL)
    except ValueError as err:
        print(err, file=sys.stderr)
        return 2

    pygame.init()
    try:
        display = Display(scale=args.scale, title="Spotlight - demo",
                          border=border)
        clock = pygame.time.Clock()
        screen = Screen()
        speaker = spike_sound.Speaker()
        speaker.open()
        shell = spike1.Shell(screen, speaker=speaker, seed=args.seed,
                             luminous=args.luminous, trail=args.trail,
                             building=building)
        demo = Demo(shell, bot=args.bot, runs=args.runs,
                    title_seconds=args.title_seconds,
                    ending_seconds=args.ending_seconds, cycle=cycle)
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN \
                        and event.key == pygame.K_ESCAPE:
                    running = False
            demo.frame()
            display.render(screen)
            clock.tick(FRAME_RATE)
            if demo.done and shell.state != spike1.PLAY \
                    and demo.waited >= demo.ending_frames:
                running = False
    finally:
        speaker.close()
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
