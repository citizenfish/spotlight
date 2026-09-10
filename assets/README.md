# Assets

Source-of-truth art and level data, in editable form. Converted output belongs
to the targets, not here — see `tools/`.

Anything authored here has to survive the Spectrum's limits: a 256×192 bitmap
with colour only at 8×8 cell granularity, one ink and one paper per cell.
Design to the cell grid from the start.

- `sprites/` — character and object bitmaps
- `tiles/` — wall and doorway tiles, sixteen per variant, named by mask;
  the two floor stipples and the spray's droplets
- `levels/` — level maps

Bitmaps are `.txt` files of named ASCII grids: `;` starts a comment, a block is
a `name:` and a `size:` followed by its rows of `#` and `.`, and anything after
column 8 on a row is a comment on that row. `tools/bitmaps.py` generates the
prototype's tables and the port's `DEFB` tables from them — **this directory is
the source, and nothing that draws declares bytes of its own.**

That last claim is checked rather than asserted: `test_bitmaps_tool.py` reads
every module under `prototype/spikes/` and fails on a run of byte constants,
with the permitted exceptions listed there and each carrying its reason. It
grew that check because the claim had been made once and was not true — the
floor and spray stipples went on being hex in the drawing code for a slice,
which is what a rule with unrecorded exceptions does.
