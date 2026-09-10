"""Run a session headless, from a seed, and write the two reports.

    python -m spikes.spike_driver --bot listener --seeds 5
    python -m spikes.spike_driver --bot statue --light --frames 3000
    python -m spikes.spike_driver --script "300R 100D T 600."
    python -m spikes.spike_driver --bot listener --snap 0,300,900
    python -m spikes.spike_driver --gallery runs/gallery

Issue #17, and it is the enabling issue for the whole of phase 2. **Every number
in the phase-0 review came from monkey-patching the loop to fake a headless
run**, which means every one of them came from code nobody reviewed and nobody
kept. This is the supported version.

Three things it is careful about, because they are what make the numbers worth
having:

* **It runs the real loop.** `Session.step` is the same method the window
  drives, with the same constants, in the same order. There is no second
  simulation here and there must never be one -- a parallel model is a thing
  that can be right about a game that does not exist.
* **A seed names a run.** Everything random in a session comes from the session
  seed through the Z80's own xorshift, so the same seed and the same bot give
  the same run, today and after a constant moves. `--repeat` checks it.
* **It needs no host at all.** No window, no audio device, no pygame: the
  session, the bots and the reports are all portable code. It therefore works
  under `SDL_VIDEODRIVER=dummy` because it works with no SDL whatsoever.
  `--draw` exercises the real drawing path anyway, through `core.Screen`, so
  that a change which breaks rendering fails here too rather than only in front
  of a tester.

**Two artefacts per run, for two readers.** The `.json` is for the tester agent
-- metrics that tabulate across seeds, one record per person, and the whole
event log. The `.txt` is five or six lines of English for the user to talk from
while a playtester remembers. Neither is a compromise between the two.

**And now a third, when asked for: a picture** (issue #45). Every playtest note
in this project was written from those two files, because nobody reviewing the
game could open a window -- so nobody had ever seen a frame of it. `--snap`
photographs named frames of the run into the same directory and under the same
name as its reports; `--gallery` writes the screens that are not a run at all.
Both go through `spike_snap`, which resolves colour with the window's own code,
so a picture cannot disagree with what a player sees. Neither is loaded unless
it is asked for, so this module still runs where there is no pygame.

This module is host-side scaffolding: argparse, files, stdout. It is named
`spike_*` so the portability suite exempts it, and it is the only part of the
driver that is not portable.
"""

import argparse
import json
import os
import sys
import time

from spotlight.core.screen import Screen

from . import bots, report, session as session_mod

#: Frames a run is allowed before the driver stops it. 9000 is three minutes at
#: 50Hz, comfortably past the 144 seconds it currently takes for the last
#: worker to bleed out, so a default run ends on its own terms.
DEFAULT_FRAMES = 9000

#: Where reports go unless told otherwise. Gitignored: they are measurements,
#: not source, and they belong in the vault when they mean something.
DEFAULT_OUT = "runs"


