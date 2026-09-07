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
