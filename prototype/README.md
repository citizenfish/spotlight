# Spotlight prototype (Pygame)

## Setup

From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # or requirements.txt for runtime only
```

## Run

```sh
cd prototype
python -m spotlight            # --scale N to resize the window (default 3)
```

That starts the game. Three controls, and the title screen names them: arrow
keys to walk, `T` for your torch, `SPACE` for the flyspray. `ESC` quits.

## Developer keys

Off by default, and deliberately not mentioned on any screen:

```sh
python -m spotlight --debug
```

That unlocks about sixteen keys on ordinary letters — the searchlight's shape
and speed, the light hue, the remembered-light wipe, and `F`, which reveals the
whole room and everybody in it and holds it there. They are listed in the
`Debug` class in `spikes/spike1.py`.

Without the flag only the three controls and `ESC` do anything, and every other
key is ignored. That is the point: a playtester who presses a key to see what it
does would otherwise be able to solve the game by accident and never know they
had.

## Headless runs

A scripted or bot-driven session, from a seed, with no window and no host:

```sh
python -m spikes.spike_driver --bot listener --seeds 5
python -m spikes.spike_driver --bot statue --light --frames 3000
python -m spikes.spike_driver --script "300R 100D T 600."   # exact replay
python -m spikes.spike_driver --bot oracle --repeat          # check a seed reproduces
```

It runs the **real** loop with the real constants — `session.Session.step`, the
same method the window drives — and writes two files per run into `runs/`:

| File | Reader | Contains |
| --- | --- | --- |
| `*.json` | the tester agent | metrics that tabulate across seeds, one record per person, and the whole event log |
| `*.txt` | a human | five or six lines in words: who got out, who did not and roughly when, how it ended, how long it took |

The four reference bots are `statue`, `wanderer`, `listener` and `oracle`, named
after the ones the phase-0 difficulty targets are stated against. They walk;
they cannot reach into the run.

## Seeing it without a window

Until issue #45 the only way to look at this game was to be sitting in front of
it: the driver has no window, so every playtest note in the project was written
from the two files above and nobody reviewing the art had seen a frame. These
two flags are the answer, and both work with no window and no display device.

```sh
cd prototype
python -m spikes.spike_driver --bot listener --seed 1 --snap 0,300,900
python -m spikes.spike_driver --gallery runs/gallery
```

| Flag | What it does |
| --- | --- |
| `--snap 0,300,900` | Saves those frames of the run as PNGs, into `--out`, named after the same run as its `.json` and `.txt`. Implies `--draw`. |
| `--scales 1,3` | Which scales to write (the default). 1:1 is the only honest view of the pixels; x3 is what a person can actually look at. |
| `--gallery DIR` | Writes the sheets a look-and-feel review needs and prints the paths: the title screen (both halves of its flash), the ending screen, a labelled sprite sheet, and each room both fully lit and as it looks a few seconds into a run. Runs no seeds and writes no report. |

A snapshot is named by its session frame. **Frame 0 is the run before it has
run** — the walls are drawn but no light has been applied yet, so it comes out
almost black; the window never shows that frame, because the loop steps and then
draws. Frame 1 is the first picture a player sees, and the opening flash of a
room is frames 1 to 12.

Scaling is nearest-neighbour at whole numbers only — a smoothed screenshot of a
1-bit display invents colours the Spectrum does not have. The colour comes from
the window's own resolver, so a PNG cannot disagree with what a player sees.

## Hearing it without a speaker

The same problem, and the same answer (issue #54). Everything the game can say
goes down one channel — the proximity sonar, a body's tick and fourteen effects,
because a Spectrum has one beeper — and these two flags write it to disk so it
can be judged by ear rather than described.

```sh
cd prototype
python -m spikes.spike_driver --bank runs/sounds
python -m spikes.spike_driver --bot listener --seed 1 --wav runs/listener.wav
```

| Flag | What it does |
| --- | --- |
| `--bank DIR` | One WAV per effect, plus the sonar at its three rates and a body's tick from fresh to about to turn, and an `effects.wav` of all fourteen in order. Runs no seeds and writes no report. |
| `--wav FILE` | Renders that run's audio alongside its two reports, from the decisions the speaker actually made frame by frame. With `--seeds N` the seed goes in the name. |

Both work with no audio device at all: the files are written and nothing is
played. The run render is a *recording* — it comes from what the arbiter decided
as the run went past, not from a second pass over the event log, because a
re-derived performance is not evidence about the one that happened.

## Test

```sh
cd prototype
pytest
```

## Layout

| Path | Contains |
| --- | --- |
| `spotlight/core/` | Portable game logic. **No pygame, no floats.** |
| `spotlight/frontend/` | Pygame window, keyboard, audio — replaced by the port. |
| `spotlight/data/` | Level and entity data. |
| `tests/` | Includes `test_portability.py`, which fails the build if `core/` imports a host library or uses a float literal. |

The split is the point: `core/` is the part that has to survive the move to
Z80, so it is written as if the Z80 were already the target — integers, fixed
point, and an 8×8 attribute grid. `frontend/` is the throwaway half.
