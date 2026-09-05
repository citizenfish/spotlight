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

## Current state

Greenfield. This repo contains only `README.md` and `LICENSE` — no source, no
build, no tests yet. Nothing below describes existing code; it describes the
target.

Decisions **not yet made** (record them in the vault when they are, then update
this file):

- Python/Pygame project layout, dependency management and test approach
- Z80 assembler and toolchain, emulator, and target model (48K vs 128K)
- Asset pipeline from prototype art to Spectrum screen/attribute data

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

- Python 3.12 is available. **Pygame is not currently installed** — install it
  (and settle on how dependencies are managed) as part of the first
  implementation issue.
- **The `gh` CLI is not installed.** Issue creation currently has to happen via
  the GitHub web UI, or by installing `gh` first. Do not assume `gh` commands
  will work.
- Both repos are on GitHub under `citizenfish`.

## Conventions

- Reference the driving issue in commit messages (e.g. `Refs #12`).
- Don't commit or push unless asked.
- `.idea/` is JetBrains project config and is currently untracked in both repos.
