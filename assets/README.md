# Assets

Source-of-truth art and level data, in editable form. Converted output belongs
to the targets, not here — see `tools/`.

Anything authored here has to survive the Spectrum's limits: a 256×192 bitmap
with colour only at 8×8 cell granularity, one ink and one paper per cell.
Design to the cell grid from the start.

- `sprites/` — character and object bitmaps
- `tiles/` — wall and doorway tiles, sixteen per variant, named by mask;
  the two floor stipples and the spray's droplets
- `logo/` — the title screen's double-height `SPOTLIGHT` face
- `levels/` — level maps

`logo/` is generated into files of its own — `prototype/spikes/logo_gen.py` and
`spectrum/src/logo.asm` — rather than into the table the rest of the art shares.
The reason is memory, not pipeline: the logo is wanted on one screen that is not
the game, so on the Spectrum it lives outside the resident set, and a test holds
the play path to not importing it.

Bitmaps are `.txt` files of named ASCII grids: `;` starts a comment, a block is
a `name:` and a `size:` followed by its rows of `#` and `.`, and anything after
the grid on a row is a comment on that row. A block is `8x8`, `8x16` or — for
the body alone — `16x8`; **each size is a drawing routine on the Z80**, so a new
one is a decision rather than a drawing. `tools/bitmaps.py` generates the
prototype's tables and the port's `DEFB` tables from them — **this directory is
the source, and nothing that draws declares bytes of its own.**

That last claim is checked rather than asserted: `test_bitmaps_tool.py` reads
every module under `prototype/spikes/` and fails on a run of byte constants,
with the permitted exceptions listed there and each carrying its reason. It
grew that check because the claim had been made once and was not true — the
floor and spray stipples went on being hex in the drawing code for a slice,
which is what a rule with unrecorded exceptions does.
