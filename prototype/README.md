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