def drive(bot=None, seed: int = session_mod.DEFAULT_SEED,
          frames: int = DEFAULT_FRAMES, draw: bool = False,
          screen: Screen | None = None, on_frame=None,
          metrics: bool = True) -> session_mod.Session:
    """Play one session to its end, or to the frame limit. Returns the run.

    The whole driver, and it is six lines, because everything that makes a run
    a run lives in `Session`. If this function ever grows a rule about the game
    in it, the rule is in the wrong place.

    `on_frame(run, screen)` is called after each frame is drawn, and before any
    of the next one happens, so a caller can look at a frame while it exists
    (issue #45: `--snap` photographs one). It only fires when `draw` is on --
    there is nothing to look at otherwise. It may not touch the run: this is a
    window onto the loop, not a hook into it, and a driver that could change a
    run would make every number it prints unrepeatable.

    **A pause is not honoured here, and that is deliberate** (issue #52). Three
    moments ask the *shell* to stop stepping the game for a while -- a death and
    the two endings -- and this loop asks `run.moments` for nothing. Its frames
    are frames of simulation: a hold here would mean the same `--frames` bought
    fewer stepped frames, every run would end somewhere else, and the tail of
    every event log in the project would shift. Bot runs are untouched by the
    moments and have to stay that way.

    **Frame zero is the run before it has run**, drawn once before the first
    step, so that a frame number given to `--snap` means the session frame of
    that name and `--snap 0` is not a request that quietly fails. It is worth
    knowing what it looks like: the light field is built during a step, so on
    frame zero the walls are drawn but every attribute is still black on black
    and the play area photographs almost empty. The **window never shows this
    frame** -- the host loop steps and then draws -- so frame 1 is the first
    picture a player sees, and the opening flash is frames 1 to 12.
    """
    # **The driver is where the repaint counter is on** (issue #46). The game
    # is played, not measured, and carries none of it; this is the thing that
    # measures, so every run it drives is priced. It costs a 704-byte compare
    # a frame, which three frames in four settle on the first instruction.
    run = session_mod.Session(seed=seed, metrics=metrics)
    if draw and screen is None:
        screen = Screen()
    if draw:
        run.draw(screen)
        if on_frame is not None:
            on_frame(run, screen)
    while run.over is None and run.frame < frames:
        run.step(bot.intent(run) if bot is not None else session_mod.IDLE)
        if draw:
            run.draw(screen)
            if on_frame is not None:
                on_frame(run, screen)
    if run.over is None:
        run.finish(session_mod.FRAME_LIMIT)
    return run


def stamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def measured(bot) -> dict | None:
    """Whatever the bot measured for itself, if it measured anything.

    The crossing walker's T3e figures are the first and may be the only ones
    (issue #29): a crossing is not something the session has a concept of, so
    the bot that walks one is the only thing that can count them.
    """
    summary = getattr(bot, "summary", None)
    return summary() if callable(summary) else None


def base_name(name: str, seed: int, out_dir: str, when: str = "") -> str:
    """What every artefact of one run is called, before its extension.

    One function because a run now writes more than the two reports: the
    snapshots share the name so that a run's `.json`, its `.txt` and its PNGs
    sort together in one listing (issue #45). Somebody reviewing a run wants
    all of it in front of them, and a picture whose filename does not say which
    run it came from is a picture nobody can act on.
    """
    return os.path.join(out_dir, f"{when or stamp()}_{name}_seed{seed}")


def write(run, name: str, out_dir: str, when: str = "",
          extra: dict | None = None) -> tuple[str, str]:
    """Write both reports. Returns the two paths."""
    os.makedirs(out_dir, exist_ok=True)
    base = base_name(name, run.seed, out_dir, when)
    with open(f"{base}.json", "w") as handle:
        json.dump(report.results(run, bot=name, extra=extra), handle, indent=1)
        handle.write("\n")
    with open(f"{base}.txt", "w") as handle:
        handle.write("\n".join(report.human(run, bot=name, measured=extra))
                     + "\n")
    return f"{base}.json", f"{base}.txt"


# --- photographing a run (issue #45) ---------------------------------------

def numbers(text: str, what: str) -> list[int]:
    """A comma-separated list of whole numbers, as given on the command line."""
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise ValueError(f"{what} must be whole numbers, not {part!r}")
        out.append(int(part))
    if not out:
        raise ValueError(f"{what} is empty")
    return out


