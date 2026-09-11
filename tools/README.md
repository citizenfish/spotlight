# Tools

Asset and data converters that sit between `assets/` and the two targets.

The prototype and the port must not drift, so anything both need — level maps,
sprite bitmaps, attribute data — is authored once in `assets/` and converted
here: into whatever the Python side loads, and into Spectrum-ready bytes for
`spectrum/src/`.

## `bitmaps.py`

Turns the text art in `assets/sprites/` and `assets/tiles/` into tables for
both machines. Decided in the vault as *2026-09-10 The asset pipeline*, built
by issue #48.

```sh
python tools/bitmaps.py --python prototype/spikes/bitmaps_gen.py \
    --asm spectrum/src/bitmaps.asm assets/sprites assets/tiles
```

The title logo is the same tool over a separate tree, into a separate pair of
files, because it is 128 bytes that must not be resident during play:

```sh
python tools/bitmaps.py --python prototype/spikes/logo_gen.py \
    --asm spectrum/src/logo.asm assets/logo
```

Both outputs are **committed**, so a clone builds without running the tool, and
`prototype/tests/test_bitmaps_tool.py` regenerates them into a temporary path
and compares byte for byte. If art and code have drifted, the suite fails.

It is deterministic — blocks sorted by name, no timestamp — because a file that
churns is a file nobody can diff. It converts a picture into bytes and stops:
no pre-shifting, no masks, no rotation tables, no colour.
