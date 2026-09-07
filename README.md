# Spotlight

I've always wanted to create a game based upon the jeopardy of darkness so here is Spotlight

First step is to prototype in Pygame then port to the ZX Spectrum

## The game

You are an emergency worker in a dark building. Seven people are hurt and
trapped in it, and they are bleeding. Find them, walk them out through the exit
door, and get back in for the next one before the ones you left run out of time.

Your torch shows you the room. It also shows the biting flies where you are.
That trade is the whole game.

## Playing it

You need Python 3.12 and about a minute. On a clean machine:

```sh
git clone https://github.com/citizenfish/spotlight.git
cd spotlight
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd prototype
python -m spotlight
```

`--scale N` makes the window bigger or smaller; the default is 3, which is a
768x576 window for a 256x192 screen.

The title screen says everything a first-time player needs, in words. Briefly:

| | |
| --- | --- |
| **Arrow keys** | walk |
| **T** | torch on and off |
| **Space** | flyspray |

Touching the exit hands over whoever is following you and the run continues;
**keep walking into the door** to leave the building for good.

## Working on it

```sh
pip install -r requirements-dev.txt
cd prototype
pytest                                        # headless, no window needed
python -m spikes.spike_driver --bot listener --seeds 5     # play it without hands
```

The driver runs the real game loop with no window and writes two reports per
run: a JSON of every measurement, and five or six lines of English for talking
a playtest through afterwards. `--bot` takes `statue`, `wanderer`, `listener`,
`scout`, `crosser` or `oracle`; `--script "300R 100D T 600."` presses keys.

## How it is built

```
prototype/          the Pygame prototype
  spotlight/
    core/           portable game logic - no pygame, no floats
    frontend/       window, keyboard, audio - the port replaces this
  spikes/           the game as it stands, until the architecture lands
  tests/
spectrum/           the Z80 port. Empty; the toolchain is undecided
assets/             source-of-truth art and level data
tools/              converters: assets -> prototype and Spectrum formats
```

`core.screen.Screen` is a real Spectrum display: a 1-bit bitmap and a 32x24
grid of hardware attribute bytes, two colours per 8x8 cell. Everything draws
through it, so attribute clash shows up here rather than at port time.
`prototype/tests/test_portability.py` fails if anything under `core/` imports
pygame or uses a float.

Design lives in a separate Obsidian vault, which is where mechanics are argued
out before anything is built. This repo is the source of truth for what runs;
the vault is the source of truth for why.
