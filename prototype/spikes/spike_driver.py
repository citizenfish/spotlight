"""Run a session headless, from a seed, and write the two reports.

    python -m spikes.spike_driver --bot listener --seeds 5
    python -m spikes.spike_driver --bot statue --light --frames 3000
    python -m spikes.spike_driver --script "300R 100D T 600."

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
          screen: Screen | None = None) -> session_mod.Session:
    """Play one session to its end, or to the frame limit. Returns the run.

    The whole driver, and it is six lines, because everything that makes a run
    a run lives in `Session`. If this function ever grows a rule about the game
    in it, the rule is in the wrong place.
    """
    run = session_mod.Session(seed=seed)
    if draw and screen is None:
        screen = Screen()
    while run.over is None and run.frame < frames:
        run.step(bot.intent(run) if bot is not None else session_mod.IDLE)
        if draw:
            run.draw(screen)
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


def write(run, name: str, out_dir: str, when: str = "",
          extra: dict | None = None) -> tuple[str, str]:
    """Write both reports. Returns the two paths."""
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, f"{when or stamp()}_{name}_seed{run.seed}")
    with open(f"{base}.json", "w") as handle:
        json.dump(report.results(run, bot=name, extra=extra), handle, indent=1)
        handle.write("\n")
    with open(f"{base}.txt", "w") as handle:
        handle.write("\n".join(report.human(run, bot=name, measured=extra))
                     + "\n")
    return f"{base}.json", f"{base}.txt"


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
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    name = "script" if args.script else args.bot
    when = stamp()
    rows = []
    for i in range(args.seeds):
        seed = args.seed + i
        bot = _bot(args, seed)
        run = drive(bot, seed=seed, frames=args.frames, draw=args.draw)
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

    if len(rows) > 1:
        print()
        for line in summary_lines(rows):
            print(line)
    return 0


def _bot(args, seed: int):
    if args.script:
        return bots.Script(bots.parse_script(args.script), seed=seed)
    return bots.make(args.bot, seed=seed, light=args.light)


if __name__ == "__main__":
    raise SystemExit(main())
