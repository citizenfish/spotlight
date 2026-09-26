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
pytest                     # 1665 tests, headless-safe
SPOTLIGHT_SLOW=1 pytest    # + 132 room runs (tests/test_rooms.py), ~21 min
```

Dependencies are a plain venv plus pinned `requirements.txt`; there is no
pyproject and the package is not installed — `prototype/pytest.ini` sets
`pythonpath` instead.

## Current state

A playable prototype with a face and a voice, tagged `look-3` (2026-09-13).
Three buildings of three rooms each and a fourth that tightens for ever, a
swarm, a searchlight in every room, and the light bargain the design rests on:
the beam is how you see the room and the thing that gives you away. Each room
is built from an **authored shell** whose walls may reach the border -- so a
room can have a bay, a division or a chamber in it -- with the furniture, the
people and the flies still rolled from the run's seed inside it. The look-and-feel round gave it textured walls, a colour per room,
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

**The light round** (2026-09-17, #116–#125), from the user's five rulings
after watching the demo: the torch is gone; the searchlight is in every room,
seeded per room, never opening on the start, spilling through doorways, and
writing the walls it passes into the fade, which is how a room is now seen;
every room is a template (`roll:` in the level file) whose walls, furniture,
people and flies rolled from the run's seed by `spikes/roller.py`, proved
pocket-free over a thousand seeds a template (the walls stopped rolling in
#132 and are authored now); all out opens the next building
through a card with lives carried and a score, `BEST` on the title, Level 4
and on is Level 3 tightening; the demo's listener sprays. The game starts at
Level 1 (`DEFAULT_LEVEL`); `scene.py` stays a view of Level 3 (`SCENE_LEVEL`)
for the tests. The sixteen baseline hashes were re-taken once, at the end
(*2026-09-17 The light round baseline*). See *The light round* §11.

**The searchlight's look** (2026-09-24, #127–#130), from the user: the
beam's disc was `dx*dx + dy*dy <= r*r`, which at radius 3 is a cross with a
fat middle, and nothing drew its edge although the edge is where the magnet
fires. The disc is now a table (`sources.disc_widths`, `3 5 7 7 7 5 3`, 37
cells) that both the light and the hit test read; the pool is authored art
(`assets/tiles/beam.txt`) whose one-pixel ring `floor.ring` draws over the
stipple and under every sprite; and the housing wears one of eight tiles so
it points at its own beam. It is a rule change, re-baselined in
*2026-09-24 The searchlight baseline*, which also records that a gate stated
as a mean now runs over eight seeds: a mean of four rolled seeds is a coin.

**The plateau and the rooms** (2026-09-25/26, #131–#139), from the user: *"Kick
off a design round to fix the plateau and the rooms."* Measured, Levels 2 to 6
did not get harder — 84, 86, 91 and 83 per cent of the people rescued, four
level-ups a player would have felt as the same level renamed — and every room
in the game was one open hall, because the roll's clearance rule made a wall
that touches the border unrepresentable.

Seven slices. **A fly follows a wall to its end** (#131): the slide is held
across the axis it began across, where before it was dropped whenever the
longest axis changed, so a fly beside a long wall ping-ponged for ever — 400
steps in 14 cells of one column. That was also the whole of the #26 refuge, so
the corner that was ninety-one times safer is ordinary floor now. **The walls
are authored** (#132): `shape:` blocks in the level file, `shell:` in a room,
the roll picking one; the clearance rule is kept and the border is the one
exemption. **The gate is a theorem** (#133): `swarming.strands_a_shell` runs on
the bare walls with the doorways as the only origins, and because adding a start
can only grow what a fly reaches, a shell that passes passes on every seed —
40 ms, in `pytest`, instead of four core-hours. **The plan is a grid** (#134),
`at: col row` a room, capped at nine, because a row of four overflowed a
256-pixel screen in silence. **Doorways leave the middle of the wall** (#135)
from Level 4 and cycle through six bands. **A room nobody is looking at keeps
its charge and not its picture** (#136) — 3.00 display rebuilds a frame down to
1.00 on a three-room level, byte-identical. **Level 3 gained a third room**
(#137), which is the round's fix: the same seven clocks and six flies over
three rooms instead of two take a dark listener from 94 per cent to 63, at no
cost to the 48K frame, because `worst_case()` scales with flies and people and
not with rooms. The dials that were frozen at Level 3 now move: `pace:` 6→5,
`spray:` 5→4→3, the wall memory six seconds early and three late (`fade:`),
and `mount:` is gone — the housing's corner rotates round the building from the
run's seed.

**Buildings cap at three rooms until #139.** Rulings 6, 7 and 8 are not jointly
satisfiable: rooms are only ever adjacent east–west, so a connected building
runs along one row of a plan three wide. Doorways in horizontal walls are
raised as #139 and the four-, five- and six-room rungs wait for it, as do the
loop and the branch. See *The plateau and the rooms* and its issues note.

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