class Snapper:
    """Saves named frames of a run as PNGs, as the run goes past them.

    A frame only exists while it is on screen: the play area is cleared and
    redrawn every frame, so there is no keeping one to photograph afterwards.
    Hence a hook into the loop rather than anything the run remembers.

    **pygame is imported here and not at the top of the module.** The driver's
    first claim, and the reason phase 2 could measure anything at all, is that
    it needs no host whatsoever -- no window, no audio device, no SDL. Taking a
    picture does need pygame, so the cost is paid by the runs that ask for one
    and by nobody else, and `--bot listener --seeds 5` on a machine without
    pygame goes on working exactly as it did.
    """

    def __init__(self, base: str, frames, scales=None) -> None:
        from . import spike_snap
        from spotlight.frontend.display import FLASH_PERIOD

        self._snap = spike_snap
        self._period = FLASH_PERIOD
        self.base = base
        self.wanted = set(frames)
        self.scales = tuple(scales or spike_snap.DEFAULT_SCALES)
        #: The files written, in the order they were written.
        self.paths: list[str] = []
        #: The frames actually caught. A run can end before a frame the caller
        #: asked for, and saying which were missed is more use than a gap in a
        #: directory listing.
        self.taken: list[int] = []

    def __call__(self, run, screen) -> None:
        if run.frame not in self.wanted:
            return
        # The phase the hardware flash would be in on that frame, so a
        # snapshot of a flashing cell shows what the player would have been
        # looking at rather than always the same half of the cycle. The window
        # renders once per session frame, which is what makes the two agree.
        flashing = (run.frame // self._period) % 2 == 1
        self.taken.append(run.frame)
        self.paths.extend(self._snap.save_scales(
            screen, f"{self.base}_f{run.frame:05d}", self.scales, flashing))

    def missed(self) -> list[int]:
        return sorted(self.wanted - set(self.taken))


#: The columns of the across-seeds summary, and the order they read best in.
#: Chosen against the eight difficulty targets in the phase-0 review, so that
#: the table on stdout is the table the tuning conversation needs.
SUMMARY = (
    ("seed", "seed", 5),
    ("ending", "ending", 12),
    ("secs", "seconds", 5),
    ("out", "rescued", 4),
    ("died", "died", 5),
    ("in", "still_inside", 3),
    ("blood", "blood_lost", 6),
    ("bites", "attachments", 6),
    ("1stbite", "first_attachment_seconds", 8),
    ("torch", "torch_seconds", 6),
    ("tries", "tries_lost", 6),
    ("dspread", "death_spread_seconds", 8),
    # Blood by lure, at the point of attachment (issue #22). The searchlight
    # is the largest single term in every dark-player number the tester has
    # taken, and until this hook existed the figure behind that claim was
    # inferred from proximity in time. Three columns rather than six because
    # the table has to stay readable; the JSON carries all of them.
    ("beam", "blood_by_beam", 5),
    ("torch", "blood_by_torch", 5),
    ("glow", "blood_by_glow", 5),
    # What each frame costs to draw (issue #46), which is what every slice of
    # the look-and-feel round has to be priced against. The first column is the
    # mean per hundred frames -- 306 is 3.06 cells a frame -- kept integer like
    # everything else here. `chgmax` is 704 in any run that entered a room,
    # because the opening flash changes the whole field at once.
    ("chg/100f", "cells_changed_per_100f", 8),
    ("chgp99", "cells_changed_p99", 6),
    ("chgmax", "cells_changed_max", 6),
    ("wall/100f", "wall_cells_changed_per_100f", 9),
)


def summary_lines(rows: list[dict]) -> list[str]:
    """The runs as a table, one line each. For reading, not for parsing.

    The JSON is what gets parsed. This is so that whoever ran it can see at a
    glance whether the seeds agree, because seeds that disagree wildly are
    themselves a finding.
    """
    head = "".join(f"{title:>{width}} " for title, _key, width in SUMMARY)
    lines = [head.rstrip(), "-" * len(head.rstrip())]
    for row in rows:
        cells = []
        for _title, key, width in SUMMARY:
            value = row.get(key, row["metrics"].get(key))
            cells.append(f"{'-' if value is None else value:>{width}} ")
        lines.append("".join(cells).rstrip())
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m spikes.spike_driver",
        description="Run Spotlight headless and write the two run reports.")
    parser.add_argument("--bot", default="statue",
                        choices=sorted(bots.BOTS),
                        help="which reference bot plays (default: statue)")
    parser.add_argument("--script", default=None,
                        help='fixed key presses instead of a bot, '
                             'e.g. "300R 100D T 600."')
    parser.add_argument("--seed", type=int, default=session_mod.DEFAULT_SEED,
                        help="the seed of the first run")
    parser.add_argument("--seeds", type=int, default=1,
                        help="how many consecutive seeds to run")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES,
                        help=f"frame limit per run (default {DEFAULT_FRAMES}, "
                             f"three minutes)")
    parser.add_argument("--light", dest="light", action="store_true",
                        default=None,
                        help="make the bot hold the torch on")
    parser.add_argument("--no-light", dest="light", action="store_false",
                        help="make the bot never light")
    parser.add_argument("--draw", action="store_true",
                        help="run the real drawing code too, into a Screen")
    parser.add_argument("--repeat", action="store_true",
                        help="run each seed twice and check they agree")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help=f"where the reports go (default {DEFAULT_OUT}/)")
    parser.add_argument("--no-files", action="store_true",
                        help="print the reports instead of writing them")
    parser.add_argument("--snap", default=None,
                        help="frames to save as PNGs, e.g. 0,300,900; "
                             "implies --draw. Frame 0 is before the first "
                             "step and has no light in it yet; frame 1 is the "
                             "first frame a player would see")
    parser.add_argument("--scales", default=None,
                        help="scales the PNGs are written at (default 1,3): "
                             "1:1 is the honest view, x3 is a readable one")
    parser.add_argument("--gallery", default=None,
                        help="write the look-and-feel sheets into this "
                             "directory and stop; runs no seeds")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        scales = numbers(args.scales, "--scales") if args.scales else None
        snap_at = numbers(args.snap, "--snap") if args.snap else []
    except ValueError as bad:
        print(bad, file=sys.stderr)
        return 2

    if args.gallery is not None:
        return gallery(args.gallery, scales)

    # A snapshot is of a drawn frame, so asking for one turns the drawing on.
    # Making the user pass both would only ever produce an empty directory and
    # a puzzled tester.
    draw = args.draw or bool(snap_at)

    name = "script" if args.script else args.bot
    when = stamp()
    rows = []
    for i in range(args.seeds):
        seed = args.seed + i
        bot = _bot(args, seed)
        snapper = (Snapper(base_name(name, seed, args.out, when), snap_at,
                           scales) if snap_at else None)
        run = drive(bot, seed=seed, frames=args.frames, draw=draw,
                    on_frame=snapper)
        extra = measured(bot)
        if args.repeat:
            again = drive(_bot(args, seed), seed=seed, frames=args.frames)
            if report.results(again, name)["metrics"] != \
                    report.results(run, name)["metrics"]:
                print(f"seed {seed} did not reproduce", file=sys.stderr)
                return 1
        results = report.results(run, bot=name, extra=extra)
        rows.append(results)

        print()
        for line in report.human(run, bot=name, measured=extra):
            print(line)
        if not args.no_files:
            paths = write(run, name, args.out, when, extra)
            print(f"\n  -> {paths[0]}\n  -> {paths[1]}")
        if snapper is not None:
            for path in snapper.paths:
                print(f"  -> {path}")
            if snapper.missed():
                # The run ended before those frames. Said out loud, because the
                # alternative is a reviewer counting six files, finding four,
                # and not knowing whether the tool or the game is at fault.
                print(f"  (the run ended at frame {run.frame}; no snapshot of "
                      f"{', '.join(str(f) for f in snapper.missed())})")

    if len(rows) > 1:
        print()
        for line in summary_lines(rows):
            print(line)
    return 0


def gallery(out_dir: str, scales=None) -> int:
    """Write the look-and-feel sheets and print where they went.

    It runs no seeds and writes no report: the gallery is not a measurement of
    a run, it is the game's own screens photographed so that somebody who
    cannot open a window can look at them. Kept in `spike_gallery` and imported
    here for the same reason as `Snapper` -- everything that needs pygame is
    loaded only when it is asked for, so the reporting driver still runs on a
    machine with no host libraries at all.
    """
    from . import spike_gallery

    paths = spike_gallery.write(out_dir, scales or spike_snap_scales())
    print(f"\ngallery: {len(paths)} files in {out_dir}")
    for path in paths:
        print(f"  -> {path}")
    return 0


def spike_snap_scales():
    """The default scales, without importing pygame until somebody wants one."""
    from . import spike_snap
    return spike_snap.DEFAULT_SCALES


def _bot(args, seed: int):
    if args.script:
        return bots.Script(bots.parse_script(args.script), seed=seed)
    return bots.make(args.bot, seed=seed, light=args.light)


if __name__ == "__main__":
    raise SystemExit(main())
