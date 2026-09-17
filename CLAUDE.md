# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**Spotlight** is a game built around the jeopardy of darkness — the player's
limited light is the core mechanic and the core constraint.

It is being developed in two phases:

1. **Prototype in Pygame** (Python) — establish and tune the mechanics.
2. **Port to the ZX Spectrum** in Z80 assembly.

The prototype is not throwaway: it is the design reference for the port. Every
mechanic proven in Pygame has to survive the move to 3.5MHz and 48K, so treat
the Spectrum's limits as design constraints on the prototype too (see
[Designing for the port](#designing-for-the-port)).

## Working agreement

Specification and planning happen in the **knowledge base before any code is
written**. The pipeline is:

```
discuss in the vault  →  agreed spec/plan note  →  GitHub issue  →  code
```

- **Vault:** `../spotlight_kb` — an Obsidian vault, and a separate git repo
  (`citizenfish/spotlight_kb`). This is where specs, mechanics, level design,
  memory maps and technical decisions live and get argued out.
- **Issues:** work is only coded from a GitHub issue on `citizenfish/spotlight`.
  Issues are derived from vault notes, not invented on the fly.
- **Code:** this repo (`citizenfish/spotlight`).

What this means in practice:

- When asked to design, spec, or plan something, write it as a note in the
  vault. Do not jump to implementation.
- When asked to implement something, expect an issue number. If there isn't
  one, ask whether to raise one — or whether this is a spike that should feed
  a vault note instead.
- Keep the vault as the source of truth for *why*. Keep this repo the source
  of truth for *what runs*. When implementation forces a design change, update
  the vault note rather than letting the two drift.
- Vault notes use Obsidian conventions: `[[wikilinks]]` between notes, frontmatter
  where it helps. Prefer linking notes to duplicating content.

## Layout

```
prototype/          Pygame prototype
  spotlight/
    core/           portable game logic — no pygame, no floats
    frontend/       pygame window, keyboard, audio — the port replaces this
    data/           level and entity data
  tests/
spectrum/           Z80 port (src/) — src/bitmaps.asm is generated; toolchain undecided
assets/             source-of-truth art and level data, authored as text
tools/              converters: assets -> prototype and Spectrum formats
```

The `core` / `frontend` split is the load-bearing decision. `core` is written
as if the Z80 were already the target, and `prototype/tests/test_portability.py`
enforces that mechanically: the suite fails if anything under `core/` imports
pygame or uses a float literal.

`core.screen.Screen` models the real display — a 1-bit bitmap plus a 32x24 grid
of hardware-format attribute bytes. Draw through it and attribute clash shows up
in the prototype rather than at port time.

**Art is authored as text in `assets/` and every table is generated from it.**
`assets/sprites/` and `assets/tiles/` hold `.txt` files of named ASCII grids;
`tools/bitmaps.py --python` writes `prototype/spikes/bitmaps_gen.py` and
`--asm` writes `spectrum/src/bitmaps.asm`, so the same source feeds both
machines. Both generated files are committed, and `tests/test_bitmaps_tool.py`
regenerates them and compares byte for byte — **if art and code have drifted,
the suite fails.** Nothing that draws declares bytes of its own:

```sh
python tools/bitmaps.py --python prototype/spikes/bitmaps_gen.py \
    --asm spectrum/src/bitmaps.asm assets/sprites assets/tiles
```

Design documentation lives in the vault, not in this repo, so there is one home
for it and no drift.

## Commands

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

cd prototype
python -m spotlight        # run (--scale N for window size)
pytest                     # 1577 tests, headless-safe
SPOTLIGHT_SLOW=1 pytest    # + 124 room runs (tests/test_rooms.py), ~25 s
```

Dependencies are a plain venv plus pinned `requirements.txt`; there is no
pyproject and the package is not installed — `prototype/pytest.ini` sets
`pythonpath` instead.

## Current state

A playable prototype with a face and a voice, tagged `look-3` (2026-09-13).
Three levels and eight rooms (two of them the original playtest building),
a swarm, and the light bargain the design rests on. The look-and-feel round gave it textured walls, a colour per room,
redrawn sprites, fourteen announced moments, a one-voice beeper with effects and
music, and the mains surge (since removed).

The round after it, from the user's own play, added walking overhead figures,
flies that beat their wings, coursed walls, the flash showing everyone (since
removed), a
distant siren, and two rule changes: flies keep personal space, and no two
share a cell through a doorway. **Those two move the game**: about six per
cent fewer bites a minute, recorded and not tuned. Everything before them was
checked to leave the event log byte-identical.

The second look-and-feel round after that, with The Great Escape as the reference, gave it
a noise floor in place of the dot lattice, a four-stride walk, a halo mask on
every sprite, a three-frame wingbeat, seven furniture tiles (drawn, not yet
placed), a border colour flag, and a beam across the title. All seven slices
left the event log byte-identical. See *Look and feel 2* in the vault.

**Look and feel 3** (2026-09-16), the last round before new levels: three
reviewers, a designer's plan with 123 mocks, thirteen rulings all taken in one
sitting, eight slices built as #98–#105 with every event log byte-identical
to the tester's sixteen hashes. Red flies only on dark cells, the player bright
white, the worker's frames swapped, a closed box for the magnet, thin walls in
a running bond, remembered walls as outline only, the furniture placed, three
strip marks redrawn, the title's beam replaced by a still pool, the logo on
the ending, the strip black through the opening. See *Look and feel 3*.

The day after, from play, the user overruled two of those slices (#78): the
people are **drawn from above again**, as everything else is, with the walk
kept and no bar under the player; and the dotted rule under the play area is
gone. See *2026-09-13 People are drawn from above, and the rule goes*. Then
(#79) **the opening flash and the mains surge were removed**: no room is ever
shown whole and the building plan is never shown. See *2026-09-14 No preview*.

**The rooms** (2026-09-17, #107–#115): three levels, each its own building,
authored as text under `assets/levels/` and loaded by `spikes/levels.py` —
`scene.py` is now a view of Level 3. Level 1 *Dark* (three rooms, one fly),
Level 2 *Infested* (three rooms, six flies), Level 3 *Rescue* (the playtest
building, untouched). `--level N`, `--room M` and `--solo` on the window, the
driver, the demo and the gallery; default level 3, so the sixteen baseline
hashes are unmoved. `Session(building=, start_room=)`, `Building.solo(i)`, the
bots reading the building from the run, budgets in the level file, and
`tests/test_rooms.py` (`SPOTLIGHT_SLOW=1`) playing every room alone and in its
building. See *The rooms* §8 in the vault.

`core/game.py` is **not** a design — it is a walking skeleton that proves the
loop runs end to end, and it should be replaced by the first real spec from the
vault. The game that runs lives in `spikes/`.

Decisions **not yet made** (record them in the vault when they are, then update
this file):

- Z80 assembler and toolchain, emulator, and target model (48K vs 128K)
- Audio approach (48K beeper vs 128K AY)

The **asset pipeline** was on that list and is now decided — text in `assets/`,
tables generated by `tools/bitmaps.py` (see *2026-09-10 The asset pipeline* in
the vault, and [Layout](#layout) above).

## Designing for the port

The Spectrum target should shape prototype decisions from the start. Relevant
hardware limits:

- **Screen:** 256×192 pixels, with colour held in a separate 32×24 grid of
  8×8 attribute cells.
- **Colour:** each attribute cell gets one ink and one paper from 15 colours
  (8 base colours, 7 of them with a BRIGHT variant), plus flash and bright bits.
  Two colours per 8×8 cell — this causes *attribute clash* and it is the single
  biggest constraint on a darkness-and-light game. Lighting that needs
  per-pixel colour will not port; lighting expressed at 8×8 cell granularity
  will.
- **Memory:** 48K usable (or 128K with paging, if chosen). Assets are tight.
- **CPU:** ~3.5MHz Z80. No floating point, no hardware multiply, no sprites,
  no blitter. Use integer or fixed-point maths in the prototype; avoid
  `float`-based physics and per-pixel work that has no cheap Z80 equivalent.
- **Frame budget:** 50Hz interrupt. Budget work per frame, and beware the
  contended-memory region (the lower 16K screen RAM).
- **Audio:** 48K is beeper-only (1-bit); 128K adds an AY-3-8912.

When prototyping, prefer mechanics that are expressible as cell-grid state and
integer arithmetic. When a Pygame convenience is used deliberately as a stand-in
for something that will need reworking on the Spectrum, note it in the code and
in the vault.

## Environment

- Python 3.12, with the venv at `.venv/` (gitignored). Pygame 2.6.1.
- `gh` is installed and authenticated as `citizenfish`; git pushes use a token
  in the macOS keychain. Both work without prompting.
- **`citizenfish/spotlight` is public; `citizenfish/spotlight_kb` is private.**
  Issue bodies should summarise what to build; the fuller design rationale stays
  in the private vault. Do not paste vault content wholesale into public issues.

## Conventions

- Reference the driving issue in commit messages (e.g. `Refs #12`).
- Don't commit or push unless asked. When asked, commit straight to `main` —
  these are solo repos and feature branches just add a merge step.
- Keep `core/` free of pygame and floats; `test_portability.py` will catch it.
- Tests must pass headless (`SDL_VIDEODRIVER=dummy`).
