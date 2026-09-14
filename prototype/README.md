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
python -m spotlight --border blue   # a Spectrum BORDER round the frame
```

That starts the game. `--border` takes one of the Spectrum's fifteen colours
(`black` … `white`, `bright-blue` … `bright-white`), default `black`; it is the
window's margin and nothing else -- no snapshot shows it and no rule reads it. Three controls, and the title screen names them: arrow
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
| `--gallery DIR` | Writes the sheets a look-and-feel review needs and prints the paths: the title screen (both halves of its flash), the ending screen, a labelled sprite sheet of the objects, the doors and the body, a people sheet with every frame of the three standing figures and their walk laid out as a strip, each room fully lit and as it looks a few seconds into a run — the same instant four times, with every walker on each stride of the cycle N A N B in turn, so the walk can be judged where a figure is actually seen — and the frames a bot cannot produce on its own — a spotlight burning on the floor, a moment's flash, and **a body in a played room beside somebody standing up**. Runs no seeds and writes no report. |

A snapshot is named by its session frame. **Frame 0 is the run before it has
run** — the walls are drawn but no light has been applied yet, so it comes out
almost black; the window never shows that frame, because the loop steps and then
draws. Frame 1 is the first picture a player sees.

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
| `--bank DIR` | One WAV per effect, plus the sonar at its three rates and a body's tick from fresh to about to turn, an `effects.wav` of all fourteen in order, and the four music files below. Runs no seeds and writes no report. |
| `--wav FILE` | Renders that run's audio alongside its two reports, from the decisions the speaker actually made frame by frame. With `--seeds N` the seed goes in the name. |

The music is one more thing down the same channel, and it is bottom of the order
(issue #55): the theme on the title screen, a distant siren in play (issue
#67), and **a frame with a click, a tick or an effect in it is a frame with no
music in it.** What is left of the frame after the fixed work and the Clegs is
what the music gets — `52,416 − 19,584 − 830n` T-states, where the 830 is
`building.CLEG_COST` and is read from there rather than copied — and it renders
whole half-cycles of the note in play until that runs out, so the music breaks
up as the room fills and comes back when it empties.

The siren is four integers and a decrement: the period falls from 8,750
T-states (400 Hz) to 5,000 (700 Hz) by 25 a frame over three seconds, rises
the same way, and rests for twelve; the cycle is eighteen seconds and it loops.
It is linear in the period, not the frequency, because the Z80 decrements a
delay constant and never divides. It holds a pitch — four or more half-cycles a
frame — at every load up to eighteen Clegs, and is down to a single flip at the
top of the wail at the port model's ceiling of 36; the busiest room measured
over seven bots and five seeds held 25. Two thirds of every run is the siren
waiting, by design, and the run report says so rather than counting it as a
dropout. The 50 Hz gate under every note is exposed by a six-second glide and
is not smoothed: it is the machine, and it was heard and ruled on. The
ostinato it replaced is struck through in the vault, not kept here.

`theme.wav` and `siren.wav` are the two with the building quiet (the siren
over two cycles, as the sketch was); `siren-under-load.wav` is the wail
thinning as the room fills to the ceiling; `siren-with-sonar.wav` is a swarm
arriving over two cycles so that it is on top of you as the second wail
starts, and is the file the dropout should be judged on.

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
